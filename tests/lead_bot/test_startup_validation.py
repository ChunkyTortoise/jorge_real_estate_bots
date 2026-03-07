"""T6: Tests for startup environment variable validation in lifespan()."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _patch_settings(env: str = "production", **overrides):
    """Return a mock settings object for startup tests."""
    defaults = {
        "environment": env,
        "anthropic_api_key": "real-key",
        "ghl_api_key": "real-key",
        "ghl_location_id": "real-loc",
        "redis_url": "redis://localhost",
        "admin_api_key": "admin-key",
        "lead_response_timeout_seconds": 300,
        "sentry_dsn": None,
        "ghl_webhook_public_key": None,
        "ghl_webhook_secret": None,
    }
    defaults.update(overrides)
    mock_s = MagicMock()
    for k, v in defaults.items():
        setattr(mock_s, k, v)
    return mock_s


class TestStartupEnvValidation:
    """T6: Lifespan raises RuntimeError in production on missing required env vars."""

    @pytest.mark.asyncio
    async def test_production_raises_on_missing_anthropic_key(self):
        """RuntimeError raised in production when anthropic_api_key is absent."""
        from bots.lead_bot.main import lifespan
        from fastapi import FastAPI

        mock_s = _patch_settings(env="production", anthropic_api_key="")

        with patch("bots.lead_bot.main.settings", mock_s):
            with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
                async with lifespan(FastAPI()):
                    pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_production_raises_on_missing_ghl_api_key(self):
        """RuntimeError raised in production when ghl_api_key is absent."""
        from bots.lead_bot.main import lifespan
        from fastapi import FastAPI

        mock_s = _patch_settings(env="production", ghl_api_key="")

        with patch("bots.lead_bot.main.settings", mock_s):
            with pytest.raises(RuntimeError, match="GHL_API_KEY"):
                async with lifespan(FastAPI()):
                    pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_development_does_not_raise_runtime_error(self):
        """Development mode: missing env vars do not raise RuntimeError."""
        from bots.lead_bot.main import lifespan
        from fastapi import FastAPI

        mock_s = _patch_settings(env="development", anthropic_api_key="")

        # Mock everything that runs after the env check
        with (
            patch("bots.lead_bot.main.settings", mock_s),
            patch("bots.lead_bot.main.LeadAnalyzer"),
            patch("bots.lead_bot.main.get_cache_service", return_value=AsyncMock()),
            patch("bots.lead_bot.main.settings_load", new_callable=AsyncMock),
            patch("bots.lead_bot.main.event_broker") as mock_eb,
            patch("bots.lead_bot.main.websocket_manager") as mock_wm,
            patch("bots.lead_bot.main.JorgeSellerBot"),
            patch("bots.lead_bot.main.JorgeBuyerBot"),
            patch("bots.lead_bot.main.GHLClient"),
            patch("asyncio.create_task"),
        ):
            mock_eb.initialize = AsyncMock()
            mock_wm.initialize = AsyncMock()

            try:
                async with lifespan(FastAPI()):
                    pass
            except RuntimeError as exc:
                pytest.fail(f"RuntimeError must not be raised in development: {exc}")
            except Exception:
                # Other setup errors (unmocked DB, etc.) are acceptable
                pass
