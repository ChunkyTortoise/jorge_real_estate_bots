"""
Tests for billing API endpoints.
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from httpx import AsyncClient, ASGITransport
from bots.lead_bot.main import app


@pytest.fixture
async def client():
    """Create test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers():
    """Mock auth headers."""
    return {"Authorization": "Bearer test-token"}


class TestBillingPlans:
    """Tests for billing plans endpoint."""
    
    async def test_get_plans_returns_all_tiers(self, client):
        """Test GET /api/billing/plans returns all plan tiers."""
        response = await client.get("/api/billing/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        # Response has 'plans' key containing list of plans
        plans = data.get("plans", [])
        tiers = [p["tier"] for p in plans]
        assert "starter" in tiers
        assert "professional" in tiers
        assert "enterprise" in tiers
    
    async def test_plan_structure(self, client):
        """Test plan objects have required fields."""
        response = await client.get("/api/billing/plans")
        
        assert response.status_code == 200
        data = response.json()
        
        plans = data.get("plans", [])
        for plan in plans:
            assert "tier" in plan
            assert "name" in plan
            assert "description" in plan
            assert "price_monthly_cents" in plan
            assert "price_annual_cents" in plan
            assert "lead_quota" in plan
            assert "features" in plan


class TestSubscription:
    """Tests for subscription endpoints."""
    
    async def test_get_subscription_requires_auth(self, client):
        """Test subscription endpoint requires authentication."""
        response = await client.get("/api/billing/subscription")
        
        assert response.status_code == 401
    
    async def test_get_subscription_success(self, client, auth_headers, db_session):
        """Test getting subscription details."""
        # Create agency and subscription
        from database.billing_models import AgencyModel, SubscriptionModel
        
        agency = AgencyModel(
            id="api-test-agency",
            name="API Test Agency",
            slug="api-test",
            email="api@test.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        sub = SubscriptionModel(
            id="api-test-sub",
            agency_id=agency.id,
            plan_tier="starter",
            status="active",
            lead_quota=100,
            leads_used_this_period=25,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=15),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add_all([agency, sub])
        await db_session.commit()
        
        with patch("api.routes.billing.get_current_active_user") as mock_user:
            mock_user.return_value = {"agency_id": agency.id}
            
            response = await client.get("/api/billing/subscription", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "active"
            assert data["plan_tier"] == "starter"


class TestSubscribe:
    """Tests for subscription creation."""
    
    async def test_subscribe_success(self, client, auth_headers):
        """Test successful subscription creation."""
        with patch("api.routes.billing.SubscriptionService") as mock_service:
            mock_instance = Mock()
            mock_instance.create_subscription = Mock(return_value={
                "success": True,
                "subscription_id": "sub_new_123",
            })
            mock_service.return_value = mock_instance
            
            response = await client.post(
                "/api/billing/subscribe",
                json={
                    "price_id": "price_starter_123",
                    "payment_method_id": "pm_123",
                },
                headers=auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["subscription_id"] == "sub_new_123"


class TestUpgrade:
    """Tests for subscription upgrade."""
    
    async def test_upgrade_success(self, client, auth_headers):
        """Test successful plan upgrade."""
        with patch("api.routes.billing.SubscriptionService") as mock_service:
            mock_instance = Mock()
            mock_instance.upgrade_subscription = Mock(return_value={
                "success": True,
                "proration_amount": 2500,
            })
            mock_service.return_value = mock_instance
            
            response = await client.post(
                "/api/billing/upgrade",
                json={"price_id": "price_professional_123"},
                headers=auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["proration_amount"] == 2500


class TestCancel:
    """Tests for subscription cancellation."""
    
    async def test_cancel_at_period_end(self, client, auth_headers):
        """Test cancellation at period end."""
        with patch("api.routes.billing.SubscriptionService") as mock_service:
            mock_instance = Mock()
            mock_instance.cancel_subscription = Mock(return_value={
                "success": True,
                "cancel_at_period_end": True,
                "effective_date": (datetime.now(timezone.utc) + timedelta(days=15)).isoformat(),
            })
            mock_service.return_value = mock_instance
            
            response = await client.post(
                "/api/billing/cancel",
                json={"at_period_end": True},
                headers=auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["cancel_at_period_end"] is True


class TestUsage:
    """Tests for usage endpoints."""
    
    async def test_get_usage(self, client, auth_headers, db_session):
        """Test getting usage summary."""
        from database.billing_models import AgencyModel, UsageRecordModel
        
        agency = AgencyModel(
            id="usage-test-agency",
            name="Usage Test Agency",
            slug="usage-test",
            email="usage@test.com",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        # Create usage records
        for i in range(5):
            record = UsageRecordModel(
                id=f"usage-{i}",
                agency_id=agency.id,
                resource_type="lead",
                quantity=1,
                timestamp=datetime.now(timezone.utc),
            )
            db_session.add(record)
        
        await db_session.commit()
        
        with patch("api.routes.billing.get_current_active_user") as mock_user:
            mock_user.return_value = {"agency_id": agency.id}
            
            response = await client.get("/api/billing/usage", headers=auth_headers)
            
            assert response.status_code == 200
            data = response.json()
            assert "usage" in data
            assert "period" in data


class TestWebhook:
    """Tests for Stripe webhook endpoint."""
    
    async def test_webhook_invoice_paid(self, client):
        """Test processing invoice.paid webhook."""
        payload = {
            "id": "evt_123",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_123",
                    "subscription": "sub_123",
                    "customer": "cus_123",
                    "amount_paid": 2900,
                }
            }
        }
        
        with patch("billing.webhook_handler.process_webhook_event") as mock_process:
            mock_process.return_value = True
            
            response = await client.post(
                "/billing/webhook",
                json=payload,
                headers={"Stripe-Signature": "test_sig"},
            )
            
            assert response.status_code == 200
            assert response.json()["processed"] is True
    
    async def test_webhook_subscription_updated(self, client):
        """Test processing customer.subscription.updated webhook."""
        payload = {
            "id": "evt_456",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_123",
                    "status": "active",
                    "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp()),
                }
            }
        }
        
        with patch("billing.webhook_handler.process_webhook_event") as mock_process:
            mock_process.return_value = True
            
            response = await client.post(
                "/billing/webhook",
                json=payload,
                headers={"Stripe-Signature": "test_sig"},
            )
            
            assert response.status_code == 200
    
    async def test_webhook_invalid_signature(self, client):
        """Test webhook with invalid signature."""
        payload = {
            "id": "evt_123",
            "type": "invoice.payment_succeeded",
            "data": {"object": {"id": "in_123"}}
        }
        
        response = await client.post(
            "/billing/webhook",
            json=payload,
            headers={"Stripe-Signature": "invalid_sig"},
        )
        
        # Should return error for invalid signature
        assert response.status_code in [400, 401]


class TestPaymentMethods:
    """Tests for payment method endpoints."""
    
    async def test_add_payment_method(self, client, auth_headers):
        """Test adding payment method."""
        with patch("api.routes.billing.SubscriptionService") as mock_service:
            mock_instance = Mock()
            mock_instance.add_payment_method = Mock(return_value={
                "success": True,
                "payment_method_id": "pm_new_123",
            })
            mock_service.return_value = mock_instance
            
            response = await client.post(
                "/api/billing/payment-method",
                json={"payment_method_id": "pm_new_123"},
                headers=auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
    
    async def test_remove_payment_method(self, client, auth_headers):
        """Test removing payment method."""
        with patch("api.routes.billing.SubscriptionService") as mock_service:
            mock_instance = Mock()
            mock_instance.remove_payment_method = Mock(return_value={
                "success": True,
            })
            mock_service.return_value = mock_instance
            
            response = await client.delete(
                "/api/billing/payment-method/pm_old_123",
                headers=auth_headers,
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
