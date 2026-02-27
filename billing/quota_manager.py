"""Quota management utilities for billing plans."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select

from billing import PLAN_QUOTAS, PlanTier
from database.billing_models import SubscriptionModel, UsageRecordModel
from database.session import AsyncSessionFactory


class QuotaManager:
    async def _get_subscription(self, agency_id: str) -> SubscriptionModel | None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(SubscriptionModel)
                .where(SubscriptionModel.agency_id == agency_id)
                .order_by(desc(SubscriptionModel.updated_at))
            )
            return result.scalars().first()

    async def check_quota(self, agency_id: str, resource_type: str = "lead") -> bool:
        sub = await self._get_subscription(agency_id)
        if not sub:
            return True
        if sub.status not in {"active", "trialing"}:
            return False
        if resource_type == "lead":
            return sub.leads_used_this_period < sub.lead_quota
        return True

    async def get_quota_limit(self, agency_id: str, resource_type: str = "lead") -> int:
        sub = await self._get_subscription(agency_id)
        if not sub:
            return PLAN_QUOTAS[PlanTier.STARTER.value]
        if resource_type == "lead":
            return sub.lead_quota
        return PLAN_QUOTAS[PlanTier.STARTER.value]

    async def record_usage(
        self,
        agency_id: str,
        resource_type: str,
        quantity: int = 1,
        **metadata: Any,
    ) -> None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(SubscriptionModel)
                .where(SubscriptionModel.agency_id == agency_id)
                .where(SubscriptionModel.status.in_(["active", "trialing"]))
                .order_by(desc(SubscriptionModel.updated_at))
            )
            sub = result.scalars().first()
            if not sub:
                return

            if resource_type == "lead":
                sub.leads_used_this_period += quantity

            record = UsageRecordModel(
                id=metadata.get("usage_id") or f"usage-{agency_id}-{datetime.now(timezone.utc).timestamp()}",
                agency_id=agency_id,
                subscription_id=sub.id,
                resource_type=resource_type,
                quantity=quantity,
                contact_id=metadata.get("contact_id"),
                bot_type=metadata.get("bot_type"),
                metadata_json=metadata.get("metadata_json", {}),
                timestamp=datetime.now(timezone.utc),
            )
            session.add(record)
            await session.merge(sub)
            await session.commit()

    async def get_usage_summary(self, agency_id: str) -> dict[str, Any]:
        async with AsyncSessionFactory() as session:
            sub_result = await session.execute(
                select(SubscriptionModel)
                .where(SubscriptionModel.agency_id == agency_id)
                .order_by(desc(SubscriptionModel.updated_at))
            )
            sub = sub_result.scalars().first()

            usage_result = await session.execute(
                select(UsageRecordModel).where(UsageRecordModel.agency_id == agency_id)
            )
            usage_records = usage_result.scalars().all()

        counters: dict[str, int] = defaultdict(int)
        for rec in usage_records:
            counters[rec.resource_type] += rec.quantity

        if not sub:
            return {
                "has_subscription": False,
                "quota": 0,
                "used": 0,
                "remaining": 0,
                **dict(counters),
            }

        used = sub.leads_used_this_period
        summary = {
            "has_subscription": True,
            "quota": sub.lead_quota,
            "used": used,
            "remaining": max(0, sub.lead_quota - used),
        }
        summary.update(dict(counters))
        return summary

    async def reset_quotas(self, agency_id: str | None = None) -> None:
        async with AsyncSessionFactory() as session:
            stmt = select(SubscriptionModel)
            if agency_id:
                stmt = stmt.where(SubscriptionModel.agency_id == agency_id)
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()
            for sub in subscriptions:
                sub.leads_used_this_period = 0
                sub.updated_at = datetime.now(timezone.utc)
                await session.merge(sub)
            await session.commit()
