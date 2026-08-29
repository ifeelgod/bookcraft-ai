"""
Payments API router — Endpoints for Stripe & PayPal checkout, verification, JWT token issuance, and webhooks.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Payment, Lead
from app.db.session import get_db
from app.services.payments.payment_orchestrator import payment_orchestrator

logger = logging.getLogger("bookcraft.payments.api")

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Request / Response Schemas ───────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    provider: str = Field(default="paypal", description="'paypal' only")
    tier: str = Field(default="tier_1_pass", description="'tier_1_pass' ($9), 'tier_2_monthly' ($19/mo), 'tier_3_monthly' ($29/mo), or 'tier_3_annual' ($199/yr)")
    lead_email: str = Field(default="author@example.com", description="User / author email")
    lead_name: Optional[str] = Field(default=None, description="Author full name")
    success_url: Optional[str] = Field(default=None, description="Redirect URL upon successful payment")
    cancel_url: Optional[str] = Field(default=None, description="Redirect URL upon checkout cancellation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Custom tracking metadata")


class CheckoutResponse(BaseModel):
    provider: str
    session_id: str
    checkout_url: str
    amount_cents: int
    currency: str
    tier: str
    mode: Optional[str] = "test"


class VerifyRequest(BaseModel):
    provider: str = Field(default="paypal", description="'paypal' only")
    session_id: Optional[str] = Field(default=None, description="Stripe Checkout session_id")
    order_id: Optional[str] = Field(default=None, description="PayPal order_id")
    lead_email: Optional[str] = Field(default=None, description="Customer email")
    lead_name: Optional[str] = Field(default=None, description="Customer name")
    tier: str = Field(default="tier_1_pass", description="Requested tier: 'tier_1_pass', 'tier_2_monthly', etc.")


class VerifyResponse(BaseModel):
    success: bool
    status: str
    access_token: str
    tier: str
    email: Optional[str] = None
    lead_id: Optional[str] = None
    payment_id: Optional[str] = None
    transaction_id: Optional[str] = None
    amount_cents: Optional[int] = None
    currency: Optional[str] = None
    expires_at: Optional[str] = None


class PaymentRecordResponse(BaseModel):
    id: str
    lead_id: Optional[str] = None
    provider: str
    transaction_id: str
    amount_cents: int
    currency: str
    tier: str
    status: str
    created_at: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/config",
    summary="Get public payment configuration",
    description="Returns public API keys, pricing tiers, and enabled gateway status.",
)
async def get_payment_config():
    """Returns gateway configuration for frontend pricing and checkout rendering."""
    return payment_orchestrator.get_public_config()


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Create a checkout session or order",
    description="Initializes a Stripe Checkout session or PayPal Order v2 in test or live mode.",
)
async def create_checkout(
    payload: CheckoutRequest,
):
    try:
        result = await payment_orchestrator.create_checkout(
            provider=payload.provider,
            tier=payload.tier,
            lead_email=payload.lead_email,
            lead_name=payload.lead_name,
            success_url=payload.success_url,
            cancel_url=payload.cancel_url,
            metadata=payload.metadata,
        )
        return result
    except Exception as exc:
        logger.exception("Checkout creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "checkout_failed", "message": str(exc)},
        )


@router.post(
    "/verify",
    response_model=VerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify payment and issue signed Pro JWT token",
    description=(
        "Validates Stripe session or PayPal order, creates transaction record in database, "
        "upgrades the lead to Pro tier, and issues a cryptographically signed HS256 JWT access token."
    ),
)
async def verify_payment(
    payload: VerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await payment_orchestrator.verify_and_fulfill(
            provider=payload.provider,
            session_id=payload.session_id,
            order_id=payload.order_id,
            lead_email=payload.lead_email,
            lead_name=payload.lead_name,
            tier=payload.tier,
            db=db,
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result,
            )
        return result
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Payment verification exception: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "verification_error", "message": str(exc)},
        )


@router.post(
    "/webhook/{provider}",
    summary="Receive asynchronous payment gateway webhooks",
    description="Handles webhook events for Stripe and PayPal transactions.",
)
async def receive_webhook(
    provider: str,
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: AsyncSession = Depends(get_db),
):
    body = await request.body()
    provider_clean = provider.lower().strip()

    if provider_clean == "stripe":
        verification = payment_orchestrator.stripe.verify_webhook_signature(
            payload=body,
            sig_header=stripe_signature or "",
        )
        if not verification.get("valid"):
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.")

        event = verification.get("event", {})
        event_type = event.get("type", "")
        logger.info("Received Stripe webhook event: %s", event_type)

        if event_type in ("checkout.session.completed", "payment_intent.succeeded"):
            session_obj = event.get("data", {}).get("object", {})
            session_id = session_obj.get("id")
            email = session_obj.get("customer_email") or session_obj.get("metadata", {}).get("lead_email")
            tier = session_obj.get("metadata", {}).get("tier", "pro")
            if session_id:
                await payment_orchestrator.verify_and_fulfill(
                    provider="stripe",
                    session_id=session_id,
                    lead_email=email,
                    tier=tier,
                    db=db,
                )

        return {"status": "received", "provider": "stripe", "event": event_type}

    elif provider_clean == "paypal":
        import json
        try:
            event = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            event = {}

        event_type = event.get("event_type", "")
        logger.info("Received PayPal webhook event: %s", event_type)

        if event_type in ("PAYMENT.CAPTURE.COMPLETED", "CHECKOUT.ORDER.APPROVED"):
            resource = event.get("resource", {})
            order_id = resource.get("id")
            if order_id:
                await payment_orchestrator.verify_and_fulfill(
                    provider="paypal",
                    order_id=order_id,
                    tier="pro",
                    db=db,
                )

        return {"status": "received", "provider": "paypal", "event": event_type}

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported provider '{provider}'.")


@router.get(
    "/history/{email_or_lead_id}",
    response_model=List[PaymentRecordResponse],
    summary="Query payment history for customer",
    description="Returns all completed transactions matching customer email or lead ID.",
)
async def get_payment_history(
    email_or_lead_id: str,
    db: AsyncSession = Depends(get_db),
):
    clean_query = email_or_lead_id.strip()

    # Search for lead first
    stmt = select(Lead).where(
        (Lead.email == clean_query.lower()) | (Lead.id == clean_query)
    )
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()

    if not lead:
        # Query payments directly by transaction_id or lead_id
        pay_stmt = select(Payment).where(
            (Payment.lead_id == clean_query) | (Payment.transaction_id == clean_query)
        ).order_by(desc(Payment.created_at))
        pay_res = await db.execute(pay_stmt)
        payments = pay_res.scalars().all()
        return [p.to_dict() for p in payments]

    pay_stmt = select(Payment).where(Payment.lead_id == lead.id).order_by(desc(Payment.created_at))
    pay_res = await db.execute(pay_stmt)
    payments = pay_res.scalars().all()

    return [p.to_dict() for p in payments]
