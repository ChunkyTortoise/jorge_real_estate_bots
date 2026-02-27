"""Integration smoke tests for auth middleware paths."""

from __future__ import annotations

import os

import pytest
from fastapi.security import HTTPAuthorizationCredentials

from bots.shared import auth_middleware as auth_middleware_module
from bots.shared.auth_middleware import AuthMiddleware


def _require_integration_mode() -> None:
    if os.getenv("RUN_INTEGRATION_TESTS") != "1":
        pytest.skip("Set RUN_INTEGRATION_TESTS=1 to run integration tests")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_auth_middleware_bearer_token_smoke(monkeypatch) -> None:
    """Exercise auth middleware with a bearer token in integration mode."""
    _require_integration_mode()
    monkeypatch.setattr(auth_middleware_module.settings, "environment", "test")

    middleware = AuthMiddleware()
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="test-token")
    user = await middleware.get_current_user(credentials)

    assert user.user_id == "test-user"
    assert user.is_active is True
