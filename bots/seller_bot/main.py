"""
Seller Bot FastAPI Application.
Exposes Jorge's confrontational qualification system via REST API.
"""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from bots.seller_bot.jorge_seller_bot import JorgeSellerBot
from bots.shared.auth_middleware import get_current_active_user
from bots.shared.config import settings
from bots.shared.logger import get_logger
from bots.shared.models import ProcessMessageRequest

logger = get_logger(__name__)

# Initialize bot on startup
seller_bot = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management for FastAPI app."""
    global seller_bot
    logger.info("🔥 Starting Seller Bot...")
    seller_bot = JorgeSellerBot()
    logger.info("✅ Seller Bot ready!")
    yield
    logger.info("🛑 Shutting down Seller Bot...")

app = FastAPI(
    title="Jorge's Seller Bot",
    description="Confrontational qualification system for motivated sellers",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for browser-based clients
cors_origins = settings.cors_origins or []
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "seller_bot", "timestamp": datetime.now().isoformat()}

@app.post("/api/jorge-seller/process")
async def process_message(request: ProcessMessageRequest, user=Depends(get_current_active_user())):
    try:
        result = await seller_bot.process_seller_message(
            contact_id=request.contact_id,
            location_id=request.location_id,
            message=request.message,
            contact_info=request.contact_info
        )
        return result
    except Exception as e:
        logger.error(f"Error in process_message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jorge-seller/{contact_id}/progress")
async def get_progress(contact_id: str, location_id: str = Query(...), user=Depends(get_current_active_user())):
    try:
        analytics = await seller_bot.get_seller_analytics(contact_id, location_id)
        return analytics
    except Exception as e:
        logger.error(f"Error in get_progress: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jorge-seller/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user=Depends(get_current_active_user())):
    try:
        # Using conversation_id as contact_id
        state = await seller_bot.get_conversation_state(conversation_id)
        if not state:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return state
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/jorge-seller/active")
async def get_active_conversations(user=Depends(get_current_active_user())):
    try:
        return await seller_bot.get_all_active_conversations()
    except Exception as e:
        logger.error(f"Error in get_active_conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/jorge-seller/{contact_id}/state")
async def reset_state(contact_id: str, user=Depends(get_current_active_user())):
    """Delete a contact's seller bot conversation state (Redis + in-memory)."""
    try:
        await seller_bot.delete_conversation_state(contact_id)
        return {"status": "ok", "contact_id": contact_id, "message": "Seller bot state cleared"}
    except Exception as e:
        logger.error(f"Error resetting state for {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class TriggerCmaRequest(BaseModel):
    contact_id: str


class AdvanceStageRequest(BaseModel):
    stage: Optional[str] = None


def _check_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    """Allow requests that carry the configured admin API key."""
    if not settings.admin_api_key:
        return  # no key configured — open access (dev mode)
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@app.post("/api/jorge-seller/trigger-cma")
async def trigger_cma(
    request: TriggerCmaRequest,
    _: None = Depends(_check_admin_key),
):
    """Trigger CMA generation for a contact (dashboard action)."""
    try:
        state = await seller_bot.get_conversation_state(request.contact_id)
        if not state:
            raise HTTPException(status_code=404, detail="Contact not found in seller bot")
        # Apply cma_requested tag via GHL so the CMA workflow fires
        from bots.shared.ghl_client import GHLClient
        ghl = GHLClient()
        await ghl.add_tag(request.contact_id, "cma_requested")
        logger.info(f"CMA triggered for contact {request.contact_id}")
        return {"status": "ok", "contact_id": request.contact_id, "action": "cma_requested"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering CMA for {request.contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/jorge-seller/{contact_id}/advance-stage")
async def advance_stage(
    contact_id: str,
    request: AdvanceStageRequest,
    _: None = Depends(_check_admin_key),
):
    """Advance a contact's seller bot conversation stage (dashboard action)."""
    try:
        state = await seller_bot.get_conversation_state(contact_id)
        if not state:
            raise HTTPException(status_code=404, detail="Contact not found in seller bot")

        stage_order = ["Q0", "Q1", "Q2", "Q3", "Q4", "QUALIFIED"]
        target = request.stage or _next_stage(state.stage)
        if target not in stage_order:
            raise HTTPException(status_code=400, detail=f"Invalid stage: {target}")

        state.stage = target
        await seller_bot.save_conversation_state(contact_id, state)
        logger.info(f"Stage advanced to {target} for contact {contact_id}")
        return {"status": "ok", "contact_id": contact_id, "stage": target}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error advancing stage for {contact_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _next_stage(current: str) -> str:
    progression = {"Q0": "Q1", "Q1": "Q2", "Q2": "Q3", "Q3": "Q4", "Q4": "QUALIFIED"}
    return progression.get(current, current)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bots.seller_bot.main:app", host="0.0.0.0", port=8002, reload=settings.debug)
