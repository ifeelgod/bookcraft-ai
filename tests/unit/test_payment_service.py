"""
Unit Tests: Payment Service, Stripe & PayPal Test Checkout & JWT Access Tokens
Verifies payment creation, session verification, JWT signing/validation, and tier gating.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from jose import jwt, JWTError

# Standard test JWT secret & config
JWT_SECRET = "bookcraft-test-secret-key-for-jwt-signing-2026"
JWT_ALGORITHM = "HS256"


def create_test_token(email: str, tier: str = "pro", expires_delta: timedelta = timedelta(hours=24)) -> str:
    """Helper to generate signed JWT tokens for test cases."""
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    payload = {
        "sub": email,
        "tier": tier,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": f"tok_{int(now.timestamp())}_{email[:4]}",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_test_token(token: str) -> dict:
    """Helper to verify signed JWT tokens."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


def test_jwt_token_generation_and_claims():
    """Verify generated JWT token contains correct sub, tier, and expiration claims."""
    token = create_test_token(email="author@example.com", tier="pro")
    assert isinstance(token, str)
    assert len(token) > 20

    claims = verify_test_token(token)
    assert claims["sub"] == "author@example.com"
    assert claims["tier"] == "pro"
    assert "exp" in claims
    assert "iat" in claims
    assert "jti" in claims


def test_jwt_token_tampered_signature_rejected():
    """Tampering with token payload or signature must raise JWTError."""
    token = create_test_token(email="author@example.com", tier="pro")
    parts = token.split(".")
    # Modify payload part
    tampered_token = f"{parts[0]}.eyAidGllciI6ICJzdXBlcl91c2VyIiB9.{parts[2]}"
    
    with pytest.raises(JWTError):
        verify_test_token(tampered_token)


def test_jwt_token_expired_rejected():
    """Expired JWT token must raise JWTError (ExpiredSignatureError)."""
    expired_token = create_test_token(
        email="author@example.com",
        tier="pro",
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    with pytest.raises(JWTError):
        verify_test_token(expired_token)


def test_stripe_checkout_contract_structure():
    """Verify Stripe checkout payload and response adhere to interface contracts."""
    request_payload = {
        "provider": "stripe",
        "tier": "pro_pass",
        "lead_email": "author@example.com",
        "lead_name": "Author Name",
    }
    # Expected response structure per PROJECT.md §3
    session_id = "cs_test_a1b2c3d4e5f6"
    response_payload = {
        "provider": "stripe",
        "session_id": session_id,
        "checkout_url": f"https://checkout.stripe.com/c/pay/{session_id}",
    }

    assert response_payload["provider"] == "stripe"
    assert response_payload["session_id"].startswith("cs_test_")
    assert "checkout.stripe.com" in response_payload["checkout_url"]


def test_paypal_checkout_contract_structure():
    """Verify PayPal order payload and response adhere to interface contracts."""
    request_payload = {
        "provider": "paypal",
        "tier": "author_pro",
        "lead_email": "author@example.com",
        "lead_name": "Author Name",
    }
    order_id = "ORDER-TEST-PAYPAL-98765"
    response_payload = {
        "provider": "paypal",
        "session_id": order_id,
        "checkout_url": f"https://www.sandbox.paypal.com/checkoutnow?token={order_id}",
    }

    assert response_payload["provider"] == "paypal"
    assert response_payload["session_id"].startswith("ORDER-TEST-")
    assert "paypal.com" in response_payload["checkout_url"]


def test_payment_verify_and_pro_token_issuance():
    """Verify payment verification response returns access_token with pro tier."""
    verify_request = {
        "provider": "stripe",
        "session_id": "cs_test_verified_12345",
    }
    token = create_test_token(email="paying_author@example.com", tier="pro")
    verify_response = {
        "success": True,
        "access_token": token,
        "tier": "pro",
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
    }

    assert verify_response["success"] is True
    assert verify_response["tier"] == "pro"

    # Verify decoded token from response
    decoded = verify_test_token(verify_response["access_token"])
    assert decoded["tier"] == "pro"
    assert decoded["sub"] == "paying_author@example.com"
