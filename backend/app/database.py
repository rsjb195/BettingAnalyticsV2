"""
Database engine, session factories, and base model for SQLAlchemy ORM.

Provides both async (for FastAPI) and sync (for scripts/migrations) engines.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import get_settings

logger = logging.getLogger(__name__)

# Naming convention for constraints — ensures Alembic auto-generates
# deterministic, readable migration names.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base with shared metadata naming convention."""

    metadata = MetaData(naming_convention=convention)


def get_async_engine():
    """Create the async SQLAlchemy engine."""
    settings = get_settings()
    return create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        echo=(settings.log_level == "DEBUG"),
    )


def get_sync_engine():
    """Create the synchronous SQLAlchemy engine (for scripts and migrations)."""
    settings = get_settings()
    return create_engine(
        settings.database_url_sync,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        echo=(settings.log_level == "DEBUG"),
    )


# Lazy-initialised module-level engines and session factories.
_async_engine = None
_sync_engine = None
_async_session_factory = None
_sync_session_factory = None


def _init_async():
    global _async_engine, _async_session_factory
    if _async_engine is None:
        _async_engine = get_async_engine()
        _async_session_factory = async_sessionmaker(
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )


def _init_sync():
    global _sync_engine, _sync_session_factory
    if _sync_engine is None:
        _sync_engine = get_sync_engine()
        _sync_session_factory = sessionmaker(bind=_sync_engine)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async session with auto-rollback on error."""
    _init_async()
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def async_session_ctx() -> AsyncGenerator[AsyncSession, None]:
    """Standalone async context manager for use outside FastAPI request cycle."""
    _init_async()
    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_sync_session() -> Session:
    """Return a synchronous session for scripts."""
    _init_sync()
    return _sync_session_factory()


async def create_all_tables():
    """Create all tables from ORM metadata. Used in development only."""
    _init_async()
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("All database tables created successfully.")


async def drop_all_tables():
    """Drop all tables. DANGEROUS — development only."""
    _init_async()
    async with _async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All database tables dropped.")
