"""Tests for StallReengagementService."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from bots.shared.stall_reengagement import StallReengagementService, _MESSAGES


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    return redis


@pytest.fixture
def mock_ghl() -> AsyncMock:
    ghl = AsyncMock()
    ghl.send_message = AsyncMock(return_value={"success": True})
    return ghl


@pytest.fixture
def service(mock_redis: AsyncMock, mock_ghl: AsyncMock) -> StallReengagementService:
    svc = StallReengagementService(redis_client=mock_redis, ghl_client=mock_ghl)
    return svc


@pytest.mark.asyncio
async def test_trigger_reengagement_sends_sms(
    service: StallReengagementService,
    mock_redis: AsyncMock,
    mock_ghl: AsyncMock,
) -> None:
    """First attempt should send SMS and store state in Redis."""
    result = await service.trigger_reengagement(
        contact_id="c1",
        stage="Q2",
        name="Alice",
        location_id="loc1",
    )

    assert result is True
    mock_ghl.send_message.assert_awaited_once()
    call_kwargs = mock_ghl.send_message.call_args.kwargs
    assert call_kwargs["contact_id"] == "c1"
    assert "Alice" in call_kwargs["message"]
    assert call_kwargs["message_type"] == "SMS"

    # Should persist attempt to Redis
    mock_redis.set.assert_awaited_once()
    stored = json.loads(mock_redis.set.call_args.args[1])
    assert stored["attempts"] == 1
    assert stored["last_sent"] is not None


@pytest.mark.asyncio
async def test_trigger_reengagement_respects_attempt_limit(
    service: StallReengagementService,
    mock_redis: AsyncMock,
    mock_ghl: AsyncMock,
) -> None:
    """Should return False when MAX_ATTEMPTS already reached."""
    mock_redis.get.return_value = json.dumps({
        "attempts": 2,
        "last_sent": (datetime.now(timezone.utc) - timedelta(hours=100)).isoformat(),
    })

    result = await service.trigger_reengagement(
        contact_id="c2",
        stage="Q1",
        name="Bob",
        location_id="loc1",
    )

    assert result is False
    mock_ghl.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_reengagement_respects_time_limit(
    service: StallReengagementService,
    mock_redis: AsyncMock,
    mock_ghl: AsyncMock,
) -> None:
    """Should return False if last attempt was less than MIN_HOURS_BETWEEN ago."""
    mock_redis.get.return_value = json.dumps({
        "attempts": 1,
        "last_sent": (datetime.now(timezone.utc) - timedelta(hours=10)).isoformat(),
    })

    result = await service.trigger_reengagement(
        contact_id="c3",
        stage="Q0",
        name="Carol",
        location_id="loc1",
    )

    assert result is False
    mock_ghl.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_trigger_reengagement_allows_after_cooldown(
    service: StallReengagementService,
    mock_redis: AsyncMock,
    mock_ghl: AsyncMock,
) -> None:
    """Should allow second attempt after cooldown period."""
    mock_redis.get.return_value = json.dumps({
        "attempts": 1,
        "last_sent": (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat(),
    })

    result = await service.trigger_reengagement(
        contact_id="c4",
        stage="Q4",
        name="Dave",
        location_id="loc1",
    )

    assert result is True
    mock_ghl.send_message.assert_awaited_once()
    stored = json.loads(mock_redis.set.call_args.args[1])
    assert stored["attempts"] == 2


@pytest.mark.asyncio
async def test_trigger_reengagement_unknown_stage_falls_back(
    service: StallReengagementService,
    mock_ghl: AsyncMock,
) -> None:
    """Unknown stage should use Q0 template."""
    await service.trigger_reengagement(
        contact_id="c5",
        stage="UNKNOWN",
        name="Eve",
        location_id="loc1",
    )

    call_kwargs = mock_ghl.send_message.call_args.kwargs
    expected = _MESSAGES["Q0"].format(name="Eve", address="your property")
    assert call_kwargs["message"] == expected


@pytest.mark.asyncio
async def test_trigger_reengagement_with_address(
    service: StallReengagementService,
    mock_ghl: AsyncMock,
) -> None:
    """Q3 template should include the address."""
    await service.trigger_reengagement(
        contact_id="c6",
        stage="Q3",
        name="Frank",
        location_id="loc1",
        address="123 Main St",
    )

    call_kwargs = mock_ghl.send_message.call_args.kwargs
    assert "123 Main St" in call_kwargs["message"]


@pytest.mark.asyncio
async def test_trigger_reengagement_ghl_failure(
    service: StallReengagementService,
    mock_redis: AsyncMock,
    mock_ghl: AsyncMock,
) -> None:
    """Should return False and not update Redis when GHL send fails."""
    mock_ghl.send_message.side_effect = Exception("GHL down")

    result = await service.trigger_reengagement(
        contact_id="c7",
        stage="Q1",
        name="Grace",
        location_id="loc1",
    )

    assert result is False
    mock_redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_record_reply(
    service: StallReengagementService,
    mock_redis: AsyncMock,
) -> None:
    """record_reply should set a reply key in Redis."""
    await service.record_reply("c8")

    mock_redis.set.assert_awaited_once()
    args = mock_redis.set.call_args
    assert args.args[0] == "stall_reply:c8"
    assert args.args[1] == "1"
    assert args.kwargs["ex"] == 86400 * 7


def _async_iter(items):
    """Return an async iterator from a list (for mocking scan_iter)."""
    async def _gen():
        for item in items:
            yield item
    return _gen()


@pytest.mark.asyncio
async def test_get_stats(
    service: StallReengagementService,
    mock_redis: AsyncMock,
) -> None:
    """get_stats should aggregate attempt counts and reply rate."""
    call_count = [0]

    def _scan_iter_side_effect(**kwargs):
        match = kwargs.get("match", "")
        if "stall_reengagement" in match:
            return _async_iter(["stall_reengagement:c1", "stall_reengagement:c2"])
        return _async_iter(["stall_reply:c1"])

    mock_redis.scan_iter = _scan_iter_side_effect
    mock_redis.get.side_effect = [
        json.dumps({"attempts": 2, "last_sent": "2026-01-01T00:00:00+00:00"}),
        json.dumps({"attempts": 1, "last_sent": "2026-01-02T00:00:00+00:00"}),
    ]

    stats = await service.get_stats()

    assert stats["total_contacts_reached"] == 2
    assert stats["total_attempts"] == 3
    assert stats["replies"] == 1
    assert stats["reply_rate"] == 0.5


@pytest.mark.asyncio
async def test_get_stats_empty(
    service: StallReengagementService,
    mock_redis: AsyncMock,
) -> None:
    """get_stats with no data should return zeros."""
    mock_redis.scan_iter = lambda **kwargs: _async_iter([])

    stats = await service.get_stats()

    assert stats["total_contacts_reached"] == 0
    assert stats["total_attempts"] == 0
    assert stats["replies"] == 0
    assert stats["reply_rate"] == 0.0


# ---------------------------------------------------------------------------
# T4: Opt-out keyword detection, recording, and lookup
# ---------------------------------------------------------------------------

class TestOptOut:
    """T4: is_opt_out_message, record_opt_out, is_opted_out."""

    # -- is_opt_out_message --------------------------------------------------

    @pytest.mark.parametrize("text", ["stop", "STOP", "Stop", "unsubscribe", "opt out", "optout", "cancel", "quit"])
    def test_opt_out_keywords_return_true(self, text: str, service: StallReengagementService) -> None:
        assert service.is_opt_out_message(text) is True

    @pytest.mark.parametrize("text", ["hello", "yes", "no thanks", "stop it please", "stopping by"])
    def test_non_opt_out_returns_false(self, text: str, service: StallReengagementService) -> None:
        assert service.is_opt_out_message(text) is False

    def test_opt_out_strips_whitespace(self, service: StallReengagementService) -> None:
        assert service.is_opt_out_message("  stop  ") is True

    # -- record_opt_out ------------------------------------------------------

    @pytest.mark.asyncio
    async def test_record_opt_out_sets_redis_key(
        self, service: StallReengagementService, mock_redis: AsyncMock
    ) -> None:
        await service.record_opt_out("contact-99")

        mock_redis.set.assert_awaited_once()
        args = mock_redis.set.call_args
        assert args.args[0] == "stall_optout:contact-99"
        assert args.args[1] == "1"
        assert args.kwargs["ex"] == 86400 * 365

    # -- is_opted_out --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_is_opted_out_true_for_string_one(
        self, service: StallReengagementService, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = "1"
        assert await service.is_opted_out("contact-99") is True

    @pytest.mark.asyncio
    async def test_is_opted_out_true_for_bytes_one(
        self, service: StallReengagementService, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = b"1"
        assert await service.is_opted_out("contact-99") is True

    @pytest.mark.asyncio
    async def test_is_opted_out_false_for_none(
        self, service: StallReengagementService, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = None
        assert await service.is_opted_out("contact-99") is False

    @pytest.mark.asyncio
    async def test_is_opted_out_false_for_other_value(
        self, service: StallReengagementService, mock_redis: AsyncMock
    ) -> None:
        mock_redis.get.return_value = '{"attempts": 1}'
        assert await service.is_opted_out("contact-99") is False

    # -- opted-out contact skipped by trigger_reengagement -------------------

    @pytest.mark.asyncio
    async def test_trigger_skips_opted_out_contact(
        self, service: StallReengagementService, mock_redis: AsyncMock, mock_ghl: AsyncMock
    ) -> None:
        """trigger_reengagement returns False without sending SMS when opted out."""
        # get() for opt-out key returns "1"; get() for reengagement data returns None
        async def _get(key):
            if "stall_optout" in key:
                return "1"
            return None

        mock_redis.get = AsyncMock(side_effect=_get)

        result = await service.trigger_reengagement(
            contact_id="opted-out-contact",
            stage="Q1",
            name="Jane",
            location_id="loc1",
        )

        assert result is False
        mock_ghl.send_message.assert_not_awaited()
