"""Minimal async Stripe client wrapper used by billing services/tests."""

from __future__ import annotations

import os
from typing import Any


class StripeClient:
    """Thin abstraction over Stripe operations.

    In tests, these methods are commonly mocked. This implementation keeps a
    conservative default behavior for environments where Stripe is not wired.
    """

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("STRIPE_SECRET_KEY")
        self.enabled = bool(self.api_key)

    async def create_customer(self, **kwargs: Any) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured")
        return {"id": kwargs.get("id") or "cus_local"}

    async def attach_payment_method(self, customer_id: str, payment_method_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured")
        return {"id": payment_method_id, "customer": customer_id}

    async def create_subscription(self, customer_id: str, price_id: str, **kwargs: Any) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured")
        return {
            "id": "sub_local",
            "status": "active",
            "customer": customer_id,
            "price_id": price_id,
            **kwargs,
        }

    async def update_subscription(self, subscription_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured")
        return {"id": subscription_id, "status": "active", **payload}

    async def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured")
        return {
            "id": subscription_id,
            "status": "active" if at_period_end else "canceled",
            "cancel_at_period_end": at_period_end,
        }

    async def get_subscription(self, subscription_id: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Stripe is not configured")
        return {"id": subscription_id, "status": "active"}


def get_stripe_client() -> StripeClient:
    return StripeClient()
