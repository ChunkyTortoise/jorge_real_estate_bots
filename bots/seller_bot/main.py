"""
Seller Bot FastAPI Application.
Exposes Jorge's confrontational qualification system via REST API.
"""
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks, Query, Depends
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from datetime import datetime

from bots.shared.logger import get_logger, set_correlation_id
from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState
from bots.shared.auth_middleware import get_current_active_user

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

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "seller_bot", "timestamp": datetime.now().isoformat()}

@app.post("/api/jorge-seller/process")
async def process_message(request: Request, user=Depends(get_current_active_user())):
    try:
        body = await request.json()
        contact_id = body.get("contact_id")
        location_id = body.get("location_id")
        message = body.get("message")
        contact_info = body.get("contact_info")

        if not all([contact_id, location_id, message]):
            raise HTTPException(status_code=400, detail="Missing required fields: contact_id, location_id, message")

        result = await seller_bot.process_seller_message(
            contact_id=contact_id,
            location_id=location_id,
            message=message,
            contact_info=contact_info
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("bots.seller_bot.main:app", host="0.0.0.0", port=8002, reload=True)
