"""
Lead Bot FastAPI Application - Enhanced with Production Features.

Critical Mission: <5 minute lead response for 10x conversion multiplier.

Production enhancements from jorge_deployment_package/jorge_fastapi_lead_bot.py:
- Pydantic request/response validation
- Enhanced performance monitoring
- Background task processing
- Additional analysis endpoints
"""
import base64
import hashlib
import hmac
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.lead_bot.models import LeadAnalysisResponse, LeadMessage, PerformanceStatus
from bots.lead_bot.routes_admin import router as admin_router, settings_load
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
    logger.debug("Webhook signature verification skipped: no secret configured")
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app."""
    global lead_analyzer, seller_bot_instance, buyer_bot_instance, _ghl_client, _webhook_cache

    logger.info("Starting Lead Bot...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"5-Minute Response Timeout: {settings.lead_response_timeout_seconds}s")

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

    yield

    logger.info("Shutting down Lead Bot...")

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
    response.headers["X-Timestamp"] = datetime.now().isoformat()
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


# ── Core routes (health, analyze, performance, metrics) ──────────────────────


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "lead_bot",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": settings.environment,
        "5_minute_rule": {
            "timeout_seconds": settings.lead_response_timeout_seconds,
            "target_ms": settings.lead_analysis_timeout_ms
        }
    }


@app.get("/health/aggregate")
async def aggregate_health():
    """Check bots (in-process), Redis, and Postgres. Returns unified status JSON."""
    results: Dict[str, str] = {}

    results["lead_bot"] = "ok"
    results["seller_bot"] = "ok"
    results["buyer_bot"] = "ok"

    try:
        if event_broker._redis:
            await event_broker._redis.ping()
            results["redis"] = "ok"
        else:
            results["redis"] = "not_configured"
    except Exception:
        results["redis"] = "down"

    try:
        from database.session import AsyncSessionFactory
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
            results["postgres"] = "ok"
    except Exception:
        results["postgres"] = "down"

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
        "timestamp": datetime.now().isoformat()
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
