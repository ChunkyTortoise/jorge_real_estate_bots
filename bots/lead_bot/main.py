"""
Lead Bot FastAPI Application - Enhanced with Production Features.

Critical Mission: <5 minute lead response for 10x conversion multiplier.

Production enhancements from jorge_deployment_package/jorge_fastapi_lead_bot.py:
- Pydantic request/response validation
- Enhanced performance monitoring
- Background task processing
- Additional analysis endpoints
"""
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import json
import base64
import hmac
import hashlib

from bots.shared.logger import get_logger, set_correlation_id
from bots.shared.config import settings
from bots.shared.event_broker import event_broker
from bots.lead_bot.services.lead_analyzer import LeadAnalyzer
from bots.lead_bot.websocket_manager import websocket_manager
from bots.shared.auth_middleware import get_current_active_user
from bots.shared.auth_service import get_auth_service
from bots.lead_bot.models import (
    LeadMessage,
    GHLWebhook,
    LeadAnalysisResponse,
    PerformanceStatus
)

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app."""
    global lead_analyzer

    logger.info("🔥 Starting Lead Bot...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"5-Minute Response Timeout: {settings.lead_response_timeout_seconds}s")

    # Initialize services
    lead_analyzer = LeadAnalyzer()

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if hasattr(settings, 'cors_origins') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_ghl_signature(payload: bytes, signature: Optional[str]) -> bool:
    if not signature:
        return False
    signature = signature.strip()

    # RSA signature with public key (current GHL webhook scheme)
    if settings.ghl_webhook_public_key:
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            public_key = serialization.load_pem_public_key(
                settings.ghl_webhook_public_key.encode()
            )
            public_key.verify(
                base64.b64decode(signature),
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
        computed = hmac.new(
            settings.ghl_webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        sig = signature.replace("sha256=", "").strip()
        if hmac.compare_digest(computed, sig):
            return True
        # Try base64 format
        computed_b64 = base64.b64encode(
            hmac.new(settings.ghl_webhook_secret.encode(), payload, hashlib.sha256).digest()
        ).decode()
        return hmac.compare_digest(computed_b64, signature)

    return False


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


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Lead Bot on port 8001...")
    uvicorn.run(
        "bots.lead_bot.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug
    )
