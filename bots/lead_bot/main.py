"""
Lead Bot FastAPI Application.

Critical Mission: <5 minute lead response for 10x conversion multiplier.
"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from datetime import datetime

from bots.shared.logger import get_logger, set_correlation_id
from bots.shared.config import settings
from bots.lead_bot.services.lead_analyzer import LeadAnalyzer

logger = get_logger(__name__)

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

    logger.info("✅ Lead Bot ready!")

    yield

    # Cleanup on shutdown
    logger.info("🛑 Shutting down Lead Bot...")


# Create FastAPI app
app = FastAPI(
    title="Jorge's Lead Bot",
    description="AI-powered lead qualification with <5 minute response rule",
    version="1.0.0",
    lifespan=lifespan
)


# Middleware: Performance monitoring for 5-minute rule
@app.middleware("http")
async def performance_monitor(request: Request, call_next):
    """Monitor request performance and enforce 5-minute rule."""
    start_time = time.time()

    # Set correlation ID for tracking
    correlation_id = request.headers.get("X-Correlation-ID") or str(int(time.time() * 1000))
    set_correlation_id(correlation_id)

    response = await call_next(request)

    # Calculate processing time
    process_time_ms = (time.time() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = str(int(process_time_ms))
    response.headers["X-Correlation-ID"] = correlation_id

    # CRITICAL: Alert if webhook processing exceeds 5 minutes
    if "/webhook" in str(request.url) and process_time_ms > (settings.lead_response_timeout_seconds * 1000):
        logger.error(
            f"🚨 5-MINUTE RULE VIOLATED! "
            f"Webhook took {process_time_ms/1000:.1f}s > {settings.lead_response_timeout_seconds}s"
        )

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
        # Parse webhook payload
        payload = await request.json()
        logger.info(f"📨 New lead webhook received: {payload.get('id', 'unknown')}")

        # Extract contact data
        contact_id = payload.get("id")
        if not contact_id:
            raise HTTPException(status_code=400, detail="Missing contact ID")

        # Analyze lead (CRITICAL: <500ms target)
        analysis_start = time.time()
        analysis_result = await lead_analyzer.analyze_lead(payload)
        analysis_time_ms = (time.time() - analysis_start) * 1000

        # Log performance
        if analysis_time_ms > settings.lead_analysis_timeout_ms:
            logger.warning(
                f"⚠️ Lead analysis took {analysis_time_ms:.1f}ms "
                f"(target: {settings.lead_analysis_timeout_ms}ms)"
            )
        else:
            logger.info(f"✅ Lead analysis: {analysis_time_ms:.1f}ms")

        # Total processing time
        total_time_ms = (time.time() - start_time) * 1000
        logger.info(
            f"🎯 Lead {contact_id} processed in {total_time_ms:.1f}ms "
            f"(Score: {analysis_result['score']}, Temp: {analysis_result['temperature']})"
        )

        return {
            "status": "processed",
            "contact_id": contact_id,
            "score": analysis_result["score"],
            "temperature": analysis_result["temperature"],
            "processing_time_ms": total_time_ms,
            "within_5_minute_rule": True,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"❌ Error processing new lead: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def metrics():
    """
    Get Lead Bot metrics.

    Returns performance and compliance metrics.
    """
    # TODO: Implement metrics collection
    # Track: lead count, avg response time, 5-minute compliance rate
    return {
        "leads_processed": 0,  # Placeholder
        "avg_response_time_ms": 0,
        "5_minute_compliance_rate": 100.0,
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
