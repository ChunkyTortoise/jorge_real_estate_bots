"""
Tests for opt-out detection via the unified webhook HTTP endpoint.

Verifies: TCPA word-boundary matching, GHL tag application, opted-out contact blocking.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.routes_webhook import router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockCache:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    async def get(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ttl: int = 0, **kwargs: Any) -> None:
        # Accept redis.asyncio-style ex= kwarg silently (StallReengagementService uses ex=)
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def setnx(self, key: str, value: Any, ttl: int = 300) -> bool:
        if key in self._store:
            return False
        self._store[key] = value
        return True

    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None) -> int:
        current = self._store.get(key, 0)
        new_value = int(current) + amount
        self._store[key] = new_value
        return new_value


def _make_state(cache: Optional[MockCache] = None) -> MagicMock:
    mock_ghl = AsyncMock()
    mock_ghl.add_tag = AsyncMock(return_value={"success": True})
    mock_ghl.get_contact = AsyncMock(return_value={"customFields": [], "tags": []})

    state = MagicMock()
    state.verify_ghl_signature = MagicMock(return_value=True)
    state._webhook_cache = cache if cache is not None else MockCache()
    state._ghl_client = mock_ghl
    state.seller_bot_instance = None
    state.buyer_bot_instance = None
    state.lead_analyzer = AsyncMock()
    state.performance_stats = {"total_requests": 0, "cache_hits": 0}
    return state


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _payload(contact_id: str, body: str) -> bytes:
    return json.dumps(
        {"contactId": contact_id, "locationId": "loc-test", "body": body}
    ).encode()


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return _make_app()


@pytest.fixture(autouse=True)
def instant_sleep():
    """Make asyncio.sleep a no-op to avoid slowing tests."""
    with patch("bots.lead_bot.routes_webhook.asyncio.sleep", new=AsyncMock()):
        yield


# ---------------------------------------------------------------------------
# Opt-out via HTTP webhook
# ---------------------------------------------------------------------------


class TestOptOutHTTPFlow:
    @pytest.mark.asyncio
    async def test_stop_keyword_returns_opted_out(self, app):
        """Message 'STOP' → {"status": "opted_out"}."""
        cache = MockCache()
        state = _make_state(cache)

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_payload("opt-001", "STOP"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["status"] == "opted_out"
        # Opted-out key should be stored in cache
        opt_key = "stall_optout:opt-001"
        assert await cache.get(opt_key) == "1"

    @pytest.mark.asyncio
    async def test_stop_please_word_boundary_returns_opted_out(self, app):
        """Message 'stop please' triggers opt-out via word-boundary match."""
        cache = MockCache()
        state = _make_state(cache)

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_payload("opt-002", "stop please"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["status"] == "opted_out"

    @pytest.mark.asyncio
    async def test_opted_out_contact_future_message_is_skipped(self, app):
        """Contact that previously opted out → subsequent messages return skipped/opted_out."""
        cache = MockCache()
        state = _make_state(cache)

        # Seed the opt-out in cache (simulates a previously recorded opt-out)
        await cache.set("stall_optout:opt-003", "1")

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_payload("opt-003", "Hey are you still there?"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("skipped", "opted_out")
        if data["status"] == "skipped":
            assert data.get("reason") == "opted_out"

    @pytest.mark.asyncio
    async def test_unrelated_message_does_not_trigger_opt_out(self, app):
        """'stopping by later this week' should NOT trigger opt-out (no standalone stop word at start)."""
        cache = MockCache()
        state = _make_state(cache)

        mock_lead = AsyncMock()
        mock_lead.analyze_lead = AsyncMock(
            return_value=(
                {"score": 40, "temperature": "warm", "jorge_priority": "normal"},
                MagicMock(five_minute_rule_compliant=True),
            )
        )
        state.lead_analyzer = mock_lead

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_payload("opt-004", "I am stopping by later this week"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        # Should NOT be opted_out — "stopping" is not an exact opt-out word
        assert r.json()["status"] != "opted_out"
        opt_key = "stall_optout:opt-004"
        assert await cache.get(opt_key) is None

    @pytest.mark.asyncio
    async def test_opted_out_contact_gets_ghl_tag(self, app):
        """When opt-out is recorded, GHL add_tag is called with 'opted-out-sms'."""
        cache = MockCache()
        state = _make_state(cache)

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                await c.post(
                    "/api/ghl/webhook",
                    content=_payload("opt-005", "STOP"),
                    headers={"Content-Type": "application/json"},
                )

        state._ghl_client.add_tag.assert_awaited()
        calls = [str(c) for c in state._ghl_client.add_tag.await_args_list]
        assert any("opted-out-sms" in call for call in calls)
