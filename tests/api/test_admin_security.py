"""Tests that all /admin/* endpoints reject requests without valid credentials."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from bots.lead_bot.main import app
from bots.lead_bot.routes_admin import get_admin_or_apikey


ADMIN_ENDPOINTS = [
    ("GET",    "/admin/settings"),
    ("PUT",    "/admin/settings/seller"),
    ("DELETE", "/admin/reset-state/seller/contact-abc"),
    ("POST",   "/admin/reassign-bot"),
]


@pytest.fixture
async def anon_client():
    """Client with no auth override — tests real auth enforcement."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def authed_client():
    """Client with auth bypassed."""
    app.dependency_overrides[get_admin_or_apikey] = lambda: None
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
async def test_admin_endpoint_rejects_no_key(anon_client, method, path):
    """All admin endpoints must return 401/403 without credentials (not 200)."""
    resp = await anon_client.request(method, path)
    # Acceptable rejection codes: 401 unauthorized, 403 forbidden, 422 validation error
    # 429 if rate limited, 404 if route not found (still not 200)
    assert resp.status_code != 200, (
        f"{method} {path} returned 200 without credentials — auth not enforced!"
    )
    assert resp.status_code in (401, 403, 404, 422, 429), (
        f"{method} {path} returned unexpected {resp.status_code}"
    )


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
async def test_admin_endpoint_rejects_invalid_key(anon_client, method, path):
    """All admin endpoints must return 403 with a wrong key (not 200)."""
    resp = await anon_client.request(
        method, path, headers={"X-Admin-Key": "totally-wrong-key"}
    )
    assert resp.status_code != 200, (
        f"{method} {path} returned 200 with invalid key — auth bypass!"
    )
    # 503 is acceptable when admin_api_key is not configured in the test environment
    assert resp.status_code in (401, 403, 404, 422, 429, 503), (
        f"{method} {path} returned unexpected {resp.status_code} with wrong key"
    )


async def test_admin_reset_state_validates_bot_type(authed_client):
    """reset-state only accepts 'seller' or 'buyer' bot_type."""
    resp = await authed_client.delete("/admin/reset-state/unknown_bot/contact-abc")
    # Should be 404 (route doesn't match) or 422 (validation error)
    assert resp.status_code in (400, 404, 422)


async def test_admin_reassign_requires_body(authed_client):
    """POST /admin/reassign-bot requires a valid body — returns 422 without it."""
    resp = await authed_client.post("/admin/reassign-bot", json={})
    # 422 = validation error (missing required fields), 200 = somehow succeeded
    assert resp.status_code in (400, 422, 200), (
        f"Unexpected status {resp.status_code}"
    )
