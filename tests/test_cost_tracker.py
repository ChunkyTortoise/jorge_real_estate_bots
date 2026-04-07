"""Tests for bots.shared.cost_tracker."""
import pytest
from datetime import datetime, timezone

from bots.shared.cache_service import MemoryCache
from bots.shared.cost_tracker import CostRecord, CostTracker


@pytest.fixture
def tracker(monkeypatch):
    """CostTracker backed by a fresh MemoryCache."""
    t = CostTracker()
    t.cache_service = MemoryCache()
    return t


def _make_record(
    model="claude-sonnet-4-5-20250514",
    input_tokens=1000,
    output_tokens=500,
    bot_type="lead",
    request_id="req-1",
) -> CostRecord:
    cost = CostTracker.calculate_cost(model, input_tokens, output_tokens)
    return CostRecord(
        request_id=request_id,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        bot_type=bot_type,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_record_stores_in_redis(tracker):
    """record() persists data retrievable by get_summary()."""
    record = _make_record()
    await tracker.record(record)

    day_key = f"cost:{record.timestamp.strftime('%Y-%m-%d')}"
    stored = await tracker.cache_service.get(day_key)
    assert stored is not None
    assert len(stored) == 1
    assert stored[0]["request_id"] == "req-1"
    assert stored[0]["model"] == "claude-sonnet-4-5-20250514"


@pytest.mark.asyncio
async def test_get_summary_returns_all_fields(tracker):
    """get_summary() returns total_cost, request_count, by_model, by_bot, per_request_average."""
    await tracker.record(_make_record(bot_type="seller", request_id="r1"))
    await tracker.record(_make_record(bot_type="buyer", request_id="r2"))

    summary = await tracker.get_summary("24h")

    assert summary["period"] == "24h"
    assert summary["request_count"] == 2
    assert summary["total_cost"] > 0
    assert "claude-sonnet-4-5-20250514" in summary["by_model"]
    assert "seller" in summary["by_bot"]
    assert "buyer" in summary["by_bot"]
    assert summary["per_request_average"] > 0


@pytest.mark.asyncio
async def test_cost_calculation_haiku(tracker):
    """Haiku pricing: $0.80/M input, $4.00/M output."""
    cost = CostTracker.calculate_cost("claude-haiku-4-5-20251001", 1_000_000, 1_000_000)
    # 1M input * 0.80 + 1M output * 4.00 = 4.80
    assert abs(cost - 4.80) < 0.0001


@pytest.mark.asyncio
async def test_cost_calculation_sonnet(tracker):
    """Sonnet pricing: $3.00/M input, $15.00/M output."""
    cost = CostTracker.calculate_cost("claude-sonnet-4-5-20250514", 1_000_000, 1_000_000)
    # 1M input * 3.0 + 1M output * 15.0 = 18.0
    assert abs(cost - 18.0) < 0.0001


@pytest.mark.asyncio
async def test_empty_period_returns_zero(tracker):
    """get_summary() with no records returns zeroed fields."""
    summary = await tracker.get_summary("24h")

    assert summary["total_cost"] == 0.0
    assert summary["request_count"] == 0
    assert summary["by_model"] == {}
    assert summary["by_bot"] == {}
    assert summary["per_request_average"] == 0.0
