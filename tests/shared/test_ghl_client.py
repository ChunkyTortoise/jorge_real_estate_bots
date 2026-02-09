"""
Comprehensive test suite for GHL Client.

Tests all GHL API methods with mocked responses:
- Contact management
- Opportunity management
- Messaging and conversations
- Workflows and automation
- Calendar appointments
- Custom fields and tags
- Batch operations
- Health monitoring
- Error handling and retries
"""
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from bots.shared.ghl_client import GHLClient, create_ghl_client, get_ghl_client

# ========== FIXTURES ==========

@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("bots.shared.ghl_client.settings") as mock_settings:
        mock_settings.ghl_api_key = "test_api_key_123"
        mock_settings.ghl_location_id = "test_location_456"
        yield mock_settings


@pytest.fixture
def ghl_client(mock_settings):
    """Create GHL client with mocked settings."""
    return GHLClient()


@pytest.fixture
def mock_httpx_client():
    """Mock httpx.AsyncClient for testing."""
    mock_client = AsyncMock()
    return mock_client


# ========== INITIALIZATION TESTS ==========

def test_ghl_client_init_with_env_vars(mock_settings):
    """Test client initialization with environment variables."""
    client = GHLClient()
    assert client.api_key == "test_api_key_123"
    assert client.location_id == "test_location_456"
    assert client.BASE_URL == "https://services.leadconnectorhq.com"
    assert "Authorization" in client.headers
    assert client.headers["Authorization"] == "Bearer test_api_key_123"


def test_ghl_client_init_with_params():
    """Test client initialization with explicit parameters."""
    client = GHLClient(api_key="custom_key", location_id="custom_location")
    assert client.api_key == "custom_key"
    assert client.location_id == "custom_location"


def test_ghl_client_init_missing_api_key():
    """Test client initialization fails without API key."""
    with patch("bots.shared.ghl_client.settings") as mock_settings:
        mock_settings.ghl_api_key = None
        mock_settings.ghl_location_id = "test_location"
        with pytest.raises(ValueError, match="GHL_API_KEY is required"):
            GHLClient()


def test_ghl_client_init_missing_location_id():
    """Test client initialization fails without location ID."""
    with patch("bots.shared.ghl_client.settings") as mock_settings:
        mock_settings.ghl_api_key = "test_key"
        mock_settings.ghl_location_id = None
        with pytest.raises(ValueError, match="GHL_LOCATION_ID is required"):
            GHLClient()


# ========== ASYNC CONTEXT MANAGER TESTS ==========

@pytest.mark.asyncio
async def test_async_context_manager(ghl_client):
    """Test async context manager functionality."""
    async with ghl_client as client:
        assert client._client is not None
        assert isinstance(client._client, httpx.AsyncClient)


# ========== CONTACT MANAGEMENT TESTS ==========

@pytest.mark.asyncio
async def test_get_contact_success(ghl_client, mock_httpx_client):
    """Test successful contact retrieval."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "contact_123", "name": "John Doe"}'
    mock_response.json.return_value = {"id": "contact_123", "name": "John Doe"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.get_contact("contact_123")

    assert result["success"] is True
    assert result["data"]["id"] == "contact_123"
    assert result["status_code"] == 200


@pytest.mark.asyncio
async def test_create_contact_success(ghl_client, mock_httpx_client):
    """Test successful contact creation."""
    contact_data = {
        "firstName": "Jane",
        "lastName": "Smith",
        "email": "jane@example.com"
    }

    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "new_contact_123"}'
    mock_response.json.return_value = {"id": "new_contact_123"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.create_contact(contact_data)

    assert result["success"] is True
    assert "locationId" in contact_data  # Should be added automatically
    assert result["data"]["id"] == "new_contact_123"


@pytest.mark.asyncio
async def test_update_contact_success(ghl_client, mock_httpx_client):
    """Test successful contact update."""
    updates = {"firstName": "John Updated"}

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "contact_123", "firstName": "John Updated"}'
    mock_response.json.return_value = {"id": "contact_123", "firstName": "John Updated"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.update_contact("contact_123", updates)

    assert result["success"] is True
    assert result["data"]["firstName"] == "John Updated"


# ========== TAG MANAGEMENT TESTS ==========

@pytest.mark.asyncio
async def test_add_tag_success(ghl_client, mock_httpx_client):
    """Test successful tag addition."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.add_tag("contact_123", "Hot Lead")

    assert result is True


