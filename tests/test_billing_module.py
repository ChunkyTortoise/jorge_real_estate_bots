"""Billing module tests — quota, subscription lifecycle, webhook verification, usage tracking."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from billing import PLAN_QUOTAS, PlanTier, SubscriptionStatus
from billing.quota_enforcement import (
    QuotaExceededError,
    SubscriptionExpiredError,
    check_lead_quota_before_processing,
    record_lead_processed,
)
from billing.quota_manager import QuotaManager
from billing.stripe_client import StripeClient, get_stripe_client
from billing.subscription_service import SubscriptionService, _infer_plan_tier
from billing.webhook_handler import process_webhook_event, verify_webhook_signature
from database.billing_models import AgencyModel, SubscriptionModel, UsageRecordModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agency(agency_id: str = "agency-1") -> AgencyModel:
    return AgencyModel(
        id=agency_id, name="Test Agency", slug="test-agency",
        email="test@example.com", is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _make_subscription(
    agency_id: str = "agency-1", *, plan_tier: str = "starter",
    status: str = "active", lead_quota: int = 100, leads_used: int = 0,
    sub_id: str = "sub-1",
) -> SubscriptionModel:
    now = datetime.now(timezone.utc)
    return SubscriptionModel(
        id=sub_id, agency_id=agency_id,
        stripe_customer_id="cus_test", stripe_subscription_id="sub_stripe_1",
        stripe_price_id="price_starter", plan_tier=plan_tier,
        billing_interval="month", status=status,
        current_period_start=now, current_period_end=now,
        lead_quota=lead_quota, leads_used_this_period=leads_used,
        created_at=now, updated_at=now,
    )


# ---------------------------------------------------------------------------
# 1. Plan tier inference
# ---------------------------------------------------------------------------

class TestPlanTierInference:
    def test_explicit_plan_tier_wins(self):
        assert _infer_plan_tier("price_anything", "enterprise") == "enterprise"

    def test_infer_professional_from_price_id(self):
        assert _infer_plan_tier("price_pro_monthly", None) == "professional"

    def test_infer_enterprise_from_price_id(self):
        assert _infer_plan_tier("price_enterprise_annual", None) == "enterprise"

    def test_default_to_starter(self):
        assert _infer_plan_tier("price_basic", None) == "starter"

    def test_none_price_defaults_to_starter(self):
        assert _infer_plan_tier(None, None) == "starter"


# ---------------------------------------------------------------------------
# 2. PLAN_QUOTAS and PlanTier enums
# ---------------------------------------------------------------------------

class TestPlanQuotas:
    def test_starter_quota(self):
        assert PLAN_QUOTAS[PlanTier.STARTER.value] == 100

    def test_professional_quota(self):
        assert PLAN_QUOTAS[PlanTier.PROFESSIONAL.value] == 500

    def test_enterprise_quota(self):
        assert PLAN_QUOTAS[PlanTier.ENTERPRISE.value] == 999999

    def test_subscription_status_values(self):
        assert SubscriptionStatus.ACTIVE.value == "active"
        assert SubscriptionStatus.CANCELED.value == "canceled"
        assert SubscriptionStatus.PAST_DUE.value == "past_due"


# ---------------------------------------------------------------------------
# 3. QuotaManager.check_quota
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestQuotaManagerCheckQuota:
    @pytest.mark.asyncio
    async def test_allows_within_limit(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=50, lead_quota=100)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        mgr = QuotaManager()
        assert await mgr.check_quota("agency-1") is True

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=100, lead_quota=100)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        mgr = QuotaManager()
        assert await mgr.check_quota("agency-1") is False

    @pytest.mark.asyncio
    async def test_blocks_canceled_subscription(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(status="canceled", leads_used=0)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        mgr = QuotaManager()
        assert await mgr.check_quota("agency-1") is False

    @pytest.mark.asyncio
    async def test_allows_trialing_subscription(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(status="trialing", leads_used=0)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        mgr = QuotaManager()
        assert await mgr.check_quota("agency-1") is True

    @pytest.mark.asyncio
    async def test_allows_when_no_subscription(self, db_session):
        agency = _make_agency()
        db_session.add(agency)
        await db_session.commit()

        mgr = QuotaManager()
        assert await mgr.check_quota("agency-1") is True


# ---------------------------------------------------------------------------
# 4. QuotaManager.record_usage and get_usage_summary
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestQuotaManagerUsage:
    @pytest.mark.asyncio
    async def test_record_usage_increments_leads_used(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=5, lead_quota=100)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        mgr = QuotaManager()
        await mgr.record_usage("agency-1", "lead", quantity=1, contact_id="c1", bot_type="lead")

        summary = await mgr.get_usage_summary("agency-1")
        assert summary["has_subscription"] is True
        assert summary["used"] == 6
        assert summary["remaining"] == 94

    @pytest.mark.asyncio
    async def test_usage_summary_no_subscription(self, db_session):
        agency = _make_agency()
        db_session.add(agency)
        await db_session.commit()

        mgr = QuotaManager()
        summary = await mgr.get_usage_summary("agency-1")
        assert summary["has_subscription"] is False
        assert summary["quota"] == 0

    @pytest.mark.asyncio
    async def test_reset_quotas(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=50)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        mgr = QuotaManager()
        await mgr.reset_quotas("agency-1")

        summary = await mgr.get_usage_summary("agency-1")
        assert summary["used"] == 0


# ---------------------------------------------------------------------------
# 5. Quota enforcement (check_lead_quota_before_processing)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestQuotaEnforcement:
    @pytest.mark.asyncio
    async def test_passes_when_within_quota(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=10, lead_quota=100)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        # Should not raise
        await check_lead_quota_before_processing("agency-1", "contact-1")

    @pytest.mark.asyncio
    async def test_raises_quota_exceeded(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=100, lead_quota=100)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        with pytest.raises(QuotaExceededError) as exc_info:
            await check_lead_quota_before_processing("agency-1", "contact-1")
        assert exc_info.value.quota_type == "lead"
        assert exc_info.value.limit == 100

    @pytest.mark.asyncio
    async def test_raises_subscription_expired(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(status="canceled")
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        with pytest.raises(SubscriptionExpiredError) as exc_info:
            await check_lead_quota_before_processing("agency-1", "contact-1")
        assert exc_info.value.status == "canceled"

    @pytest.mark.asyncio
    async def test_passes_when_no_subscription(self, db_session):
        agency = _make_agency()
        db_session.add(agency)
        await db_session.commit()

        # Migration-safe: no subscription means allow through
        await check_lead_quota_before_processing("agency-1", "contact-1")


# ---------------------------------------------------------------------------
# 6. Stripe webhook verification
# ---------------------------------------------------------------------------

class TestWebhookVerification:
    def test_rejects_missing_signature(self):
        assert verify_webhook_signature({"id": "evt_1"}, None) is False

    def test_accepts_test_signature(self):
        assert verify_webhook_signature({"id": "evt_1"}, "test_sig_abc") is True

    def test_rejects_without_webhook_secret(self):
        assert verify_webhook_signature({"id": "evt_1"}, "sig_real") is False

    @patch.dict("os.environ", {"STRIPE_WEBHOOK_SECRET": "whsec_test"})
    def test_rejects_invalid_hmac(self):
        assert verify_webhook_signature({"id": "evt_1"}, "bad_hmac_value") is False


# ---------------------------------------------------------------------------
# 7. Stripe webhook event processing
# ---------------------------------------------------------------------------

class TestWebhookEventProcessing:
    @pytest.mark.asyncio
    async def test_valid_event_returns_true(self):
        assert await process_webhook_event({"id": "evt_1", "type": "invoice.paid"}) is True

    @pytest.mark.asyncio
    async def test_missing_id_returns_false(self):
        assert await process_webhook_event({"type": "invoice.paid"}) is False

    @pytest.mark.asyncio
    async def test_missing_type_returns_false(self):
        assert await process_webhook_event({"id": "evt_1"}) is False

    @pytest.mark.asyncio
    async def test_empty_payload_returns_false(self):
        assert await process_webhook_event({}) is False


# ---------------------------------------------------------------------------
# 8. StripeClient (non-configured mode)
# ---------------------------------------------------------------------------

class TestStripeClient:
    def test_disabled_by_default(self):
        client = StripeClient()
        assert client.enabled is False

    def test_enabled_with_key(self):
        client = StripeClient(api_key="sk_test_123")
        assert client.enabled is True

    @pytest.mark.asyncio
    async def test_create_customer_raises_when_disabled(self):
        client = StripeClient()
        with pytest.raises(RuntimeError, match="not configured"):
            await client.create_customer(email="a@b.com")

    @pytest.mark.asyncio
    async def test_cancel_subscription_at_period_end(self):
        client = StripeClient(api_key="sk_test_123")
        result = await client.cancel_subscription("sub_1", at_period_end=True)
        assert result["status"] == "active"
        assert result["cancel_at_period_end"] is True

    @pytest.mark.asyncio
    async def test_cancel_subscription_immediately(self):
        client = StripeClient(api_key="sk_test_123")
        result = await client.cancel_subscription("sub_1", at_period_end=False)
        assert result["status"] == "canceled"

    def test_get_stripe_client_returns_instance(self):
        client = get_stripe_client()
        assert isinstance(client, StripeClient)


# ---------------------------------------------------------------------------
# 9. SubscriptionService.get_subscription_status
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSubscriptionService:
    @pytest.mark.asyncio
    async def test_status_when_no_subscription(self, db_session):
        agency = _make_agency()
        db_session.add(agency)
        await db_session.commit()

        svc = SubscriptionService(stripe_client=StripeClient())
        status = await svc.get_subscription_status("agency-1")
        assert status["status"] == "none"
        assert status["is_active"] is False

    @pytest.mark.asyncio
    async def test_status_active_subscription(self, db_session):
        agency = _make_agency()
        sub = _make_subscription(leads_used=25, lead_quota=100)
        db_session.add(agency)
        db_session.add(sub)
        await db_session.commit()

        svc = SubscriptionService(stripe_client=StripeClient())
        status = await svc.get_subscription_status("agency-1")
        assert status["status"] == "active"
        assert status["is_active"] is True
        assert status["plan_tier"] == "starter"
        assert status["quota"]["used"] == 25
        assert status["quota"]["remaining"] == 75
