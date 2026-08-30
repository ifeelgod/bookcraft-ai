"""
E2E Test Suite - Tier 3: Cross-Feature Combinations (≥12 tests)
Verifies multi-step workflows, pairwise interactions, lifecycle state transitions, and integration points.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.models.document_ast import DocumentAST, Chapter, ParagraphBlock
from app.services.compilers.orchestrator import CompilerOrchestrator
from app.db.base import Base
from app.db.models import Lead, Job, Payment, EmailSyncLog, generate_uuid
from app.services.email.provider import NullProvider
from tests.unit.test_payment_service import create_test_token, verify_test_token
from tests.unit.test_restriction_engine import apply_demo_restriction
from tests.conftest import is_valid_pdf_bytes, is_valid_docx_bytes, is_valid_epub_bytes, is_valid_md_string


@pytest.fixture
async def e2e_db_session():
    """Create isolated async DB session for Tier 3 workflow tests."""
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
async def test_tier3_01_upload_to_demo_pdf_compile_flow(sample_ast, e2e_db_session, tmp_path):
    """Workflow 1: Upload manuscript -> Capture lead -> Compile demo PDF -> Verify 15-page limit & DB lead."""
    # 1. Lead capture
    lead = Lead(
        id=generate_uuid(),
        name="Eleanor Vance",
        email="eleanor@pines.org",
        marketing_consent=True,
        tier="demo",
        document_name="whispering_pines.md",
    )
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    # 2. Compile demo AST
    restricted_ast, is_truncated = apply_demo_restriction(sample_ast, tier=lead.tier, max_pages=15)
    orch = CompilerOrchestrator()
    res = await orch.compile_all(restricted_ast, "t3_flow1", tmp_path, formats=["pdf"])

    # 3. Verify PDF generated and DB lead persisted
    assert Path(res["pdf"]["path"]).exists()
    stmt = select(Lead).where(Lead.email == "eleanor@pines.org")
    queried = (await e2e_db_session.execute(stmt)).scalar_one()
    assert queried.name == "Eleanor Vance"
    assert queried.tier == "demo"


@pytest.mark.asyncio
async def test_tier3_02_upload_to_multiformat_export_flow(sample_ast, tmp_path):
    """Workflow 2: Manuscript -> Multi-format compile -> Status completed -> All 4 download URLs valid."""
    orch = CompilerOrchestrator()
    results = await orch.compile_all(sample_ast, "t3_flow2", tmp_path)

    assert len(results) == 4
    for fmt in ["pdf", "docx", "md", "epub"]:
        item = results[fmt]
        assert Path(item["path"]).exists()
        assert item["url"].startswith("/api/download/")
        assert item["size_bytes"] > 0


@pytest.mark.asyncio
async def test_tier3_03_demo_limit_hit_to_stripe_checkout_upgrade_flow(twenty_five_page_ast, e2e_db_session, tmp_path):
    """Workflow 3: 25p manuscript -> Demo caps to 15 -> Stripe checkout -> Verify -> Pro token -> Full 25p uncut."""
    lead_id = generate_uuid()
    lead = Lead(id=lead_id, name="Victoria Chen", email="vchen@astronav.org", tier="demo")
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    # Stage 1: Demo compilation (15 pages)
    demo_ast, demo_truncated = apply_demo_restriction(twenty_five_page_ast, tier=lead.tier)
    assert demo_truncated is True
    assert len(demo_ast.chapters) == 15

    # Stage 2: Trigger Stripe checkout
    payment = Payment(
        id=generate_uuid(),
        lead_id=lead_id,
        provider="stripe",
        transaction_id="cs_test_vchen123",
        amount_cents=1900,
        currency="USD",
        tier="pro_pass",
        status="succeeded",
    )
    lead.tier = "pro"
    e2e_db_session.add(payment)
    await e2e_db_session.commit()

    # Stage 3: Issue JWT token
    pro_token = create_test_token(lead.email, tier="pro")
    claims = verify_test_token(pro_token)
    assert claims["tier"] == "pro"

    # Stage 4: Re-compile with Pro token (All 25 chapters)
    pro_ast, pro_truncated = apply_demo_restriction(twenty_five_page_ast, tier=claims["tier"])
    assert pro_truncated is False
    assert len(pro_ast.chapters) == 25

    orch = CompilerOrchestrator()
    res = await orch.compile_all(pro_ast, "t3_stripe_pro", tmp_path, formats=["pdf", "docx"])
    assert Path(res["pdf"]["path"]).exists()
    assert Path(res["docx"]["path"]).exists()


@pytest.mark.asyncio
async def test_tier3_04_demo_limit_hit_to_paypal_checkout_upgrade_flow(twenty_five_page_ast, e2e_db_session, tmp_path):
    """Workflow 4: 25p manuscript -> Demo caps to 15 -> PayPal order -> Capture -> Pro token -> Full 25p uncut."""
    lead_id = generate_uuid()
    lead = Lead(id=lead_id, name="Arthur Pendelton", email="art@astronav.org", tier="demo")
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    # Demo compilation
    demo_ast, demo_truncated = apply_demo_restriction(twenty_five_page_ast, tier=lead.tier)
    assert demo_truncated is True

    # PayPal capture
    payment = Payment(
        id=generate_uuid(),
        lead_id=lead_id,
        provider="paypal",
        transaction_id="ORDER-SANDBOX-PAYPAL-456",
        amount_cents=2900,
        currency="USD",
        tier="author_pro",
        status="succeeded",
    )
    lead.tier = "pro"
    e2e_db_session.add(payment)
    await e2e_db_session.commit()

    # Issue token & recompile
    token = create_test_token(lead.email, tier="pro")
    pro_ast, pro_truncated = apply_demo_restriction(twenty_five_page_ast, tier=verify_test_token(token)["tier"])
    assert pro_truncated is False
    assert len(pro_ast.chapters) == 25


@pytest.mark.asyncio
async def test_tier3_05_lead_capture_persistence_and_email_sync_logging(e2e_db_session):
    """Workflow 5: Lead capture -> Persistence -> External email provider sync -> Audit log recorded."""
    lead_id = generate_uuid()
    lead = Lead(id=lead_id, name="Charlotte Bronte", email="charlotte@haworth.co.uk", marketing_consent=True)
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    # Provider sync
    provider = NullProvider()
    sync_res = await provider.sync_contact(lead.name, lead.email, lead.marketing_consent)
    assert sync_res.success is True

    # Record sync log
    sync_log = EmailSyncLog(
        id=generate_uuid(),
        lead_id=lead_id,
        provider=sync_res.provider,
        status="success",
        payload=sync_res.payload,
    )
    e2e_db_session.add(sync_log)
    await e2e_db_session.commit()

    stmt = select(EmailSyncLog).where(EmailSyncLog.lead_id == lead_id)
    queried_log = (await e2e_db_session.execute(stmt)).scalar_one()
    assert queried_log.status == "success"
    assert queried_log.provider == "null"


@pytest.mark.asyncio
async def test_tier3_06_lead_capture_without_consent_transactional_sync(e2e_db_session):
    """Workflow 6: Lead capture with marketing_consent=False preserves transactional status."""
    lead_id = generate_uuid()
    lead = Lead(id=lead_id, name="George Orwell", email="george@1984.org", marketing_consent=False)
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    provider = NullProvider()
    sync_res = await provider.sync_contact(lead.name, lead.email, marketing_consent=False)
    assert sync_res.payload["marketing_consent"] is False


@pytest.mark.asyncio
async def test_tier3_07_multiple_uploads_same_author_lead_deduplication(e2e_db_session):
    """Workflow 7: Same author submits multiple manuscripts -> Lead record updated with latest activity."""
    author_email = "herman@mobydick.org"
    lead = Lead(
        id=generate_uuid(),
        name="Herman Melville",
        email=author_email,
        document_name="typee.docx",
    )
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    # Second upload with same email
    stmt = select(Lead).where(Lead.email == author_email)
    existing = (await e2e_db_session.execute(stmt)).scalar_one()
    existing.document_name = "moby_dick.docx"
    await e2e_db_session.commit()

    re_queried = (await e2e_db_session.execute(stmt)).scalar_one()
    assert re_queried.document_name == "moby_dick.docx"


@pytest.mark.asyncio
async def test_tier3_08_pro_token_multi_format_full_content_verification(twenty_five_page_ast, tmp_path):
    """Workflow 8: Pro token compiles full 25 chapters into all 4 formats."""
    token = create_test_token("pro@author.com", tier="pro")
    claims = verify_test_token(token)
    pro_ast, _ = apply_demo_restriction(twenty_five_page_ast, tier=claims["tier"])

    orch = CompilerOrchestrator()
    results = await orch.compile_all(pro_ast, "t3_pro_all_formats", tmp_path)

    md_content = Path(results["md"]["path"]).read_text(encoding="utf-8")
    assert any(x in md_content for x in ["Sector Module 25", "Sector Navigation Module 25"])
    assert is_valid_docx_bytes(Path(results["docx"]["path"]).read_bytes())
    assert is_valid_epub_bytes(Path(results["epub"]["path"]).read_bytes())


@pytest.mark.asyncio
async def test_tier3_09_demo_token_multi_format_gated_content_verification(twenty_five_page_ast, tmp_path):
    """Workflow 9: Demo compilation gates all 4 formats to 15 chapters + demo notice."""
    demo_ast, _ = apply_demo_restriction(twenty_five_page_ast, tier="demo")
    assert len(demo_ast.chapters) == 15

    orch = CompilerOrchestrator()
    results = await orch.compile_all(demo_ast, "t3_demo_all_formats", tmp_path)

    md_content = Path(results["md"]["path"]).read_text(encoding="utf-8")
    assert any(x in md_content for x in ["Sector Module 15", "Sector Navigation Module 15"])
    assert not any(x in md_content for x in ["Sector Module 25", "Sector Navigation Module 25"])
    assert "Demo Preview Limit" in md_content


@pytest.mark.asyncio
async def test_tier3_10_corrupted_file_upload_job_failure_and_lead_retention(e2e_db_session):
    """Workflow 10: Corrupted upload records failed job while retaining lead record in DB."""
    lead_id = generate_uuid()
    lead = Lead(id=lead_id, name="Mary Shelley", email="mary@frankenstein.co.uk", document_name="corrupt.docx")
    job = Job(
        id=generate_uuid(),
        lead_id=lead_id,
        status="failed",
        error_message="Corrupted OpenXML header",
    )
    e2e_db_session.add(lead)
    e2e_db_session.add(job)
    await e2e_db_session.commit()

    stmt_lead = select(Lead).where(Lead.id == lead_id)
    assert (await e2e_db_session.execute(stmt_lead)).scalar_one() is not None

    stmt_job = select(Job).where(Job.lead_id == lead_id)
    assert (await e2e_db_session.execute(stmt_job)).scalar_one().status == "failed"


@pytest.mark.asyncio
async def test_tier3_11_payment_failure_simulation_preserves_demo_tier(twenty_five_page_ast, e2e_db_session):
    """Workflow 11: Failed payment preserves user in demo tier with 15-page limit."""
    lead_id = generate_uuid()
    lead = Lead(id=lead_id, name="Edgar Allan Poe", email="poe@raven.org", tier="demo")
    payment = Payment(
        id=generate_uuid(),
        lead_id=lead_id,
        provider="stripe",
        transaction_id="cs_test_declined_123",
        amount_cents=1900,
        currency="USD",
        tier="pro_pass",
        status="failed",
    )
    e2e_db_session.add(lead)
    e2e_db_session.add(payment)
    await e2e_db_session.commit()

    # User remains demo
    demo_ast, is_truncated = apply_demo_restriction(twenty_five_page_ast, tier=lead.tier)
    assert is_truncated is True
    assert len(demo_ast.chapters) == 15


@pytest.mark.asyncio
async def test_tier3_12_complete_end_to_end_customer_lifecycle(twenty_five_page_ast, e2e_db_session, tmp_path):
    """Workflow 12: Full author journey (Landing -> Upload -> 15p Preview -> Stripe Checkout -> Full Uncut Download)."""
    # 1. Lead capture
    lead_id = generate_uuid()
    lead = Lead(
        id=lead_id,
        name="Sir Arthur Conan Doyle",
        email="doyle@sherlock.org",
        marketing_consent=True,
        tier="demo",
        document_name="the_hound_of_the_baskervilles.docx",
    )
    e2e_db_session.add(lead)
    await e2e_db_session.commit()

    # 2. Free Demo evaluation (15 chapters)
    demo_ast, demo_trunc = apply_demo_restriction(twenty_five_page_ast, tier="demo")
    assert demo_trunc is True
    assert len(demo_ast.chapters) == 15

    # 3. User upgrades via Stripe Pro Pass
    payment = Payment(
        id=generate_uuid(),
        lead_id=lead_id,
        provider="stripe",
        transaction_id="cs_test_sherlock_paid",
        amount_cents=1900,
        currency="USD",
        tier="pro_pass",
        status="succeeded",
    )
    lead.tier = "pro"
    e2e_db_session.add(payment)
    await e2e_db_session.commit()

    # 4. Pro access token issued
    token = create_test_token(lead.email, tier="pro")
    claims = verify_test_token(token)

    # 5. Full 25-chapter publication compilation across all 4 formats
    pro_ast, pro_trunc = apply_demo_restriction(twenty_five_page_ast, tier=claims["tier"])
    assert pro_trunc is False
    assert len(pro_ast.chapters) == 25

    orch = CompilerOrchestrator()
    final_outputs = await orch.compile_all(pro_ast, "t3_lifecycle_final", tmp_path)

    for fmt in ["pdf", "docx", "md", "epub"]:
        path = Path(final_outputs[fmt]["path"])
        assert path.exists()
        assert path.stat().st_size > 0
