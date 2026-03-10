"""TCPA opt-out tests — verify raw Redis set() is called with ex= TTL."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_record_opt_out_calls_redis_set_with_ttl():
    """StallReengagementService.record_opt_out must use raw Redis ex= kwarg (not CacheService.set)."""
    from bots.shared.stall_reengagement import StallReengagementService

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)

    srs = StallReengagementService(redis_client=mock_redis)
    await srs.record_opt_out("contact_123")

    mock_redis.set.assert_called_once_with(
        "stall_optout:contact_123", "1", ex=86400 * 365
    )


@pytest.mark.asyncio
async def test_is_opted_out_returns_true_after_record():
    """After record_opt_out, is_opted_out must return True."""
    from bots.shared.stall_reengagement import StallReengagementService

    store: dict = {}

    async def mock_set(key, value, **kwargs):
        store[key] = value

    async def mock_get(key):
        return store.get(key)

    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(side_effect=mock_set)
    mock_redis.get = AsyncMock(side_effect=mock_get)

    srs = StallReengagementService(redis_client=mock_redis)
    await srs.record_opt_out("contact_456")
    result = await srs.is_opted_out("contact_456")
    assert result is True


@pytest.mark.asyncio
async def test_opt_out_not_dropped_when_ex_kwarg_used():
    """Confirm CacheService.set() signature WOULD fail — raw Redis must be used."""
    # CacheService.set signature is set(key, value, ttl=300) — no ex= kwarg
    # This test documents the bug and verifies the fix path
    from bots.shared.cache_service import CacheService

    cache = CacheService.__new__(CacheService)

    import inspect
    sig = inspect.signature(cache.set)
    param_names = list(sig.parameters.keys())
    # CacheService.set uses 'ttl', not 'ex' — passing ex= would raise TypeError
    assert "ttl" in param_names
    assert "ex" not in param_names
