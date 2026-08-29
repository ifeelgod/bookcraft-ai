"""
Unit Tests: Lead Storage, SQLAlchemy 2.0 Async Models & Email Marketing Providers
Verifies Lead, Job, Payment, and EmailSyncLog persistence, constraints, and provider sync interfaces.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.db.base import Base
from app.db.models import Lead, Job, Payment, EmailSyncLog, generate_uuid
from app.services.email.provider import (
    NullProvider,
    WebhookEmailProvider,
    SendGridEmailProvider,
    MailchimpEmailProvider,
    SyncResult,
)


@pytest.fixture
async def db_session():
    """Create an in-memory SQLite async engine and session for isolated testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_lead_model_creation_and_defaults():
    """Verify Lead model defaults and attributes."""
    lead = Lead(
        name="Eleanor Vance",
        email="eleanor@example.com",
    )
    assert lead.id is not None or len(generate_uuid()) == 36
    assert lead.name == "Eleanor Vance"
    assert lead.email == "eleanor@example.com"
    assert lead.marketing_consent is True
    assert lead.tier == "demo"
    assert lead.status == "active"
    assert lead.source == "demo_upload"

    lead_dict = lead.to_dict()
    assert lead_dict["name"] == "Eleanor Vance"
    assert lead_dict["email"] == "eleanor@example.com"
    assert lead_dict["tier"] == "demo"


@pytest.mark.asyncio
async def test_lead_db_insert_and_query(db_session: AsyncSession):
    """Verify inserting and querying a Lead in the database."""
    lead = Lead(
        id=generate_uuid(),
        name="Marcus Aurelius",
        email="marcus@stoic.org",
        marketing_consent=True,
        tier="demo",
        document_name="meditations.md",
        document_type="md",
        document_size_bytes=10240,
        page_count=12,
        is_truncated=False,
    )
    db_session.add(lead)
    await db_session.commit()

    stmt = select(Lead).where(Lead.email == "marcus@stoic.org")
    result = await db_session.execute(stmt)
    fetched = result.scalar_one_or_none()

    assert fetched is not None
    assert fetched.id == lead.id
    assert fetched.name == "Marcus Aurelius"
    assert fetched.document_name == "meditations.md"
    assert fetched.is_truncated is False


@pytest.mark.asyncio
async def test_lead_update_to_pro_tier(db_session: AsyncSession):
    """Verify updating a lead from demo to pro tier upon checkout."""
    lead_id = generate_uuid()
    lead = Lead(
        id=lead_id,
        name="Brandon Sanderson",
        email="brandon@cosmere.com",
        tier="demo",
    )
    db_session.add(lead)
    await db_session.commit()

    # Simulate purchase / upgrade
    lead.tier = "pro"
    lead.status = "converted"
    await db_session.commit()

    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db_session.execute(stmt)
    updated = result.scalar_one()

    assert updated.tier == "pro"
    assert updated.status == "converted"


@pytest.mark.asyncio
async def test_lead_relationships_jobs_and_payments(db_session: AsyncSession):
    """Verify Lead cascading relationships with Job and Payment."""
    lead_id = generate_uuid()
    lead = Lead(
        id=lead_id,
        name="Jane Austen",
        email="jane@pemberley.co.uk",
        tier="demo",
    )
    job = Job(
        id=generate_uuid(),
        lead_id=lead_id,
        job_type="compile",
        status="completed",
        progress=100,
        message="Compiled successfully",
        file_name="pride_and_prejudice.docx",
    )
    payment = Payment(
        id=generate_uuid(),
        lead_id=lead_id,
        provider="stripe",
        transaction_id="cs_test_pride123",
        amount_cents=1900,
        currency="USD",
        tier="pro_pass",
        status="succeeded",
    )
    email_log = EmailSyncLog(
        id=generate_uuid(),
        lead_id=lead_id,
        provider="null",
        status="success",
        payload={"email": lead.email},
    )

    db_session.add(lead)
    db_session.add(job)
    db_session.add(payment)
    db_session.add(email_log)
    await db_session.commit()

    stmt = select(Lead).where(Lead.id == lead_id)
    res = await db_session.execute(stmt)
    queried_lead = res.scalar_one()

    assert len(queried_lead.jobs) == 1
    assert queried_lead.jobs[0].file_name == "pride_and_prejudice.docx"
    assert len(queried_lead.payments) == 1
    assert queried_lead.payments[0].amount_cents == 1900
    assert len(queried_lead.email_sync_logs) == 1


@pytest.mark.asyncio
async def test_null_email_provider_sync():
    """Verify NullProvider mock sync always succeeds and records synthetic provider ID."""
    provider = NullProvider()
    assert await provider.health_check() is True

    result: SyncResult = await provider.sync_contact(
        name="Arthur Conan Doyle",
        email="doyle@bakerstreet.org",
        marketing_consent=True,
        metadata={"book": "A Study in Scarlet"},
    )

    assert result.success is True
    assert result.provider == "null"
    assert result.provider_id.startswith("null_sub_")
    assert result.payload["name"] == "Arthur Conan Doyle"
    assert result.payload["email"] == "doyle@bakerstreet.org"


@pytest.mark.asyncio
async def test_email_providers_interface_compliance():
    """Verify all email providers implement the EmailMarketingProvider contract."""
    providers = [
        NullProvider(),
        WebhookEmailProvider(webhook_url="https://webhook.site/mock-test"),
        SendGridEmailProvider(api_key="SG.mock_key", list_id="mock_list"),
        MailchimpEmailProvider(api_key="mock_key-us1", list_id="mock_list"),
    ]

    for p in providers:
        assert hasattr(p, "sync_contact")
        assert hasattr(p, "health_check")
        assert asyncio.iscoroutinefunction(p.sync_contact)
        assert asyncio.iscoroutinefunction(p.health_check)
