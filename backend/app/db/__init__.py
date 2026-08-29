"""
Database module for BookCraft AI.
Provides SQLAlchemy 2.0 async engine, declarative Base, and session factories.
"""
from app.db.base import Base, engine, async_session_factory, init_db, close_db
from app.db.models import Lead, Job, EmailSyncLog

__all__ = [
    "Base",
    "engine",
    "async_session_factory",
    "init_db",
    "close_db",
    "Lead",
    "Job",
    "EmailSyncLog",
]
