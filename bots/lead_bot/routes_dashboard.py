"""Dashboard API routes — serves Lyrio dashboard with real metrics."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from bots.lead_bot.routes_admin import get_admin_or_apikey
from bots.shared.alerting_service import AlertingService
from bots.shared.bot_metrics_collector import BotMetricsCollector
from bots.shared.dashboard_data_service import DashboardDataService
from bots.shared.logger import get_logger
from bots.shared.performance_tracker import PerformanceTracker
from bots.shared.sms_metrics_collector import SmsMetricsCollector
from database.models import ContactModel, ConversationModel
from database.session import AsyncSessionFactory

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# GET /api/dashboard/metrics
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/metrics")
async def dashboard_metrics(_=Depends(get_admin_or_apikey)):
    """Combined bot metrics + performance data."""
    collector = BotMetricsCollector()
    tracker = PerformanceTracker()

    system = collector.get_system_summary()
    perf = await tracker.get_performance_metrics()

    return {
        "system": system,
        "performance": perf.to_dict(),
    }


# ---------------------------------------------------------------------------
# GET /api/dashboard/leads/summary
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/leads/summary")
async def dashboard_leads_summary(_=Depends(get_admin_or_apikey)):
    """Aggregate lead counts from DashboardDataService."""
    svc = DashboardDataService()
    hero = await svc.get_hero_metrics_data()
    summary = await svc.get_conversation_summary()
    return {"hero": hero, "conversation_summary": summary}


# ---------------------------------------------------------------------------
# GET /api/dashboard/leads
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/leads")
async def dashboard_leads(
    page: int = 1,
    page_size: int = 20,
    temperature: Optional[str] = None,
    _=Depends(get_admin_or_apikey),
):
    """Paginated lead list with scores/temperatures."""
    async with AsyncSessionFactory() as session:
        stmt = (
            select(ContactModel, ConversationModel)
            .join(
                ConversationModel,
                ConversationModel.contact_id == ContactModel.contact_id,
                isouter=True,
            )
        )
        if temperature:
            stmt = stmt.where(ConversationModel.temperature == temperature.upper())

        result = await session.execute(stmt)
        rows = result.all()

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    page_rows = rows[start:end]

    leads = []
    for contact, conv in page_rows:
        lead = {
            "contact_id": contact.contact_id,
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
        }
        if conv:
            lead.update({
                "bot_type": conv.bot_type,
                "stage": conv.stage,
                "temperature": conv.temperature,
                "is_qualified": conv.is_qualified,
                "questions_answered": conv.questions_answered,
                "last_activity": conv.last_activity.isoformat() if conv.last_activity else None,
            })
        leads.append(lead)

    total_pages = (total + page_size - 1) // page_size if total else 0
    return {
        "leads": leads,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


# ---------------------------------------------------------------------------
# GET /api/dashboard/leads/{contact_id}
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/leads/{contact_id}")
async def dashboard_lead_detail(contact_id: str, _=Depends(get_admin_or_apikey)):
    """Single lead detail."""
    async with AsyncSessionFactory() as session:
        contact_result = await session.execute(
            select(ContactModel).where(ContactModel.contact_id == contact_id)
        )
        contact = contact_result.scalars().first()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact not found")

        conv_result = await session.execute(
            select(ConversationModel).where(ConversationModel.contact_id == contact_id)
        )
        conversations = conv_result.scalars().all()

    return {
        "contact": {
            "contact_id": contact.contact_id,
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
            "created_at": contact.created_at.isoformat() if contact.created_at else None,
        },
        "conversations": [
            {
                "bot_type": c.bot_type,
                "stage": c.stage,
                "temperature": c.temperature,
                "is_qualified": c.is_qualified,
                "questions_answered": c.questions_answered,
                "extracted_data": c.extracted_data,
                "last_activity": c.last_activity.isoformat() if c.last_activity else None,
                "conversation_started": c.conversation_started.isoformat() if c.conversation_started else None,
            }
            for c in conversations
        ],
    }


# ---------------------------------------------------------------------------
# GET /api/dashboard/handoffs
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/handoffs")
async def dashboard_handoffs(limit: int = 10, _=Depends(get_admin_or_apikey)):
    """Recent handoff events from BotMetricsCollector."""
    collector = BotMetricsCollector()

    with collector._data_lock:
        recent = list(collector._handoffs[-limit:])

    return [
        {
            "source": h.source,
            "target": h.target,
            "success": h.success,
            "duration_ms": h.duration_ms,
            "timestamp": h.timestamp,
        }
        for h in reversed(recent)
    ]


# ---------------------------------------------------------------------------
# GET /api/dashboard/conversations/{contact_id}
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/conversations/{contact_id}")
async def dashboard_conversation_detail(contact_id: str, _=Depends(get_admin_or_apikey)):
    """Q&A transcript from DB for a specific contact."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(ConversationModel).where(ConversationModel.contact_id == contact_id)
        )
        conversations = result.scalars().all()

    if not conversations:
        raise HTTPException(status_code=404, detail="No conversations found for contact")

    return [
        {
            "bot_type": c.bot_type,
            "stage": c.stage,
            "temperature": c.temperature,
            "questions_answered": c.questions_answered,
            "extracted_data": c.extracted_data,
            "metadata_json": c.metadata_json,
            "conversation_history": c.conversation_history,
            "last_activity": c.last_activity.isoformat() if c.last_activity else None,
            "conversation_started": c.conversation_started.isoformat() if c.conversation_started else None,
        }
        for c in conversations
    ]


# ---------------------------------------------------------------------------
# GET /api/alerts/active
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/costs")
async def dashboard_costs(_=Depends(get_admin_or_apikey)):
    """Cost and ROI data for Lyrio dashboard integration."""
    tracker = PerformanceTracker()
    perf = await tracker.get_performance_metrics()

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(ConversationModel))
        convs = result.scalars().all()

    appointments = sum(
        1 for c in convs if c.metadata_json and c.metadata_json.get("appointment_booked")
    )
    deals = sum(
        1 for c in convs if c.metadata_json and c.metadata_json.get("deal_closed")
    )

    perf_dict = perf.to_dict()
    return {
        "per_bot": perf_dict.get("per_bot_costs", []),
        "total_cost_usd": perf_dict.get("total_cost_usd", 0.0),
        "appointments_booked": appointments,
        "deals_closed": deals,
        "commission_pipeline": appointments * 300000 * 0.03,
    }


# ---------------------------------------------------------------------------
# GET /api/dashboard/sms-metrics
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/sms-metrics")
async def dashboard_sms_metrics(_=Depends(get_admin_or_apikey)):
    """SMS delivery stats (7-day rolling window)."""
    collector = SmsMetricsCollector()
    stats = await collector.get_delivery_stats()
    return stats


# ---------------------------------------------------------------------------
# GET /api/alerts/active
# ---------------------------------------------------------------------------
@router.get("/api/alerts/active")
async def alerts_active(_=Depends(get_admin_or_apikey)):
    """Get all currently active (unacknowledged) alerts."""
    service = AlertingService()
    return service.get_active_alerts()


# ---------------------------------------------------------------------------
# POST /api/alerts/{alert_id}/acknowledge
# ---------------------------------------------------------------------------
@router.post("/api/alerts/{alert_id}/acknowledge")
async def alert_acknowledge(alert_id: str, _=Depends(get_admin_or_apikey)):
    """Acknowledge an alert by ID."""
    service = AlertingService()
    try:
        service.acknowledge_alert(alert_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Alert '{alert_id}' not found")
    return {"status": "ok", "alert_id": alert_id, "acknowledged": True}
