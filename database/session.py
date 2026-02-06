"""
Async SQLAlchemy session management.
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


async_engine = _build_engine()


AsyncSessionFactory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for async session."""
    async with AsyncSessionFactory() as session:
        yield session
