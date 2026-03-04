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


# ─────────────────────────────────────────────────────────────────────────────
# P0 Calendar booking smoke test
#
# Drives the 5-turn HOT seller conversation from docs/E2E_SMOKE_TEST.md and
# verifies trigger_workflow: 577d56c4 appears in actions_taken.
#
# After this test passes, ask Jorge to confirm the calendar link SMS arrived.
# ─────────────────────────────────────────────────────────────────────────────

_HOT_SELLER_TURNS = [
    "Move-in ready, 3 bed 2 bath in Rancho Cucamonga",
    "Looking for around 580k",
    "Relocating for work, need to sell in 60 days",
    "Yes I can accept an offer within 2-3 weeks",
    "Morning works best for me, any day this week",
]

_CALENDAR_WORKFLOW_ID = "577d56c4-28af-4668-8d84-80f5db234f48"


def _seller_turn(contact_id: str, message: str) -> httpx.Response:
    return httpx.post(
        f"{LIVE_URL}/test/seller",
        json={"contact_id": contact_id, "message": message, "location_id": _TEST_LOCATION_ID},
        timeout=TIMEOUT,
    )


def _turn_actions(data: dict) -> list:
    """Return actions list from either the old ('actions') or new ('actions_taken') schema."""
    return data.get("actions_taken") or data.get("actions") or []


def _turn_temperature(data: dict) -> str:
    """Return temperature from either schema."""
    return data.get("seller_temperature") or data.get("temperature") or ""


def _turn_questions_answered(data: dict) -> int:
    """Return questions_answered from either schema."""
    if "questions_answered" in data:
        return data["questions_answered"]
    return (data.get("extracted_data") or {}).get("questions_answered", 0)


class TestCalendarBookingSmoke:
    """
    P0: Confirm GHL workflow 577d56c4 fires for HOT seller.

    Run:
        RUN_LIVE_SMOKE=1 pytest tests/integration/test_live_smoke.py::TestCalendarBookingSmoke -v

    Prerequisites:
        - ENVIRONMENT != "production" on the target server (test endpoints must be mounted)
        - JORGE_CALENDAR_ID must be set (otherwise calendar booking falls back to FALLBACK_MESSAGE)

    After the test passes, ask Jorge to confirm the calendar link SMS arrived on his phone.
    """

    def test_test_seller_endpoint_reachable(self):
        """/test/seller must respond (not 404/500) in non-production deployments."""
        _require_live()
        r = httpx.post(
            f"{LIVE_URL}/test/seller",
            json={"contact_id": "probe-reachable", "message": "hi"},
            timeout=TIMEOUT,
        )
        if r.status_code == 404:
            pytest.skip("/test/seller not mounted — ENVIRONMENT=production on this server")
        assert r.status_code not in (500, 503), f"Server error on /test/seller: {r.text}"

    def test_hot_seller_triggers_calendar_workflow(self):
        """
        5-turn HOT seller conversation must produce trigger_workflow: 577d56c4 action.

        Verifies bot-side calendar booking. Follow up with Jorge to confirm
        the GHL workflow actually delivers the calendar link by SMS.
        """
        _require_live()
        contact_id = f"smoke-cal-{uuid.uuid4().hex[:8]}"

        last: dict = {}
        for turn, msg in enumerate(_HOT_SELLER_TURNS, start=1):
            r = _seller_turn(contact_id, msg)
            if r.status_code == 404:
                pytest.skip("/test/seller not mounted — ENVIRONMENT=production on this server")
            assert r.status_code == 200, (
                f"Turn {turn} ({msg!r}) returned {r.status_code}: {r.text}"
            )
            last = r.json()

        actions = _turn_actions(last)
        workflow_ids = [
            a.get("workflow_id", "") or a.get("id", "")
            for a in actions
            if a.get("type") == "trigger_workflow"
        ]

        assert workflow_ids, (
            f"No trigger_workflow action in final turn.\n"
            f"  Temperature: {_turn_temperature(last)}\n"
            f"  Questions answered: {_turn_questions_answered(last)}\n"
            f"  Actions: {actions}\n"
            f"  Response: {last.get('response_message') or last.get('response')!r}"
        )
        assert any(_CALENDAR_WORKFLOW_ID in wid for wid in workflow_ids), (
            f"Expected workflow {_CALENDAR_WORKFLOW_ID!r} (calendar booking).\n"
            f"Got: {workflow_ids}"
        )
        print(
            f"\n✅  Calendar workflow triggered for contact {contact_id!r}.\n"
            f"    Temperature: {_turn_temperature(last)} | "
            f"Q answered: {_turn_questions_answered(last)}\n"
            f"    ➜  Ask Jorge to confirm the calendar link SMS arrived on his phone."
        )

    def test_seller_qualification_data_extracted(self):
        """
        Full HOT seller path extracts price, motivation, and all 4 questions answered.
        Independent of calendar config — validates data extraction only.
        """
        _require_live()
        contact_id = f"smoke-data-{uuid.uuid4().hex[:8]}"

        responses = []
        for msg in _HOT_SELLER_TURNS:
            r = _seller_turn(contact_id, msg)
            if r.status_code == 404:
                pytest.skip("/test/seller not mounted")
            assert r.status_code == 200, f"Turn failed: {r.status_code} {r.text}"
            responses.append(r.json())

        final = responses[-1]
        assert _turn_questions_answered(final) >= 4, (
            f"Expected 4 questions answered, got {_turn_questions_answered(final)}"
        )
        assert _turn_temperature(final) == "hot", (
            f"Expected 'hot' temperature, got {_turn_temperature(final)!r}"
        )

        # price_expectation must be captured — check actions or workflow data
        all_actions = [a for resp in responses for a in _turn_actions(resp)]
        price_found = any(
            "price" in str(a.get("field", "")).lower()
            or "price" in str(a.get("data", {}).get("price_expectation", "")).lower()
            or "580" in str(a.get("data", {}).get("price_expectation", ""))
            for a in all_actions
        )
        assert price_found, (
            f"Expected price_expectation to be extracted. Actions: {all_actions}"
        )
