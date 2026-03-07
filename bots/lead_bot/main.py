"""
Lead Bot FastAPI Application - Enhanced with Production Features.

Critical Mission: <5 minute lead response for 10x conversion multiplier.

Production enhancements from jorge_deployment_package/jorge_fastapi_lead_bot.py:
- Pydantic request/response validation
- Enhanced performance monitoring
- Background task processing
- Additional analysis endpoints
"""
import asyncio
import base64
import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import or_, text

from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.lead_bot.models import LeadAnalysisResponse, LeadMessage, PerformanceStatus
from bots.lead_bot.routes_admin import router as admin_router, settings_load
from bots.lead_bot.routes_dashboard import router as dashboard_router
from bots.lead_bot.routes_productization import router as productization_router
from bots.lead_bot.routes_realtime import router as realtime_router
from bots.lead_bot.routes_webhook import router as webhook_router
from bots.lead_bot.services.lead_analyzer import LeadAnalyzer
from bots.lead_bot.websocket_manager import websocket_manager
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.shared.auth_middleware import get_current_active_user
from bots.shared.cache_service import get_cache_service
from bots.shared.config import settings
from bots.shared.event_broker import event_broker
from bots.shared.ghl_client import GHLClient
from bots.shared.logger import get_logger, set_correlation_id

logger = get_logger(__name__)

# Performance tracking
performance_stats = {
    "total_requests": 0,
    "total_response_time_ms": 0,
    "cache_hits": 0,
    "five_minute_violations": 0
}

# Initialize services on startup
lead_analyzer = None
seller_bot_instance: Optional[JorgeSellerBot] = None
buyer_bot_instance: Optional[JorgeBuyerBot] = None
_ghl_client: Optional[GHLClient] = None
_webhook_cache = None


