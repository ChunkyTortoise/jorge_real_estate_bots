"""
Tests for quota enforcement and quota manager.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock

from billing.quota_manager import QuotaManager
from billing.quota_enforcement import (
    check_lead_quota_before_processing,
    record_lead_processed,
    QuotaExceededError,
    SubscriptionExpiredError,
)
from billing import PlanTier
from database.billing_models import AgencyModel, SubscriptionModel, UsageRecordModel


@pytest.fixture
def quota_manager():
    """Create quota manager instance."""
    return QuotaManager()


@pytest.fixture
def sample_agency(db_session):
    """Create sample agency."""
    agency = AgencyModel(
        id="agency-quota-001",
        name="Quota Test Agency",
        slug="quota-test",
        email="quota@test.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(agency)
    return agency


@pytest.fixture
def active_subscription(sample_agency, db_session):
    """Create active subscription with starter plan."""
    sub = SubscriptionModel(
        id="sub-quota-001",
        agency_id=sample_agency.id,
        stripe_customer_id="cus_123",
        plan_tier="starter",
        status="active",
        lead_quota=100,
        leads_used_this_period=0,
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(sub)
    return sub


class TestQuotaManager:
    """Tests for QuotaManager."""
    
    async def test_check_quota_under_limit(self, quota_manager, sample_agency, active_subscription, db_session):
        """Test quota check passes when under limit."""
        await db_session.commit()
        
        result = await quota_manager.check_quota(sample_agency.id, "lead")
        assert result is True
    
    async def test_check_quota_at_limit(self, quota_manager, sample_agency, active_subscription, db_session):
        """Test quota check fails when at limit."""
        active_subscription.leads_used_this_period = 100
        await db_session.commit()
        
        result = await quota_manager.check_quota(sample_agency.id, "lead")
        assert result is False
    
    async def test_record_usage_increments_count(self, quota_manager, sample_agency, active_subscription, db_session):
        """Test recording usage increments the counter."""
        await db_session.commit()
        
        await quota_manager.record_usage(sample_agency.id, "lead", quantity=1)
        
        # Refresh subscription
        await db_session.refresh(active_subscription)
        assert active_subscription.leads_used_this_period == 1
    
    async def test_get_usage_summary(self, quota_manager, sample_agency, active_subscription, db_session):
        """Test getting usage summary."""
        # Create usage records
        for i in range(5):
            record = UsageRecordModel(
                id=f"usage-{i}",
                agency_id=sample_agency.id,
                resource_type="lead",
                quantity=1,
                timestamp=datetime.now(timezone.utc),
            )
            db_session.add(record)
        
        await db_session.commit()
        
        summary = await quota_manager.get_usage_summary(sample_agency.id)
        assert summary["lead"] == 5
    
    async def test_reset_quotas(self, quota_manager, sample_agency, active_subscription, db_session):
        """Test resetting quotas."""
        active_subscription.leads_used_this_period = 50
        await db_session.commit()
        
        await quota_manager.reset_quotas(sample_agency.id)
        
        await db_session.refresh(active_subscription)
        assert active_subscription.leads_used_this_period == 0
    
    async def test_reset_all_quotas(self, quota_manager, db_session):
        """Test resetting all agency quotas."""
        # Create multiple agencies
        for i in range(3):
            agency = AgencyModel(
                id=f"agency-reset-{i}",
                name=f"Reset Agency {i}",
                slug=f"reset-{i}",
                email=f"reset{i}@test.com",
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            sub = SubscriptionModel(
                id=f"sub-reset-{i}",
                agency_id=agency.id,
                plan_tier="starter",
                status="active",
                leads_used_this_period=10,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            db_session.add_all([agency, sub])
        
        await db_session.commit()
        
        # Reset all
        await quota_manager.reset_quotas()
        
        # Verify all reset
        from sqlalchemy import select
        result = await db_session.execute(select(SubscriptionModel))
        subscriptions = result.scalars().all()
        
        for sub in subscriptions:
            if sub.id.startswith("sub-reset-"):
                assert sub.leads_used_this_period == 0


class TestQuotaEnforcement:
    """Tests for quota enforcement functions."""
    
    async def test_check_lead_quota_passes(self, sample_agency, active_subscription, db_session):
        """Test lead quota check passes when under limit."""
        await db_session.commit()
        
        # Should not raise
        await check_lead_quota_before_processing(sample_agency.id, "contact-123")
    
    async def test_check_lead_quota_exceeded(self, sample_agency, active_subscription, db_session):
        """Test lead quota check raises when exceeded."""
        active_subscription.leads_used_this_period = 100
        await db_session.commit()
        
        with pytest.raises(QuotaExceededError) as exc_info:
            await check_lead_quota_before_processing(sample_agency.id, "contact-123")
        
        assert exc_info.value.quota_type == "lead"
        assert exc_info.value.limit == 100
        assert exc_info.value.current == 100
    
    async def test_check_subscription_expired(self, sample_agency, active_subscription, db_session):
        """Test subscription expired check."""
        active_subscription.status = "past_due"
        await db_session.commit()
        
        with pytest.raises(SubscriptionExpiredError) as exc_info:
            await check_lead_quota_before_processing(sample_agency.id, "contact-123")
        
        assert exc_info.value.agency_id == sample_agency.id
        assert exc_info.value.status == "past_due"
    
    async def test_record_lead_processed(self, sample_agency, active_subscription, db_session):
        """Test recording lead processing."""
        await db_session.commit()
        
        await record_lead_processed(
            agency_id=sample_agency.id,
            contact_id="contact-123",
            lead_type="lead",
            was_qualified=True,
        )
        
        # Check subscription updated
        await db_session.refresh(active_subscription)
        assert active_subscription.leads_used_this_period == 1
        
        # Check usage record created
        from sqlalchemy import select
        result = await db_session.execute(
            select(UsageRecordModel).where(UsageRecordModel.agency_id == sample_agency.id)
        )
        records = result.scalars().all()
        assert len(records) == 1
        assert records[0].contact_id == "contact-123"
    
    async def test_no_agency_allows_processing(self, db_session):
        """Test that leads without agencies are allowed (migration period)."""
        # Should not raise for non-existent agency
        await check_lead_quota_before_processing("non-existent-agency", "contact-123")


class TestPlanQuotas:
    """Tests for plan-specific quota limits."""
    
    async def test_starter_plan_quota(self, sample_agency, db_session):
        """Test starter plan has correct quota."""
        sub = SubscriptionModel(
            id="sub-starter",
            agency_id=sample_agency.id,
            plan_tier="starter",
            status="active",
            lead_quota=100,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        qm = QuotaManager()
        limit = await qm.get_quota_limit(sample_agency.id, "lead")
        assert limit == 100
    
    async def test_professional_plan_quota(self, sample_agency, db_session):
        """Test professional plan has correct quota."""
        sub = SubscriptionModel(
            id="sub-pro",
            agency_id=sample_agency.id,
            plan_tier="professional",
            status="active",
            lead_quota=500,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        qm = QuotaManager()
        limit = await qm.get_quota_limit(sample_agency.id, "lead")
        assert limit == 500
    
    async def test_enterprise_plan_quota(self, sample_agency, db_session):
        """Test enterprise plan has unlimited quota."""
        sub = SubscriptionModel(
            id="sub-enterprise",
            agency_id=sample_agency.id,
            plan_tier="enterprise",
            status="active",
            lead_quota=999999,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        qm = QuotaManager()
        limit = await qm.get_quota_limit(sample_agency.id, "lead")
        assert limit == 999999
