"""
Email marketing sync orchestration service.
Handles background dispatch, provider selection, and audit logging to EmailSyncLog.
"""
from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from app.core.config import settings
from app.db.session import get_db_context
from app.db.models import Lead, EmailSyncLog
from app.services.email.provider import (
    EmailMarketingProvider,
    NullProvider,
    WebhookEmailProvider,
    SendGridEmailProvider,
    MailchimpEmailProvider,
    SyncResult,
)

logger = logging.getLogger("bookcraft.email_sync")


def get_email_provider(provider_type: Optional[str] = None) -> EmailMarketingProvider:
    """Factory function returning the configured EmailMarketingProvider instance."""
    provider_name = (provider_type or settings.EMAIL_MARKETING_PROVIDER or "null").lower().strip()

    if provider_name == "webhook":
        return WebhookEmailProvider()
    elif provider_name == "sendgrid":
        return SendGridEmailProvider()
    elif provider_name == "mailchimp":
        return MailchimpEmailProvider()
    else:
        # Default fallback to NullProvider
        return NullProvider()


class EmailSyncService:
    """Service to synchronize leads with external email marketing providers and log results."""

    def __init__(self, provider: Optional[EmailMarketingProvider] = None):
        self.provider = provider or get_email_provider()

    async def sync_lead(self, lead_id: str) -> SyncResult:
        """
        Load lead from database, sync contact details with provider,
        and log the transaction in email_sync_logs.
        """
        async with get_db_context() as db:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()

            if not lead:
                error_msg = f"Lead with id '{lead_id}' not found for email sync."
                logger.error(error_msg)
                return SyncResult(
                    success=False,
                    provider="unknown",
                    error=error_msg,
                )

            # Perform sync with the provider
            sync_res = await self.provider.sync_contact(
                name=lead.name,
                email=lead.email,
                marketing_consent=lead.marketing_consent,
                metadata={
                    "lead_id": lead.id,
                    "tier": lead.tier,
                    "document_name": lead.document_name,
                    "document_type": lead.document_type,
                    "page_count": lead.page_count,
                    "word_count": lead.word_count,
                    "is_truncated": lead.is_truncated,
                    "source": lead.source,
                },
            )

            # Record audit log in EmailSyncLog
            log_entry = EmailSyncLog(
                lead_id=lead.id,
                provider=sync_res.provider,
                status="success" if sync_res.success else "failed",
                payload=sync_res.payload,
                error=sync_res.error,
                attempted_at=datetime.now(timezone.utc),
            )
            db.add(log_entry)

            # Update lead record with marketing status
            if sync_res.success:
                lead.email_marketing_status = "synced"
                lead.email_provider_id = sync_res.provider_id
                lead.email_synced_at = datetime.now(timezone.utc)
                lead.email_sync_error = None
            else:
                lead.email_marketing_status = "failed"
                lead.email_sync_error = sync_res.error

            await db.commit()
            logger.info(
                f"Email sync finished for lead '{lead.id}' ({lead.email}): "
                f"status={lead.email_marketing_status}, provider={sync_res.provider}"
            )
            return sync_res


async def sync_lead_email_background(lead_id: str) -> None:
    """Helper entry point for FastAPI BackgroundTasks."""
    try:
        service = EmailSyncService()
        await service.sync_lead(lead_id)
    except Exception as exc:
        logger.exception(f"Background email sync failed for lead {lead_id}: {exc}")
