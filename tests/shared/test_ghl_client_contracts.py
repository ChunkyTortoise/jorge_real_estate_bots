"""
Contract tests for GHL Client API endpoints.

Validates that each GHLClient method calls the correct HTTP method and endpoint,
sends required headers, and respects retry logic (retries on 429/502/503, not on 400/404).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from bots.shared.ghl_client import GHLClient


# ========== FIXTURES ==========


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch("bots.shared.ghl_client.settings") as ms:
        ms.ghl_api_key = "test_api_key_123"
        ms.ghl_location_id = "test_location_456"
        yield ms


@pytest.fixture
def ghl_client(mock_settings):
    """Create GHL client with mocked settings."""
    return GHLClient()


@pytest.fixture
def mock_response_ok():
    """Create a successful httpx Response."""
    resp = httpx.Response(
        status_code=200,
        json={"id": "appt_001"},
        request=httpx.Request("GET", "https://example.com"),
    )
    return resp


# ========== APPOINTMENT ENDPOINT CONTRACTS ==========


@pytest.mark.asyncio
async def test_create_appointment_calls_correct_endpoint(ghl_client, mock_response_ok):
    """create_appointment should POST to calendars/events/appointments."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.create_appointment({"calendarId": "cal_1", "contactId": "c_1"})

    mock_http.request.assert_called_once()
    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "POST"
    assert call_kwargs.kwargs["url"].endswith("calendars/events/appointments")


@pytest.mark.asyncio
async def test_get_appointment_calls_correct_endpoint(ghl_client, mock_response_ok):
    """get_appointment should GET calendars/events/appointments/{id}."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.get_appointment("appt_001")

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "GET"
    assert call_kwargs.kwargs["url"].endswith("calendars/events/appointments/appt_001")


@pytest.mark.asyncio
async def test_update_appointment_calls_correct_endpoint(ghl_client, mock_response_ok):
    """update_appointment should PUT calendars/events/appointments/{id}."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.update_appointment("appt_001", {"startTime": "2026-04-01T10:00:00"})

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "PUT"
    assert call_kwargs.kwargs["url"].endswith("calendars/events/appointments/appt_001")


@pytest.mark.asyncio
async def test_delete_appointment_calls_correct_endpoint(ghl_client, mock_response_ok):
    """delete_appointment should DELETE calendars/events/appointments/{id}."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.delete_appointment("appt_001")

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "DELETE"
    assert call_kwargs.kwargs["url"].endswith("calendars/events/appointments/appt_001")


# ========== HEADER CONTRACTS ==========


@pytest.mark.asyncio
async def test_request_includes_authorization_header(ghl_client, mock_response_ok):
    """Every request must include Authorization: Bearer {token}."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.get_appointment("appt_001")

    call_kwargs = mock_http.request.call_args
    headers = call_kwargs.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test_api_key_123"


@pytest.mark.asyncio
async def test_request_includes_version_header(ghl_client, mock_response_ok):
    """Every request must include Version: 2021-07-28."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.get_appointment("appt_001")

    call_kwargs = mock_http.request.call_args
    headers = call_kwargs.kwargs["headers"]
    assert headers["Version"] == "2021-07-28"


@pytest.mark.asyncio
async def test_request_includes_content_type_json(ghl_client, mock_response_ok):
    """Every request must include Content-Type: application/json."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.create_appointment({"calendarId": "cal_1"})

    call_kwargs = mock_http.request.call_args
    headers = call_kwargs.kwargs["headers"]
    assert headers["Content-Type"] == "application/json"


# ========== RETRY LOGIC CONTRACTS ==========


