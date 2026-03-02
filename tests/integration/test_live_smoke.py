"""
Live smoke tests against the deployed Render instance.

Usage:
    RUN_LIVE_SMOKE=1 .venv/bin/python3.14 -m pytest tests/integration/test_live_smoke.py -v

Set JORGE_LIVE_URL to override the default Render URL.
"""

from __future__ import annotations

import os
import uuid

import pytest
import httpx

LIVE_URL = os.getenv("JORGE_LIVE_URL", "https://jorge-realty-ai-xxdf.onrender.com").rstrip("/")
TIMEOUT = 30  # Render cold-starts can be slow

# GHL requires locationId in webhook payloads
_TEST_LOCATION_ID = os.getenv("GHL_LOCATION_ID", "smoke-test-location")


def _require_live() -> None:
    if os.getenv("RUN_LIVE_SMOKE") != "1":
        pytest.skip("Set RUN_LIVE_SMOKE=1 to run live smoke tests")


def _contact_id() -> str:
    return f"smoke-{uuid.uuid4().hex[:8]}"


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self):
        _require_live()
        r = httpx.get(f"{LIVE_URL}/health", timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert "timestamp" in body

    def test_api_health_returns_200(self):
        _require_live()
        r = httpx.get(f"{LIVE_URL}/api/health/", timeout=TIMEOUT)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"


# ─────────────────────────────────────────────────────────────────────────────
# Admin auth (no token → 401)
# These tests pass once the security-fix deploy is live on Render.
# ─────────────────────────────────────────────────────────────────────────────

class TestAdminAuthLive:
    def test_admin_settings_get_no_auth(self):
        _require_live()
        r = httpx.get(f"{LIVE_URL}/admin/settings", timeout=TIMEOUT)
        assert r.status_code == 401, (
            f"Expected 401 (auth required). Got {r.status_code}. "
            "If deploy is still in progress, re-run after Render finishes."
        )

    def test_admin_settings_put_no_auth(self):
        _require_live()
        r = httpx.put(
            f"{LIVE_URL}/admin/settings/seller_bot",
            json={"key": "value"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401

    def test_admin_reassign_no_auth(self):
        _require_live()
        r = httpx.post(
            f"{LIVE_URL}/admin/reassign-bot",
            json={"contact_id": "smoke-test"},
            timeout=TIMEOUT,
        )
        assert r.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Webhook — shape and routing
# ─────────────────────────────────────────────────────────────────────────────

class TestWebhookSmoke:
    def _webhook(self, body: str, extra: dict | None = None) -> httpx.Response:
        payload = {
            "contactId": _contact_id(),
            "body": body,
            "type": "SMS",
            "locationId": _TEST_LOCATION_ID,
            **(extra or {}),
        }
        return httpx.post(
            f"{LIVE_URL}/api/ghl/webhook",
            json=payload,
            timeout=TIMEOUT,
        )

    def test_missing_contact_id_rejected(self):
        """No contactId → 400 or 422."""
        _require_live()
        r = httpx.post(
            f"{LIVE_URL}/api/ghl/webhook",
            json={"body": "Hello", "locationId": _TEST_LOCATION_ID},
            timeout=TIMEOUT,
        )
        assert r.status_code in (400, 422)

    def test_seller_intent_accepted(self):
        """Seller-intent message routes without 5xx."""
        _require_live()
        r = self._webhook("I want to sell my house")
        assert r.status_code not in (500, 501, 502), f"5xx: {r.text}"

    def test_buyer_intent_accepted(self):
        """Buyer-intent message routes without 5xx."""
        _require_live()
        r = self._webhook("I'm looking to buy a home in the area")
        assert r.status_code not in (500, 501, 502), f"5xx: {r.text}"

    def test_ambiguous_lead_accepted(self):
        """Generic first message routes without 5xx."""
        _require_live()
        r = self._webhook("Hi, I saw your listing")
        assert r.status_code not in (500, 501, 502), f"5xx: {r.text}"


# ─────────────────────────────────────────────────────────────────────────────
# Output filter — confirm sanitize_bot_response is active (no 500 crashes)
# ─────────────────────────────────────────────────────────────────────────────

class TestOutputFilterLive:
    def _probe(self, message: str) -> httpx.Response:
        return httpx.post(
            f"{LIVE_URL}/api/ghl/webhook",
            json={
                "contactId": _contact_id(),
                "body": message,
                "type": "SMS",
                "locationId": _TEST_LOCATION_ID,
            },
            timeout=TIMEOUT,
        )

    def test_filter_import_does_not_crash(self):
        """Broken response_filter import would 500 every webhook call."""
        _require_live()
        r = self._probe("hi")
        assert r.status_code != 500, f"Service 500 — likely import error: {r.text}"

    def test_identity_probe_no_crash(self):
        _require_live()
        r = self._probe("Are you a real person or an AI chatbot?")
        assert r.status_code != 500

    def test_url_probe_no_crash(self):
        _require_live()
        r = self._probe("Can you send me a link to your website?")
        assert r.status_code != 500

    def test_competitor_probe_no_crash(self):
        _require_live()
        r = self._probe("Should I use Opendoor or Zillow Offers instead?")
        assert r.status_code != 500

    def test_long_message_no_crash(self):
        """600-char message should be handled (truncated internally) without 5xx."""
        _require_live()
        r = self._probe("Tell me about real estate. " * 25)
        assert r.status_code != 500
