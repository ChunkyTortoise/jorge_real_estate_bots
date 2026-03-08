"""
Webhook routing unit tests — Fix 3 (bot exclusivity) and Fix 4 (deferred tags).

Tests call the FastAPI route handler directly via httpx AsyncClient + ASGITransport,
with _get_state() patched to a mock state object.  No Redis or GHL API calls.
"""

import json
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from bots.buyer_bot.buyer_bot import BuyerResult
from bots.lead_bot.routes_webhook import router
from bots.seller_bot.jorge_seller_bot import SellerResult

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


def _seller_result(temperature: str = "cold", **kwargs) -> SellerResult:
    tag_actions: List[Dict] = [
        {"type": "remove_tag", "tag": f"seller_{t}"}
        for t in ("hot", "warm", "cold")
        if t != temperature
    ]
    tag_actions.append({"type": "add_tag", "tag": f"seller_{temperature}"})
    defaults = dict(
        response_message="What condition is your property in?",
        seller_temperature=temperature,
        questions_answered=0,
        qualification_complete=False,
        actions_taken=tag_actions
        + [{"type": "update_custom_field", "field": "seller_temperature", "value": temperature}],
        next_steps="Continue Q1",
        analytics={},
    )
    defaults.update(kwargs)
    return SellerResult(**defaults)


def _buyer_result(temperature: str = "cold", **kwargs) -> BuyerResult:
    tag_actions: List[Dict] = [
        {"type": "remove_tag", "tag": f"buyer_{t}"}
        for t in ("hot", "warm", "cold")
        if t != temperature
    ]
    tag_actions.append({"type": "add_tag", "tag": f"buyer_{temperature}"})
    defaults = dict(
        response_message="How many bedrooms, what's your budget and area?",
        buyer_temperature=temperature,
        questions_answered=0,
        qualification_complete=False,
        actions_taken=tag_actions
        + [{"type": "update_custom_field", "field": "buyer_temperature", "value": temperature}],
        next_steps="Continue Q1",
        analytics={},
        matches=[],
    )
    defaults.update(kwargs)
    return BuyerResult(**defaults)


def _make_state(
    cache: Optional[MockCache] = None,
    seller_result: Optional[SellerResult] = None,
    buyer_result: Optional[BuyerResult] = None,
):
    """Build a mock state object that mimics bots.lead_bot.main module attributes."""
    mock_ghl = AsyncMock()
    mock_ghl.add_tag = AsyncMock()
    mock_ghl.remove_tag = AsyncMock()
    mock_ghl.send_message = AsyncMock(return_value={"success": True})
    mock_ghl.get_contact = AsyncMock(return_value={"customFields": []})

    mock_seller = AsyncMock()
    mock_seller.process_seller_message = AsyncMock(
        return_value=seller_result or _seller_result()
    )

    mock_buyer = AsyncMock()
    mock_buyer.process_buyer_message = AsyncMock(
        return_value=buyer_result or _buyer_result()
    )

    mock_lead = AsyncMock()
    mock_lead.analyze_lead = AsyncMock(
        return_value=(
            {"score": 50, "temperature": "warm", "jorge_priority": "normal"},
            MagicMock(five_minute_rule_compliant=True),
        )
    )

    state = MagicMock()
    state.verify_ghl_signature = MagicMock(return_value=True)
    state._webhook_cache = cache if cache is not None else MockCache()
    state.seller_bot_instance = mock_seller
    state.buyer_bot_instance = mock_buyer
    state.lead_analyzer = mock_lead
    state._ghl_client = mock_ghl
    state.performance_stats = {"total_requests": 0, "cache_hits": 0}

    return state, mock_seller, mock_buyer, mock_ghl, mock_lead


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _body(contact_id: str = "c-test", body: str = "hello", bot_type: str = "") -> bytes:
    data: Dict[str, Any] = {
        "contactId": contact_id,
        "locationId": "loc-test",
        "body": body,
    }
    if bot_type:
        data["customData"] = {"bot_type": bot_type}
    return json.dumps(data).encode()


@pytest.fixture(scope="module")
def app() -> FastAPI:
    return _make_app()


@pytest.fixture(autouse=True)
def instant_background_sleep():
    """Make asyncio.sleep instant in all tests so deferred background tasks don't stall."""
    with patch("bots.lead_bot.routes_webhook.asyncio.sleep", new=AsyncMock()):
        yield


