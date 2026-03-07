"""
Database repository helpers for common upsert and query operations.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

from sqlalchemy import func, select

from database.models import (
    BuyerPreferenceModel,
    ContactModel,
    ConversationModel,
    LeadModel,
    PropertyModel,
)
from database.session import AsyncSessionFactory


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_contact(
    contact_id: str,
    location_id: Optional[str] = None,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> None:
    async with AsyncSessionFactory() as session:
        stmt = select(ContactModel).where(ContactModel.contact_id == contact_id)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            existing.location_id = location_id or existing.location_id
            existing.name = name or existing.name
            existing.email = email or existing.email
            existing.phone = phone or existing.phone
            existing.updated_at = _now()
        else:
            session.add(
                ContactModel(
                    contact_id=contact_id,
                    location_id=location_id,
                    name=name,
                    email=email,
                    phone=phone,
                )
            )
        await session.commit()


async def upsert_conversation(
    contact_id: str,
    bot_type: str,
    stage: Optional[str],
    temperature: Optional[str],
    current_question: int,
    questions_answered: int,
    is_qualified: bool,
    extracted_data: Dict[str, Any],
    last_activity: Optional[datetime],
    conversation_started: Optional[datetime],
    conversation_history: Optional[List[Dict[str, Any]]] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
    mode: Optional[str] = None,
    mode_version: Optional[int] = None,
    status: Optional[str] = None,
    handoff_reason: Optional[str] = None,
    human_takeover: Optional[bool] = None,
    bilingual_required: Optional[bool] = None,
    message_suppression_reason: Optional[str] = None,
    qualification_summary: Optional[Dict[str, Any]] = None,
    next_recommended_action: Optional[str] = None,
    crm_sync_status: Optional[str] = None,
    last_inbound_at: Optional[datetime] = None,
    last_outbound_at: Optional[datetime] = None,
) -> None:
    metadata_json = metadata_json or {}
    qualification_summary = qualification_summary or {}
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel).where(
            ConversationModel.contact_id == contact_id,
            ConversationModel.bot_type == bot_type,
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            existing.stage = stage
            existing.temperature = temperature
            existing.current_question = current_question
            existing.questions_answered = questions_answered
            existing.is_qualified = is_qualified
            existing.mode = mode if mode is not None else (existing.mode or metadata_json.get("mode"))
            existing.mode_version = mode_version if mode_version is not None else (existing.mode_version or metadata_json.get("mode_version", 1))
            existing.status = status or existing.status or metadata_json.get("status")
            existing.handoff_reason = handoff_reason if handoff_reason is not None else existing.handoff_reason
            existing.human_takeover = human_takeover if human_takeover is not None else existing.human_takeover
            existing.bilingual_required = bilingual_required if bilingual_required is not None else existing.bilingual_required
            existing.message_suppression_reason = (
                message_suppression_reason
                if message_suppression_reason is not None
                else existing.message_suppression_reason
            )
            existing.qualification_summary = qualification_summary if qualification_summary is not None else (existing.qualification_summary or {})
            existing.next_recommended_action = (
                next_recommended_action
                if next_recommended_action is not None
                else existing.next_recommended_action
            )
            existing.crm_sync_status = crm_sync_status if crm_sync_status is not None else (existing.crm_sync_status or metadata_json.get("crm_sync_status"))
            existing.last_inbound_at = last_inbound_at or existing.last_inbound_at
            existing.last_outbound_at = last_outbound_at or existing.last_outbound_at
            if conversation_history is not None:
                existing.conversation_history = conversation_history
            existing.extracted_data = extracted_data
            existing.last_activity = last_activity
            if existing.conversation_started is None and conversation_started is not None:
                existing.conversation_started = conversation_started
            merged_meta = dict(existing.metadata_json or {})
            merged_meta.update(metadata_json)
            existing.metadata_json = merged_meta
            existing.updated_at = _now()
        else:
            session.add(
                ConversationModel(
                    contact_id=contact_id,
                    bot_type=bot_type,
                    stage=stage,
                    temperature=temperature,
                    current_question=current_question,
                    questions_answered=questions_answered,
                    is_qualified=is_qualified,
                    mode=mode or metadata_json.get("mode"),
                    mode_version=mode_version or metadata_json.get("mode_version", 1),
                    status=status or metadata_json.get("status"),
                    handoff_reason=handoff_reason,
                    human_takeover=human_takeover,
                    bilingual_required=bilingual_required,
                    message_suppression_reason=message_suppression_reason,
                    qualification_summary=qualification_summary,
                    next_recommended_action=next_recommended_action,
                    crm_sync_status=crm_sync_status or metadata_json.get("crm_sync_status"),
                    last_inbound_at=last_inbound_at,
                    last_outbound_at=last_outbound_at,
                    conversation_history=conversation_history or [],
                    extracted_data=extracted_data,
                    last_activity=last_activity,
                    conversation_started=conversation_started,
                    metadata_json=metadata_json,
                )
            )
        await session.commit()


async def upsert_lead(
    contact_id: str,
    location_id: Optional[str],
    score: Optional[float],
    temperature: Optional[str],
    budget_min: Optional[int],
    budget_max: Optional[int],
    timeline: Optional[str],
    service_area_match: Optional[bool],
    is_qualified: Optional[bool],
    metadata_json: Optional[Dict[str, Any]] = None,
) -> None:
    metadata_json = metadata_json or {}
    async with AsyncSessionFactory() as session:
        stmt = select(LeadModel).where(LeadModel.contact_id == contact_id)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            existing.location_id = location_id or existing.location_id
            existing.score = score
            existing.temperature = temperature
            existing.budget_min = budget_min
            existing.budget_max = budget_max
            existing.timeline = timeline
            existing.service_area_match = service_area_match
            existing.is_qualified = is_qualified
            existing.metadata_json = metadata_json
            existing.updated_at = _now()
        else:
            session.add(
                LeadModel(
                    contact_id=contact_id,
                    location_id=location_id,
                    score=score,
                    temperature=temperature,
                    budget_min=budget_min,
                    budget_max=budget_max,
                    timeline=timeline,
                    service_area_match=service_area_match,
                    is_qualified=is_qualified,
                    metadata_json=metadata_json,
                )
            )
        await session.commit()


async def upsert_buyer_preferences(
    contact_id: str,
    location_id: Optional[str],
    beds_min: Optional[int],
    baths_min: Optional[float],
    sqft_min: Optional[int],
    price_min: Optional[int],
    price_max: Optional[int],
    preapproved: Optional[bool],
    timeline_days: Optional[int],
    motivation: Optional[str],
    temperature: Optional[str],
    preferences_json: Dict[str, Any],
    matches_json: List[Dict[str, Any]],
) -> None:
    async with AsyncSessionFactory() as session:
        stmt = select(BuyerPreferenceModel).where(BuyerPreferenceModel.contact_id == contact_id)
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if existing:
            existing.location_id = location_id or existing.location_id
            existing.beds_min = beds_min
            existing.baths_min = baths_min
            existing.sqft_min = sqft_min
            existing.price_min = price_min
            existing.price_max = price_max
            existing.preapproved = preapproved
            existing.timeline_days = timeline_days
            existing.motivation = motivation
            existing.temperature = temperature
            existing.preferences_json = preferences_json
            existing.matches_json = matches_json
            existing.updated_at = _now()
        else:
            session.add(
                BuyerPreferenceModel(
                    contact_id=contact_id,
                    location_id=location_id,
                    beds_min=beds_min,
                    baths_min=baths_min,
                    sqft_min=sqft_min,
                    price_min=price_min,
                    price_max=price_max,
                    preapproved=preapproved,
                    timeline_days=timeline_days,
                    motivation=motivation,
                    temperature=temperature,
                    preferences_json=preferences_json,
                    matches_json=matches_json,
                )
            )
        await session.commit()


async def fetch_properties(
    city: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    beds_min: Optional[int] = None,
    baths_min: Optional[float] = None,
    sqft_min: Optional[int] = None,
    limit: int = 100,
) -> List[PropertyModel]:
    async with AsyncSessionFactory() as session:
        stmt = select(PropertyModel)
        if city:
            stmt = stmt.where(PropertyModel.city.ilike(f"%{city}%"))
        if price_min is not None:
            stmt = stmt.where(PropertyModel.price >= price_min)
        if price_max is not None:
            stmt = stmt.where(PropertyModel.price <= price_max)
        if beds_min is not None:
            stmt = stmt.where(PropertyModel.beds >= beds_min)
        if baths_min is not None:
            stmt = stmt.where(PropertyModel.baths >= baths_min)
        if sqft_min is not None:
            stmt = stmt.where(PropertyModel.sqft >= sqft_min)
        stmt = stmt.limit(limit)
        result = await session.execute(stmt)
        return list(result.scalars().all())


async def fetch_conversation(contact_id: str, bot_type: str) -> Optional[ConversationModel]:
    """Fetch a conversation record by contact_id and bot_type. Returns None if not found."""
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel).where(
            ConversationModel.contact_id == contact_id,
            ConversationModel.bot_type == bot_type,
        )
        result = await session.execute(stmt)
        return result.scalars().first()


async def merge_conversation_metadata(
    contact_id: str,
    bot_type: str,
    metadata_json: Dict[str, Any],
) -> None:
    """Merge metadata into an existing conversation record when present."""
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel).where(
            ConversationModel.contact_id == contact_id,
            ConversationModel.bot_type == bot_type,
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            logger.warning(
                "merge_conversation_metadata: no record found for contact_id=%s bot_type=%s — data not persisted",
                contact_id,
                bot_type,
            )
            return
        merged = dict(existing.metadata_json or {})
        merged.update(metadata_json)
        existing.metadata_json = merged
        existing.mode = metadata_json.get("mode", existing.mode)
        existing.mode_version = metadata_json.get("mode_version", existing.mode_version or 1)
        existing.status = metadata_json.get("status", existing.status)
        if "handoff_reason" in metadata_json:
            existing.handoff_reason = metadata_json.get("handoff_reason")
        if "human_takeover" in metadata_json:
            existing.human_takeover = bool(metadata_json.get("human_takeover"))
        if "bilingual_required" in metadata_json:
            existing.bilingual_required = bool(metadata_json.get("bilingual_required"))
        if "message_suppression_reason" in metadata_json:
            existing.message_suppression_reason = metadata_json.get("message_suppression_reason")
        if "qualification_summary" in metadata_json:
            existing.qualification_summary = metadata_json.get("qualification_summary") or {}
        if "next_recommended_action" in metadata_json:
            existing.next_recommended_action = metadata_json.get("next_recommended_action")
        if "crm_sync_status" in metadata_json:
            existing.crm_sync_status = metadata_json.get("crm_sync_status")
        if metadata_json.get("last_inbound_at"):
            try:
                existing.last_inbound_at = datetime.fromisoformat(metadata_json["last_inbound_at"])
            except Exception as _ts_err:
                logger.warning(f"Could not parse last_inbound_at {metadata_json['last_inbound_at']!r}: {_ts_err}")
        if metadata_json.get("last_outbound_at"):
            try:
                existing.last_outbound_at = datetime.fromisoformat(metadata_json["last_outbound_at"])
            except Exception as _ts_err:
                logger.warning(f"Could not parse last_outbound_at {metadata_json['last_outbound_at']!r}: {_ts_err}")
        existing.updated_at = _now()
        await session.commit()


async def update_conversation_outbound_at(
    contact_id: str,
    bot_type: str,
    outbound_at: Optional[str],
) -> None:
    """Targeted update of last_outbound_at after SMS send. Does not touch other fields."""
    if not outbound_at:
        return
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel).where(
            ConversationModel.contact_id == contact_id,
            ConversationModel.bot_type == bot_type,
        )
        result = await session.execute(stmt)
        existing = result.scalars().first()
        if not existing:
            logger.warning(
                "update_conversation_outbound_at: no record for contact_id=%s bot_type=%s",
                contact_id,
                bot_type,
            )
            return
        try:
            existing.last_outbound_at = datetime.fromisoformat(outbound_at)
        except Exception as _ts_err:
            logger.warning("Could not parse outbound_at %r: %s", outbound_at, _ts_err)
            return
        existing.updated_at = _now()
        await session.commit()


async def count_conversations_by_stage(bot_type: str) -> Dict[str, int]:
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel.stage, func.count()).where(
            ConversationModel.bot_type == bot_type
        ).group_by(ConversationModel.stage)
        result = await session.execute(stmt)
        return {row[0] or "unknown": row[1] for row in result.all()}


async def count_conversations_by_temperature(bot_type: str) -> Dict[str, int]:
    async with AsyncSessionFactory() as session:
        stmt = select(ConversationModel.temperature, func.count()).where(
            ConversationModel.bot_type == bot_type
        ).group_by(ConversationModel.temperature)
        result = await session.execute(stmt)
        return {row[0] or "unknown": row[1] for row in result.all()}
