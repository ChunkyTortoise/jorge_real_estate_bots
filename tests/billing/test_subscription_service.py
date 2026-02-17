"""
Tests for billing subscription service.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch

from billing.subscription_service import SubscriptionService
from billing.stripe_client import StripeClient
from billing import PlanTier, SubscriptionStatus
from database.billing_models import AgencyModel, SubscriptionModel


@pytest.fixture
def mock_stripe_client():
    """Create a mock Stripe client."""
    client = Mock(spec=StripeClient)
    client.create_customer = AsyncMock()
    client.create_subscription = AsyncMock()
    client.update_subscription = AsyncMock()
    client.cancel_subscription = AsyncMock()
    client.get_subscription = AsyncMock()
    client.attach_payment_method = AsyncMock()
    return client


@pytest.fixture
def subscription_service(mock_stripe_client):
    """Create subscription service."""
    return SubscriptionService(stripe_client=mock_stripe_client)


@pytest.fixture
def mock_stripe():
    """Context manager to mock stripe client in subscription service."""
    from unittest.mock import patch, AsyncMock
    mock_client = AsyncMock()
    with patch("billing.subscription_service.get_stripe_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def sample_agency(db_session):
    """Create sample agency in database."""
    agency = AgencyModel(
        id="agency-test-001",
        name="Test Agency",
        slug="test-agency",
        email="test@example.com",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(agency)
    return agency


class TestCreateSubscription:
    """Tests for subscription creation."""
    
    async def test_create_subscription_success(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test successful subscription creation."""
        await db_session.commit()
        
        # Mock Stripe responses
        mock_stripe_client.create_customer.return_value = {
            "id": "cus_test_123",
            "email": sample_agency.email,
        }
        mock_stripe_client.attach_payment_method.return_value = {"id": "pm_123"}
        mock_stripe_client.create_subscription.return_value = {
            "id": "sub_stripe_123",
            "status": "active",
            "current_period_start": int(datetime.now(timezone.utc).timestamp()),
            "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
        }
        
        result = await subscription_service.create_subscription(
            agency_id=sample_agency.id,
            price_id="price_starter_123",
            payment_method_id="pm_123",
        )
        
        assert result["success"] is True
        assert result["subscription_id"] == "sub_stripe_123"
        assert result["status"] == "active"
        
        # Verify Stripe calls
        mock_stripe_client.create_customer.assert_called_once()
        mock_stripe_client.create_subscription.assert_called_once()
    
    async def test_create_subscription_stripe_error(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test handling of Stripe errors."""
        await db_session.commit()
        
        mock_stripe_client.create_customer.side_effect = Exception("Invalid API key")
        
        with pytest.raises(Exception, match="Invalid API key"):
            await subscription_service.create_subscription(
                agency_id=sample_agency.id,
                price_id="price_starter_123",
                payment_method_id="pm_123",
            )
    
    async def test_create_subscription_with_trial(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test subscription creation with trial period."""
        await db_session.commit()
        
        mock_stripe_client.create_customer.return_value = {"id": "cus_123"}
        mock_stripe_client.create_subscription.return_value = {
            "id": "sub_123",
            "status": "trialing",
            "trial_start": int(datetime.now(timezone.utc).timestamp()),
            "trial_end": int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp()),
        }
        
        result = await subscription_service.create_subscription(
            agency_id=sample_agency.id,
            price_id="price_starter_123",
            payment_method_id="pm_123",
            trial_days=14,
        )
        
        assert result["status"] == "trialing"
        assert "trial_end" in result


