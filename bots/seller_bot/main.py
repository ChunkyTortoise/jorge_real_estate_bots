"""
Seller Bot FastAPI Application.
Exposes Jorge's confrontational qualification system via REST API.
"""
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bots.seller_bot.main:app", host="0.0.0.0", port=8002, reload=settings.debug)
