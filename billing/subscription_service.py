"""Subscription lifecycle service for billing tests and API usage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, select

from billing import PLAN_QUOTAS, PlanTier
from billing.stripe_client import StripeClient, get_stripe_client
from database.billing_models import AgencyModel, SubscriptionModel
from database.session import AsyncSessionFactory


def _dt_from_ts(value: Optional[int]) -> Optional[datetime]:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _infer_plan_tier(price_id: str | None, plan_tier: str | None) -> str:
    if plan_tier:
        return plan_tier
    normalized = (price_id or "starter").lower()
    if "enterprise" in normalized:
        return PlanTier.ENTERPRISE.value
    if "pro" in normalized:
        return PlanTier.PROFESSIONAL.value
    return PlanTier.STARTER.value


class SubscriptionService:
    def __init__(self, stripe_client: StripeClient | None = None):
        self.stripe = stripe_client or get_stripe_client()

    async def _get_active_subscription(self, agency_id: str) -> SubscriptionModel | None:
        async with AsyncSessionFactory() as session:
            result = await session.execute(
                select(SubscriptionModel)
                .where(SubscriptionModel.agency_id == agency_id)
                .where(SubscriptionModel.status.in_(["active", "trialing"]))
                .order_by(desc(SubscriptionModel.updated_at))
            )
            return result.scalars().first()

    async def create_subscription(
        self,
        agency_id: str,
        price_id: str,
        plan_tier: str | None = None,
        payment_method_id: str | None = None,
        trial_days: int | None = None,
    ) -> dict[str, Any]:
        async with AsyncSessionFactory() as session:
            agency = await session.get(AgencyModel, agency_id)
            if not agency:
                raise ValueError(f"Agency not found: {agency_id}")

            customer = await self.stripe.create_customer(email=agency.email, name=agency.name)

            if payment_method_id:
                await self.stripe.attach_payment_method(customer["id"], payment_method_id)

            stripe_sub = await self.stripe.create_subscription(
                customer["id"],
                price_id,
                trial_days=trial_days,
            )

            tier = _infer_plan_tier(price_id, plan_tier)
            quota = PLAN_QUOTAS.get(tier, PLAN_QUOTAS[PlanTier.STARTER.value])
            now = datetime.now(timezone.utc)
            model = SubscriptionModel(
                id=stripe_sub["id"],
                agency_id=agency_id,
                stripe_customer_id=customer.get("id"),
                stripe_subscription_id=stripe_sub.get("id"),
                stripe_price_id=price_id,
                plan_tier=tier,
                billing_interval="month",
                status=stripe_sub.get("status", "active"),
                current_period_start=_dt_from_ts(stripe_sub.get("current_period_start")) or now,
                current_period_end=_dt_from_ts(stripe_sub.get("current_period_end")),
                trial_end=_dt_from_ts(stripe_sub.get("trial_end")),
                cancel_at_period_end=False,
                lead_quota=quota,
                leads_used_this_period=0,
                created_at=now,
                updated_at=now,
            )
            session.add(model)
            await session.commit()

            response: dict[str, Any] = {
                "success": True,
                "subscription_id": stripe_sub.get("id"),
                "status": stripe_sub.get("status", "active"),
            }
            if stripe_sub.get("trial_end"):
                response["trial_end"] = _dt_from_ts(stripe_sub.get("trial_end")).isoformat()
            return response

    async def upgrade_subscription(self, agency_id: str, new_price_id: str) -> dict[str, Any]:
        sub = await self._get_active_subscription(agency_id)
        if not sub:
            raise ValueError("No active subscription found")

        update_payload = {"items": [{"id": "item_123", "price": new_price_id}]}
        stripe_sub = await self.stripe.update_subscription(sub.stripe_subscription_id, update_payload)

        sub.stripe_price_id = new_price_id
        sub.plan_tier = _infer_plan_tier(new_price_id, None)
        sub.updated_at = datetime.now(timezone.utc)

        async with AsyncSessionFactory() as session:
            await session.merge(sub)
            await session.commit()

        return {
            "success": True,
            "status": stripe_sub.get("status", sub.status),
            "proration_amount": stripe_sub.get("proration_amount", 0),
        }

    async def cancel_subscription(self, agency_id: str, at_period_end: bool = True) -> dict[str, Any]:
        sub = await self._get_active_subscription(agency_id)
        if not sub:
            raise ValueError("No active subscription found")

        stripe_sub = await self.stripe.cancel_subscription(sub.stripe_subscription_id, at_period_end=at_period_end)

        sub.cancel_at_period_end = at_period_end
        if not at_period_end:
            sub.status = stripe_sub.get("status", "canceled")
        sub.updated_at = datetime.now(timezone.utc)

        async with AsyncSessionFactory() as session:
            await session.merge(sub)
            await session.commit()

        return {
            "success": True,
            "cancel_at_period_end": at_period_end,
            "status": stripe_sub.get("status", sub.status),
        }

    async def get_subscription_status(self, agency_id: str) -> dict[str, Any]:
        sub = await self._get_active_subscription(agency_id)
        if not sub:
            return {"status": "none", "is_active": False, "plan_tier": None}

        if sub.stripe_subscription_id and getattr(self.stripe, "enabled", False):
            try:
                await self.stripe.get_subscription(sub.stripe_subscription_id)
            except Exception:
                pass

        return {
            "status": sub.status,
            "is_active": sub.status in {"active", "trialing"},
            "plan_tier": sub.plan_tier,
            "quota": {
                "used": sub.leads_used_this_period,
                "total": sub.lead_quota,
                "remaining": max(0, sub.lead_quota - sub.leads_used_this_period),
            },
        }

    async def add_payment_method(self, agency_id: str, payment_method_id: str) -> dict[str, Any]:
        sub = await self._get_active_subscription(agency_id)
        if not sub or not sub.stripe_customer_id:
            raise ValueError("No active subscription found")

        response = await self.stripe.attach_payment_method(sub.stripe_customer_id, payment_method_id)
        return {"success": True, "payment_method_id": response.get("id", payment_method_id)}
