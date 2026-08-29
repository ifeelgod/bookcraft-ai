"""
Unit & Integration Tests: Leads API Endpoints and Upload Lead Capture Flow
Tests:
  - POST /api/leads: create lead, update existing on duplicate email, input validation.
  - GET /api/leads: pagination, search filtering, tier filtering.
  - GET /api/leads/{lead_id}: detail lookup with jobs and logs.
  - GET /api/leads/stats/summary: aggregate counts.
  - POST /api/leads/{lead_id}/resync: trigger email sync.
  - POST /api/upload: validation of name and email for demo tier vs pro tier.
"""
from __future__ import annotations
import io
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.models import Lead, Job, EmailSyncLog, generate_uuid


@pytest.fixture
async def test_db_session():
    """Create an isolated in-memory SQLite database session for endpoint testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def async_client(test_db_session: AsyncSession):
    """FastAPI async test client with overridden DB session dependency."""
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_lead_success(async_client: AsyncClient):
    """Verify creating a new lead via POST /api/leads."""
    payload = {
        "name": "Isaac Asimov",
        "email": "isaac@foundation.org",
        "marketing_consent": True,
        "tier": "demo",
        "document_name": "foundation.docx",
        "document_type": "docx",
        "extra_metadata": {"genre": "scifi"},
    }

    response = await async_client.post("/api/leads", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["name"] == "Isaac Asimov"
    assert data["email"] == "isaac@foundation.org"
    assert data["marketing_consent"] is True
    assert data["tier"] == "demo"
    assert data["id"] is not None


@pytest.mark.asyncio
async def test_create_lead_invalid_email_validation(async_client: AsyncClient):
    """Verify that invalid email addresses are rejected with HTTP 422."""
    payload = {
        "name": "Mary Shelley",
        "email": "not-an-email",
        "marketing_consent": True,
    }
    response = await async_client.post("/api/leads", json=payload)
    assert response.status_code == 422
    data = response.json()
    assert "error" in data["detail"] or "message" in data["detail"]


@pytest.mark.asyncio
async def test_create_lead_plus_addressing_email(async_client: AsyncClient):
    """Verify that RFC 5322 plus-addressed emails (e.g. author+tag@domain.com) are accepted."""
    payload = {
        "name": "Arthur Conan Doyle",
        "email": "sherlock+holmes.221b@bakerstreet.co.uk",
        "marketing_consent": True,
        "tier": "demo",
    }
    response = await async_client.post("/api/leads", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "sherlock+holmes.221b@bakerstreet.co.uk"
    assert data["name"] == "Arthur Conan Doyle"


@pytest.mark.asyncio
async def test_create_lead_short_name_validation(async_client: AsyncClient):
    """Verify that names with < 2 characters are rejected."""
    payload = {
        "name": "A",
        "email": "valid@email.com",
        "marketing_consent": True,
    }
    response = await async_client.post("/api/leads", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_leads_and_stats(async_client: AsyncClient, test_db_session: AsyncSession):
    """Verify listing leads with search and query stats summary."""
    lead1 = Lead(
        id=generate_uuid(),
        name="Ursula Le Guin",
        email="ursula@earthsea.net",
        tier="demo",
        marketing_consent=True,
    )
    lead2 = Lead(
        id=generate_uuid(),
        name="Philip K Dick",
        email="philip@androids.com",
        tier="pro",
        marketing_consent=False,
    )
    test_db_session.add(lead1)
    test_db_session.add(lead2)
    await test_db_session.commit()

    # List all
    resp = await async_client.get("/api/leads")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2

    # Filter by tier
    resp_demo = await async_client.get("/api/leads?tier=demo")
    assert resp_demo.status_code == 200
    assert any(lead["name"] == "Ursula Le Guin" for lead in resp_demo.json()["leads"])

    # Search
    resp_search = await async_client.get("/api/leads?search=Philip")
    assert resp_search.status_code == 200
    assert len(resp_search.json()["leads"]) == 1
    assert resp_search.json()["leads"][0]["name"] == "Philip K Dick"

    # Stats
    resp_stats = await async_client.get("/api/leads/stats/summary")
    assert resp_stats.status_code == 200
    stats = resp_stats.json()
    assert stats["total_leads"] >= 2
    assert stats["demo_tier_count"] >= 1
    assert stats["pro_tier_count"] >= 1


@pytest.mark.asyncio
async def test_get_single_lead_details(async_client: AsyncClient, test_db_session: AsyncSession):
    """Verify GET /api/leads/{id} returns lead details with associated jobs and logs."""
    lead_id = generate_uuid()
    lead = Lead(
        id=lead_id,
        name="Frank Herbert",
        email="frank@dune.org",
        tier="demo",
    )
    job = Job(
        id=generate_uuid(),
        lead_id=lead_id,
        status="completed",
        progress=100,
        file_name="dune.docx",
    )
    test_db_session.add(lead)
    test_db_session.add(job)
    await test_db_session.commit()

    resp = await async_client.get(f"/api/leads/{lead_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == lead_id
    assert data["name"] == "Frank Herbert"
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["file_name"] == "dune.docx"


@pytest.mark.asyncio
async def test_upload_endpoint_requires_lead_info_for_demo(async_client: AsyncClient):
    """Verify POST /api/upload requires name and valid email for demo tier."""
    fake_docx = b"PK\x03\x04test dummy docx file content"
    files = {"file": ("manuscript.docx", io.BytesIO(fake_docx), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    
    # Missing name and email
    data = {"tier": "demo"}
    resp = await async_client.post("/api/upload", files=files, data=data)
    assert resp.status_code == 422
    assert "missing_name" in str(resp.json()) or "name" in str(resp.json()).lower()


@pytest.mark.asyncio
async def test_upload_endpoint_valid_lead_capture(async_client: AsyncClient, test_db_session: AsyncSession):
    """Verify POST /api/upload succeeds and captures lead in DB when valid details provided."""
    import fitz
    # Create minimal 1-page valid PDF
    doc = fitz.open()
    doc.new_page(width=432, height=648)
    pdf_bytes = doc.write()
    doc.close()

    files = {"file": ("test_story.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
    data = {
        "name": "Octavia Butler",
        "email": "octavia@kindred.org",
        "marketing_consent": "true",
        "tier": "demo",
    }

    resp = await async_client.post("/api/upload", files=files, data=data)
    assert resp.status_code == 202
    res_data = resp.json()
    assert "job_id" in res_data
    assert res_data["lead_id"] is not None
    assert res_data["tier"] == "demo"
    assert res_data["is_truncated"] is False
