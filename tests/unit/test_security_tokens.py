"""
Unit Tests: Security, JWT Tokens, and Tier Authorization Dependencies.
Verifies token creation, verification, tampering rejection, expiration, and FastAPI tier dependencies.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import pytest
from fastapi import HTTPException
from jose import JWTError, jwt

from app.core.config import settings
from app.core.security import (
    create_access_token,
    verify_access_token,
    get_current_tier,
    get_current_user_claims,
    require_pro_tier,
    generate_license_key,
    DEFAULT_PRO_SCOPES,
)


def test_create_and_verify_access_token():
    """Verify create_access_token generates valid signed token with expected claims."""
    data = {
        "sub": "test_author@example.com",
        "name": "Arthur Conan Doyle",
        "tier": "pro",
    }
    token = create_access_token(data=data, expires_delta=timedelta(hours=1))
    assert isinstance(token, str)
    assert len(token) > 30

    claims = verify_access_token(token)
    assert claims["sub"] == "test_author@example.com"
    assert claims["name"] == "Arthur Conan Doyle"
    assert claims["tier"] == "pro"
    assert claims["iss"] == "bookcraft-ai"
    assert "iat" in claims
    assert "exp" in claims
    assert "jti" in claims
    assert claims["scopes"] == DEFAULT_PRO_SCOPES


def test_token_tampered_payload_rejected():
    """Verify modifying any character of JWT payload raises JWTError."""
    token = create_access_token(data={"sub": "author@example.com", "tier": "pro"})
    parts = token.split(".")
    assert len(parts) == 3

    # Tamper payload
    tampered_token = f"{parts[0]}.eyAidGllciI6ICJhZG1pbiIsICJzdWIiOiAiaGFja2VyIn0.{parts[2]}"
    with pytest.raises(JWTError):
        verify_access_token(tampered_token)


def test_token_expired_rejected():
    """Verify expired token raises JWTError."""
    token = create_access_token(
        data={"sub": "author@example.com", "tier": "pro"},
        expires_delta=timedelta(seconds=-10),  # expired 10 seconds ago
    )
    with pytest.raises(JWTError):
        verify_access_token(token)


def test_get_current_tier_dependency():
    """Verify get_current_tier resolves correctly from Bearer header, query param, or fallback."""
    # 1. Valid Pro Bearer Token
    pro_token = create_access_token(data={"sub": "author@example.com", "tier": "pro"})
    tier = get_current_tier(authorization=f"Bearer {pro_token}")
    assert tier == "pro"

    # 2. Author Pro Token
    author_pro_token = create_access_token(data={"sub": "author@example.com", "tier": "author_pro"})
    tier = get_current_tier(authorization=f"Bearer {author_pro_token}")
    assert tier == "author_pro"

    # 3. Invalid Token fallback to demo
    tier = get_current_tier(authorization="Bearer invalid-token-string")
    assert tier == "demo"

    # 4. Explicit parameter override
    tier = get_current_tier(authorization=None, tier="pro")
    assert tier == "pro"

    # 5. Default fallback to demo
    tier = get_current_tier(authorization=None, tier=None)
    assert tier == "demo"


def test_require_pro_tier_dependency():
    """Verify require_pro_tier enforces payment requirement."""
    # Pro tier succeeds
    res = require_pro_tier(tier="pro")
    assert res == "pro"

    res_author = require_pro_tier(tier="author_pro")
    assert res_author == "author_pro"

    # Demo tier raises 402 Payment Required
    with pytest.raises(HTTPException) as exc_info:
        require_pro_tier(tier="demo")
    assert exc_info.value.status_code == 402
    assert exc_info.value.detail["error"] == "payment_required"


def test_generate_license_key():
    """Verify license key follows BC-TIER-XXXX-XXXX-XXXX format."""
    key = generate_license_key("PRO")
    assert key.startswith("BC-PRO-")
    parts = key.split("-")
    assert len(parts) == 5
    assert parts[0] == "BC"
    assert parts[1] == "PRO"
    assert len(parts[2]) == 4
    assert len(parts[3]) == 4
    assert len(parts[4]) == 4
