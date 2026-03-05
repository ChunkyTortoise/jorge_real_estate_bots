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
    mock_ghl.send_message = AsyncMock()
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
        """First webhook for a contact stores its bot type in the cache."""
        cache = MockCache()
        state, _, _, _, _ = _make_state(cache=cache)
        with patch("bots.lead_bot.routes_webhook._get_state", return_value=state):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                await c.post(
                    "/api/ghl/webhook",
                    content=_body(bot_type="seller", contact_id="assign-new"),
                    headers={"Content-Type": "application/json"},
                )
        assert await cache.get("assigned_bot:assign-new") == "seller"

    @pytest.mark.asyncio
    async def test_bot_assignment_exclusivity(self, app):
        """
        Contact pre-assigned to buyer.
        Payload without explicit bot_type (GHL API returns nothing) → buyer honoured.
        """
        cache = MockCache()
        await cache.set("assigned_bot:excl-c", "buyer", ttl=604800)
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
        await cache.set("assigned_bot:switch-c", "buyer", ttl=604800)
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
        assert await cache.get("assigned_bot:switch-c") == "seller"


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
    async def test_new_lead_sets_assigned_bot_in_redis(self, app):
        """POST /ghl/webhook/new-lead must write assigned_bot:<id>='lead' to cache."""
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
        assert await cache.get("assigned_bot:lock-lead-1") == "lead"

    @pytest.mark.asyncio
    async def test_new_lead_then_reply_stays_on_lead_bot(self, app):
        """
        Contact created via new-lead → assigned_bot='lead'.
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
# _normalize_bot_type unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        # Canonical values
        ("seller", "seller"),
        ("buyer", "buyer"),
        ("lead", "lead"),
        # Case variants
        ("Seller", "seller"),
        ("SELLER", "seller"),
        ("Buyer", "buyer"),
        # Known variant aliases
        ("seller_bot", "seller"),
        ("seller-bot", "seller"),
        ("SELLER_BOT", "seller"),
        ("buyer_bot", "buyer"),
        ("buyer-bot", "buyer"),
        ("new_lead", "lead"),
        ("new-lead", "lead"),
        ("lead_bot", "lead"),
        # Empty / unknown → "lead"
        ("", "lead"),
        ("unknown", "lead"),
        ("foobar", "lead"),
    ],
)
def test_normalize_bot_type(raw: str, expected: str) -> None:
    from bots.lead_bot.routes_webhook import _normalize_bot_type

    assert _normalize_bot_type(raw) == expected