# ---------------------------------------------------------------------------
# Fix 1 + 2 — Correct bot fires for each bot_type value
# ---------------------------------------------------------------------------


class TestWebhookRouting:
    @pytest.mark.asyncio
    async def test_seller_bot_type_routes_to_seller(self, app):
        """bot_type=seller → seller bot fires, buyer bot silent."""
        state, mock_seller, mock_buyer, mock_ghl, _ = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="route-s"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        mock_seller.process_seller_message.assert_awaited_once()
        mock_buyer.process_buyer_message.assert_not_awaited()
        assert r.json()["bot_type"] == "seller"

    @pytest.mark.asyncio
    async def test_buyer_bot_type_routes_to_buyer(self, app):
        """bot_type=buyer → buyer bot fires, seller bot silent."""
        state, mock_seller, mock_buyer, _, _ = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="buyer", contact_id="route-b"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        mock_buyer.process_buyer_message.assert_awaited_once()
        mock_seller.process_seller_message.assert_not_awaited()
        assert r.json()["bot_type"] == "buyer"

    @pytest.mark.asyncio
    async def test_missing_bot_type_defaults_to_lead(self, app):
        """No bot_type in payload → lead analysis, no SMS sent."""
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(contact_id="route-lead"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_awaited_once()
        mock_ghl.send_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Fix 3 — Bot exclusivity
# ---------------------------------------------------------------------------


class TestBotAssignmentExclusivity:
    @pytest.mark.asyncio
    async def test_bot_assignment_stored_on_first_contact(self, app):
        """First webhook for a contact writes conversation:mode: to the canonical cache."""
        cache = MockCache()
        state, _, _, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="assign-new"),
                    headers={"Content-Type": "application/json"},
                )
        assert await cache.get("conversation:mode:assign-new") == "seller"

    @pytest.mark.asyncio
    async def test_bot_assignment_exclusivity(self, app):
        """
        Contact pre-assigned to buyer.
        Payload without explicit bot_type (GHL API returns nothing) → buyer honoured.
        """
        cache = MockCache()
        await cache.set("conversation:mode:excl-c", "buyer", ttl=604800)
        state, mock_seller, mock_buyer, _, _ = _make_state(cache=cache)
        # No bot_type in payload → _bot_type_explicit = False → stored assignment wins
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(contact_id="excl-c", body="hi there"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        mock_buyer.process_buyer_message.assert_awaited_once()
        mock_seller.process_seller_message.assert_not_awaited()
        assert r.json()["bot_type"] == "buyer"

    @pytest.mark.asyncio
    async def test_bot_assignment_overridden_by_explicit_payload(self, app):
        """
        Contact pre-assigned to buyer.
        Explicit bot_type=seller in payload → assignment updated, seller bot fires.
        """
        cache = MockCache()
        await cache.set("conversation:mode:switch-c", "buyer", ttl=604800)
        state, mock_seller, mock_buyer, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="switch-c"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        mock_seller.process_seller_message.assert_awaited_once()
        mock_buyer.process_buyer_message.assert_not_awaited()
        assert await cache.get("conversation:mode:switch-c") == "seller"


# ---------------------------------------------------------------------------
# Fix 4 — Deferred tag application
# ---------------------------------------------------------------------------


class TestDeferredTags:
    @pytest.mark.asyncio
    async def test_seller_tags_not_applied_immediately(self, app):
        """
        add_tag / remove_tag must NOT be called synchronously inside the bot.
        The deferred background task is scheduled instead.
        """
        cache = MockCache()
        result = _seller_result("cold")
        state, _, _, mock_ghl, _ = _make_state(cache=cache, seller_result=result)

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch(
                "bots.lead_bot.routes_webhook._deferred_tag_apply",
                new=AsyncMock(),
            ) as mock_deferred,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="tag-s"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        # GHL add_tag / remove_tag NOT called directly
        mock_ghl.add_tag.assert_not_called()
        mock_ghl.remove_tag.assert_not_called()
        # Background task scheduled with the tag actions
        mock_deferred.assert_awaited_once()
        _, _, tag_actions = mock_deferred.call_args.args
        assert any(a["type"] == "add_tag" for a in tag_actions)
        assert any(a["type"] == "remove_tag" for a in tag_actions)
        # Non-tag actions (update_custom_field) are NOT in the deferred list
        assert not any(a["type"] == "update_custom_field" for a in tag_actions)

    @pytest.mark.asyncio
    async def test_buyer_tags_not_applied_immediately(self, app):
        """Same deferred-tag guarantee for the buyer bot path."""
        cache = MockCache()
        result = _buyer_result("warm")
        state, _, _, mock_ghl, _ = _make_state(cache=cache, buyer_result=result)

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch(
                "bots.lead_bot.routes_webhook._deferred_tag_apply",
                new=AsyncMock(),
            ) as mock_deferred,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="buyer", contact_id="tag-b"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        mock_ghl.add_tag.assert_not_called()
        mock_ghl.remove_tag.assert_not_called()
        mock_deferred.assert_awaited_once()
        _, _, tag_actions = mock_deferred.call_args.args
        assert any(a["type"] == "add_tag" for a in tag_actions)


# ---------------------------------------------------------------------------
# New-lead bot locking
# ---------------------------------------------------------------------------


def _new_lead_body(contact_id: str = "nl-test") -> bytes:
    return json.dumps({"id": contact_id, "email": "test@example.com"}).encode()


class TestNewLeadBotLocking:
    @pytest.mark.asyncio
    async def test_new_lead_sets_mode_in_redis(self, app):
        """POST /ghl/webhook/new-lead must write conversation:mode:<id> to cache."""
        cache = MockCache()
        state, _, _, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/ghl/webhook/new-lead",
                    content=_new_lead_body("lock-lead-1"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        assert await cache.get("conversation:mode:lock-lead-1") == "lead_intake"

    @pytest.mark.asyncio
    async def test_new_lead_then_reply_stays_on_lead_bot(self, app):
        """
        Contact created via new-lead → conversation:mode='lead_intake'.
        Follow-up reply with no explicit bot_type, even if GHL API returns 'seller',
        must still route to lead bot (redis_cache takes precedence).
        """
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        # GHL API would misroute this contact to seller
        mock_ghl.get_contact.return_value = {
            "customFields": [{"fieldKey": "bot_type", "value": "seller"}]
        }

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # Step 1 — new lead arrives
                await c.post(
                    "/ghl/webhook/new-lead",
                    content=_new_lead_body("sticky-lead"),
                    headers={"Content-Type": "application/json"},
                )
                # Step 2 — contact replies; no explicit bot_type in payload
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(contact_id="sticky-lead", body="hello"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["bot_type"] == "lead"
        mock_seller.process_seller_message.assert_not_awaited()



# ---------------------------------------------------------------------------
# Phase 3E — Additional webhook edge-case tests
# ---------------------------------------------------------------------------


class TestEmptyMessageBody:
    """Empty message body → webhook is skipped, no bot response."""

    @pytest.mark.asyncio
    async def test_empty_string_body_skipped(self, app):
        state, mock_seller, mock_buyer, _, _ = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="", bot_type="seller"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"
        assert r.json()["reason"] == "empty message"
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_whitespace_only_body_skipped(self, app):
        state, mock_seller, mock_buyer, _, _ = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="   \n\t  ", bot_type="buyer"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        assert r.json()["status"] == "skipped"
        mock_buyer.process_buyer_message.assert_not_awaited()


class TestMessageTruncation:
    """Message longer than 2000 chars → gets truncated before bot processing."""

    @pytest.mark.asyncio
    async def test_long_message_truncated_to_2000(self, app):
        long_body = "A" * 3000
        state, mock_seller, _, _, _ = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body=long_body, bot_type="seller", contact_id="trunc-c"),
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        # The seller bot should have been called — verify the message was truncated
        mock_seller.process_seller_message.assert_awaited_once()
        call_args = mock_seller.process_seller_message.call_args
        # message is the 3rd positional arg (contact_id, location_id, message, ...)
        actual_message = call_args.kwargs.get("message") or call_args.args[2] if len(call_args.args) > 2 else ""
        assert len(actual_message) <= 2000


class TestMessageDeduplication:
    """Same message from same contact within 5 minutes → deduped."""

    @pytest.mark.asyncio
    async def test_duplicate_message_skipped(self, app):
        cache = MockCache()
        state, mock_seller, _, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # First message — processed
                r1 = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="hello world", bot_type="seller", contact_id="dedup-c"),
                    headers={"Content-Type": "application/json"},
                )
                # Same message, same contact — should be deduped
                r2 = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="hello world", bot_type="seller", contact_id="dedup-c"),
                    headers={"Content-Type": "application/json"},
                )
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r2.json()["status"] == "skipped"
        assert r2.json()["reason"] == "duplicate"
        # Seller bot only called once (not for the duplicate)
        assert mock_seller.process_seller_message.await_count == 1

    @pytest.mark.asyncio
    async def test_different_message_not_deduped(self, app):
        cache = MockCache()
        state, mock_seller, _, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="first message", bot_type="seller", contact_id="dedup-diff"),
                    headers={"Content-Type": "application/json"},
                )
                r2 = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="second message", bot_type="seller", contact_id="dedup-diff"),
                    headers={"Content-Type": "application/json"},
                )
        # Both should process (second is not a duplicate — different content)
        assert r2.json().get("status") != "skipped"


