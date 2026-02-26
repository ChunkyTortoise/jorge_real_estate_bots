"""
Tests for INCREMENT 3C: GHL client retries on 429/502/503.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from bots.shared.ghl_client import _is_retryable_ghl_error


class TestGHLRetryPredicate:
    """3C: _is_retryable_ghl_error correctly identifies retryable errors."""

    def test_timeout_is_retryable(self):
        exc = httpx.TimeoutException("timeout")
        assert _is_retryable_ghl_error(exc) is True

    def test_network_error_is_retryable(self):
        exc = httpx.NetworkError("network error")
        assert _is_retryable_ghl_error(exc) is True

    def test_429_is_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 429
        exc = httpx.HTTPStatusError("rate limited", request=MagicMock(), response=mock_response)
        assert _is_retryable_ghl_error(exc) is True

    def test_502_is_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 502
        exc = httpx.HTTPStatusError("bad gateway", request=MagicMock(), response=mock_response)
        assert _is_retryable_ghl_error(exc) is True

    def test_503_is_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 503
        exc = httpx.HTTPStatusError("service unavailable", request=MagicMock(), response=mock_response)
        assert _is_retryable_ghl_error(exc) is True

    def test_404_not_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        exc = httpx.HTTPStatusError("not found", request=MagicMock(), response=mock_response)
        assert _is_retryable_ghl_error(exc) is False

    def test_400_not_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 400
        exc = httpx.HTTPStatusError("bad request", request=MagicMock(), response=mock_response)
        assert _is_retryable_ghl_error(exc) is False

    def test_500_not_retryable(self):
        mock_response = MagicMock()
        mock_response.status_code = 500
        exc = httpx.HTTPStatusError("internal error", request=MagicMock(), response=mock_response)
        assert _is_retryable_ghl_error(exc) is False

    def test_generic_exception_not_retryable(self):
        exc = ValueError("some error")
        assert _is_retryable_ghl_error(exc) is False


class TestGHLMakeRequest429Retry:
    """3C: _make_request re-raises 429/502/503 for tenacity to catch."""

    @pytest.mark.asyncio
    async def test_ghl_retries_429(self):
        """_make_request should re-raise 429 errors (tenacity retries)."""
        with patch("bots.shared.ghl_client.settings") as mock_settings:
            mock_settings.ghl_api_key = "test-key"
            mock_settings.ghl_location_id = "test-loc"

            from bots.shared.ghl_client import GHLClient
            client = GHLClient(api_key="test-key", location_id="test-loc")

            call_count = 0
            mock_request_obj = MagicMock()

            async def mock_request(**kwargs):
                nonlocal call_count
                call_count += 1
                if call_count < 3:
                    mock_response = MagicMock()
                    mock_response.status_code = 429
                    mock_response.content = b"rate limited"
                    mock_response.raise_for_status = MagicMock(
                        side_effect=httpx.HTTPStatusError(
                            "rate limited",
                            request=mock_request_obj,
                            response=mock_response,
                        )
                    )
                    mock_response.raise_for_status()
                else:
                    mock_response = MagicMock()
                    mock_response.status_code = 200
                    mock_response.content = b'{"success": true}'
                    mock_response.json = MagicMock(return_value={"success": True})
                    mock_response.raise_for_status = MagicMock()
                    return mock_response

            mock_http_client = AsyncMock()
            mock_http_client.request = mock_request
            client._client = mock_http_client

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await client._make_request("GET", "contacts/test")

            assert call_count == 3
            assert result.get("success") is True
