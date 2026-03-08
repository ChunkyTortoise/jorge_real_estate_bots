"""
Tests for /ghl/webhook/new-lead endpoint hardening.

Verifies: missing ID → 400, dedup → skipped, internal errors → 200 (not 500), invalid sig → 401.
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

    async def set(self, key: str, value: Any, ttl: int = 0) -> None:
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


def _make_state(cache: Optional[MockCache] = None, sig_valid: bool = True) -> MagicMock:
    mock_lead = AsyncMock()
    mock_lead.analyze_lead = AsyncMock(
        return_value=(
            {"score": 70, "temperature": "warm", "jorge_priority": "normal"},
            MagicMock(five_minute_rule_compliant=True, cache_hit=False, analysis_type="full"),
        )
    )
    state = MagicMock()
    state.verify_ghl_signature = MagicMock(return_value=sig_valid)
    state._webhook_cache = cache if cache is not None else MockCache()
    state._ghl_client = None
    state.lead_analyzer = mock_lead
    state.performance_stats = {"total_requests": 0, "cache_hits": 0}
    return state


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return _make_app()


class TestNewLeadHardening:
    @pytest.mark.asyncio
    async def test_missing_contact_id_returns_400(self, app):
        """Payload without 'id' field → 400 Bad Request."""
        state = _make_state()
        payload = {"email": "test@example.com", "firstName": "Test"}  # no 'id'

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/ghl/webhook/new-lead",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 400
        assert "contact" in r.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_duplicate_within_60s_returns_skipped(self, app):
        """Same contact_id arriving twice within 60s → second request returns skipped."""
        cache = MockCache()
        state = _make_state(cache=cache)
        payload = {"id": "nl-dedup-001", "email": "dedup@example.com"}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # First request: should process
                r1 = await c.post(
                    "/ghl/webhook/new-lead",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )
                # Second request: same contact within dedup window → skipped
                r2 = await c.post(
                    "/ghl/webhook/new-lead",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r1.status_code == 200
        assert r1.json()["status"] == "processed"
        assert r2.status_code == 200
        assert r2.json()["status"] == "skipped"
        assert r2.json()["reason"] == "duplicate"

    @pytest.mark.asyncio
    async def test_internal_error_returns_200_not_500(self, app):
        """analyze_lead raising an exception → returns 200 (not 500) to prevent GHL retries."""
        cache = MockCache()
        state = _make_state(cache=cache)
        state.lead_analyzer.analyze_lead = AsyncMock(
            side_effect=RuntimeError("Claude API timeout")
        )
        payload = {"id": "nl-err-001", "email": "error@example.com"}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/ghl/webhook/new-lead",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "error"
        assert "internal" in data["detail"]

    @pytest.mark.asyncio
    async def test_invalid_signature_returns_401(self, app):
        """Invalid webhook signature → 401 (not swallowed as 200)."""
        state = _make_state(sig_valid=False)
        payload = {"id": "nl-sig-001"}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/ghl/webhook/new-lead",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json", "x-wh-signature": "bad"},
                )

        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_successful_lead_analyze_lead_called_once(self, app):
        """Valid new-lead → analyze_lead is called exactly once."""
        cache = MockCache()
        state = _make_state(cache=cache)
        payload = {"id": "nl-ok-001", "email": "valid@example.com", "firstName": "Valid"}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/ghl/webhook/new-lead",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["status"] == "processed"
        state.lead_analyzer.analyze_lead.assert_awaited_once()
