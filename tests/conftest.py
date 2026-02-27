"""
Root conftest — provides mock async DB session for all tests by default.

Tests marked with @pytest.mark.integration skip the mock and hit real DB.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

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
