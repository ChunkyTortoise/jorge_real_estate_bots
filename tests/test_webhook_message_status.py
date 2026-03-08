"""
Tests for /api/ghl/webhook/message-status endpoint hardening.

Verifies: try/except wrapping returns 200 on errors, sig check still returns 401.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.routes_webhook import router


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _make_state(sig_valid: bool = True) -> MagicMock:
    state = MagicMock()
    state.verify_ghl_signature = MagicMock(return_value=sig_valid)
    state._webhook_cache = None
    state._ghl_client = None
    return state


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return _make_app()


class TestMessageStatusEndpoint:
    @pytest.mark.asyncio
    async def test_delivered_event_returns_ok(self, app):
        """Valid message.delivered event → 200 {"status": "ok"}."""
        state = _make_state()
        payload = {"type": "message.delivered", "contactId": "c-001"}

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch(
                "bots.lead_bot.routes_webhook.SmsMetricsCollector"
            ) as mock_collector_cls,
        ):
            mock_collector = AsyncMock()
            mock_collector.record_delivery = AsyncMock()
            mock_collector_cls.return_value = mock_collector

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
        mock_collector.record_delivery.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_failed_event_returns_ok(self, app):
        """Valid message.failed event → 200 {"status": "ok"}."""
        state = _make_state()
        payload = {"type": "message.failed", "contactId": "c-002"}

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.SmsMetricsCollector") as mock_cls,
        ):
            mock_cls.return_value = AsyncMock(record_delivery=AsyncMock())

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    @pytest.mark.asyncio
    async def test_read_event_returns_ok(self, app):
        """Valid message.read event → 200 {"status": "ok"}."""
        state = _make_state()
        payload = {"type": "message.read", "contactId": "c-003"}

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.SmsMetricsCollector") as mock_cls,
        ):
            mock_cls.return_value = AsyncMock(record_delivery=AsyncMock())

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_unknown_event_type_returns_ok_without_crash(self, app):
        """Unknown event type → silently returns 200 (no SmsMetricsCollector call)."""
        state = _make_state()
        payload = {"type": "message.bounced", "contactId": "c-004"}

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.SmsMetricsCollector") as mock_cls,
        ):
            mock_cls.return_value = AsyncMock(record_delivery=AsyncMock())

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        mock_cls.return_value.record_delivery.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_contact_id_returns_ok_without_crash(self, app):
        """Missing contactId → returns 200 (no record_delivery call)."""
        state = _make_state()
        payload = {"type": "message.delivered"}  # no contactId

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.SmsMetricsCollector") as mock_cls,
        ):
            mock_cls.return_value = AsyncMock(record_delivery=AsyncMock())

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        mock_cls.return_value.record_delivery.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_malformed_json_returns_ok_not_500(self, app):
        """Malformed JSON body → returns 200 (no unhandled 500 that would trigger GHL retries)."""
        state = _make_state()

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=b"not-valid-json{{{",
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self, app):
        """Invalid signature → 401 (signature check is NOT swallowed by try/except)."""
        state = _make_state(sig_valid=False)
        payload = {"type": "message.delivered", "contactId": "c-sig"}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "x-wh-signature": "bad"},
                )

        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_collector_error_returns_ok_not_500(self, app):
        """SmsMetricsCollector raising an exception → still returns 200."""
        state = _make_state()
        payload = {"type": "message.delivered", "contactId": "c-err"}

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.SmsMetricsCollector") as mock_cls,
        ):
            mock_cls.return_value = AsyncMock(
                record_delivery=AsyncMock(side_effect=RuntimeError("Redis down"))
            )

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
