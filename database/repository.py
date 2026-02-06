"""
Database repository helpers for common upsert and query operations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert

from database.session import AsyncSessionFactory
from database.models import (
    ContactModel,
    ConversationModel,
    LeadModel,
    BuyerPreferenceModel,
    PropertyModel,
)


def _now() -> datetime:
    return datetime.utcnow()


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
    conversation_history: List[Dict[str, Any]],
    extracted_data: Dict[str, Any],
    last_activity: Optional[datetime],
    conversation_started: Optional[datetime],
    metadata_json: Optional[Dict[str, Any]] = None,
) -> None:
    metadata_json = metadata_json or {}
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
            existing.conversation_history = conversation_history
            existing.extracted_data = extracted_data
            existing.last_activity = last_activity
            existing.conversation_started = conversation_started
            existing.metadata_json = metadata_json
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
                    conversation_history=conversation_history,
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
