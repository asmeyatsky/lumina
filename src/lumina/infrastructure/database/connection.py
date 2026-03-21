"""
Database Connection Management

Provides async SQLAlchemy engine and session factory with connection pooling.
DATABASE_URL is read from the environment variable LUMINA_DATABASE_URL.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

DATABASE_URL: str = os.environ.get(
    "LUMINA_DATABASE_URL",
    "postgresql+asyncpg://lumina:lumina@localhost:5432/lumina",
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(url: str | None = None) -> AsyncEngine:
    """Return the singleton async engine, creating it on first call.

    Args:
        url: Optional override for the database URL.  Falls back to
             the ``LUMINA_DATABASE_URL`` environment variable.
    """
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            url or DATABASE_URL,
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            echo=False,
        )
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return the singleton session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=engine or get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session(engine: AsyncEngine | None = None) -> AsyncIterator[AsyncSession]:
    """Async context manager that yields a scoped session.

    Usage::

        async with get_session() as session:
            result = await session.execute(...)
    """
    factory = get_session_factory(engine)
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the engine and reset singletons.  Call on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
