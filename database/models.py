"""
SQLAlchemy ORM models for Jorge Real Estate Bots.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class SessionModel(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ContactModel(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    contact_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    location_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ConversationModel(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    contact_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    bot_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    temperature: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    current_question: Mapped[int] = mapped_column(Integer, default=0)
    questions_answered: Mapped[int] = mapped_column(Integer, default=0)
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False)
    conversation_history: Mapped[dict] = mapped_column(JSONB, default=list)
    extracted_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    conversation_started: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_conversations_contact_bot", "contact_id", "bot_type"),
    )


class LeadModel(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    contact_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    location_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    budget_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    budget_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    timeline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    service_area_match: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    is_qualified: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class DealModel(Base):
    __tablename__ = "deals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    contact_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    commission: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)


class CommissionModel(Base):
    __tablename__ = "commissions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    deal_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey("deals.id"), nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class PropertyModel(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    mls_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    zip: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    price: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    beds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    baths: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sqft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    listed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class BuyerPreferenceModel(Base):
    __tablename__ = "buyer_preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid_str)
    contact_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    location_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    beds_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    baths_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sqft_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    preapproved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    timeline_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    motivation: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    temperature: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    preferences_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    matches_json: Mapped[dict] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
