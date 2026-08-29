"""
Pluggable Email Marketing Provider Interface.
Supports NullProvider (local/test), WebhookEmailProvider, SendGrid, and Mailchimp.
"""
from __future__ import annotations
import abc
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger("bookcraft.email_provider")


@dataclass
class SyncResult:
    """Standardized response from an EmailMarketingProvider."""
    success: bool
    provider: str
    provider_id: Optional[str] = None
    error: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "provider": self.provider,
            "provider_id": self.provider_id,
            "error": self.error,
            "payload": self.payload,
            "timestamp": self.timestamp.isoformat(),
        }


class EmailMarketingProvider(abc.ABC):
    """Abstract interface for external email marketing and CRM platforms."""

    @abc.abstractmethod
    async def sync_contact(
        self,
        name: str,
        email: str,
        marketing_consent: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        """
        Create or update a subscriber contact in the target email system.
        """
        pass

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Verify connectivity/credentials with the external service."""
        pass


class NullProvider(EmailMarketingProvider):
    """
    Default mock provider for local development, automated testing, and offline modes.
    Always succeeds and records synthetic provider IDs.
    """

    async def sync_contact(
        self,
        name: str,
        email: str,
        marketing_consent: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        generated_id = f"null_sub_{uuid.uuid4().hex[:12]}"
        payload = {
            "name": name,
            "email": email,
            "marketing_consent": marketing_consent,
            "metadata": metadata or {},
            "provider_mode": "mock_null_provider",
        }
        logger.info(
            f"[NullProvider] Mock sync contact: name='{name}', email='{email}', "
            f"consent={marketing_consent} -> assigned id {generated_id}"
        )
        return SyncResult(
            success=True,
            provider="null",
            provider_id=generated_id,
            payload=payload,
        )

    async def health_check(self) -> bool:
        return True


class WebhookEmailProvider(EmailMarketingProvider):
    """
    Dispatches HTTP POST JSON webhook to external workflows (Zapier, Make, HubSpot, n8n).
    """

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.EMAIL_WEBHOOK_URL

    async def sync_contact(
        self,
        name: str,
        email: str,
        marketing_consent: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        if not self.webhook_url:
            logger.warning("[WebhookEmailProvider] No EMAIL_WEBHOOK_URL configured.")
            return SyncResult(
                success=False,
                provider="webhook",
                error="EMAIL_WEBHOOK_URL is not configured.",
                payload={"name": name, "email": email},
            )

        payload = {
            "event": "lead_captured",
            "name": name,
            "email": email,
            "marketing_consent": marketing_consent,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "bookcraft_demo_tier",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self.webhook_url, json=payload)
                if 200 <= resp.status_code < 300:
                    logger.info(f"[WebhookEmailProvider] Successfully posted webhook for {email}: {resp.status_code}")
                    return SyncResult(
                        success=True,
                        provider="webhook",
                        provider_id=f"webhook_{resp.status_code}",
                        payload=payload,
                    )
                else:
                    error_msg = f"Webhook HTTP error {resp.status_code}: {resp.text[:200]}"
                    logger.error(f"[WebhookEmailProvider] {error_msg}")
                    return SyncResult(
                        success=False,
                        provider="webhook",
                        error=error_msg,
                        payload=payload,
                    )
        except Exception as exc:
            error_msg = f"Webhook request exception: {exc}"
            logger.error(f"[WebhookEmailProvider] {error_msg}")
            return SyncResult(
                success=False,
                provider="webhook",
                error=error_msg,
                payload=payload,
            )

    async def health_check(self) -> bool:
        return bool(self.webhook_url)


class SendGridEmailProvider(EmailMarketingProvider):
    """
    SendGrid Marketing Contacts API v3 Integration.
    PUT https://api.sendgrid.com/v3/marketing/contacts
    """

    def __init__(self, api_key: Optional[str] = None, list_id: Optional[str] = None):
        self.api_key = api_key or settings.SENDGRID_API_KEY
        self.list_id = list_id or settings.SENDGRID_LIST_ID

    async def sync_contact(
        self,
        name: str,
        email: str,
        marketing_consent: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        if not self.api_key:
            return SyncResult(
                success=False,
                provider="sendgrid",
                error="SENDGRID_API_KEY is not configured.",
                payload={"name": name, "email": email},
            )

        name_parts = name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        contact = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "custom_fields": {
                "marketing_consent": str(marketing_consent),
                "platform": "bookcraft_ai",
            },
        }

        body: Dict[str, Any] = {"contacts": [contact]}
        if self.list_id:
            body["list_ids"] = [self.list_id]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.put(
                    "https://api.sendgrid.com/v3/marketing/contacts",
                    json=body,
                    headers=headers,
                )
                if resp.status_code in (200, 202):
                    data = resp.json()
                    job_id = data.get("job_id", f"sg_{uuid.uuid4().hex[:8]}")
                    return SyncResult(
                        success=True,
                        provider="sendgrid",
                        provider_id=job_id,
                        payload=body,
                    )
                else:
                    return SyncResult(
                        success=False,
                        provider="sendgrid",
                        error=f"SendGrid API error ({resp.status_code}): {resp.text[:200]}",
                        payload=body,
                    )
        except Exception as exc:
            return SyncResult(
                success=False,
                provider="sendgrid",
                error=f"SendGrid request failed: {exc}",
                payload=body,
            )

    async def health_check(self) -> bool:
        return bool(self.api_key)


class MailchimpEmailProvider(EmailMarketingProvider):
    """
    Mailchimp Marketing API v3 Integration.
    POST https://<dc>.api.mailchimp.com/3.0/lists/{list_id}/members
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        list_id: Optional[str] = None,
        server_prefix: Optional[str] = None,
    ):
        self.api_key = api_key or settings.MAILCHIMP_API_KEY
        self.list_id = list_id or settings.MAILCHIMP_LIST_ID
        self.server_prefix = server_prefix or settings.MAILCHIMP_SERVER_PREFIX

    async def sync_contact(
        self,
        name: str,
        email: str,
        marketing_consent: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SyncResult:
        if not self.api_key or not self.list_id:
            return SyncResult(
                success=False,
                provider="mailchimp",
                error="MAILCHIMP_API_KEY or MAILCHIMP_LIST_ID not configured.",
                payload={"name": name, "email": email},
            )

        name_parts = name.strip().split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        body = {
            "email_address": email,
            "status": "subscribed" if marketing_consent else "transactional",
            "merge_fields": {
                "FNAME": first_name,
                "LNAME": last_name,
            },
        }

        url = f"https://{self.server_prefix}.api.mailchimp.com/3.0/lists/{self.list_id}/members"
        auth = ("anystring", self.api_key)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=body, auth=auth)
                if resp.status_code in (200, 201):
                    data = resp.json()
                    member_id = data.get("id", f"mc_{uuid.uuid4().hex[:8]}")
                    return SyncResult(
                        success=True,
                        provider="mailchimp",
                        provider_id=member_id,
                        payload=body,
                    )
                else:
                    return SyncResult(
                        success=False,
                        provider="mailchimp",
                        error=f"Mailchimp API error ({resp.status_code}): {resp.text[:200]}",
                        payload=body,
                    )
        except Exception as exc:
            return SyncResult(
                success=False,
                provider="mailchimp",
                error=f"Mailchimp request failed: {exc}",
                payload=body,
            )

    async def health_check(self) -> bool:
        return bool(self.api_key and self.list_id)
