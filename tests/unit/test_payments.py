"""
Unit & Integration Tests: Payments API, Stripe & PayPal Services, and Payment Orchestrator.
Validates checkout initiation, order capture, verification, database persistence, and token issuance.
"""
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from main import app
from app.db.base import Base
from app.db.session import get_db
from app.db.models import Lead, Payment
from app.core.security import verify_access_token
from app.services.payments.stripe_service import StripeService
from app.services.payments.paypal_service import PayPalService
from app.services.payments.payment_orchestrator import PaymentOrchestrator, payment_orchestrator


@pytest.fixture
async def test_db_session():
    """Create an isolated in-memory SQLite database session for payments testing."""
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
    """FastAPI async test client with overridden DB session."""
    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


# ── Payment Services Unit Tests ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_stripe_service_create_checkout_test_mode():
    """Verify StripeService generates valid test checkout session dictionary."""
    stripe_svc = StripeService()
    session = await stripe_svc.create_checkout_session(
        tier="pro_pass",
        lead_email="author@example.com",
        lead_name="Jane Author",
    )
    assert session["provider"] == "stripe"
    assert session["session_id"].startswith("cs_test_")
    assert "checkout.stripe.com" in session["checkout_url"]
    assert session["amount_cents"] == 1900
    assert session["tier"] == "pro_pass"


@pytest.mark.asyncio
async def test_stripe_service_author_pro_tier():
    """Verify StripeService author_pro plan sets $29.00 amount."""
    stripe_svc = StripeService()
    session = await stripe_svc.create_checkout_session(
        tier="author_pro",
        lead_email="publisher@example.com",
    )
    assert session["amount_cents"] == 2900
    assert session["tier"] == "author_pro"


@pytest.mark.asyncio
async def test_paypal_service_create_order_test_mode():
    """Verify PayPalService generates valid sandbox order."""
    paypal_svc = PayPalService()
    order = await paypal_svc.create_order(
        tier="pro_pass",
        lead_email="author@example.com",
    )
    assert order["provider"] == "paypal"
    assert order["session_id"].startswith("ORDER-TEST-PAYPAL-")
    assert "paypal.com" in order["checkout_url"]
    assert order["amount_cents"] == 1900


@pytest.mark.asyncio
async def test_paypal_service_capture_order():
    """Verify PayPalService order capture returns successful status."""
    paypal_svc = PayPalService()
    order_id = "ORDER-TEST-PAYPAL-ABC12345"
    capture_res = await paypal_svc.capture_order(order_id)
    assert capture_res["success"] is True
    assert capture_res["status"] == "succeeded"
    assert capture_res["order_id"] == order_id


# ── Payment Orchestrator Unit Tests ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_payment_orchestrator_get_public_config():
    """Verify public config returns enabled providers and pricing tiers."""
    config = payment_orchestrator.get_public_config()
    assert "stripe" in config
    assert "paypal" in config
    assert "tiers" in config
    tier_ids = [t["id"] for t in config["tiers"]]
    assert "demo" in tier_ids
    assert "pro_pass" in tier_ids
    assert "author_pro" in tier_ids


@pytest.mark.asyncio
async def test_payment_orchestrator_verify_and_fulfill(test_db_session: AsyncSession):
    """Verify fulfill payment creates DB records, updates lead, and returns signed JWT."""
    # Seed initial demo lead
    lead = Lead(
        name="Mary Shelley",
        email="mary@frankenstein.org",
        tier="demo",
    )
    test_db_session.add(lead)
    await test_db_session.commit()

    result = await payment_orchestrator.verify_and_fulfill(
        provider="stripe",
        session_id="cs_test_shelley_12345",
        lead_email="mary@frankenstein.org",
        lead_name="Mary Shelley",
        tier="pro",
        db=test_db_session,
    )

    assert result["success"] is True
    assert result["status"] == "succeeded"
    assert result["tier"] == "pro"
    assert result["email"] == "mary@frankenstein.org"
    assert result["access_token"] is not None

    # Validate generated JWT token
    claims = verify_access_token(result["access_token"])
    assert claims["sub"] == "mary@frankenstein.org"
    assert claims["tier"] == "pro"
    assert "unlimited_pages" in claims["scopes"]

    # Verify Database Payment record
    stmt = select(Payment).where(Payment.lead_id == lead.id)
    res = await test_db_session.execute(stmt)
    payment = res.scalar_one_or_none()
    assert payment is not None
    assert payment.provider == "stripe"
    assert payment.amount_cents == 1900
    assert payment.status == "succeeded"

    # Verify Lead tier was upgraded to pro
    await test_db_session.refresh(lead)
    assert lead.tier == "pro"


