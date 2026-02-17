"""Integration smoke tests for billing paths against live dependencies."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from billing.subscription_service import SubscriptionService
from database.session import AsyncSessionFactory


def _require_integration_mode() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_billing_db_connectivity_smoke() -> None:
    """Verify we can execute a trivial query against the configured live DB."""
    _require_integration_mode()
    if not os.getenv("DATABASE_URL"):
        pytest.skip("DATABASE_URL is required for DB integration smoke test")

    async with AsyncSessionFactory() as session:
        result = await session.execute(text("SELECT 1"))

    assert result.scalar() == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_billing_stripe_configuration_smoke() -> None:
    """Verify Stripe is wired when integration mode is explicitly enabled."""
    _require_integration_mode()
    if not os.getenv("STRIPE_SECRET_KEY"):
        pytest.skip("STRIPE_SECRET_KEY is required for Stripe integration smoke test")

    service = SubscriptionService()
    assert getattr(service.stripe, "enabled", False) is True
