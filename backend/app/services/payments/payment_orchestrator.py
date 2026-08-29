"""
Unified Payment Orchestrator.
Coordinates checkout initiation, transaction verification, database record persistence,
lead tier upgrading, and signed Pro JWT access token issuance.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token, generate_license_key
from app.db.models import Lead, Payment
from app.db.session import get_db_context
from app.services.payments.paypal_service import PayPalService
from app.services.payments.stripe_service import StripeService

logger = logging.getLogger("bookcraft.payments.orchestrator")


class PaymentOrchestrator:
    """
    Unified payment gateway management service.
    Orchestrates checkout, capture, database audit recording, and JWT token issuance.
    """

    def __init__(
        self,
        stripe_service: Optional[StripeService] = None,
        paypal_service: Optional[PayPalService] = None,
    ):
        self.stripe = stripe_service or StripeService()
        self.paypal = paypal_service or PayPalService()

    def get_public_config(self) -> Dict[str, Any]:
        """
        Return public gateway configuration for frontend client rendering.
        """
        return {
            "mode": settings.PAYMENT_MODE,
            "stripe": {
                "enabled": False,
                "publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
                "price_pro_pass": "$19.00",
                "price_author_pro": "$29.00",
            },
            "paypal": {
                "enabled": True,
                "client_id": settings.PAYPAL_CLIENT_ID,
                "environment": settings.PAYPAL_ENVIRONMENT,
                "price_tier_1": "$9.00",
                "price_tier_2": "$19.00",
                "price_tier_3_monthly": "$29.00",
                "price_tier_3_annual": "$199.00",
            },
            "tiers": [
                {
                    "id": "demo",
                    "name": "Free Demo",
                    "price_cents": 0,
                    "price_display": "$0",
                    "period": "forever",
                    "features": [
                        "Up to 15 pages output",
                        "Instant PDF preview",
                        "Standard typography presets",
                        "Interactive web editor",
                    ],
                },
                {
                    "id": "tier_1_pass",
                    "name": "Single Book Pass (Tier 1)",
                    "price_cents": 900,
                    "price_display": "$9",
                    "period": "one-time per book",
                    "features": [
                        "Single book unlimited pages",
                        "Print-ready PDF compilation",
                        "Editable Word (.docx) export",
                        "Markdown (.md) export",
                        "EPUB3 ebook export",
                        "30-day edit and re-download window",
                        "Zero watermarks",
                    ],
                },
                {
                    "id": "tier_2_monthly",
                    "name": "Monthly Pro (Tier 2)",
                    "price_cents": 1900,
                    "price_display": "$19",
                    "period": "per month",
                    "popular": True,
                    "features": [
                        "Up to 9 books / month",
                        "Unlimited pages for all titles",
                        "All export formats (PDF, DOCX, MD, EPUB)",
                        "Priority compilation queue",
                        "Continuous updates & cloud backups",
                    ],
                },
                {
                    "id": "tier_3_monthly",
                    "name": "Unlimited Monthly (Tier 3)",
                    "price_cents": 2900,
                    "price_display": "$29",
                    "period": "per month",
                    "features": [
                        "Unlimited books & manuscripts",
                        "Unlimited pages for all titles",
                        "All export formats (PDF, DOCX, MD, EPUB)",
                        "Priority compilation queue",
                        "Custom typography & trim sizes",
                        "Continuous updates & cloud backups",
                    ],
                },
                {
                    "id": "tier_3_annual",
                    "name": "Unlimited Annual (Tier 3)",
                    "price_cents": 19900,
                    "price_display": "$199",
                    "period": "per year",
                    "features": [
                        "Unlimited books & manuscripts",
                        "Unlimited pages for all titles",
                        "All export formats (PDF, DOCX, MD, EPUB)",
                        "Priority compilation queue",
                        "Custom typography & trim sizes",
                        "Continuous updates & cloud backups (Save 40%)",
                    ],
                },
            ],
        }

    async def create_checkout(
        self,
        provider: str,
        tier: str = "pro_pass",
        lead_email: str = "author@example.com",
        lead_name: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a checkout session or order across the requested payment provider.
        """
        provider_clean = (provider or "stripe").lower().strip()

        if provider_clean == "paypal":
            return await self.paypal.create_order(
                tier=tier,
                lead_email=lead_email,
                lead_name=lead_name,
                return_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
            )
        else:
            return await self.stripe.create_checkout_session(
                tier=tier,
                lead_email=lead_email,
                lead_name=lead_name,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata,
            )

    async def verify_and_fulfill(
        self,
        provider: str,
        session_id: Optional[str] = None,
        order_id: Optional[str] = None,
        lead_email: Optional[str] = None,
        lead_name: Optional[str] = None,
        tier: str = "pro",
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        """
        Verify payment with provider, persist transaction in DB, upgrade lead,
        and issue signed Pro JWT access token.
        """
        provider_clean = (provider or "stripe").lower().strip()
        txn_id = session_id or order_id or f"txn_{provider_clean}_{int(datetime.now(timezone.utc).timestamp())}"

        # 1. Provider Verification
        if provider_clean == "paypal":
            verification = await self.paypal.capture_order(txn_id, tier=tier)
        else:
            verification = await self.stripe.verify_session(txn_id)

        if not verification.get("success", False):
            logger.warning("Verification failed for %s transaction %s", provider_clean, txn_id)
            return {
                "success": False,
                "status": "failed",
                "error": "verification_failed",
                "message": verification.get("message", "Payment verification failed with provider."),
            }

        # 2. Database Record Persistence & Lead Upgrade
        email_clean = (lead_email or verification.get("customer_email") or "author@example.com").lower().strip()
        name_clean = lead_name or "Pro Author"
        amount_cents = verification.get("amount_cents", 900)
        currency = verification.get("currency", "USD").upper()
        granted_tier = tier.lower().strip()

        lead_id = None
        payment_id = None

        try:
            # If db session not passed, create a context session
            async def _persist_to_db(session: AsyncSession):
                nonlocal lead_id, payment_id
                # Find or upsert Lead
                stmt = select(Lead).where(Lead.email == email_clean)
                res = await session.execute(stmt)
                lead = res.scalar_one_or_none()

                if lead:
                    lead.tier = granted_tier
                    lead.name = name_clean if name_clean != "Pro Author" else lead.name
                    lead_id = lead.id
                else:
                    lead = Lead(
                        name=name_clean,
                        email=email_clean,
                        tier=granted_tier,
                        source="checkout_upgrade",
                    )
                    session.add(lead)
                    await session.flush()
                    lead_id = lead.id

                # Create Payment Record
                payment = Payment(
                    lead_id=lead_id,
                    provider=provider_clean,
                    transaction_id=txn_id,
                    amount_cents=amount_cents,
                    currency=currency,
                    tier=granted_tier,
                    status="succeeded",
                )
                session.add(payment)
                await session.commit()
                await session.refresh(payment)
                payment_id = payment.id

            if db is not None:
                await _persist_to_db(db)
            else:
                async with get_db_context() as session:
                    await _persist_to_db(session)

        except Exception as exc:
            logger.warning("Database persistence warning during payment fulfillment: %s", exc)

        # 3. Generate Signed Pro JWT Access Token
        now = datetime.now(timezone.utc)
        expires_delta = timedelta(days=30)
        expires_at = now + expires_delta

        token_payload = {
            "sub": email_clean,
            "name": name_clean,
            "lead_id": lead_id,
            "tier": granted_tier,
            "provider": provider_clean,
            "transaction_id": txn_id,
            "license_key": generate_license_key(granted_tier),
        }

        access_token = create_access_token(data=token_payload, expires_delta=expires_delta)

        logger.info(
            "Fulfillment succeeded for %s: email=%s, tier=%s, txn=%s",
            provider_clean,
            email_clean,
            granted_tier,
            txn_id,
        )

        return {
            "success": True,
            "status": "succeeded",
            "access_token": access_token,
            "tier": granted_tier,
            "email": email_clean,
            "lead_id": lead_id,
            "payment_id": payment_id,
            "transaction_id": txn_id,
            "amount_cents": amount_cents,
            "currency": currency,
            "expires_at": expires_at.isoformat(),
        }


payment_orchestrator = PaymentOrchestrator()
