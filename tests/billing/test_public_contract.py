"""Contract tests for billing compatibility surface."""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from billing.quota_manager import QuotaManager
from billing.subscription_service import SubscriptionService
from database.billing_models import AgencyModel, SubscriptionModel, UsageRecordModel


@pytest.fixture
def agency_for_contract(db_session):
    agency = AgencyModel(
        id="contract-agency-001",
        name="Contract Agency",
        slug="contract-agency",
        email="contract@example.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(agency)
    return agency


class TestSubscriptionServiceContract:
    def test_subscription_service_signature_contract(self):
        sig = inspect.signature(SubscriptionService.create_subscription)
        for required_name in ["agency_id", "price_id", "plan_tier"]:
            assert required_name in sig.parameters

        upgrade_sig = inspect.signature(SubscriptionService.upgrade_subscription)
        assert "new_price_id" in upgrade_sig.parameters

        cancel_sig = inspect.signature(SubscriptionService.cancel_subscription)
        assert "at_period_end" in cancel_sig.parameters

        assert hasattr(SubscriptionService, "get_subscription_status")
        assert hasattr(SubscriptionService, "add_payment_method")

    @pytest.mark.asyncio
    async def test_get_subscription_status_payload_no_subscription(
        self, agency_for_contract, db_session
    ):
        await db_session.commit()
        service = SubscriptionService()

        result = await service.get_subscription_status(agency_for_contract.id)

        assert result == {"status": "none", "is_active": False, "plan_tier": None}

    @pytest.mark.asyncio
    async def test_get_subscription_status_payload_active_subscription(
        self, agency_for_contract, db_session
    ):
        sub = SubscriptionModel(
            id="contract-sub-001",
            agency_id=agency_for_contract.id,
            stripe_subscription_id="sub_contract_123",
            plan_tier="starter",
            status="active",
            lead_quota=100,
            leads_used_this_period=20,
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()

        service = SubscriptionService()
        result = await service.get_subscription_status(agency_for_contract.id)

        assert result["status"] == "active"
        assert result["is_active"] is True
        assert result["plan_tier"] == "starter"
        assert result["quota"] == {"used": 20, "total": 100, "remaining": 80}


class TestQuotaManagerContract:
    def test_quota_manager_compatibility_methods_exist(self):
        for method_name in ["check_quota", "record_usage", "reset_quotas", "get_quota_limit"]:
            assert hasattr(QuotaManager, method_name)

    @pytest.mark.asyncio
    async def test_usage_summary_includes_legacy_resource_counters(
        self, agency_for_contract, db_session
    ):
        sub = SubscriptionModel(
            id="contract-sub-002",
            agency_id=agency_for_contract.id,
            stripe_subscription_id="sub_contract_456",
            plan_tier="starter",
            status="active",
            lead_quota=100,
            leads_used_this_period=1,
            current_period_start=datetime.now(timezone.utc),
            current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)

        db_session.add(
            UsageRecordModel(
                id="contract-usage-001",
                agency_id=agency_for_contract.id,
                subscription_id=sub.id,
                resource_type="lead",
                quantity=1,
                timestamp=datetime.now(timezone.utc),
            )
        )
        await db_session.commit()

        qm = QuotaManager()
        summary = await qm.get_usage_summary(agency_for_contract.id)

        assert summary["has_subscription"] is True
        assert summary["quota"] == 100
        assert summary["used"] == 1
        assert summary["remaining"] == 99
        assert summary["lead"] == 1