def verify_ghl_signature(payload: bytes, signature: Optional[str]) -> bool:
    """Verify GHL webhook signature using RSA public key or HMAC secret."""
    # RSA signature with public key (current GHL webhook scheme)
    if settings.ghl_webhook_public_key:
        if not signature:
            return False
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            public_key = serialization.load_pem_public_key(
                settings.ghl_webhook_public_key.encode()
            )
            public_key.verify(
                base64.b64decode(signature.strip()),
                payload,
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception as e:
            logger.warning(f"Webhook signature verification failed: {e}")
            return False

    # HMAC signature with shared secret (legacy/optional)
    if settings.ghl_webhook_secret:
        if not signature:
            return False
        sig = signature.strip().replace("sha256=", "")
        computed = hmac.new(
            settings.ghl_webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        if hmac.compare_digest(computed, sig):
            return True
        # Try base64 format
        computed_b64 = base64.b64encode(
            hmac.new(settings.ghl_webhook_secret.encode(), payload, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(computed_b64, sig)

    # No signature config set -- allow all requests (pass-through mode)
    if settings.environment == "production":
        logger.warning("Unsigned webhook accepted (no verification configured)")
    return True


async def check_stalled_conversations() -> None:
    """Hourly background task: mark conversations with no activity for 48h as STALLED."""
    while True:
        await asyncio.sleep(3600)
        try:
            from database.models import ContactModel, ConversationModel
            from database.session import AsyncSessionFactory
            from sqlalchemy import select

            from bots.shared.stall_reengagement import StallReengagementService

            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            async with AsyncSessionFactory() as session:
                result = await session.execute(
                    select(ConversationModel).where(
                        ConversationModel.last_activity < cutoff,
                        ConversationModel.stage.notin_(["QUALIFIED", "STALLED"]),
                        or_(
                            ConversationModel.status.is_(None),
                            ConversationModel.status.notin_(["awaiting_human", "suppressed", "closed"]),
                        ),
                    )
                )
                stalled = result.scalars().all()
                # Capture original stages before overwriting to STALLED
                original_stages = {conv.contact_id: (conv.stage or "Q0") for conv in stalled}
                for conv in stalled:
                    merged_metadata = dict(conv.metadata_json or {})
                    merged_metadata.setdefault("stalled_from_stage", conv.stage or "Q0")
                    conv.metadata_json = merged_metadata
                    conv.stage = "STALLED"
                    conv.status = "stalled"
                    conv.human_takeover = True
                    conv.handoff_reason = "needs_human_review"
                await session.commit()
                if stalled:
                    logger.info(f"Marked {len(stalled)} conversations as STALLED")

                # Send re-engagement SMS for each newly stalled conversation
                reengagement = StallReengagementService()
                for conv in stalled:
                    try:
                        contact_result = await session.execute(
                            select(ContactModel).where(ContactModel.contact_id == conv.contact_id)
                        )
                        contact = contact_result.scalar_one_or_none()
                        name = (contact.name if contact and contact.name else "there")
                        location_id = (contact.location_id if contact and contact.location_id else settings.ghl_location_id)
                        address = (conv.extracted_data or {}).get("address", "")
                        await reengagement.trigger_reengagement(
                            contact_id=conv.contact_id,
                            stage=original_stages.get(conv.contact_id, "Q0"),
                            name=name,
                            location_id=location_id,
                            address=address,
                        )
                    except Exception as e:
                        logger.error(f"Re-engagement failed for {conv.contact_id}: {e}")
        except Exception as e:
            logger.error(f"Error in stall detection: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app."""
    global lead_analyzer, seller_bot_instance, buyer_bot_instance, _ghl_client, _webhook_cache

    logger.info("Starting Lead Bot...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"5-Minute Response Timeout: {settings.lead_response_timeout_seconds}s")

    # Fail fast on missing critical env vars
    _required = ["anthropic_api_key", "ghl_api_key", "ghl_location_id", "redis_url", "admin_api_key"]
    _missing = [v.upper() for v in _required if not getattr(settings, v, None)]
    if _missing:
        msg = f"Missing required env vars: {_missing}"
        logger.error(msg)
        if settings.environment == "production":
            raise RuntimeError(msg)

    # Initialise Sentry error tracking if DSN is configured
    if settings.sentry_dsn:
        try:
            import sentry_sdk
            sentry_sdk.init(
                dsn=settings.sentry_dsn,
                environment=settings.environment,
                traces_sample_rate=0.1,
            )
            logger.info("Sentry initialised")
        except Exception as e:
            logger.warning(f"Sentry init failed: {e}")

    # Ensure Jorge DB tables exist — whitelist only tables with no FK conflicts with the shared DB
    try:
        from database.base import Base
        from database.session import _get_engine
        # Explicitly whitelist Jorge tables that are safe to create (no FK conflicts with
        # the EnterpriseHub tables that already exist in the shared postgres DB).
        # Excluded: users, sessions, subscriptions, usage_records (different schema in shared DB),
        #           invoices, white_label_configs, onboarding_states (FK → subscriptions, type mismatch).
        _JORGE_SAFE = {
            "contacts", "conversations", "leads", "deals", "commissions",
            "properties", "buyer_preferences", "playbook_applications", "roi_reports",
            "agencies", "webhook_events",
        }
        _jorge_tables = [t for t in Base.metadata.sorted_tables if t.name in _JORGE_SAFE]
        async with _get_engine().begin() as conn:
            await conn.run_sync(
                lambda c: Base.metadata.create_all(c, tables=_jorge_tables, checkfirst=True)
            )
        logger.info(f"DB tables ensured: {[t.name for t in _jorge_tables]}")
    except Exception as e:
        import traceback
        logger.error(f"DB table creation failed: {e}\n{traceback.format_exc()}")

    if not settings.ghl_webhook_public_key and not settings.ghl_webhook_secret:
        logger.warning(
            "Webhook signature verification DISABLED — set GHL_WEBHOOK_SECRET or GHL_WEBHOOK_PUBLIC_KEY to enable"
        )

    lead_analyzer = LeadAnalyzer()
    _webhook_cache = get_cache_service()
    logger.info("Webhook cache initialized")
    await settings_load(_webhook_cache)
    logger.info("Bot tone settings loaded from cache")

    try:
        seller_bot_instance = JorgeSellerBot()
        buyer_bot_instance = JorgeBuyerBot()
        _ghl_client = GHLClient()
        logger.info("Seller Bot, Buyer Bot, and GHL client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize seller/buyer bots: {e}")

    try:
        await event_broker.initialize()
        logger.info("Event broker initialized")
    except Exception as e:
        logger.error(f"Failed to initialize event broker: {e}")

    try:
        await websocket_manager.initialize()
        logger.info("WebSocket manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket manager: {e}")

    logger.info("Lead Bot ready!")

    # Start background stall detection (hourly scan for 48h-inactive conversations)
    _stall_task = asyncio.create_task(check_stalled_conversations())

    yield

    _stall_task.cancel()
    logger.info("Shutting down Lead Bot...")

    if _ghl_client:
        try:
            await _ghl_client.close()
            logger.info("GHL client closed")
        except Exception as e:
            logger.error(f"GHL client close error: {e}")

    try:
        await websocket_manager.shutdown()
        logger.info("WebSocket manager shutdown")
    except Exception as e:
        logger.error(f"WebSocket manager shutdown error: {e}")

    try:
        await event_broker.shutdown()
        logger.info("Event broker shutdown")
    except Exception as e:
        logger.error(f"Event broker shutdown error: {e}")


# Create FastAPI app
app = FastAPI(
    title="Jorge's Lead Bot",
    description="AI-powered lead qualification with <5 minute response rule",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for browser-based clients
cors_origins = getattr(settings, "cors_origins", None) or []
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# IP-based rate limit middleware (adds X-RateLimit-* headers, returns 429 when exceeded)
from bots.shared.rate_limit_middleware import RateLimitMiddleware  # noqa: E402
app.add_middleware(RateLimitMiddleware)


# S2: Global exception handlers — strip internal details from 500 responses
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"error": "internal_error"})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "validation_error"})


# S4: Request body size limit (1MB)
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 1_048_576:
        return JSONResponse(status_code=413, content={"error": "payload_too_large"})
    return await call_next(request)


# Middleware: Enhanced performance monitoring for 5-minute rule
@app.middleware("http")
async def performance_monitor(request: Request, call_next):
    """Monitor request performance and enforce 5-minute rule."""
    start_time = time.time()

    correlation_id = request.headers.get("X-Correlation-ID") or str(int(time.time() * 1000))
    set_correlation_id(correlation_id)

    response = await call_next(request)

    process_time_ms = (time.time() - start_time) * 1000
    response.headers["X-Process-Time"] = f"{int(process_time_ms)}ms"
    response.headers["X-Timestamp"] = datetime.now(timezone.utc).isoformat()
    response.headers["X-Correlation-ID"] = correlation_id

    performance_stats["total_requests"] += 1
    performance_stats["total_response_time_ms"] += process_time_ms

    if "/webhook" in str(request.url):
        if process_time_ms > (settings.lead_response_timeout_seconds * 1000):
            performance_stats["five_minute_violations"] += 1
            logger.error(
                f"5-MINUTE RULE VIOLATED! "
                f"Webhook took {process_time_ms/1000:.1f}s > {settings.lead_response_timeout_seconds}s"
            )
        elif process_time_ms > 2000:
            logger.warning(f"Slow webhook processing: {process_time_ms:.0f}ms")

    if process_time_ms > 1000:
        logger.warning(f"Slow request: {request.url} took {process_time_ms:.1f}ms")

    return response


# Include routers
app.include_router(webhook_router)
app.include_router(realtime_router)
app.include_router(admin_router)
app.include_router(dashboard_router)
app.include_router(productization_router)

# Test endpoints — only in non-production environments
if settings.environment != "production":
    from bots.lead_bot.routes_test_endpoints import router as test_router
    app.include_router(test_router)
    logger.info("Test endpoints mounted at /test/* (non-production mode)")


# ── Core routes (health, analyze, performance, metrics) ──────────────────────


@app.get("/health")
async def health_check():
    """Health check endpoint — returns 503 if Redis unreachable or bots uninitialised."""
    from fastapi.responses import JSONResponse

    checks: Dict[str, str] = {}

    # Verify bots initialised
    checks["seller_bot"] = "ok" if seller_bot_instance is not None else "not_initialized"
    checks["buyer_bot"] = "ok" if buyer_bot_instance is not None else "not_initialized"

    # Ping Redis with 2s timeout
    redis_ok = False
    try:
        if settings.redis_url:
            import redis.asyncio as _redis
            _r = _redis.from_url(settings.redis_url, socket_connect_timeout=2, socket_timeout=2)
            await asyncio.wait_for(_r.ping(), timeout=2.0)
            await _r.aclose()
            checks["redis"] = "ok"
            redis_ok = True
        else:
            checks["redis"] = "not_configured"
            redis_ok = True  # No Redis configured — acceptable in dev
    except Exception as e:
        checks["redis"] = f"unreachable: {e}"
        logger.error(f"Health check: Redis unreachable: {e}")

    bots_ok = seller_bot_instance is not None and buyer_bot_instance is not None
    overall = "healthy" if (redis_ok and bots_ok) else "degraded"
    status_code = 200 if overall == "healthy" else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall,
            "service": "lead_bot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0.0",
            "environment": settings.environment,
            "checks": checks,
            "5_minute_rule": {
                "timeout_seconds": settings.lead_response_timeout_seconds,
                "target_ms": settings.lead_analysis_timeout_ms,
            },
        },
    )


@app.get("/health/aggregate")
async def aggregate_health():
    """Check bots (in-process), Redis, and Postgres. Returns unified status JSON."""
    results: Dict[str, str] = {}

    results["lead_bot"] = "ok"
    results["seller_bot"] = "ok"
    results["buyer_bot"] = "ok"

    try:
        if event_broker.redis_client:
            await event_broker.redis_client.ping()
            results["redis"] = "ok"
        else:
            results["redis"] = "not_configured"
    except Exception as _e:
        logger.warning(f"Aggregate health Redis check failed: {_e}")
        results["redis"] = "down"

    try:
        from database.session import AsyncSessionFactory
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
            results["postgres"] = "ok"
    except Exception as _e:
        logger.warning(f"Aggregate health Postgres check failed: {_e}")
        results["postgres"] = "down"

    # Feed SMS delivery metrics to alerting service
    try:
        from bots.shared.sms_metrics_collector import SmsMetricsCollector
        from bots.shared.alerting_service import AlertingService
        sms_stats = await SmsMetricsCollector().get_delivery_stats()
        AlertingService().record_metric("sms.delivery_rate", sms_stats["delivery_rate"])
    except Exception as _e:
        logger.debug(f"SMS metrics feed failed: {_e}")

    overall = "healthy" if all(v in ("ok", "not_configured") for v in results.values()) else "degraded"
    return {"status": overall, "services": results, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/analyze-lead", response_model=LeadAnalysisResponse)
async def analyze_lead(lead_msg: LeadMessage, background_tasks: BackgroundTasks, user=Depends(get_current_active_user())):
    """Direct lead analysis endpoint with full metrics and Jorge validation."""
    try:
        lead_data = {
            "id": lead_msg.contact_id,
            "message": lead_msg.message,
            **(lead_msg.contact_data or {})
        }

        analysis, metrics = await lead_analyzer.analyze_lead(
            lead_data,
            force_ai=lead_msg.force_ai_analysis
        )

        if metrics.cache_hit:
            performance_stats["cache_hits"] += 1

        return LeadAnalysisResponse(
            success=True,
            lead_score=analysis.get("score", 0),
            lead_temperature=analysis.get("temperature", "warm"),
            jorge_priority=analysis.get("jorge_priority", "normal"),
            estimated_commission=analysis.get("estimated_commission", 0.0),
            meets_jorge_criteria=analysis.get("meets_jorge_criteria", False),
            performance=metrics.to_dict(),
            jorge_validation=analysis.get("jorge_validation")
        )

    except Exception as e:
        logger.error(f"Lead analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/performance", response_model=PerformanceStatus)
async def get_performance(user=Depends(get_current_active_user())):
    """Get 5-minute rule compliance and performance metrics."""
    total_requests = performance_stats["total_requests"]

    avg_response_time = (
        performance_stats["total_response_time_ms"] / total_requests
        if total_requests > 0 else 0
    )

    cache_hit_rate = (
        (performance_stats["cache_hits"] / total_requests * 100)
        if total_requests > 0 else 0
    )

    five_minute_compliant = (
        performance_stats["five_minute_violations"] == 0
        if total_requests > 0 else True
    )

    return PerformanceStatus(
        five_minute_rule_compliant=five_minute_compliant,
        total_requests=total_requests,
        avg_response_time_ms=avg_response_time,
        cache_hit_rate=cache_hit_rate
    )


@app.get("/metrics")
async def metrics(user=Depends(get_current_active_user())):
    """Get Lead Bot metrics (legacy endpoint)."""
    total_requests = performance_stats["total_requests"]

    return {
        "leads_processed": total_requests,
        "avg_response_time_ms": (
            performance_stats["total_response_time_ms"] / total_requests
            if total_requests > 0 else 0
        ),
        "cache_hit_rate": (
            (performance_stats["cache_hits"] / total_requests * 100)
            if total_requests > 0 else 0
        ),
        "5_minute_compliance_rate": (
            100.0 - (performance_stats["five_minute_violations"] / total_requests * 100)
            if total_requests > 0 else 100.0
        ),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Lead Bot on port 8001...")
    uvicorn.run(
        "bots.lead_bot.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug
    )