@pytest.mark.asyncio
async def test_create_appointment_retries_on_429(ghl_client):
    """create_appointment should retry on 429 rate limit."""
    error_response = httpx.Response(
        status_code=429,
        json={"error": "rate limited"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )
    ok_response = httpx.Response(
        status_code=200,
        json={"id": "appt_001"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )

    call_count = 0

    async def _side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = error_response
            resp.raise_for_status()  # This will raise HTTPStatusError
        return ok_response

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=_side_effect)
    ghl_client._client = mock_http

    # The first call raises, tenacity retries, second call succeeds
    result = await ghl_client.create_appointment({"calendarId": "cal_1"})
    assert result["success"] is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_create_appointment_retries_on_502(ghl_client):
    """create_appointment should retry on 502 Bad Gateway."""
    error_response = httpx.Response(
        status_code=502,
        json={"error": "bad gateway"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )
    ok_response = httpx.Response(
        status_code=200,
        json={"id": "appt_001"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )

    call_count = 0

    async def _side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = error_response
            resp.raise_for_status()
        return ok_response

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=_side_effect)
    ghl_client._client = mock_http

    result = await ghl_client.create_appointment({"calendarId": "cal_1"})
    assert result["success"] is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_create_appointment_retries_on_503(ghl_client):
    """create_appointment should retry on 503 Service Unavailable."""
    error_response = httpx.Response(
        status_code=503,
        json={"error": "service unavailable"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )
    ok_response = httpx.Response(
        status_code=200,
        json={"id": "appt_001"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )

    call_count = 0

    async def _side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = error_response
            resp.raise_for_status()
        return ok_response

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(side_effect=_side_effect)
    ghl_client._client = mock_http

    result = await ghl_client.create_appointment({"calendarId": "cal_1"})
    assert result["success"] is True
    assert call_count == 2


@pytest.mark.asyncio
async def test_create_appointment_does_not_retry_on_400(ghl_client):
    """create_appointment should NOT retry on 400 Bad Request."""
    error_response = httpx.Response(
        status_code=400,
        json={"error": "bad request"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=error_response)
    ghl_client._client = mock_http

    result = await ghl_client.create_appointment({"calendarId": "cal_1"})
    # 400 returns error dict, does NOT raise/retry
    assert result["success"] is False
    assert result["status_code"] == 400
    # Only called once — no retry
    assert mock_http.request.call_count == 1


@pytest.mark.asyncio
async def test_create_appointment_does_not_retry_on_404(ghl_client):
    """create_appointment should NOT retry on 404 Not Found."""
    error_response = httpx.Response(
        status_code=404,
        json={"error": "not found"},
        request=httpx.Request("POST", "https://services.leadconnectorhq.com/calendars/events/appointments"),
    )

    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=error_response)
    ghl_client._client = mock_http

    result = await ghl_client.create_appointment({"calendarId": "cal_1"})
    assert result["success"] is False
    assert result["status_code"] == 404
    assert mock_http.request.call_count == 1


# ========== SEND MESSAGE CONTRACT ==========


@pytest.mark.asyncio
async def test_send_message_calls_conversations_messages_endpoint(ghl_client, mock_response_ok):
    """send_message should POST to conversations/messages."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    with patch("bots.shared.ghl_client.event_broker"):
        await ghl_client.send_message("contact_1", "Hello!", "SMS")

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "POST"
    assert call_kwargs.kwargs["url"].endswith("conversations/messages")


@pytest.mark.asyncio
async def test_send_message_passes_correct_payload(ghl_client, mock_response_ok):
    """send_message should include contactId, message, and type in payload."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    with patch("bots.shared.ghl_client.event_broker"):
        await ghl_client.send_message("contact_1", "Hello!", "SMS")

    call_kwargs = mock_http.request.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["contactId"] == "contact_1"
    assert payload["message"] == "Hello!"
    assert payload["type"] == "SMS"


# ========== TAG MANAGEMENT CONTRACTS ==========


@pytest.mark.asyncio
async def test_add_tag_calls_correct_endpoint(ghl_client, mock_response_ok):
    """add_tag should POST to contacts/{id}/tags."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    with patch("bots.shared.ghl_client.event_broker"):
        await ghl_client.add_tag("contact_1", "Hot Lead")

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "POST"
    assert call_kwargs.kwargs["url"].endswith("contacts/contact_1/tags")
    assert call_kwargs.kwargs["json"] == {"tags": ["Hot Lead"]}


@pytest.mark.asyncio
async def test_remove_tag_calls_correct_endpoint(ghl_client, mock_response_ok):
    """remove_tag should DELETE contacts/{id}/tags."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.remove_tag("contact_1", "Cold Lead")

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "DELETE"
    assert call_kwargs.kwargs["url"].endswith("contacts/contact_1/tags")
    assert call_kwargs.kwargs["json"] == {"tags": ["Cold Lead"]}


# ========== ADDITIONAL CONTRACT TESTS ==========


@pytest.mark.asyncio
async def test_get_contact_calls_correct_endpoint(ghl_client, mock_response_ok):
    """get_contact should GET contacts/{id}."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.get_contact("contact_1")

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "GET"
    assert call_kwargs.kwargs["url"].endswith("contacts/contact_1")


@pytest.mark.asyncio
async def test_create_contact_includes_location_id(ghl_client, mock_response_ok):
    """create_contact should inject locationId."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    await ghl_client.create_contact({"name": "Test User"})

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["json"]["locationId"] == "test_location_456"


@pytest.mark.asyncio
async def test_update_contact_calls_put(ghl_client, mock_response_ok):
    """update_contact should PUT contacts/{id}."""
    mock_http = AsyncMock()
    mock_http.request = AsyncMock(return_value=mock_response_ok)
    ghl_client._client = mock_http

    with patch("bots.shared.ghl_client.event_broker"):
        await ghl_client.update_contact("contact_1", {"name": "Updated"})

    call_kwargs = mock_http.request.call_args
    assert call_kwargs.kwargs["method"] == "PUT"
    assert call_kwargs.kwargs["url"].endswith("contacts/contact_1")


@pytest.mark.asyncio
async def test_base_url_is_ghl_services(ghl_client):
    """BASE_URL must point to GHL services."""
    assert ghl_client.BASE_URL == "https://services.leadconnectorhq.com"
