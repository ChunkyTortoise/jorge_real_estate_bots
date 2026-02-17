"""
Tests for billing database models.
"""
import pytest
from datetime import datetime, timedelta, timezone
from database.billing_models import (
    AgencyModel,
    SubscriptionModel,
    UsageRecordModel,
    WhiteLabelConfigModel,
    InvoiceModel,
    WebhookEventModel,
    OnboardingStateModel,
)


@pytest.fixture
def sample_agency():
    """Create a sample agency for testing."""
    return AgencyModel(
        id="test-agency-001",
        name="Test Real Estate Agency",
        slug="test-agency",
        email="admin@testagency.com",
        phone="555-123-4567",
        ghl_location_id="test-location-001",
        ghl_api_key="test-api-key",
        service_areas="Dallas,Plano,Frisco",
        min_price=200000,
        max_price=800000,
        standard_commission=0.06,
        is_active=True,
        is_verified=True,
        onboarding_completed=True,
        onboarding_step="complete",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_subscription(sample_agency):
    """Create a sample subscription for testing."""
    return SubscriptionModel(
        id="sub-001",
        agency_id=sample_agency.id,
        stripe_customer_id="cus_test_123",
        stripe_subscription_id="sub_stripe_123",
        stripe_price_id="price_starter_123",
        plan_tier="starter",
        billing_interval="month",
        status="active",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        trial_end=None,
        cancel_at_period_end=False,
        lead_quota=100,
        leads_used_this_period=10,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_usage_record(sample_agency, sample_subscription):
    """Create a sample usage record for testing."""
    return UsageRecordModel(
        id="usage-001",
        agency_id=sample_agency.id,
        subscription_id=sample_subscription.id,
        resource_type="lead",
        quantity=1,
        contact_id="contact-123",
        bot_type="lead_bot",
        metadata_json={"source": "ghl_webhook", "qualified": True},
        timestamp=datetime.now(timezone.utc),
    )


class TestAgencyModel:
    """Tests for AgencyModel."""
    
    async def test_agency_creation(self, sample_agency, db_session):
        """Test agency model can be created and persisted."""
        db_session.add(sample_agency)
        await db_session.commit()
        
        # Query back
        result = await db_session.get(AgencyModel, sample_agency.id)
        assert result is not None
        assert result.name == "Test Real Estate Agency"
        assert result.is_active is True
    
    async def test_agency_to_dict(self, sample_agency):
        """Test agency serialization."""
        data = sample_agency.to_dict()
        assert data["id"] == "test-agency-001"
        assert data["name"] == "Test Real Estate Agency"
        assert data["email"] == "admin@testagency.com"
        assert "created_at" in data
    
    async def test_agency_unique_constraints(self, sample_agency, db_session):
        """Test unique constraints on email and slug."""
        db_session.add(sample_agency)
        await db_session.commit()
        
        # Try to create duplicate
        duplicate = AgencyModel(
            id="test-agency-002",
            name="Duplicate Agency",
            slug=sample_agency.slug,  # Same slug
            email="different@email.com",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(duplicate)
        
        with pytest.raises(Exception):  # IntegrityError
            await db_session.commit()


class TestSubscriptionModel:
    """Tests for SubscriptionModel."""
    
    async def test_subscription_creation(self, sample_agency, sample_subscription, db_session):
        """Test subscription can be created."""
        db_session.add(sample_agency)
        db_session.add(sample_subscription)
        await db_session.commit()
        
        result = await db_session.get(SubscriptionModel, sample_subscription.id)
        assert result is not None
        assert result.plan_tier == "starter"
        assert result.status == "active"
        assert result.lead_quota == 100
    
    async def test_subscription_agency_relationship(self, sample_agency, sample_subscription, db_session):
        """Test subscription-agency foreign key relationship."""
        db_session.add(sample_agency)
        db_session.add(sample_subscription)
        await db_session.commit()
        
        # Refresh to load relationship
        await db_session.refresh(sample_subscription)
        assert sample_subscription.agency_id == sample_agency.id
    
    async def test_subscription_status_transitions(self, sample_agency, sample_subscription, db_session):
        """Test subscription status can be updated."""
        db_session.add(sample_agency)
        db_session.add(sample_subscription)
        await db_session.commit()
        
        # Update status
        sample_subscription.status = "past_due"
        await db_session.commit()
        
        result = await db_session.get(SubscriptionModel, sample_subscription.id)
        assert result.status == "past_due"


class TestUsageRecordModel:
    """Tests for UsageRecordModel."""
    
    async def test_usage_record_creation(self, sample_agency, sample_subscription, sample_usage_record, db_session):
        """Test usage record can be created."""
        db_session.add(sample_agency)
        db_session.add(sample_subscription)
        db_session.add(sample_usage_record)
        await db_session.commit()
        
        result = await db_session.get(UsageRecordModel, sample_usage_record.id)
        assert result is not None
        assert result.resource_type == "lead"
        assert result.quantity == 1
        assert result.metadata_json["qualified"] is True
    
    async def test_usage_record_query_by_agency(self, sample_agency, sample_subscription, db_session):
        """Test querying usage records by agency."""
        from sqlalchemy import select, func
        
        # Create multiple records
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
        
        # Query count
        result = await db_session.execute(
            select(func.count(UsageRecordModel.id))
            .where(UsageRecordModel.agency_id == sample_agency.id)
        )
        count = result.scalar()
        assert count == 5


class TestWhiteLabelConfigModel:
    """Tests for WhiteLabelConfigModel."""
    
    async def test_white_label_creation(self, sample_agency, db_session):
        """Test white-label config can be created."""
        config = WhiteLabelConfigModel(
            id="wl-001",
            agency_id=sample_agency.id,
            brand_name="Custom Realty",
            primary_color="#FF5733",
            secondary_color="#33FF57",
            custom_domain="realestate.example.com",
            email_from_name="Custom Realty Team",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        db_session.add(sample_agency)
        db_session.add(config)
        await db_session.commit()
        
        result = await db_session.get(WhiteLabelConfigModel, config.id)
        assert result is not None
        assert result.brand_name == "Custom Realty"
        assert result.primary_color == "#FF5733"


class TestInvoiceModel:
    """Tests for InvoiceModel."""
    
    async def test_invoice_creation(self, sample_agency, sample_subscription, db_session):
        """Test invoice can be created."""
        invoice = InvoiceModel(
            id="inv-001",
            agency_id=sample_agency.id,
            subscription_id=sample_subscription.id,
            stripe_invoice_id="in_stripe_123",
            status="paid",
            amount_due_cents=2900,
            amount_paid_cents=2900,
            invoice_date=datetime.now(timezone.utc),
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
            paid_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        
        db_session.add(sample_agency)
        db_session.add(sample_subscription)
        db_session.add(invoice)
        await db_session.commit()
        
        result = await db_session.get(InvoiceModel, invoice.id)
        assert result is not None
        assert result.status == "paid"
        assert result.amount_due_cents == 2900


class TestWebhookEventModel:
    """Tests for WebhookEventModel."""
    
    async def test_webhook_event_creation(self, db_session):
        """Test webhook event can be logged."""
        event = WebhookEventModel(
            id="evt-001",
            stripe_event_id="evt_stripe_123",
            event_type="invoice.payment_succeeded",
            processed=False,
            payload_summary={"invoice_id": "in_123"},
            received_at=datetime.now(timezone.utc),
        )
        
        db_session.add(event)
        await db_session.commit()
        
        result = await db_session.get(WebhookEventModel, event.id)
        assert result is not None
        assert result.event_type == "invoice.payment_succeeded"
        assert result.processed is False
    
    async def test_webhook_event_mark_processed(self, db_session):
        """Test marking webhook event as processed."""
        event = WebhookEventModel(
            id="evt-002",
            stripe_event_id="evt_stripe_456",
            event_type="customer.subscription.updated",
            processed=False,
            received_at=datetime.now(timezone.utc),
        )
        
        db_session.add(event)
        await db_session.commit()
        
        # Mark as processed
        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        result = await db_session.get(WebhookEventModel, event.id)
        assert result.processed is True
        assert result.processed_at is not None


class TestOnboardingStateModel:
    """Tests for OnboardingStateModel."""
    
    async def test_onboarding_state_creation(self, sample_agency, db_session):
        """Test onboarding state can be created."""
        state = OnboardingStateModel(
            id="obs-001",
            agency_id=sample_agency.id,
            current_step="ghl_connect",
            step_ghl_connected=False,
            step_agents_configured=False,
            step_territory_set=False,
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        db_session.add(sample_agency)
        db_session.add(state)
        await db_session.commit()
        
        result = await db_session.get(OnboardingStateModel, state.id)
        assert result is not None
        assert result.current_step == "ghl_connect"
        assert result.step_ghl_connected is False
    
    async def test_onboarding_progress_update(self, sample_agency, db_session):
        """Test updating onboarding progress."""
        state = OnboardingStateModel(
            id="obs-002",
            agency_id=sample_agency.id,
            current_step="ghl_connect",
            step_ghl_connected=False,
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        db_session.add(sample_agency)
        db_session.add(state)
        await db_session.commit()
        
        # Update progress
        state.step_ghl_connected = True
        state.current_step = "territory"
        state.updated_at = datetime.now(timezone.utc)
        await db_session.commit()
        
        result = await db_session.get(OnboardingStateModel, state.id)
        assert result.step_ghl_connected is True
        assert result.current_step == "territory"
