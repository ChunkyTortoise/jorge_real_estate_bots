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
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.lead_bot.models import LeadAnalysisResponse, LeadMessage, PerformanceStatus
from bots.lead_bot.services.lead_analyzer import LeadAnalyzer
from bots.lead_bot.websocket_manager import websocket_manager
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.shared.auth_middleware import get_current_active_user
from bots.shared.auth_service import get_auth_service
from bots.shared.bot_settings import get_all_overrides as _settings_get_all, update_settings as _settings_update, KNOWN_BOTS as _known_bots
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app."""
    global lead_analyzer, seller_bot_instance, buyer_bot_instance, _ghl_client, _webhook_cache

    logger.info("🔥 Starting Lead Bot...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"5-Minute Response Timeout: {settings.lead_response_timeout_seconds}s")

    # Initialize services
    lead_analyzer = LeadAnalyzer()
    _webhook_cache = get_cache_service()
    logger.info("✅ Webhook cache initialized")

    try:
        seller_bot_instance = JorgeSellerBot()
        buyer_bot_instance = JorgeBuyerBot()
        _ghl_client = GHLClient()
        logger.info("✅ Seller Bot, Buyer Bot, and GHL client initialized")
    except Exception as e:
        logger.error(f"Failed to initialize seller/buyer bots: {e}")

    # Initialize event broker and WebSocket manager
    try:
        await event_broker.initialize()
        logger.info("✅ Event broker initialized")
    except Exception as e:
        logger.error(f"Failed to initialize event broker: {e}")

    try:
        await websocket_manager.initialize()
        logger.info("✅ WebSocket manager initialized")
    except Exception as e:
        logger.error(f"Failed to initialize WebSocket manager: {e}")

    logger.info("✅ Lead Bot ready!")

    yield

    # Cleanup on shutdown
    logger.info("🛑 Shutting down Lead Bot...")

    try:
        await websocket_manager.shutdown()
        logger.info("✅ WebSocket manager shutdown")
    except Exception as e:
        logger.error(f"WebSocket manager shutdown error: {e}")

    try:
        await event_broker.shutdown()
        logger.info("✅ Event broker shutdown")
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

def verify_ghl_signature(payload: bytes, signature: Optional[str]) -> bool:
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

    # No signature config set — allow all requests (pass-through mode)
    # Add GHL_WEBHOOK_SECRET or GHL_WEBHOOK_PUBLIC_KEY env var to enable verification
    logger.debug("Webhook signature verification skipped: no secret configured")
    return True


# Middleware: Enhanced performance monitoring for 5-minute rule
@app.middleware("http")
async def performance_monitor(request: Request, call_next):
    """
    Monitor request performance and enforce 5-minute rule.

    Production enhancements:
    - Track performance statistics
    - Add timestamp header
    - Enhanced 5-minute rule monitoring
    """
    start_time = time.time()

    # Set correlation ID for tracking
    correlation_id = request.headers.get("X-Correlation-ID") or str(int(time.time() * 1000))
    set_correlation_id(correlation_id)

    response = await call_next(request)

    # Calculate processing time
    process_time_ms = (time.time() - start_time) * 1000
    response.headers["X-Process-Time"] = f"{int(process_time_ms)}ms"
    response.headers["X-Timestamp"] = datetime.now().isoformat()
    response.headers["X-Correlation-ID"] = correlation_id

    # Update performance stats
    performance_stats["total_requests"] += 1
    performance_stats["total_response_time_ms"] += process_time_ms

    # CRITICAL: Alert if webhook processing exceeds 5 minutes
    if "/webhook" in str(request.url):
        if process_time_ms > (settings.lead_response_timeout_seconds * 1000):
            performance_stats["five_minute_violations"] += 1
            logger.error(
                f"🚨 5-MINUTE RULE VIOLATED! "
                f"Webhook took {process_time_ms/1000:.1f}s > {settings.lead_response_timeout_seconds}s"
            )
        elif process_time_ms > 2000:  # Warn if over 2 seconds
            logger.warning(f"⚠️ Slow webhook processing: {process_time_ms:.0f}ms")

    # Log slow requests
    if process_time_ms > 1000:  # >1 second
        logger.warning(f"Slow request: {request.url} took {process_time_ms:.1f}ms")

    return response


@app.get("/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        Health status and system metrics
    """
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

    # All bots run in the same process on Render — they are healthy if this endpoint responds
    results["lead_bot"] = "ok"
    results["seller_bot"] = "ok"
    results["buyer_bot"] = "ok"

    # Check Redis
    try:
        if event_broker._redis:
            await event_broker._redis.ping()
            results["redis"] = "ok"
        else:
            results["redis"] = "not_configured"
    except Exception:
        results["redis"] = "down"

    # Check Postgres
    try:
        from database.session import AsyncSessionFactory
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
            results["postgres"] = "ok"
    except Exception:
        results["postgres"] = "down"

    overall = "healthy" if all(v in ("ok", "not_configured") for v in results.values()) else "degraded"
    return {"status": overall, "services": results, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/ghl/webhook/new-lead")
async def handle_new_lead(request: Request):
    """
    GHL Webhook: New Lead Created.

    CRITICAL: Must complete within 5 minutes for 10x conversion.

    Flow:
    1. Parse webhook payload (<100ms)
    2. Analyze lead with Claude (<500ms)
    3. Update GHL custom fields (<200ms)
    4. Send immediate follow-up based on temperature (<200ms)
    5. Total: <1 second, well under 5-minute rule

    Returns:
        Processing status and lead score
    """
    start_time = time.time()

    try:
        payload_bytes = await request.body()
        signature = request.headers.get("x-wh-signature") or request.headers.get("X-HighLevel-Signature")
        if not verify_ghl_signature(payload_bytes, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

        payload = json.loads(payload_bytes.decode("utf-8"))
        logger.info(f"📨 New lead webhook received: {payload.get('id', 'unknown')}")

        # Extract contact data
        contact_id = payload.get("id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Missing contact ID")

        # Analyze lead with enhanced analyzer (returns analysis + metrics)
        analysis_start = time.time()
        analysis_result, metrics = await lead_analyzer.analyze_lead(payload)
        analysis_time_ms = (time.time() - analysis_start) * 1000

        # Track cache hits
        if metrics.cache_hit:
            performance_stats["cache_hits"] += 1

        # Log performance
        if analysis_time_ms > settings.lead_analysis_timeout_ms:
            logger.warning(
                f"⚠️ Lead analysis took {analysis_time_ms:.1f}ms "
                f"(target: {settings.lead_analysis_timeout_ms}ms)"
            )
        else:
            logger.info(f"✅ Lead analysis: {analysis_time_ms:.1f}ms ({metrics.analysis_type})")

        # Total processing time
        total_time_ms = (time.time() - start_time) * 1000
        logger.info(
            f"🎯 Lead {contact_id} processed in {total_time_ms:.1f}ms "
            f"(Score: {analysis_result.get('score', 0)}, Temp: {analysis_result.get('temperature', 'unknown')})"
        )

        return {
            "status": "processed",
            "contact_id": contact_id,
            "score": analysis_result.get("score", 0),
            "temperature": analysis_result.get("temperature", "warm"),
            "jorge_priority": analysis_result.get("jorge_priority", "normal"),
            "meets_jorge_criteria": analysis_result.get("meets_jorge_criteria", False),
            "estimated_commission": analysis_result.get("estimated_commission", 0.0),
            "processing_time_ms": total_time_ms,
            "within_5_minute_rule": metrics.five_minute_rule_compliant,
            "cache_hit": metrics.cache_hit,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Error processing new lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ghl/webhook")
async def unified_ghl_webhook(request: Request):
    """
    Unified GHL webhook dispatcher.

    GHL workflow '5. Process Message - Which Bot?' fires this endpoint for all bots.
    Reads Bot Type from the payload's customData or fetches it from the GHL contact,
    then routes to the appropriate bot (Lead / Seller / Buyer).

    Always returns HTTP 200 so GHL does not retry the webhook.
    """
    try:
        payload_bytes = await request.body()
        signature = request.headers.get("x-wh-signature") or request.headers.get("X-HighLevel-Signature")
        if not verify_ghl_signature(payload_bytes, signature):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
        payload = json.loads(payload_bytes.decode("utf-8"))

        contact_id = payload.get("contactId") or payload.get("contact_id") or payload.get("id")
        location_id = (
            payload.get("locationId")
            or payload.get("location_id")
            or settings.ghl_location_id
        )
        message_body = payload.get("body") or payload.get("message") or ""

        if not contact_id:
            logger.error("Unified webhook: missing contactId in payload")
            return {"status": "error", "detail": "missing contactId"}

        if not message_body.strip():
            logger.info(f"Unified webhook: empty message for {contact_id}, skipping")
            return {"status": "skipped", "reason": "empty message"}

        # 2C: Input length cap — SMS is 160 chars; anything >2000 is abuse or email forwarding
        if len(message_body) > 2000:
            logger.warning(f"Long message truncated: contact={contact_id}, original_len={len(message_body)}")
            message_body = message_body[:2000]

        # 3D: Per-minute rate limiting
        if _webhook_cache:
            rate_key = f"rate:webhook:{datetime.now().strftime('%Y%m%d%H%M')}"
            rate_val = await _webhook_cache.get(rate_key)
            count = int(rate_val) if rate_val is not None else 0
            if count >= settings.rate_limit_per_minute:
                logger.warning(f"Webhook rate limit exceeded: {count} req/min for contact={contact_id}")
                return {"status": "throttled", "reason": "rate_limit"}
            await _webhook_cache.set(rate_key, str(count + 1), ttl=60)

        # 2A: Message deduplication (5-minute TTL)
        if _webhook_cache:
            dedup_key = f"dedup:{contact_id}:{hashlib.md5(message_body.encode()).hexdigest()}"
            if await _webhook_cache.get(dedup_key):
                logger.info(f"Duplicate message skipped: contact={contact_id}")
                return {"status": "skipped", "reason": "duplicate"}
            await _webhook_cache.set(dedup_key, "1", ttl=300)

        # 2B: Per-contact processing lock (30s TTL, wait up to 10s before throttling)
        _lock_acquired = False
        lock_key = f"lock:{contact_id}"
        if _webhook_cache:
            for _ in range(10):
                if not await _webhook_cache.get(lock_key):
                    break
                await asyncio.sleep(1)
            else:
                logger.warning(f"Processing lock held for contact={contact_id}, throttling")
                return {"status": "throttled", "reason": "processing_lock"}
            await _webhook_cache.set(lock_key, "1", ttl=30)
            _lock_acquired = True

        try:
            # --- Determine bot type ---
            # GHL workflow branches add customData; fall back to GHL API contact lookup.
            custom_data: Dict = payload.get("customData") or {}
            bot_type: str = (
                custom_data.get("bot_type")
                or custom_data.get("Bot Type")
                or payload.get("bot_type")
                or ""
            )

            if not bot_type and _ghl_client:
                try:
                    contact_resp = await _ghl_client.get_contact(contact_id)
                    custom_fields = (
                        contact_resp.get("contact", contact_resp).get("customFields", [])
                    )
                    for cf in custom_fields:
                        key = (cf.get("fieldKey") or cf.get("name") or "").lower().replace(" ", "_")
                        if key in ("bot_type", "bot type"):
                            bot_type = cf.get("value") or ""
                            break
                except Exception as e:
                    logger.warning(f"Could not fetch contact for bot_type lookup: {e}")

            bot_type_lower = (bot_type or "lead").lower()

            contact_info = {
                "name": payload.get("fullName") or custom_data.get("name"),
                "email": payload.get("email") or custom_data.get("email"),
                "phone": payload.get("phone") or custom_data.get("phone"),
            }

            logger.info(
                f"Unified webhook: contact={contact_id}, bot_type={bot_type_lower!r}, "
                f"msg={message_body[:60]!r}"
            )

            # --- Route to bot ---
            response_message: Optional[str] = None
            result_meta: Dict = {"bot_type": bot_type_lower}

            if "seller" in bot_type_lower:
                if not seller_bot_instance:
                    logger.error("Seller bot not initialized")
                    return {"status": "error", "detail": "seller bot unavailable"}
                result = await seller_bot_instance.process_seller_message(
                    contact_id=contact_id,
                    location_id=location_id,
                    message=message_body,
                    contact_info=contact_info,
                )
                response_message = result.response_message
                result_meta.update(
                    {
                        "temperature": result.seller_temperature,
                        "questions_answered": result.questions_answered,
                        "qualification_complete": result.qualification_complete,
                    }
                )

            elif "buyer" in bot_type_lower:
                if not buyer_bot_instance:
                    logger.error("Buyer bot not initialized")
                    return {"status": "error", "detail": "buyer bot unavailable"}
                result = await buyer_bot_instance.process_buyer_message(
                    contact_id=contact_id,
                    location_id=location_id,
                    message=message_body,
                    contact_info=contact_info,
                )
                response_message = result.response_message
                result_meta.update(
                    {
                        "temperature": result.buyer_temperature,
                        "questions_answered": result.questions_answered,
                        "qualification_complete": result.qualification_complete,
                    }
                )

            else:
                # Default: Lead bot analysis (no direct SMS reply — GHL workflows handle follow-up)
                lead_data = {"id": contact_id, "message": message_body, **contact_info}
                analysis, metrics = await lead_analyzer.analyze_lead(lead_data)
                result_meta.update(
                    {
                        "score": analysis.get("score", 0),
                        "temperature": analysis.get("temperature", "warm"),
                        "jorge_priority": analysis.get("jorge_priority", "normal"),
                    }
                )
                return {"status": "processed", **result_meta}

            # --- Send reply via GHL SMS (seller / buyer bots) ---
            if response_message and _ghl_client:
                try:
                    await _ghl_client.send_message(contact_id, response_message, "SMS")
                    logger.info(f"Reply sent to {contact_id} via GHL SMS")
                except Exception as e:
                    logger.error(f"Failed to send GHL reply to {contact_id}: {e}")

            return {"status": "processed", **result_meta}

        finally:
            if _lock_acquired and _webhook_cache:
                await _webhook_cache.delete(lock_key)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified webhook unhandled error: {e}", exc_info=True)
        # Return 200 so GHL does not retry
        return {"status": "error", "detail": str(e)}


@app.post("/analyze-lead", response_model=LeadAnalysisResponse)
async def analyze_lead(lead_msg: LeadMessage, background_tasks: BackgroundTasks, user=Depends(get_current_active_user())):
    """
    Direct lead analysis endpoint.

    Production endpoint for analyzing leads with full metrics and Jorge validation.

    Args:
        lead_msg: Lead message with contact data
        background_tasks: FastAPI background tasks for async processing

    Returns:
        Complete lead analysis with score, temperature, and Jorge validation
    """
    try:
        # Build lead data from message
        lead_data = {
            "id": lead_msg.contact_id,
            "message": lead_msg.message,
            **(lead_msg.contact_data or {})
        }

        # Analyze lead
        analysis, metrics = await lead_analyzer.analyze_lead(
            lead_data,
            force_ai=lead_msg.force_ai_analysis
        )

        # Track cache hits
        if metrics.cache_hit:
            performance_stats["cache_hits"] += 1

        # Return structured response
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
        logger.error(f"❌ Lead analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/performance", response_model=PerformanceStatus)
async def get_performance(user=Depends(get_current_active_user())):
    """
    Get 5-minute rule compliance and performance metrics.

    Returns comprehensive performance statistics including:
    - 5-minute rule compliance
    - Average response times
    - Cache hit rates
    - Request volume
    """
    total_requests = performance_stats["total_requests"]

    # Calculate averages
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
    """
    Get Lead Bot metrics (legacy endpoint).

    Returns performance and compliance metrics.
    Use /performance for detailed metrics with Pydantic validation.
    """
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


# =============================================================================
# REAL-TIME WEBSOCKET ENDPOINTS (Phase 3C)
# =============================================================================

@app.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None, description="Optional client identifier"),
    token: Optional[str] = Query(None, description="JWT access token"),
):
    """
    WebSocket endpoint for real-time dashboard updates.

    Provides:
    - Real-time event streaming from Redis pub/sub
    - Recent events on connection (last 60 seconds)
    - Heartbeat for connection health
    - Automatic reconnection support
    """
    assigned_client_id = None

    try:
        auth_service = get_auth_service()
        if not token or not await auth_service.validate_token(token):
            await websocket.close(code=4401)
            return

        # Connect WebSocket client
        assigned_client_id = await websocket_manager.connect(websocket, client_id)
        logger.info(f"Dashboard WebSocket connected: {assigned_client_id}")

        # Keep connection alive and handle client messages
        try:
            while True:
                # Wait for client messages (ping/pong, filters, etc.)
                data = await websocket.receive_text()

                # Handle client ping
                if data == "ping":
                    await websocket.send_text("pong")
                    continue

                # Could add event filtering here in the future
                # e.g., client sends {"filter": {"event_types": ["lead.*"]}}
                logger.debug(f"Client {assigned_client_id} message: {data}")

        except WebSocketDisconnect:
            logger.info(f"Dashboard WebSocket disconnected: {assigned_client_id}")

    except Exception as e:
        logger.error(f"WebSocket error for client {assigned_client_id}: {e}")

    finally:
        # Clean up connection
        if assigned_client_id:
            await websocket_manager.disconnect(assigned_client_id)


@app.get("/api/events/recent")
async def get_recent_events(
    since_minutes: int = Query(5, description="Get events from last N minutes"),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    limit: int = Query(100, description="Maximum number of events to return"),
    user=Depends(get_current_active_user()),
):
    """
    HTTP polling fallback for WebSocket events.

    Use this endpoint if WebSocket connection is not available.
    Provides recent events for dashboard polling updates.

    Args:
        since_minutes: Get events from last N minutes (default: 5)
        event_types: Comma-separated event types (e.g., "lead.analyzed,ghl.tag_added")
        limit: Maximum events to return (default: 100, max: 500)

    Returns:
        List of recent events with metadata
    """
    try:
        # Parse event types filter
        event_type_list = None
        if event_types:
            event_type_list = [t.strip() for t in event_types.split(",")]

        # Limit maximum lookback and results
        since_minutes = min(since_minutes, 60)  # Max 1 hour
        limit = min(limit, 500)  # Max 500 events

        # Get recent events
        since_time = datetime.now() - timedelta(minutes=since_minutes)
        events = await event_broker.get_recent_events(
            since=since_time,
            event_types=event_type_list,
            limit=limit
        )

        # Format events for API response
        formatted_events = []
        for event in events:
            formatted_events.append({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat(),
                "source": event.source,
                "category": event.category.value,
                "payload": event.sanitize_payload()
            })

        return {
            "events": formatted_events,
            "count": len(formatted_events),
            "since": since_time.isoformat(),
            "event_types_filter": event_type_list,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get recent events: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve recent events: {str(e)}"
        )


@app.get("/api/websocket/status")
async def websocket_status(user=Depends(get_current_active_user())):
    """
    Get WebSocket manager status and metrics.

    Useful for debugging and monitoring WebSocket health.
    """
    try:
        health_data = await websocket_manager.health_check()
        metrics_data = websocket_manager.get_metrics()

        return {
            "status": "healthy" if health_data["websocket_manager_running"] else "unhealthy",
            "health": health_data,
            "metrics": metrics_data,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"WebSocket status check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/api/events/health")
async def event_system_health(user=Depends(get_current_active_user())):
    """
    Get event system health (event broker + WebSocket manager).

    Combined health check for the entire real-time event system.
    """
    try:
        # Get event broker health
        broker_health = await event_broker.health_check()
        broker_metrics = event_broker.get_metrics()

        # Get WebSocket manager health
        ws_health = await websocket_manager.health_check()
        ws_metrics = websocket_manager.get_metrics()

        # Overall system status
        overall_healthy = (
            broker_health.get("redis_connected", False) and
            ws_health.get("websocket_manager_running", False)
        )

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "event_broker": {
                "health": broker_health,
                "metrics": broker_metrics
            },
            "websocket_manager": {
                "health": ws_health,
                "metrics": ws_metrics
            },
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Event system health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# ── Admin: Bot Tone Settings ──────────────────────────────────────────────────

@app.get("/admin/settings")
async def admin_get_settings():
    """Return current effective settings — bot defaults merged with any live overrides."""
    from bots.seller_bot.jorge_seller_bot import (
        SELLER_SYSTEM_PROMPT, JorgeSellerBot
    )
    from bots.shared.bot_settings import get_override as _get_override

    seller_override = _get_override("seller")
    qs_raw = JorgeSellerBot.QUALIFICATION_QUESTIONS
    return {
        "seller": {
            "system_prompt": seller_override.get("system_prompt", SELLER_SYSTEM_PROMPT),
            "jorge_phrases": seller_override.get("jorge_phrases", JorgeSellerBot.JORGE_PHRASES),
            "questions": {
                str(k): seller_override.get("questions", {}).get(str(k), v)
                for k, v in qs_raw.items()
            },
        }
    }


@app.put("/admin/settings/{bot}")
async def admin_update_settings(bot: str, request: Request):
    """
    Update tone settings for a bot (seller | buyer | lead).

    Body: partial settings dict — only supplied keys are overridden.
    Supported keys for seller: system_prompt, jorge_phrases, questions
    """
    if bot not in _known_bots:
        raise HTTPException(status_code=404, detail=f"Unknown bot: {bot}. Valid: {sorted(_known_bots)}")
    body = await request.json()
    _settings_update(bot, body)
    logger.info(f"Admin: updated {bot} settings — keys: {list(body)}")
    return {"status": "ok", "bot": bot, "updated_keys": list(body)}


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Lead Bot on port 8001...")
    uvicorn.run(
        "bots.lead_bot.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug
    )
