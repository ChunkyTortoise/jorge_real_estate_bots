"""FastAPI routes for Buyer Bot."""
from fastapi import APIRouter, HTTPException, Request, Query, Depends
from datetime import datetime

from bots.buyer_bot.buyer_bot import JorgeBuyerBot
from bots.shared.auth_middleware import get_current_active_user

router = APIRouter()

buyer_bot: JorgeBuyerBot | None = None


def init_buyer_bot(bot: JorgeBuyerBot) -> None:
    global buyer_bot
    buyer_bot = bot


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "buyer_bot", "timestamp": datetime.now().isoformat()}


@router.post("/api/jorge-buyer/process")
async def process_buyer_message(request: Request, user=Depends(get_current_active_user())):
    try:
        body = await request.json()
        contact_id = body.get("contact_id")
        location_id = body.get("location_id")
        message = body.get("message")
        contact_info = body.get("contact_info")

        if not all([contact_id, location_id, message]):
            raise HTTPException(status_code=400, detail="Missing required fields: contact_id, location_id, message")

        result = await buyer_bot.process_buyer_message(
            contact_id=contact_id,
            location_id=location_id,
            message=message,
            contact_info=contact_info,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/jorge-buyer/{contact_id}/progress")
async def get_progress(contact_id: str, location_id: str = Query(...), user=Depends(get_current_active_user())):
    try:
        return await buyer_bot.get_buyer_analytics(contact_id, location_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/jorge-buyer/preferences/{contact_id}")
async def get_preferences(contact_id: str, location_id: str = Query(...), user=Depends(get_current_active_user())):
    try:
        return await buyer_bot.get_preferences(contact_id, location_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/jorge-buyer/matches/{contact_id}")
async def get_matches(contact_id: str, location_id: str = Query(...), user=Depends(get_current_active_user())):
    try:
        return await buyer_bot.get_matches(contact_id, location_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/jorge-buyer/active")
async def get_active_conversations(user=Depends(get_current_active_user())):
    try:
        return await buyer_bot.get_all_active_conversations()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
