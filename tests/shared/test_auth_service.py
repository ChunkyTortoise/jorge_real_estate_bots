"""Unit tests for bots.shared.auth_service.AuthService."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import jwt
import pytest

from bots.shared.auth_service import AuthService, AuthToken, User, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_auth_service(secret: str = "test-secret-key-for-jwt") -> AuthService:
    """Create an AuthService with a known secret for deterministic tokens."""
    mock_cache = MagicMock()
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock()
    mock_cache.increment = AsyncMock(return_value=1)

    with patch("bots.shared.auth_service.get_cache_service", return_value=mock_cache), \
         patch("bots.shared.auth_service.settings") as mock_settings, \
         patch.dict("os.environ", {"JWT_SECRET": secret}):
        mock_settings.jwt_secret = secret
        mock_settings.environment = "test"
        svc = AuthService()
    return svc


def _make_user(role=UserRole.ADMIN, is_active=True) -> User:
    return User(
        user_id="u1",
        email="test@test.com",
        name="Test User",
        role=role,
        created_at=datetime.now(timezone.utc),
        is_active=is_active,
    )


# ---------------------------------------------------------------------------
# Token generation
# ---------------------------------------------------------------------------

class TestTokenGeneration:
    @pytest.mark.asyncio
    async def test_generates_access_and_refresh(self):
        svc = _make_auth_service()
        user = _make_user()
        tokens = await svc._generate_tokens(user)
        assert isinstance(tokens, AuthToken)
        assert tokens.access_token
        assert tokens.refresh_token
        assert tokens.token_type == "Bearer"
        assert tokens.expires_in == 30 * 60

    @pytest.mark.asyncio
    async def test_access_token_contains_user_info(self):
        svc = _make_auth_service()
        user = _make_user()
        tokens = await svc._generate_tokens(user)
        payload = jwt.decode(tokens.access_token, svc.secret_key, algorithms=["HS256"])
        assert payload["user_id"] == "u1"
        assert payload["email"] == "test@test.com"
        assert payload["role"] == "admin"
        assert payload["token_type"] == "access"

    @pytest.mark.asyncio
    async def test_refresh_token_type(self):
        svc = _make_auth_service()
        user = _make_user()
        tokens = await svc._generate_tokens(user)
        payload = jwt.decode(tokens.refresh_token, svc.secret_key, algorithms=["HS256"])
        assert payload["token_type"] == "refresh"

    @pytest.mark.asyncio
    async def test_access_token_expiry(self):
        svc = _make_auth_service()
        user = _make_user()
        tokens = await svc._generate_tokens(user)
        payload = jwt.decode(tokens.access_token, svc.secret_key, algorithms=["HS256"])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        iat = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        delta = exp - iat
        assert abs(delta.total_seconds() - 30 * 60) < 5


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------

class TestTokenValidation:
    @pytest.mark.asyncio
    async def test_valid_token(self):
        svc = _make_auth_service()
        user = _make_user()
        tokens = await svc._generate_tokens(user)

        with patch.object(svc, "get_user_by_id", new_callable=AsyncMock, return_value=user):
            result = await svc.validate_token(tokens.access_token)
        assert result is not None
        assert result.user_id == "u1"

    @pytest.mark.asyncio
    async def test_expired_token(self):
        svc = _make_auth_service()
        payload = {
            "user_id": "u1",
            "email": "test@test.com",
            "role": "admin",
            "token_type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
        }
        token = jwt.encode(payload, svc.secret_key, algorithm="HS256")
        result = await svc.validate_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_signature(self):
        svc = _make_auth_service()
        payload = {
            "user_id": "u1",
            "token_type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        result = await svc.validate_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_missing_user_id(self):
        svc = _make_auth_service()
        payload = {
            "email": "test@test.com",
            "token_type": "access",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, svc.secret_key, algorithm="HS256")
        result = await svc.validate_token(token)
        assert result is None

    @pytest.mark.asyncio
    async def test_inactive_user_returns_none(self):
        svc = _make_auth_service()
        user = _make_user(is_active=False)
        tokens = await svc._generate_tokens(user)

        with patch.object(svc, "get_user_by_id", new_callable=AsyncMock, return_value=user):
            result = await svc.validate_token(tokens.access_token)
        assert result is None

    @pytest.mark.asyncio
    async def test_user_not_found_returns_none(self):
        svc = _make_auth_service()
        user = _make_user()
        tokens = await svc._generate_tokens(user)

        with patch.object(svc, "get_user_by_id", new_callable=AsyncMock, return_value=None):
            result = await svc.validate_token(tokens.access_token)
        assert result is None


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

_bcrypt_broken = False
try:
    from passlib.context import CryptContext
    CryptContext(schemes=["bcrypt"], deprecated="auto").hash("test")
except Exception:
    _bcrypt_broken = True


@pytest.mark.skipif(_bcrypt_broken, reason="passlib/bcrypt incompatible on this Python")
class TestPasswordHashing:
    def test_hash_and_verify(self):
        svc = _make_auth_service()
        hashed = svc._hash_password("secure-password-123")
        assert svc._verify_password("secure-password-123", hashed)

    def test_wrong_password_fails(self):
        svc = _make_auth_service()
        hashed = svc._hash_password("correct-password")
        assert not svc._verify_password("wrong-password", hashed)

    def test_long_password_truncated(self):
        svc = _make_auth_service()
        long_pw = "a" * 200
        hashed = svc._hash_password(long_pw)
        # bcrypt truncates at 72 bytes, our code pre-truncates
        assert svc._verify_password(long_pw, hashed)


# ---------------------------------------------------------------------------
# Permissions
# ---------------------------------------------------------------------------

class TestPermissions:
    @pytest.mark.asyncio
    async def test_admin_has_all_permissions(self):
        svc = _make_auth_service()
        user = _make_user(role=UserRole.ADMIN)
        assert await svc.check_permission(user, "anything", "delete") is True

    @pytest.mark.asyncio
    async def test_agent_can_read_dashboard(self):
        svc = _make_auth_service()
        user = _make_user(role=UserRole.AGENT)
        assert await svc.check_permission(user, "dashboard", "read") is True

    @pytest.mark.asyncio
    async def test_agent_cannot_access_settings(self):
        svc = _make_auth_service()
        user = _make_user(role=UserRole.AGENT)
        assert await svc.check_permission(user, "settings", "write") is False

    @pytest.mark.asyncio
    async def test_viewer_read_only(self):
        svc = _make_auth_service()
        user = _make_user(role=UserRole.VIEWER)
        assert await svc.check_permission(user, "leads", "read") is True
        assert await svc.check_permission(user, "leads", "write") is False

    @pytest.mark.asyncio
    async def test_viewer_no_commission_access(self):
        svc = _make_auth_service()
        user = _make_user(role=UserRole.VIEWER)
        assert await svc.check_permission(user, "commission", "read") is False


# ---------------------------------------------------------------------------
# Token hash
# ---------------------------------------------------------------------------

class TestTokenHash:
    def test_deterministic(self):
        svc = _make_auth_service()
        h1 = svc._hash_token("my-token")
        h2 = svc._hash_token("my-token")
        assert h1 == h2

    def test_different_tokens_different_hashes(self):
        svc = _make_auth_service()
        assert svc._hash_token("token-a") != svc._hash_token("token-b")


# ---------------------------------------------------------------------------
# Secret key
# ---------------------------------------------------------------------------

class TestSecretKey:
    def test_uses_configured_secret(self):
        svc = _make_auth_service(secret="my-custom-secret")
        assert svc.secret_key == "my-custom-secret"

    def test_test_env_generates_ephemeral(self):
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        mock_cache.set = AsyncMock()
        with patch("bots.shared.auth_service.get_cache_service", return_value=mock_cache), \
             patch("bots.shared.auth_service.settings") as mock_settings, \
             patch.dict("os.environ", {}, clear=False):
            mock_settings.jwt_secret = ""
            mock_settings.environment = "test"
            # Remove JWT_SECRET from env if present
            import os
            old = os.environ.pop("JWT_SECRET", None)
            try:
                svc = AuthService()
                assert svc.secret_key  # Non-empty
            finally:
                if old is not None:
                    os.environ["JWT_SECRET"] = old