@pytest.mark.asyncio
async def test_remove_tag_success(ghl_client, mock_httpx_client):
    """Test successful tag removal."""
    mock_response = Mock()
    mock_response.status_code = 204
    mock_response.content = b''
    mock_response.json.return_value = {}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.remove_tag("contact_123", "Cold Lead")

    assert result is True


# ========== CUSTOM FIELD TESTS ==========

@pytest.mark.asyncio
async def test_update_custom_field_success(ghl_client, mock_httpx_client):
    """Test successful custom field update."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.update_custom_field(
        "contact_123",
        "ai_lead_score",
        "95"
    )

    assert result is True


# ========== OPPORTUNITY TESTS ==========

@pytest.mark.asyncio
async def test_create_opportunity_success(ghl_client, mock_httpx_client):
    """Test successful opportunity creation."""
    opp_data = {
        "name": "House Purchase",
        "contactId": "contact_123",
        "monetaryValue": 450000
    }

    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "opp_123"}'
    mock_response.json.return_value = {"id": "opp_123"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.create_opportunity(opp_data)

    assert result["success"] is True
    assert "locationId" in opp_data


@pytest.mark.asyncio
async def test_get_opportunity_success(ghl_client, mock_httpx_client):
    """Test successful opportunity retrieval."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"id": "opp_123", "name": "House Purchase"}'
    mock_response.json.return_value = {"id": "opp_123", "name": "House Purchase"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.get_opportunity("opp_123")

    assert result["success"] is True
    assert result["data"]["name"] == "House Purchase"


# ========== MESSAGING TESTS ==========

@pytest.mark.asyncio
async def test_send_message_success(ghl_client, mock_httpx_client):
    """Test successful message sending."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"messageId": "msg_123"}'
    mock_response.json.return_value = {"messageId": "msg_123"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.send_message(
        "contact_123",
        "Hello from Jorge!",
        "SMS"
    )

    assert result["success"] is True
    assert result["data"]["messageId"] == "msg_123"


@pytest.mark.asyncio
async def test_get_conversations_success(ghl_client, mock_httpx_client):
    """Test successful conversation retrieval."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"conversations": [{"id": "conv_1"}, {"id": "conv_2"}]}'
    mock_response.json.return_value = {
        "conversations": [{"id": "conv_1"}, {"id": "conv_2"}]
    }
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.get_conversations("contact_123")

    assert len(result) == 2
    assert result[0]["id"] == "conv_1"


# ========== WORKFLOW TESTS ==========

@pytest.mark.asyncio
async def test_trigger_workflow_success(ghl_client, mock_httpx_client):
    """Test successful workflow triggering."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true, "workflowId": "wf_123"}'
    mock_response.json.return_value = {"success": True, "workflowId": "wf_123"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.trigger_workflow("contact_123", "wf_123")

    assert result["success"] is True
    assert result["data"]["workflowId"] == "wf_123"


# ========== CALENDAR TESTS ==========

@pytest.mark.asyncio
async def test_create_appointment_success(ghl_client, mock_httpx_client):
    """Test successful appointment creation."""
    appt_data = {
        "contactId": "contact_123",
        "calendarId": "cal_123",
        "startTime": "2026-01-25T10:00:00Z"
    }

    mock_response = Mock()
    mock_response.status_code = 201
    mock_response.content = b'{"id": "appt_123"}'
    mock_response.json.return_value = {"id": "appt_123"}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.create_appointment(appt_data)

    assert result["success"] is True
    assert result["data"]["id"] == "appt_123"


# ========== BATCH OPERATIONS TESTS ==========

@pytest.mark.asyncio
async def test_apply_actions_all_success(ghl_client, mock_httpx_client):
    """Test batch actions when all succeed."""
    actions = [
        {"type": "add_tag", "tag": "Hot Lead"},
        {"type": "update_custom_field", "field": "ai_lead_score", "value": "95"},
        {"type": "trigger_workflow", "workflow_id": "wf_123"}
    ]

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.apply_actions("contact_123", actions)

    assert result is True


@pytest.mark.asyncio
async def test_apply_actions_partial_failure(ghl_client, mock_httpx_client):
    """Test batch actions when some fail."""
    actions = [
        {"type": "add_tag", "tag": "Hot Lead"},
        {"type": "unknown_action", "data": "test"}  # This will fail
    ]

    # First action succeeds
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.content = b'{"success": true}'
    mock_response_success.json.return_value = {"success": True}
    mock_response_success.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response_success
    ghl_client._client = mock_httpx_client

    result = await ghl_client.apply_actions("contact_123", actions)

    # Should return False because one action failed
    assert result is False


# ========== JORGE-SPECIFIC TESTS ==========

@pytest.mark.asyncio
async def test_update_lead_score_success(ghl_client, mock_httpx_client):
    """Test updating lead score and temperature."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.update_lead_score("contact_123", 95, "hot")

    assert result["success"] is True


@pytest.mark.asyncio
async def test_update_budget_and_timeline_success(ghl_client, mock_httpx_client):
    """Test updating budget and timeline."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.update_budget_and_timeline(
        "contact_123",
        budget_min=200000,
        budget_max=500000,
        timeline="ASAP"
    )

    assert result["success"] is True


@pytest.mark.asyncio
async def test_send_immediate_followup_hot_lead(ghl_client, mock_httpx_client):
    """Test sending immediate follow-up for hot lead."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.send_immediate_followup("contact_123", "hot")

    assert result["success"] is True


# ========== ERROR HANDLING TESTS ==========

@pytest.mark.asyncio
async def test_http_error_handling(ghl_client, mock_httpx_client):
    """Test handling of HTTP errors."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.content = b'{"error": "Contact not found"}'
    mock_response.json.return_value = {"error": "Contact not found"}

    error = httpx.HTTPStatusError(
        "Not Found",
        request=Mock(),
        response=mock_response
    )
    mock_httpx_client.request.side_effect = error
    ghl_client._client = mock_httpx_client

    result = await ghl_client.get_contact("nonexistent_123")

    assert result["success"] is False
    assert result["status_code"] == 404


@pytest.mark.asyncio
async def test_network_error_with_retry(ghl_client, mock_httpx_client):
    """Test retry logic for network errors."""
    # First two attempts fail, third succeeds
    mock_response_success = Mock()
    mock_response_success.status_code = 200
    mock_response_success.content = b'{"id": "contact_123"}'
    mock_response_success.json.return_value = {"id": "contact_123"}
    mock_response_success.raise_for_status = Mock()

    mock_httpx_client.request.side_effect = [
        httpx.NetworkError("Network error"),
        httpx.NetworkError("Network error"),
        mock_response_success
    ]
    ghl_client._client = mock_httpx_client

    result = await ghl_client.get_contact("contact_123")

    assert result["success"] is True
    assert mock_httpx_client.request.call_count == 3


# ========== HEALTH CHECK TESTS ==========

@pytest.mark.asyncio
async def test_health_check_success(ghl_client, mock_httpx_client):
    """Test successful health check."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b'{"contacts": []}'
    mock_response.json.return_value = {"contacts": []}
    mock_response.raise_for_status = Mock()

    mock_httpx_client.request.return_value = mock_response
    ghl_client._client = mock_httpx_client

    result = await ghl_client.health_check()

    assert result["healthy"] is True
    assert result["api_key_valid"] is True
    assert "checked_at" in result


@pytest.mark.asyncio
async def test_health_check_failure(ghl_client, mock_httpx_client):
    """Test health check failure."""
    # _make_request catches exceptions and returns error dict
    mock_response = Mock()
    mock_response.status_code = 500
    mock_response.content = b'{"error": "Server error"}'
    mock_response.json.return_value = {"error": "Server error"}

    error = httpx.HTTPStatusError(
        "Internal Server Error",
        request=Mock(),
        response=mock_response
    )
    mock_httpx_client.request.side_effect = error
    ghl_client._client = mock_httpx_client

    result = await ghl_client.health_check()

    assert result["healthy"] is False
    assert result["api_key_valid"] is False
    assert "checked_at" in result


def test_check_health_sync_success(ghl_client):
    """Test synchronous health check success."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client_class.return_value = mock_client

        result = ghl_client.check_health_sync()

        assert result["healthy"] is True
        assert result["status_code"] == 200


# ========== FACTORY FUNCTION TESTS ==========

def test_get_ghl_client(mock_settings):
    """Test factory function."""
    client = get_ghl_client()
    assert isinstance(client, GHLClient)
    assert client.api_key == "test_api_key_123"


def test_create_ghl_client_with_custom_key():
    """Test factory function with custom key."""
    client = create_ghl_client(api_key="custom_key_789")
    assert client.api_key == "custom_key_789"


# ========== CLEANUP TESTS ==========

@pytest.mark.asyncio
async def test_client_close(ghl_client):
    """Test client cleanup."""
    ghl_client._client = AsyncMock()
    await ghl_client.close()
    assert ghl_client._client is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=bots.shared.ghl_client", "--cov-report=term-missing"])
