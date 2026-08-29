"""
Security, JWT token issuance, verification, and tier authorization dependencies.
Uses python-jose with HS256 algorithm for tamper-proof access tokens.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, Header, HTTPException, Query, status
from jose import JWTError, jwt

from app.core.config import settings

logger = logging.getLogger("bookcraft.security")

# Standard Pro scopes granted upon successful upgrade
DEFAULT_PRO_SCOPES: List[str] = [
    "unlimited_pages",
    "docx_export",
    "md_export",
    "epub_export",
    "pdf_export",
    "custom_typography",
    "full_manuscript_ai",
]


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Generate a cryptographically signed HS256 JWT access token.
    Contains claims for user email (sub), tier, granted scopes, issuance time, and expiration.
    """
    to_encode = data.copy()
    now = datetime.now(timezone.utc)

    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.setdefault("iss", "bookcraft-ai")
    to_encode.setdefault("iat", int(now.timestamp()))
    to_encode["exp"] = int(expire.timestamp())
    to_encode.setdefault("jti", f"tok_{int(now.timestamp())}_{uuid.uuid4().hex[:8]}")

    # Ensure tier and capabilities
    if "tier" not in to_encode:
        to_encode["tier"] = "pro"

    if "scopes" not in to_encode:
        to_encode["scopes"] = DEFAULT_PRO_SCOPES

    encoded_jwt = jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded_jwt


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and verify a signed JWT token.
    Raises JWTError if token is invalid, tampered, or expired.
    """
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# Standard list of all paid tiers
PAID_TIERS = (
    "pro",
    "pro_pass",
    "author_pro",
    "unlimited",
    "tier_1_pass",
    "tier_2_monthly",
    "tier_3_monthly",
    "tier_3_annual",
)


def get_current_user_claims(
    authorization: Optional[str] = Header(None),
) -> Optional[Dict[str, Any]]:
    """
    Extract and verify JWT claims from Authorization Bearer header.
    Returns None if header is absent or token is invalid.
    """
    if not authorization:
        return None

    token = authorization.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()

    try:
        claims = verify_access_token(token)
        return claims
    except JWTError as exc:
        logger.debug("Failed to verify access token: %s", exc)
        return None


def get_current_tier(
    authorization: Optional[str] = Header(None, description="Bearer Pro JWT token"),
    tier: Optional[str] = Query(None, description="Explicit tier override (for testing/direct pass)"),
) -> str:
    """
    FastAPI dependency that resolves the active user tier:
    1. Inspects Bearer token in Authorization header.
    2. Inspects query/form parameter `tier`.
    3. Defaults to 'demo' if no valid Pro credentials exist.
    """
    # 1. Bearer Token Verification
    if authorization:
        token = authorization.strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()

        try:
            claims = verify_access_token(token)
            token_tier = claims.get("tier", "pro").lower().strip()
            if token_tier in PAID_TIERS:
                return token_tier
        except JWTError:
            logger.warning("Invalid or expired JWT token provided in Authorization header.")

    # 2. Direct parameter fallback (if passed explicitly)
    if tier:
        cleaned = tier.lower().strip()
        if cleaned in PAID_TIERS:
            return cleaned

    # 3. Default to demo tier
    return "demo"


def require_pro_tier(
    tier: str = Depends(get_current_tier),
) -> str:
    """
    FastAPI dependency that raises HTTP 402 Payment Required
    if the caller is not on a Pro/Author Pro tier.
    """
    if tier not in PAID_TIERS:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "payment_required",
                "message": "This feature requires BookCraft Pro. Please upgrade to continue.",
                "tier": tier,
                "upgrade_url": "/checkout",
            },
        )
    return tier


def generate_license_key(tier: str = "PRO") -> str:
    """
    Generate a human-readable license key format (e.g. BC-PRO-A7B2-9F4C-81E0).
    """
    prefix = f"BC-{tier.upper()}"
    part1 = uuid.uuid4().hex[:4].upper()
    part2 = uuid.uuid4().hex[:4].upper()
    part3 = uuid.uuid4().hex[:4].upper()
    return f"{prefix}-{part1}-{part2}-{part3}"
