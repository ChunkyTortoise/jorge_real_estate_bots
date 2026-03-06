"""Unit tests for bots.shared.auth_middleware.AuthMiddleware."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bots.shared.auth_service import User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(role=UserRole.ADMIN, is_active=True) -> User:
    return User(
        user_id="u1",
        email="test@test.com",
        name="Test",
        role=role,
        created_at=datetime.now(),
        is_active=is_active,
    )


def _make_credentials(token: str = "valid-token"):
    cred = MagicMock()
    cred.credentials = token
    return cred


# ---------------------------------------------------------------------------
# get_current_user
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_missing_credentials_raises_401(self):
        from bots.shared.auth_middleware import AuthMiddleware

        with patch("bots.shared.auth_middleware.get_auth_service"):
            mw = AuthMiddleware()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mw.get_current_user(None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_raises_401(self):
        from bots.shared.auth_middleware import AuthMiddleware

        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=None)
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth):
            mw = AuthMiddleware()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mw.get_current_user(_make_credentials("bad-token"))
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_valid_token_returns_user(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user()
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=1)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth):
            mw = AuthMiddleware()
        result = await mw.get_current_user(_make_credentials())
        assert result.user_id == "u1"

    @pytest.mark.asyncio
    async def test_test_token_in_test_env(self):
        from bots.shared.auth_middleware import AuthMiddleware

        mock_auth = MagicMock()
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth), \
             patch("bots.shared.auth_middleware.settings") as mock_settings:
            mock_settings.environment = "test"
            mock_settings.rate_limit_per_minute = 0
            mock_settings.rate_limit_per_hour = 0
            mw = AuthMiddleware()
        result = await mw.get_current_user(_make_credentials("test-token"))
        assert result.user_id == "test-user"
        assert result.role == UserRole.ADMIN


# ---------------------------------------------------------------------------
# get_current_active_user
# ---------------------------------------------------------------------------

class TestGetCurrentActiveUser:
    @pytest.mark.asyncio
    async def test_active_user_passes(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user(is_active=True)
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=1)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth):
            mw = AuthMiddleware()
        result = await mw.get_current_active_user(_make_credentials())
        assert result.is_active is True

    @pytest.mark.asyncio
    async def test_inactive_user_raises_400(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user(is_active=False)
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=1)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth):
            mw = AuthMiddleware()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mw.get_current_active_user(_make_credentials())
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_user_object_direct_pass(self):
        """Backward compat: passing a User object directly works."""
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user()
        with patch("bots.shared.auth_middleware.get_auth_service"):
            mw = AuthMiddleware()
        result = await mw.get_current_active_user(user)
        assert result.user_id == "u1"


# ---------------------------------------------------------------------------
# get_admin_user
# ---------------------------------------------------------------------------

class TestGetAdminUser:
    @pytest.mark.asyncio
    async def test_admin_passes(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user(role=UserRole.ADMIN)
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=1)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth):
            mw = AuthMiddleware()
        result = await mw.get_admin_user(_make_credentials())
        assert result.role == UserRole.ADMIN

    @pytest.mark.asyncio
    async def test_non_admin_raises_403(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user(role=UserRole.VIEWER)
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=1)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth):
            mw = AuthMiddleware()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mw.get_admin_user(_make_credentials())
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    @pytest.mark.asyncio
    async def test_minute_rate_limit_exceeded(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user()
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=999)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth), \
             patch("bots.shared.auth_middleware.settings") as mock_settings:
            mock_settings.environment = "production"
            mock_settings.rate_limit_per_minute = 60
            mock_settings.rate_limit_per_hour = 1000
            mw = AuthMiddleware()
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await mw.get_current_user(_make_credentials())
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_no_rate_limit_when_disabled(self):
        from bots.shared.auth_middleware import AuthMiddleware

        user = _make_user()
        mock_auth = MagicMock()
        mock_auth.validate_token = AsyncMock(return_value=user)
        mock_cache = MagicMock()
        mock_cache.increment = AsyncMock(return_value=1)
        mock_auth.cache_service = mock_cache
        with patch("bots.shared.auth_middleware.get_auth_service", return_value=mock_auth), \
             patch("bots.shared.auth_middleware.settings") as mock_settings:
            mock_settings.environment = "test"
            mock_settings.rate_limit_per_minute = 0
            mock_settings.rate_limit_per_hour = 0
            mw = AuthMiddleware()
        result = await mw.get_current_user(_make_credentials())
        assert result.user_id == "u1"


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

class TestModuleHelpers:
    def test_get_current_user_returns_callable(self):
        from bots.shared.auth_middleware import get_current_user
        assert callable(get_current_user())

    def test_get_current_active_user_returns_callable(self):
        from bots.shared.auth_middleware import get_current_active_user
        assert callable(get_current_active_user())

    def test_get_admin_user_returns_callable(self):
        from bots.shared.auth_middleware import get_admin_user
        assert callable(get_admin_user())

    def test_require_permission_returns_callable(self):
        from bots.shared.auth_middleware import require_permission
        assert callable(require_permission("dashboard", "read"))
