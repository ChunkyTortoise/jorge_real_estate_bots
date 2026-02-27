"""Billing API routes used by tests and lightweight local flows."""

from __future__ import annotations

import inspect
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select

from billing import PLAN_QUOTAS, PlanTier
from billing.quota_manager import QuotaManager
from billing.subscription_service import SubscriptionService
from billing.webhook_handler import process_webhook_event, verify_webhook_signature
from bots.shared.auth_middleware import get_current_active_user
from database.billing_models import AgencyModel
from database.session import AsyncSessionFactory

router = APIRouter(prefix="/api/billing", tags=["billing"])


def _agency_id_from_user(user: Any) -> str:
    if isinstance(user, dict):
        agency_id = user.get("agency_id")
    else:
        agency_id = getattr(user, "agency_id", None)
    return agency_id or "test-agency"


async def _resolve_agency_id(user: Any) -> str:
    agency_id = _agency_id_from_user(user)
    if agency_id != "test-agency":
        return agency_id

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(AgencyModel.id))
        first_id = result.scalars().first()
        return first_id or agency_id


async def _resolve(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


@router.get("/plans")
async def get_plans():
    plans = [
        {
            "tier": PlanTier.STARTER.value,
            "name": "Starter",
            "description": "For solo agents getting started",
            "price_monthly_cents": 2900,
            "price_annual_cents": 29000,
            "lead_quota": PLAN_QUOTAS[PlanTier.STARTER.value],
            "features": ["Lead bot", "Basic dashboard"],
        },
        {
            "tier": PlanTier.PROFESSIONAL.value,
            "name": "Professional",
            "description": "Growing teams",
            "price_monthly_cents": 9900,
            "price_annual_cents": 99000,
            "lead_quota": PLAN_QUOTAS[PlanTier.PROFESSIONAL.value],
            "features": ["Seller + buyer bots", "Advanced analytics"],
        },
        {
            "tier": PlanTier.ENTERPRISE.value,
            "name": "Enterprise",
            "description": "Scale operations",
            "price_monthly_cents": 24900,
            "price_annual_cents": 249000,
            "lead_quota": PLAN_QUOTAS[PlanTier.ENTERPRISE.value],
            "features": ["Unlimited leads", "Priority support"],
        },
    ]
    return {"plans": plans}


@router.get("/subscription")
async def get_subscription(user=Depends(get_current_active_user())):
    agency_id = await _resolve_agency_id(user)
    service = SubscriptionService()
    return await _resolve(service.get_subscription_status(agency_id))


@router.post("/subscribe")
async def subscribe(payload: dict[str, Any], user=Depends(get_current_active_user())):
    agency_id = _agency_id_from_user(user)
    service = SubscriptionService()
    return await _resolve(
        service.create_subscription(
            agency_id=agency_id,
            price_id=payload["price_id"],
            payment_method_id=payload.get("payment_method_id"),
            trial_days=payload.get("trial_days"),
        )
    )


@router.post("/upgrade")
async def upgrade(payload: dict[str, Any], user=Depends(get_current_active_user())):
    agency_id = _agency_id_from_user(user)
    service = SubscriptionService()
    return await _resolve(service.upgrade_subscription(agency_id=agency_id, new_price_id=payload["price_id"]))


@router.post("/cancel")
async def cancel(payload: dict[str, Any], user=Depends(get_current_active_user())):
    agency_id = _agency_id_from_user(user)
    service = SubscriptionService()
    return await _resolve(
        service.cancel_subscription(agency_id=agency_id, at_period_end=payload.get("at_period_end", True))
    )


@router.get("/usage")
async def usage(user=Depends(get_current_active_user())):
    agency_id = await _resolve_agency_id(user)
    qm = QuotaManager()
    return {
        "usage": await _resolve(qm.get_usage_summary(agency_id)),
        "period": "current",
    }


@router.post("/payment-method")
async def add_payment_method(payload: dict[str, Any], user=Depends(get_current_active_user())):
    agency_id = _agency_id_from_user(user)
    service = SubscriptionService()
    return await _resolve(
        service.add_payment_method(agency_id=agency_id, payment_method_id=payload["payment_method_id"])
    )


@router.delete("/payment-method/{payment_method_id}")
async def remove_payment_method(payment_method_id: str, user=Depends(get_current_active_user())):
    _agency_id_from_user(user)
    return {"success": True, "payment_method_id": payment_method_id}


webhook_router = APIRouter(prefix="/billing", tags=["billing-webhook"])


@webhook_router.post("/webhook")
async def billing_webhook(payload: dict[str, Any], stripe_signature: str | None = Header(None, alias="Stripe-Signature")):
    if not verify_webhook_signature(payload, stripe_signature):
        raise HTTPException(status_code=401, detail="Invalid Stripe signature")

    processed = await process_webhook_event(payload)
    return {"processed": bool(processed)}
