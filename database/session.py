"""
Async SQLAlchemy session management.

Engine and session factory are lazy-initialized so that importing this
module does not require a running database (important for tests).
"""
from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bots.shared.config import settings


def _make_async_database_url(url: str) -> str:
    """Convert sync DB URL to async if needed."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


ASYNC_DATABASE_URL = _make_async_database_url(settings.database_url)

_async_engine = None
_session_factory = None


def _build_engine():
    if ASYNC_DATABASE_URL.startswith("sqlite"):
        return create_async_engine(
            ASYNC_DATABASE_URL,
            echo=False,
            future=True,
        )
    return create_async_engine(
        ASYNC_DATABASE_URL,
        echo=False,
        future=True,
        pool_size=10,
        max_overflow=0,
        pool_pre_ping=True,
        pool_timeout=30,
    )


def _get_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = _build_engine()
    return _async_engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


# Keep the same call interface: AsyncSessionFactory() returns an AsyncSession
def AsyncSessionFactory():  # noqa: N802
    return _get_session_factory()()


# For backward compat with `from database import async_engine`
def __getattr__(name):
    if name == "async_engine":
        return _get_engine()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async session."""
    async with AsyncSessionFactory() as session:
        yield session