class TestPerContactRateLimit:
    """Per-contact rate limit: 11th message in the window → throttled."""

    @pytest.mark.asyncio
    async def test_11th_message_throttled(self, app):
        cache = MockCache()
        state, mock_seller, _, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                last_response = None
                for i in range(12):
                    last_response = await c.post(
                        "/api/ghl/webhook",
                        content=_body(
                            body=f"message number {i}",
                            bot_type="seller",
                            contact_id="rate-c",
                        ),
                        headers={"Content-Type": "application/json"},
                    )
        assert last_response is not None
        assert last_response.status_code == 200
        assert last_response.json()["status"] == "throttled"
        assert last_response.json()["reason"] == "per_contact_rate_limit"


class TestBotTypeFromCustomData:
    """customData.bot_type = 'seller' → routes to seller bot."""

    @pytest.mark.asyncio
    async def test_customdata_seller_routes_to_seller(self, app):
        state, mock_seller, mock_buyer, _, _ = _make_state()
        payload = json.dumps({
            "contactId": "cd-seller",
            "locationId": "loc-test",
            "body": "Hi there",
            "customData": {"bot_type": "seller"},
        }).encode()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )
        assert r.status_code == 200
        assert r.json()["bot_type"] == "seller"
        mock_seller.process_seller_message.assert_awaited_once()
        mock_buyer.process_buyer_message.assert_not_awaited()