class TestUpgradeSubscription:
    """Tests for subscription upgrades."""
    
    async def test_upgrade_subscription_success(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test successful plan upgrade."""
        # Create existing subscription
        sub = SubscriptionModel(
            id="sub-001",
            agency_id=sample_agency.id,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_stripe_123",
            stripe_price_id="price_starter",
            plan_tier="starter",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        mock_stripe_client.update_subscription.return_value = {
            "id": "sub_stripe_123",
            "status": "active",
            "proration_amount": 2500,  # $25 proration
        }
        
        result = await subscription_service.upgrade_subscription(
            agency_id=sample_agency.id,
            new_price_id="price_professional",
        )
        
        assert result["success"] is True
        assert result["proration_amount"] == 2500
        
        mock_stripe_client.update_subscription.assert_called_once_with(
            "sub_stripe_123",
            {"items": [{"id": "item_123", "price": "price_professional"}]},
        )
    
    async def test_upgrade_no_active_subscription(
        self, subscription_service, sample_agency, db_session
    ):
        """Test upgrade when no active subscription exists."""
        await db_session.commit()
        
        with pytest.raises(ValueError, match="No active subscription found"):
            await subscription_service.upgrade_subscription(
                agency_id=sample_agency.id,
                new_price_id="price_professional",
            )


class TestCancelSubscription:
    """Tests for subscription cancellation."""
    
    async def test_cancel_at_period_end(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test cancellation at period end."""
        sub = SubscriptionModel(
            id="sub-001",
            agency_id=sample_agency.id,
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_stripe_123",
            plan_tier="starter",
            status="active",
            cancel_at_period_end=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        mock_stripe_client.cancel_subscription.return_value = {
            "id": "sub_stripe_123",
            "cancel_at_period_end": True,
        }
        
        result = await subscription_service.cancel_subscription(
            agency_id=sample_agency.id,
            at_period_end=True,
        )
        
        assert result["success"] is True
        assert result["cancel_at_period_end"] is True
        
        mock_stripe_client.cancel_subscription.assert_called_once_with(
            "sub_stripe_123",
            at_period_end=True,
        )
    
    async def test_cancel_immediately(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test immediate cancellation."""
        sub = SubscriptionModel(
            id="sub-001",
            agency_id=sample_agency.id,
            stripe_subscription_id="sub_stripe_123",
            plan_tier="starter",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        mock_stripe_client.cancel_subscription.return_value = {
            "id": "sub_stripe_123",
            "status": "canceled",
        }
        
        result = await subscription_service.cancel_subscription(
            agency_id=sample_agency.id,
            at_period_end=False,
        )
        
        assert result["success"] is True
        assert result["status"] == "canceled"


class TestGetSubscriptionStatus:
    """Tests for getting subscription status."""
    
    async def test_get_active_subscription_status(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test getting status of active subscription."""
        sub = SubscriptionModel(
            id="sub-001",
            agency_id=sample_agency.id,
            stripe_subscription_id="sub_stripe_123",
            plan_tier="starter",
            status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=15),
            lead_quota=100,
            leads_used_this_period=25,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        mock_stripe_client.get_subscription.return_value = {
            "id": "sub_stripe_123",
            "status": "active",
            "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=15)).timestamp()),
        }
        
        result = await subscription_service.get_subscription_status(sample_agency.id)
        
        assert result["status"] == "active"
        assert result["is_active"] is True
        assert result["plan_tier"] == "starter"
        assert result["quota"]["used"] == 25
        assert result["quota"]["total"] == 100
        assert result["quota"]["remaining"] == 75
    
    async def test_get_subscription_status_no_subscription(
        self, subscription_service, sample_agency, db_session
    ):
        """Test getting status when no subscription exists."""
        await db_session.commit()
        
        result = await subscription_service.get_subscription_status(sample_agency.id)
        
        assert result["status"] == "none"
        assert result["is_active"] is False
        assert result["plan_tier"] is None


class TestPaymentMethodManagement:
    """Tests for payment method operations."""
    
    async def test_add_payment_method(
        self, subscription_service, mock_stripe_client, sample_agency, db_session
    ):
        """Test adding payment method."""
        sub = SubscriptionModel(
            id="sub-001",
            agency_id=sample_agency.id,
            stripe_customer_id="cus_123",
            plan_tier="starter",
            status="active",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(sub)
        await db_session.commit()
        
        mock_stripe_client.attach_payment_method.return_value = {
            "id": "pm_new_123",
            "customer": "cus_123",
        }
        
        result = await subscription_service.add_payment_method(
            agency_id=sample_agency.id,
            payment_method_id="pm_new_123",
        )
        
        assert result["success"] is True
        assert result["payment_method_id"] == "pm_new_123"
