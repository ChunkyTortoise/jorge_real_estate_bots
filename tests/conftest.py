"""
Root conftest — provides mock async DB session for all tests by default.

Tests marked with @pytest.mark.integration skip the mock and hit real DB.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from bots.shared.rate_limit_middleware import _memory_counters
from bots.shared.cache_service import CacheService

from database.base import Base
from database import billing_models  # noqa: F401
from database import session as db_session_module


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

    def scalar_one(self):
        return 0


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
    "bots.lead_bot.routes_dashboard.AsyncSessionFactory",
    "bots.shared.dashboard_data_service.AsyncSessionFactory",
    "bots.shared.metrics_service.AsyncSessionFactory",
    "bots.shared.auth_service.AsyncSessionFactory",
]


def _clear_cache_backend_storage(backend) -> None:
    """Clear real in-memory cache storage, but ignore mocked backends."""
    cache = getattr(backend, "_cache", None)
    expiry = getattr(backend, "_expiry", None)
    if isinstance(cache, dict):
        cache.clear()
    if isinstance(expiry, dict):
        expiry.clear()


@pytest.fixture(autouse=True)
def _clear_rate_limit_counters():
    """Clear in-memory rate limit counters before/after each test to prevent bleed."""
    _memory_counters.clear()
    # Also clear the CacheService singleton's MemoryCache to prevent rate-limit bleed
    if CacheService._instance is not None:
        svc = CacheService._instance
        _clear_cache_backend_storage(getattr(svc, "backend", None))
        _clear_cache_backend_storage(getattr(svc, "fallback_backend", None))
    yield
    _memory_counters.clear()
    if CacheService._instance is not None:
        svc = CacheService._instance
        _clear_cache_backend_storage(getattr(svc, "backend", None))
        _clear_cache_backend_storage(getattr(svc, "fallback_backend", None))


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


@pytest.fixture
async def db_session():
    """Provide an isolated async SQLite session for tests that need real ORM behavior."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    billing_tables = [
        billing_models.AgencyModel.__table__,
        billing_models.SubscriptionModel.__table__,
        billing_models.UsageRecordModel.__table__,
        billing_models.WhiteLabelConfigModel.__table__,
        billing_models.InvoiceModel.__table__,
        billing_models.WebhookEventModel.__table__,
        billing_models.OnboardingStateModel.__table__,
    ]

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=billing_tables))

    Session = async_sessionmaker(bind=engine, expire_on_commit=False)

    prev_engine = db_session_module._async_engine
    prev_factory = db_session_module._session_factory
    db_session_module._async_engine = engine
    db_session_module._session_factory = Session

    async with Session() as session:
        original_execute = session.execute

        async def _execute_with_refresh(*args, **kwargs):
            session.sync_session.expire_all()
            return await original_execute(*args, **kwargs)

        session.execute = _execute_with_refresh
        yield session

    db_session_module._async_engine = prev_engine
    db_session_module._session_factory = prev_factory

    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.drop_all(sync_conn, tables=billing_tables))
    await engine.dispose()
