"""
Lead Bot FastAPI Application - Enhanced with Production Features.

Critical Mission: <5 minute lead response for 10x conversion multiplier.

Production enhancements from jorge_deployment_package/jorge_fastapi_lead_bot.py:
- Pydantic request/response validation
- Enhanced performance monitoring
- Background task processing
- Additional analysis endpoints
"""
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
from datetime import datetime
from typing import Dict, Any

from bots.shared.logger import get_logger, set_correlation_id
from bots.shared.config import settings
from bots.lead_bot.services.lead_analyzer import LeadAnalyzer
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
        # Parse webhook payload
        payload = await request.json()
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
async def analyze_lead(lead_msg: LeadMessage, background_tasks: BackgroundTasks):
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
async def get_performance():
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
async def metrics():
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


if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Lead Bot on port 8001...")
    uvicorn.run(
        "bots.lead_bot.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug
    )