class TestWebhookPayloadParsing:
    """Payload extraction branches from the unified webhook."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("payload", "expected_message"),
        [
            (
                {
                    "contactId": "msg-dict-body",
                    "locationId": "loc-test",
                    "message": {"body": "dict body wins", "text": "ignored"},
                    "customData": {"bot_type": "seller"},
                },
                "dict body wins",
            ),
            (
                {
                    "contactId": "msg-dict-text",
                    "locationId": "loc-test",
                    "message": {"text": "dict text fallback"},
                    "customData": {"bot_type": "seller"},
                },
                "dict text fallback",
            ),
            (
                {
                    "contactId": "msg-string",
                    "locationId": "loc-test",
                    "message": "plain string payload",
                    "customData": {"bot_type": "seller"},
                },
                "plain string payload",
            ),
        ],
    )
    async def test_message_body_extraction_variants(self, app, payload, expected_message):
        state, mock_seller, _, _, _ = _make_state()
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        mock_seller.process_seller_message.assert_awaited_once()
        assert mock_seller.process_seller_message.call_args.kwargs["message"] == expected_message

    @pytest.mark.asyncio
    async def test_strong_seller_intent_without_explicit_bot_routes_to_seller(self, app):
        cache = MockCache()
        state, mock_seller, mock_buyer, _, mock_lead = _make_state(cache=cache)
        payload = json.dumps(
            {"contactId": "intent-seller", "locationId": "loc-test", "body": "I want to sell my house"}
        ).encode()

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/ghl/webhook", content=payload, headers={"Content-Type": "application/json"})

        assert r.status_code == 200
        assert r.json()["mode"] == "seller"
        mock_seller.process_seller_message.assert_awaited_once()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ambiguous_unknown_contact_stays_in_lead_intake(self, app):
        cache = MockCache()
        state, mock_seller, mock_buyer, _, mock_lead = _make_state(cache=cache)
        payload = json.dumps(
            {"contactId": "intent-ambiguous", "locationId": "loc-test", "body": "Hi there"}
        ).encode()

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post("/api/ghl/webhook", content=payload, headers={"Content-Type": "application/json"})

        assert r.status_code == 200
        assert r.json()["mode"] == "lead_intake"
        assert r.json()["conversation_status"] == "active"
        mock_lead.analyze_lead.assert_awaited_once()
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("contact_key", ["contactId", "contact_id", "id"])
    async def test_contact_identifier_aliases_are_accepted(self, app, contact_key):
        state, mock_seller, _, _, _ = _make_state()
        payload = {
            contact_key: f"alias-{contact_key}",
            "locationId": "loc-test",
            "body": "hello from alias",
            "customData": {"bot_type": "seller"},
        }

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        mock_seller.process_seller_message.assert_awaited_once()
        assert mock_seller.process_seller_message.call_args.kwargs["contact_id"] == f"alias-{contact_key}"

    @pytest.mark.asyncio
    async def test_missing_location_id_falls_back_to_settings(self, app):
        state, mock_seller, _, _, _ = _make_state()
        payload = {
            "contactId": "fallback-location",
            "body": "hello",
            "customData": {"bot_type": "seller"},
        }

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.settings.ghl_location_id", "env-loc-123"),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert mock_seller.process_seller_message.call_args.kwargs["location_id"] == "env-loc-123"

    @pytest.mark.asyncio
    async def test_missing_contact_id_returns_error(self, app):
        state, mock_seller, mock_buyer, _, _ = _make_state()
        payload = {"locationId": "loc-test", "body": "hello"}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "error", "detail": "missing contactId"}
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()


class TestWebhookAvailabilityAndStatusCallbacks:
    @pytest.mark.asyncio
    async def test_unavailable_seller_bot_returns_error(self, app):
        state, _, _, _, _ = _make_state()
        state.seller_bot_instance = None

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="seller-down"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "error", "detail": "seller bot unavailable"}

    @pytest.mark.asyncio
    async def test_jorge_active_suppresses_before_bot_dispatch(self, app):
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": ["Jorge-Active"], "customFields": []}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="jorge-active"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "human_handoff"
        assert r.json()["conversation_status"] == "suppressed"
        assert r.json()["handoff_reason"] == "jorge_active"
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_lowercase_jorge_active_suppresses_before_bot_dispatch(self, app):
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": ["jorge-active"], "customFields": []}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="jorge-active-lower"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "human_handoff"
        assert r.json()["conversation_status"] == "suppressed"
        assert r.json()["handoff_reason"] == "jorge_active"
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cached_human_handoff_stays_suppressed(self, app):
        cache = MockCache()
        await cache.set("conversation:mode:cached-human", "human_handoff", ttl=604800)
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(contact_id="cached-human"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "human_handoff"
        assert r.json()["conversation_status"] == "suppressed"
        assert r.json()["handoff_reason"] == "manual_override"
        assert r.json()["message_suppression_reason"] == "manual_override"
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_message_status_records_sms_delivery_metric(self, app):
        state, _, _, _, _ = _make_state()
        payload = json.dumps({"type": "message.delivered", "contactId": "sms-123"}).encode()

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch(
                "bots.lead_bot.routes_webhook.SmsMetricsCollector.record_delivery",
                new_callable=AsyncMock,
            ) as mock_record,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook/message-status",
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
        mock_record.assert_awaited_once()
        args = mock_record.await_args.args
        assert args[0] == "sms-123"
        assert args[1] == "delivered"


# ---------------------------------------------------------------------------
# H1 — Manual takeover (Jorge-Active tag) updates Redis caches
# ---------------------------------------------------------------------------


class TestManualTakeoverCacheUpdate:
    @pytest.mark.asyncio
    async def test_manual_takeover_updates_caches(self, app):
        """Jorge-Active tag should re-write Redis caches to HUMAN_HANDOFF."""
        cache = MockCache()
        # Pre-seed cache with a seller assignment
        await cache.set("conversation:mode:jorge-takeover", "seller", ttl=604800)

        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": ["Jorge-Active"], "customFields": []}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="jorge-takeover"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        # Cache should be updated to human_handoff mode
        assert await cache.get("conversation:mode:jorge-takeover") == "human_handoff"
        # No bot should have fired
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_not_awaited()


# ---------------------------------------------------------------------------
# H2 — Bilingual upsert creates DB row
# ---------------------------------------------------------------------------


class TestBilingualHandoffDB:
    @pytest.mark.asyncio
    async def test_bilingual_handoff_creates_db_row(self, app):
        """Bilingual detection should create a conversation DB record via upsert_conversation."""
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}

        # Spanish message with 2+ indicator words triggers bilingual handoff
        spanish_msg = "Hola, quiero vender mi casa"

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock) as mock_upsert,
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps({
                        "contactId": "bilingual-c1",
                        "locationId": "loc-test",
                        "body": spanish_msg,
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "bilingual_handoff"
        # upsert_conversation must have been called with HANDOFF stage
        mock_upsert.assert_awaited_once()
        call_kwargs = mock_upsert.call_args.kwargs
        assert call_kwargs["contact_id"] == "bilingual-c1"
        assert call_kwargs["bot_type"] == "lead"
        assert call_kwargs["stage"] == "HANDOFF"
        assert call_kwargs["temperature"] == "cold"
        # No bots should have fired
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# H3 — Bilingual idempotency (cache transitions to HUMAN_HANDOFF)
# ---------------------------------------------------------------------------


class TestBilingualIdempotency:
    @pytest.mark.asyncio
    async def test_bilingual_handoff_cache_transitions_to_human_handoff(self, app):
        """After bilingual message, canonical cache should be HUMAN_HANDOFF so second message is suppressed."""
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}

        spanish_msg = "Hola, quiero vender mi casa"

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # First bilingual message
                r1 = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps({
                        "contactId": "bilingual-idem",
                        "locationId": "loc-test",
                        "body": spanish_msg,
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r1.status_code == 200
        assert r1.json()["mode"] == "bilingual_handoff"
        # After processing, cache should be set to human_handoff (not bilingual_handoff)
        cached_mode = await cache.get("conversation:mode:bilingual-idem")
        assert cached_mode == "human_handoff"

    @pytest.mark.asyncio
    async def test_second_bilingual_message_is_suppressed(self, app):
        """Second bilingual message should route to HUMAN_HANDOFF (suppressed), not bilingual again."""
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                # First bilingual message — sets cache to human_handoff
                await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps({
                        "contactId": "bilingual-twice",
                        "locationId": "loc-test",
                        "body": "Hola quiero comprar casa",
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                )
                # Second message from same contact — different Spanish text to avoid dedup
                r2 = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps({
                        "contactId": "bilingual-twice",
                        "locationId": "loc-test",
                        "body": "Hola gracias por responder",
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r2.status_code == 200
        # Second message should be routed as human_handoff (suppressed), not bilingual
        assert r2.json()["mode"] == "human_handoff"
        assert r2.json()["conversation_status"] == "suppressed"
        # No bots should fire on the suppressed message
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# H5 — q4_attempts survives Redis eviction (persisted in extracted_data)
# ---------------------------------------------------------------------------


class TestQ4AttemptsPersistence:
    @pytest.mark.asyncio
    async def test_q4_attempts_persisted_in_extracted_data(self):
        """q4_attempts should be in extracted_data so DB fallback can restore it."""
        from bots.seller_bot.jorge_seller_bot import JorgeSellerBot, SellerQualificationState

        state = SellerQualificationState(
            contact_id="test-contact",
            location_id="test-loc",
            q4_attempts=3,
            offer_presented=True,
            scheduling_offered=True,
            appointment_booked=False,
        )

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        mock_cache.sadd = AsyncMock()

        with (
            patch("bots.seller_bot.jorge_seller_bot.get_cache_service", return_value=mock_cache),
            patch("bots.seller_bot.jorge_seller_bot.upsert_conversation", new_callable=AsyncMock) as mock_upsert,
        ):
            bot = JorgeSellerBot()
            await bot.save_conversation_state("test-contact", state, temperature="warm")

            # Check that q4_attempts is in extracted_data passed to upsert
            mock_upsert.assert_awaited_once()
            call_kwargs = mock_upsert.call_args.kwargs
            assert call_kwargs["extracted_data"]["q4_attempts"] == 3
            assert call_kwargs["extracted_data"]["offer_presented"] is True
            assert call_kwargs["extracted_data"]["scheduling_offered"] is True
            assert call_kwargs["extracted_data"]["appointment_booked"] is False


# ---------------------------------------------------------------------------
# Canonical migration — edge-case coverage
# ---------------------------------------------------------------------------


class TestBotUnavailability:
    @pytest.mark.asyncio
    async def test_unavailable_buyer_bot_returns_error(self, app):
        """buyer_bot_instance=None → error response (mirrors existing seller test)."""
        state, _, _, _, _ = _make_state()
        state.buyer_bot_instance = None

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="buyer", contact_id="buyer-down"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json() == {"status": "error", "detail": "buyer bot unavailable"}


class TestHandoffGHLSync:
    @pytest.mark.asyncio
    async def test_bilingual_handoff_syncs_ghl_fields(self, app):
        """Bilingual path writes ai_mode=human_handoff to GHL immediately."""
        cache = MockCache()
        state, _, _, mock_ghl, _ = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}
        mock_ghl.update_custom_field = AsyncMock()

        spanish_msg = "Hola quiero vender mi casa"

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=json.dumps({
                        "contactId": "bilingual-ghl-sync",
                        "locationId": "loc-test",
                        "body": spanish_msg,
                    }).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "bilingual_handoff"
        # GHL update_custom_field must have been called with ai_mode=human_handoff
        mock_ghl.update_custom_field.assert_awaited()
        calls = [call.args for call in mock_ghl.update_custom_field.await_args_list]
        ai_mode_calls = [c for c in calls if c[1] == "ai_mode"]
        assert any(c[2] == "human_handoff" for c in ai_mode_calls)

    @pytest.mark.asyncio
    async def test_human_handoff_syncs_ghl_fields(self, app):
        """Human handoff path (cached) writes ai_mode=human_handoff to GHL before returning."""
        cache = MockCache()
        await cache.set("conversation:mode:human-ghl-sync", "human_handoff", ttl=604800)
        state, _, _, mock_ghl, _ = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}
        mock_ghl.update_custom_field = AsyncMock()

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(contact_id="human-ghl-sync", body="still need help"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "human_handoff"
        mock_ghl.update_custom_field.assert_awaited()
        calls = [call.args for call in mock_ghl.update_custom_field.await_args_list]
        ai_mode_calls = [c for c in calls if c[1] == "ai_mode"]
        assert any(c[2] == "human_handoff" for c in ai_mode_calls)


class TestProcessingLock:
    @pytest.mark.asyncio
    async def test_processing_lock_throttles_concurrent(self, app):
        """Lock already held → returns reason: processing_lock."""
        cache = MockCache()
        # Pre-seed the processing lock
        await cache.set("lock:lock-contact", "1", ttl=90)
        state, _, _, _, _ = _make_state(cache=cache)

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(contact_id="lock-contact", body="help me"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["status"] == "throttled"
        assert r.json()["reason"] == "processing_lock"


class TestOptOut:
    @pytest.mark.asyncio
    async def test_opt_out_message_skipped(self, app):
        """'STOP' message → opt-out path, no bot processing."""
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state()

        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(body="STOP", bot_type="seller", contact_id="opt-out-c"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        data = r.json()
        # Must not have processed through any bot
        mock_seller.process_seller_message.assert_not_awaited()
        mock_buyer.process_buyer_message.assert_not_awaited()
        mock_lead.analyze_lead.assert_not_awaited()
        # Should be skipped/suppressed/opted_out — any non-bot-processed status
        assert data.get("status") in ("skipped", "processed", "suppressed", "opted_out")


class TestBotTagHandoffs:
    @pytest.mark.asyncio
    async def test_seller_needs_human_review_sets_handoff(self, app):
        """Seller bot returns needs-human-review tag → canonical has human_takeover=True, stage=STALLED."""
        cache = MockCache()
        result = _seller_result(
            temperature="cold",
            actions_taken=[{"type": "add_tag", "tag": "needs-human-review"}],
        )
        state, mock_seller, _, mock_ghl, _ = _make_state(cache=cache, seller_result=result)
        mock_ghl.send_message = AsyncMock(return_value={"success": True})

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
            patch("bots.lead_bot.routes_webhook.update_conversation_outbound_at", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="seller-review"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        data = r.json()
        assert data["handoff_reason"] == "needs_human_review"

    @pytest.mark.asyncio
    async def test_buyer_needs_bilingual_sets_handoff(self, app):
        """Buyer bot returns needs-bilingual tag → canonical has bilingual_required=True."""
        cache = MockCache()
        result = _buyer_result(
            temperature="cold",
            actions_taken=[{"type": "add_tag", "tag": "needs-bilingual"}],
        )
        state, _, mock_buyer, mock_ghl, _ = _make_state(cache=cache, buyer_result=result)
        mock_ghl.send_message = AsyncMock(return_value={"success": True})

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
            patch("bots.lead_bot.routes_webhook.update_conversation_outbound_at", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="buyer", contact_id="buyer-bilingual"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        data = r.json()
        assert data["handoff_reason"] == "needs_bilingual"

# ---------------------------------------------------------------------------
# Fix 1 — manual_takeover syncs GHL ai_mode
# ---------------------------------------------------------------------------


class TestManualTakeoverGHLSync:
    @pytest.mark.asyncio
    async def test_manual_takeover_syncs_ghl_fields(self, app):
        """Jorge-Active tag path must call update_custom_field with ai_mode=human_handoff."""
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, _ = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": ["Jorge-Active"], "customFields": []}
        mock_ghl.update_custom_field = AsyncMock(return_value={"success": True})

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="takeover-ghl"),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "human_handoff"
        # Must have synced ai_mode to GHL
        calls = [str(c) for c in mock_ghl.update_custom_field.call_args_list]
        assert any("ai_mode" in c and "human_handoff" in c for c in calls), (
            f"Expected ai_mode=human_handoff GHL sync call, got: {calls}"
        )


# ---------------------------------------------------------------------------
# Fix 5 — lead_intake syncs GHL ai_mode
# ---------------------------------------------------------------------------


class TestLeadIntakeGHLSync:
    @pytest.mark.asyncio
    async def test_lead_intake_syncs_ghl_fields(self, app):
        """LEAD_INTAKE branch must call update_custom_field with ai_mode=lead_intake."""
        cache = MockCache()
        state, mock_seller, mock_buyer, mock_ghl, mock_lead = _make_state(cache=cache)
        mock_ghl.get_contact.return_value = {"tags": [], "customFields": []}
        mock_ghl.update_custom_field = AsyncMock(return_value={"success": True})

        with (
            patch("bots.lead_bot.routes_webhook._get_state", return_value=state),
            patch("bots.lead_bot.routes_webhook.upsert_conversation", new_callable=AsyncMock),
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/api/ghl/webhook",
                    # No bot_type → LEAD_INTAKE path
                    content=json.dumps({"contactId": "lead-ghl", "locationId": "loc-test", "body": "interested"}).encode(),
                    headers={"Content-Type": "application/json"},
                )

        assert r.status_code == 200
        assert r.json()["mode"] == "lead_intake"
        calls = [str(c) for c in mock_ghl.update_custom_field.call_args_list]
        assert any("ai_mode" in c and "lead_intake" in c for c in calls), (
            f"Expected ai_mode=lead_intake GHL sync call, got: {calls}"
        )


# ---------------------------------------------------------------------------
# Fix 2 — buyer-to-seller handoff syncs GHL ai_mode
# ---------------------------------------------------------------------------


class TestBuyerToSellerHandoffGHLSync:
    @pytest.mark.asyncio
    async def test_buyer_to_seller_handoff_syncs_ghl_mode(self):
        """JorgeBuyerBot seller-intent path must sync ai_mode=seller to GHL."""
        from bots.buyer_bot.buyer_bot import JorgeBuyerBot
        from bots.shared.conversation_contract import ConversationMode

        mock_ghl = AsyncMock()
        mock_ghl.update_custom_field = AsyncMock(return_value={"success": True})

        mock_cache = AsyncMock()
        mock_cache.get = AsyncMock(return_value=None)  # cache miss → create state
        mock_cache.set = AsyncMock()
        mock_cache.delete = AsyncMock()

        mock_state = MagicMock()
        mock_state.current_question = 0
        mock_state.scheduling_offered = False

        with (
            patch.object(JorgeBuyerBot, "_get_or_create_state", new=AsyncMock(return_value=mock_state)),
            patch("bots.buyer_bot.buyer_bot.get_cache_service", return_value=mock_cache),
        ):
            bot = JorgeBuyerBot(ghl_client=mock_ghl)
            bot.cache = mock_cache

            result = await bot.process_buyer_message(
                contact_id="buyer-handoff",
                location_id="loc-test",
                message="actually I want to sell my house",
                contact_info={},
            )

        assert "sell" in result.response_message.lower() or "seller" in result.response_message.lower()
        # Must have synced ai_mode=seller to GHL
        calls = [str(c) for c in mock_ghl.update_custom_field.call_args_list]
        assert any("ai_mode" in c and "seller" in c for c in calls), (
            f"Expected ai_mode=seller GHL sync call, got: {calls}"
        )
