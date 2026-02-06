"""
Root conftest — provides mock async DB session for all tests by default.

Tests marked with @pytest.mark.integration skip the mock and hit real DB.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration (needs DB)")


class _MockResult:
    """Minimal result proxy that returns empty collections."""

    def scalars(self):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def scalar(self):
        return None


def _make_mock_session():
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_MockResult())
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.get = AsyncMock(return_value=None)

    # Support `async with AsyncSessionFactory() as session:`
    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx


_ASYNC_SESSION_FACTORY_LOCATIONS = [
    "database.session.AsyncSessionFactory",
    "database.repository.AsyncSessionFactory",
    "bots.shared.dashboard_data_service.AsyncSessionFactory",
    "bots.shared.metrics_service.AsyncSessionFactory",
    "bots.shared.auth_service.AsyncSessionFactory",
]


@pytest.fixture(autouse=True)
def _patch_async_session_factory(request, monkeypatch):
    """Patch AsyncSessionFactory for all tests unless marked integration."""
    if "integration" in {m.name for m in request.node.iter_markers()}:
        return

    mock_factory = _make_mock_session()
    for location in _ASYNC_SESSION_FACTORY_LOCATIONS:
        try:
            monkeypatch.setattr(location, mock_factory)
        except (AttributeError, ImportError):
            pass  # Module not imported in this test's context
