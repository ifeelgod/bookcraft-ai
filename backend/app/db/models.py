"""
SQLAlchemy 2.0 async ORM models for BookCraft AI.
Defines schemas for Lead, Job, EmailSyncLog, and Payment.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.dialects.postgresql import JSONB as PostgresJSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def generate_uuid() -> str:
    """Generate a string representation of a UUID4."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(timezone.utc)


class Lead(Base):
    """
    Prospective customer or demo user captured before manuscript processing.
    """
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="demo", nullable=False)  # "demo", "pro", "pro_pass"
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # "active", "converted", "unsubscribed"
    source: Mapped[str] = mapped_column(String(50), default="demo_upload", nullable=False)

    # Document details from the upload attempt
    document_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    document_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    page_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Network / Attribution metadata
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Email marketing sync status
    email_marketing_status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    email_provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    email_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Flexible metadata dictionary
    extra_metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    jobs: Mapped[List[Job]] = relationship(
        "Job",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    email_sync_logs: Mapped[List[EmailSyncLog]] = relationship(
        "EmailSyncLog",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    payments: Mapped[List[Payment]] = relationship(
        "Payment",
        back_populates="lead",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __init__(self, **kwargs):
        kwargs.setdefault("marketing_consent", True)
        kwargs.setdefault("tier", "demo")
        kwargs.setdefault("status", "active")
        kwargs.setdefault("source", "demo_upload")
        kwargs.setdefault("email_marketing_status", "pending")
        kwargs.setdefault("extra_metadata", {})
        kwargs.setdefault("is_truncated", False)
        super().__init__(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Lead model instance to JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "marketing_consent": self.marketing_consent,
            "tier": self.tier,
            "status": self.status,
            "source": self.source,
            "document_name": self.document_name,
            "document_type": self.document_type,
            "document_size_bytes": self.document_size_bytes,
            "page_count": self.page_count,
            "word_count": self.word_count,
            "is_truncated": self.is_truncated,
            "email_marketing_status": self.email_marketing_status,
            "email_provider_id": self.email_provider_id,
            "email_synced_at": self.email_synced_at.isoformat() if self.email_synced_at else None,
            "extra_metadata": self.extra_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Job(Base):
    """
    Persistent record of a manuscript parsing, normalization, or compilation job.
    """
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    lead_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(20), default="parse", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    input_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    download_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_demo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ast_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    lead: Mapped[Optional[Lead]] = relationship("Lead", back_populates="jobs")

    def to_dict(self) -> Dict[str, Any]:
        """Convert Job instance to dictionary."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "file_name": self.file_name,
            "file_type": self.file_type,
            "download_url": self.download_url,
            "is_demo": self.is_demo,
            "is_truncated": self.is_truncated,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class EmailSyncLog(Base):
    """
    Audit log for external email marketing provider synchronizations.
    """
    __tablename__ = "email_sync_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    lead_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "null", "webhook", "sendgrid", "mailchimp"
    status: Mapped[str] = mapped_column(String(50), nullable=False)  # "success", "failed", "pending"
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    lead: Mapped[Lead] = relationship("Lead", back_populates="email_sync_logs")

    def to_dict(self) -> Dict[str, Any]:
        """Convert EmailSyncLog instance to dictionary."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "provider": self.provider,
            "status": self.status,
            "payload": self.payload,
            "error": self.error,
            "attempted_at": self.attempted_at.isoformat() if self.attempted_at else None,
        }


class Payment(Base):
    """
    Monetization and checkout transaction record for Pro upgrades.
    """
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )
    lead_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "stripe", "paypal"
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    tier: Mapped[str] = mapped_column(String(50), default="pro", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)  # "pending", "succeeded", "failed"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    lead: Mapped[Optional[Lead]] = relationship("Lead", back_populates="payments")

    def to_dict(self) -> Dict[str, Any]:
        """Convert Payment instance to dictionary."""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "provider": self.provider,
            "transaction_id": self.transaction_id,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "tier": self.tier,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