# ── Payment API Endpoint Tests ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_get_payment_config(async_client: AsyncClient):
    """GET /api/payments/config returns public configuration."""
    response = await async_client.get("/api/payments/config")
    assert response.status_code == 200
    data = response.json()
    assert data["stripe"]["enabled"] is True
    assert data["paypal"]["enabled"] is True
    assert len(data["tiers"]) >= 3


@pytest.mark.asyncio
async def test_api_create_checkout_stripe(async_client: AsyncClient):
    """POST /api/payments/checkout initializes Stripe session."""
    payload = {
        "provider": "stripe",
        "tier": "pro_pass",
        "lead_email": "author@example.com",
        "lead_name": "Author Name",
    }
    response = await async_client.post("/api/payments/checkout", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "stripe"
    assert data["session_id"].startswith("cs_test_")
    assert "checkout_url" in data


@pytest.mark.asyncio
async def test_api_create_checkout_paypal(async_client: AsyncClient):
    """POST /api/payments/checkout initializes PayPal order."""
    payload = {
        "provider": "paypal",
        "tier": "author_pro",
        "lead_email": "publisher@example.com",
    }
    response = await async_client.post("/api/payments/checkout", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "paypal"
    assert data["session_id"].startswith("ORDER-TEST-PAYPAL-")
    assert data["amount_cents"] == 2900


@pytest.mark.asyncio
async def test_api_verify_payment_endpoint(async_client: AsyncClient, test_db_session: AsyncSession):
    """POST /api/payments/verify processes transaction and returns Pro JWT token."""
    payload = {
        "provider": "stripe",
        "session_id": "cs_test_verified_session_8899",
        "lead_email": "buyer@example.com",
        "lead_name": "Buyer Name",
        "tier": "pro",
    }
    response = await async_client.post("/api/payments/verify", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["tier"] == "pro"
    assert "access_token" in data

    # Verify decoded token
    decoded = verify_access_token(data["access_token"])
    assert decoded["sub"] == "buyer@example.com"
    assert decoded["tier"] == "pro"


@pytest.mark.asyncio
async def test_api_payment_history(async_client: AsyncClient, test_db_session: AsyncSession):
    """GET /api/payments/history/{email} queries past transactions."""
    # First verify a payment to populate DB
    payload = {
        "provider": "stripe",
        "session_id": "cs_test_history_session_1122",
        "lead_email": "history_user@example.com",
        "lead_name": "History User",
        "tier": "pro",
    }
    await async_client.post("/api/payments/verify", json=payload)

    # Query history
    response = await async_client.get("/api/payments/history/history_user@example.com")
    assert response.status_code == 200
    history = response.json()
    assert len(history) >= 1
    assert history[0]["transaction_id"] == "cs_test_history_session_1122"
    assert history[0]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_api_stripe_webhook(async_client: AsyncClient):
    """POST /api/payments/webhook/stripe handles checkout completed events."""
    webhook_payload = {
        "id": "evt_test_webhook_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_webhook_session_9900",
                "customer_email": "webhook_user@example.com",
                "metadata": {"tier": "pro", "lead_email": "webhook_user@example.com"},
            }
        },
    }
    response = await async_client.post("/api/payments/webhook/stripe", json=webhook_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert data["provider"] == "stripe"
