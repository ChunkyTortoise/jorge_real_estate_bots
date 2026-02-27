"""Quota enforcement helpers used by lead-processing paths."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import desc, select

from billing.quota_manager import QuotaManager
from database.billing_models import SubscriptionModel
from database.session import AsyncSessionFactory


@dataclass
class QuotaExceededError(Exception):
    quota_type: str
    limit: int
    current: int

    def __str__(self) -> str:
        return f"{self.quota_type} quota exceeded: {self.current}/{self.limit}"


@dataclass
class SubscriptionExpiredError(Exception):
    agency_id: str
    status: str

    def __str__(self) -> str:
        return f"Subscription for {self.agency_id} is not active (status={self.status})"


async def check_lead_quota_before_processing(agency_id: str, contact_id: str) -> None:
    """Raise explicit exceptions when quota or subscription state blocks processing."""
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(SubscriptionModel)
            .where(SubscriptionModel.agency_id == agency_id)
            .order_by(desc(SubscriptionModel.updated_at))
        )
        sub = result.scalars().first()

    # Migration-safe behavior for leads not mapped to a billing agency yet.
    if not sub:
        return

    if sub.status not in {"active", "trialing"}:
        raise SubscriptionExpiredError(agency_id=agency_id, status=sub.status)

    if sub.leads_used_this_period >= sub.lead_quota:
        raise QuotaExceededError(
            quota_type="lead",
            limit=sub.lead_quota,
            current=sub.leads_used_this_period,
        )


async def record_lead_processed(
    agency_id: str,
    contact_id: str,
    lead_type: str = "lead",
    was_qualified: bool = False,
) -> None:
    manager = QuotaManager()
    await manager.record_usage(
        agency_id=agency_id,
        resource_type=lead_type,
        quantity=1,
        contact_id=contact_id,
        bot_type="lead_bot",
        metadata_json={"qualified": was_qualified},
    )
