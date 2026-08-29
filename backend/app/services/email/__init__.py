"""
Email marketing service package for BookCraft AI.
Provides pluggable provider interface (Null, Webhook, SendGrid, Mailchimp)
and asynchronous sync orchestration.
"""
from app.services.email.provider import (
    EmailMarketingProvider,
    SyncResult,
    NullProvider,
    WebhookEmailProvider,
    SendGridEmailProvider,
    MailchimpEmailProvider,
)
from app.services.email.sync_service import (
    EmailSyncService,
    get_email_provider,
    sync_lead_email_background,
)

__all__ = [
    "EmailMarketingProvider",
    "SyncResult",
    "NullProvider",
    "WebhookEmailProvider",
    "SendGridEmailProvider",
    "MailchimpEmailProvider",
    "EmailSyncService",
    "get_email_provider",
    "sync_lead_email_background",
]
