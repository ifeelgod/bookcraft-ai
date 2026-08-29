"""
SQLAlchemy 2.0 Async Base and Engine Configuration.
Supports PostgreSQL (asyncpg) with automatic fallback / support for SQLite (aiosqlite).
"""
from __future__ import annotations
import logging
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger("bookcraft.db")


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.0 models."""
    pass


def normalize_database_url(url: str) -> str:
    """Ensure database URL has appropriate async driver scheme."""
    if not url:
        return "sqlite+aiosqlite:///./bookcraft.db"
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


def create_engine_and_factory() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create async engine and session factory with appropriate connection options."""
    db_url = normalize_database_url(settings.DATABASE_URL)
    connect_args: dict[str, Any] = {}
    engine_kwargs: dict[str, Any] = {
        "echo": settings.DB_ECHO,
        "future": True,
    }

    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        engine_kwargs["connect_args"] = connect_args
    else:
        # PostgreSQL connection pool settings
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 20
        engine_kwargs["pool_pre_ping"] = True

    try:
        engine = create_async_engine(db_url, **engine_kwargs)
        logger.info(f"Configured async database engine with URL schema: {db_url.split('://')[0]}://...")
    except Exception as exc:
        logger.warning(
            f"Failed to initialize database engine for '{db_url}': {exc}. "
            "Falling back to local SQLite aiosqlite engine."
        )
        db_url = "sqlite+aiosqlite:///./bookcraft.db"
        connect_args = {"check_same_thread": False}
        engine = create_async_engine(db_url, connect_args=connect_args, echo=settings.DB_ECHO, future=True)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    return engine, session_factory


engine, async_session_factory = create_engine_and_factory()


async def init_db() -> None:
    """Initialize database tables on application startup."""
    try:
        # Import models so all tables are registered with Base.metadata
        import app.db.models  # noqa: F401

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/initialized successfully.")
    except Exception as exc:
        logger.error(f"Error initializing database tables: {exc}", exc_info=True)


async def close_db() -> None:
    """Close and dispose database engine pools."""
    try:
        await engine.dispose()
        logger.info("Database connection pool disposed.")
    except Exception as exc:
        logger.error(f"Error closing database engine: {exc}")
