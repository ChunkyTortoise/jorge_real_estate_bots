"""Dashboard API routes — serves Lyrio dashboard with real metrics."""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select

from bots.lead_bot.routes_admin import get_admin_or_apikey
from bots.shared.alerting_service import AlertingService
from bots.shared.bot_metrics_collector import BotMetricsCollector
from bots.shared.business_rules import JorgeBusinessRules
from bots.shared.conversation_contract import extract_canonical_view
from bots.shared.dashboard_data_service import DashboardDataService
from bots.shared.logger import get_logger
from bots.shared.performance_tracker import PerformanceTracker
from bots.shared.sms_metrics_collector import SmsMetricsCollector
from bots.shared.stall_reengagement import StallReengagementService
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
            stmt = stmt.where(ConversationModel.temperature == temperature.lower())

        # Count query for pagination metadata
        count_stmt = select(func.count(ContactModel.id)).join(
            ConversationModel,
            ConversationModel.contact_id == ContactModel.contact_id,
            isouter=True,
        )
        if temperature:
            count_stmt = count_stmt.where(ConversationModel.temperature == temperature.lower())
        count_result = await session.execute(count_stmt)
        total = count_result.scalar_one()

        # DB-level pagination
        stmt = stmt.limit(page_size).offset((page - 1) * page_size)
        result = await session.execute(stmt)
        page_rows = result.all()

    leads = []
    for contact, conv in page_rows:
        lead = {
            "contact_id": contact.contact_id,
            "name": contact.name,
            "email": contact.email,
            "phone": contact.phone,
        }
        if conv:
            canonical = extract_canonical_view(conv)
            lead.update({
                "bot_type": conv.bot_type,
                "mode": canonical["mode"],
                "mode_version": canonical["mode_version"],
                "status": canonical["status"],
                "handoff_reason": canonical.get("handoff_reason"),
                "message_suppression_reason": canonical.get("message_suppression_reason"),
                "qualification_summary": canonical.get("qualification_summary"),
                "crm_sync_status": canonical.get("crm_sync_status"),
                "next_recommended_action": canonical.get("next_recommended_action"),
                "last_inbound_at": canonical.get("last_inbound_at"),
                "last_outbound_at": canonical.get("last_outbound_at"),
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
                "mode": (canonical := extract_canonical_view(c))["mode"],
                "mode_version": canonical["mode_version"],
                "status": canonical["status"],
                "handoff_reason": canonical.get("handoff_reason"),
                "message_suppression_reason": canonical.get("message_suppression_reason"),
                "qualification_summary": canonical.get("qualification_summary"),
                "crm_sync_status": canonical.get("crm_sync_status"),
                "next_recommended_action": canonical.get("next_recommended_action"),
                "last_inbound_at": canonical.get("last_inbound_at"),
                "last_outbound_at": canonical.get("last_outbound_at"),
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
            "contact_id": h.contact_id,
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
            "mode": (canonical := extract_canonical_view(c))["mode"],
            "mode_version": canonical["mode_version"],
            "status": canonical["status"],
            "handoff_reason": canonical.get("handoff_reason"),
            "message_suppression_reason": canonical.get("message_suppression_reason"),
            "qualification_summary": canonical.get("qualification_summary"),
            "crm_sync_status": canonical.get("crm_sync_status"),
            "next_recommended_action": canonical.get("next_recommended_action"),
            "last_inbound_at": canonical.get("last_inbound_at"),
            "last_outbound_at": canonical.get("last_outbound_at"),
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
        result = await session.execute(select(ConversationModel).limit(2000))
        convs = result.scalars().all()

    appointments = sum(
        1 for c in convs if c.metadata_json and c.metadata_json.get("appointment_booked")
    )
    deals = sum(
        1 for c in convs if c.metadata_json and c.metadata_json.get("deal_closed")
    )

    # Sum commissions from actual price data where available
    commission_total = 0.0
    priced_count = 0
    for c in convs:
        if not (c.metadata_json and c.metadata_json.get("appointment_booked")):
            continue
        ed = c.extracted_data or {}
        price = ed.get("price_expectation") or ed.get("price_max")
        if price and isinstance(price, (int, float)) and price > 0:
            commission_total += JorgeBusinessRules.calculate_commission(price)
            priced_count += 1

    # Fall back to estimate for appointments without price data
    unpriced = appointments - priced_count
    if unpriced > 0:
        commission_total += unpriced * JorgeBusinessRules.calculate_commission(300000)

    perf_dict = perf.to_dict()
    return {
        "per_bot": perf_dict.get("per_bot_costs", []),
        "total_cost_usd": perf_dict.get("total_cost_usd", 0.0),
        "appointments_booked": appointments,
        "deals_closed": deals,
        "commission_pipeline": commission_total,
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
# GET /api/dashboard/funnel
# ---------------------------------------------------------------------------
# Map Q-stages from ConversationModel to funnel display stages
_Q_STAGE_MAP: dict[str | None, str] = {
    "Q0": "AWARENESS",
    "Q1": "AWARENESS",
    "Q2": "INTEREST",
    "Q3": "CONSIDERATION",
    "Q4": "INTENT",
    "QUALIFIED": "CONVERSION",
}

_FUNNEL_ORDER = ["AWARENESS", "INTEREST", "CONSIDERATION", "INTENT", "CONVERSION"]


@router.get("/api/dashboard/funnel")
async def dashboard_funnel(_=Depends(get_admin_or_apikey)):
    """Funnel conversion data across qualification stages."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(ConversationModel).limit(2000))
        convs = result.scalars().all()

    # Count contacts at each funnel stage (use highest Q-stage per contact)
    contact_stages: dict[str, str] = {}
    first_activity: dict[str, float] = {}
    qualified_activity: dict[str, float] = {}

    for c in convs:
        q_stage = c.stage or "Q0"
        funnel_stage = _Q_STAGE_MAP.get(q_stage, "AWARENESS")
        existing = contact_stages.get(c.contact_id)
        if existing is None or _FUNNEL_ORDER.index(funnel_stage) > _FUNNEL_ORDER.index(existing):
            contact_stages[c.contact_id] = funnel_stage

        # Track time-to-qualify
        if c.conversation_started:
            ts = c.conversation_started.timestamp()
            if c.contact_id not in first_activity or ts < first_activity[c.contact_id]:
                first_activity[c.contact_id] = ts
        if c.is_qualified and c.last_activity:
            qualified_activity[c.contact_id] = c.last_activity.timestamp()

    # Count contacts that reached each stage (cumulative — reaching INTENT means you passed AWARENESS)
    stage_counts: dict[str, int] = {s: 0 for s in _FUNNEL_ORDER}
    for cid, highest_stage in contact_stages.items():
        idx = _FUNNEL_ORDER.index(highest_stage)
        for i in range(idx + 1):
            stage_counts[_FUNNEL_ORDER[i]] += 1

    # Build stage list with conversion rates
    stages = []
    for i, name in enumerate(_FUNNEL_ORDER):
        count = stage_counts[name]
        if i < len(_FUNNEL_ORDER) - 1:
            next_count = stage_counts[_FUNNEL_ORDER[i + 1]]
            conversion_rate = round(next_count / count, 2) if count > 0 else 0.0
        else:
            conversion_rate = None
        stages.append({"name": name, "count": count, "conversion_rate": conversion_rate})

    # Average time to qualify (hours)
    qualify_times = []
    for cid, q_ts in qualified_activity.items():
        if cid in first_activity:
            hours = (q_ts - first_activity[cid]) / 3600
            qualify_times.append(hours)

    avg_time = round(sum(qualify_times) / len(qualify_times), 1) if qualify_times else None

    total_contacts = len(contact_stages)
    return {
        "stages": stages,
        "total_contacts": total_contacts,
        "avg_time_to_qualify_hours": avg_time,
    }


# ---------------------------------------------------------------------------
# GET /api/dashboard/stall-stats
# ---------------------------------------------------------------------------
@router.get("/api/dashboard/stall-stats")
async def dashboard_stall_stats(
    contact_id: Optional[str] = Query(None),
    _=Depends(get_admin_or_apikey),
):
    """Stall re-engagement statistics."""
    # Get re-engagement stats from StallReengagementService (Redis-backed)
    try:
        svc = StallReengagementService()
        re_stats = await svc.get_stats()
    except Exception:
        re_stats = {
            "total_contacts_reached": 0,
            "total_attempts": 0,
            "replies": 0,
            "reply_rate": 0.0,
        }

    # Count stalled conversations by stage from DB
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel).where(ConversationModel.stage == "STALLED")
        if contact_id:
            stmt = stmt.where(ConversationModel.contact_id == contact_id)
        result = await session.execute(stmt)
        stalled = result.scalars().all()

    by_stage: dict[str, int] = {}
    for c in stalled:
        # Use metadata to find original Q-stage before stall, or fallback
        orig = (c.metadata_json or {}).get("stalled_from_stage", "Q0")
        by_stage[orig] = by_stage.get(orig, 0) + 1

    total_stalled = len(stalled)
    return {
        "total_stalled": total_stalled,
        "reengagement_attempts": re_stats.get("total_attempts", 0),
        "reengagement_replies": re_stats.get("replies", 0),
        "reply_rate": re_stats.get("reply_rate", 0.0),
        "by_stage": by_stage,
    }


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
