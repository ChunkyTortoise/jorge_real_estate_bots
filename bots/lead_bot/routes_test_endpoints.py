"""
Test-only bot endpoints for smoke testing.

Mounted at /test/* only when ENVIRONMENT != "production".
These routes bypass GHL signature verification so conversations can be driven
from curl or pytest without a live GHL account or webhook signature.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from bots.shared.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/test", tags=["smoke-test"])


class _TurnRequest(BaseModel):
    contact_id: str
    message: str
    location_id: str = "smoke-test"
    contact_info: Optional[Dict[str, Any]] = None


def _get_state():
    from bots.lead_bot import main as _m
    return _m


@router.post("/seller")
async def test_seller_turn(req: _TurnRequest) -> Dict[str, Any]:
    """Drive one seller bot turn. Returns full result including actions_taken."""
    state = _get_state()
    if not state.seller_bot_instance:
        raise HTTPException(status_code=503, detail="seller bot not initialised")
    result = await state.seller_bot_instance.process_seller_message(
        contact_id=req.contact_id,
        location_id=req.location_id,
        message=req.message,
        contact_info=req.contact_info or {},
    )
    return {
        "response_message": result.response_message,
        "seller_temperature": result.seller_temperature,
        "questions_answered": result.questions_answered,
        "qualification_complete": result.qualification_complete,
        "actions_taken": result.actions_taken,
        "next_steps": result.next_steps,
    }


@router.post("/buyer")
async def test_buyer_turn(req: _TurnRequest) -> Dict[str, Any]:
    """Drive one buyer bot turn. Returns full result including actions_taken."""
    state = _get_state()
    if not state.buyer_bot_instance:
        raise HTTPException(status_code=503, detail="buyer bot not initialised")
    result = await state.buyer_bot_instance.process_buyer_message(
        contact_id=req.contact_id,
        location_id=req.location_id,
        message=req.message,
        contact_info=req.contact_info or {},
    )
    return {
        "response_message": result.response_message,
        "buyer_temperature": result.buyer_temperature,
        "questions_answered": result.questions_answered,
        "qualification_complete": result.qualification_complete,
        "actions_taken": result.actions_taken,
        "next_steps": result.next_steps,
    }
