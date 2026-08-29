"""
Leads API router — Endpoints for creating, querying, managing, and re-syncing captured leads.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lead, Job, EmailSyncLog
from app.db.session import get_db
from app.services.email.sync_service import EmailSyncService

logger = logging.getLogger("bookcraft.leads")

router = APIRouter(prefix="/leads", tags=["Leads"])

EMAIL_REGEX = re.compile(r"^[\w\.\+-]+@[\w\.-]+\.\w+$")


# ── Pydantic Request / Response Schemas ───────────────────────────────────────

class LeadCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Full name of the lead")
    email: str = Field(..., description="Valid email address")
    marketing_consent: bool = Field(default=True, description="Consent for marketing communications")
    tier: str = Field(default="demo", description="Tier: 'demo', 'pro', 'pro_pass'")
    document_name: Optional[str] = None
    document_type: Optional[str] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)


class LeadResponse(BaseModel):
    id: str
    name: str
    email: str
    marketing_consent: bool
    tier: str
    status: str
    source: str
    document_name: Optional[str] = None
    document_type: Optional[str] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    is_truncated: bool
    email_marketing_status: str
    email_provider_id: Optional[str] = None
    email_synced_at: Optional[str] = None
    extra_metadata: Dict[str, Any]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class LeadDetailResponse(LeadResponse):
    jobs: List[Dict[str, Any]] = Field(default_factory=list)
    email_sync_logs: List[Dict[str, Any]] = Field(default_factory=list)


class LeadListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    leads: List[LeadResponse]


class LeadStatsSummary(BaseModel):
    total_leads: int
    demo_tier_count: int
    pro_tier_count: int
    marketing_consented_count: int
    email_synced_count: int
    email_failed_count: int
    recent_24h_count: int


# ── Helper Validators ─────────────────────────────────────────────────────────

def validate_email_format(email: str) -> str:
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_email", "message": f"'{email}' is not a valid email address."},
        )
    return cleaned


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update a lead",
    description="Captures prospect name, email, and marketing consent.",
)
async def create_lead(
    lead_in: LeadCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    cleaned_email = validate_email_format(lead_in.email)
    cleaned_name = lead_in.name.strip()
    if len(cleaned_name) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "invalid_name", "message": "Name must be at least 2 characters."},
        )

    # Check for existing lead by email to update or create
    stmt = select(Lead).where(Lead.email == cleaned_email)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if lead:
        lead.name = cleaned_name
        lead.marketing_consent = lead_in.marketing_consent
        if lead_in.tier:
            lead.tier = lead_in.tier
        if lead_in.document_name:
            lead.document_name = lead_in.document_name
        if lead_in.document_type:
            lead.document_type = lead_in.document_type
        if lead_in.extra_metadata:
            merged = dict(lead.extra_metadata or {})
            merged.update(lead_in.extra_metadata)
            lead.extra_metadata = merged
        lead.updated_at = datetime.now(timezone.utc)
        logger.info(f"Updated existing lead {lead.id} ({lead.email})")
    else:
        lead = Lead(
            name=cleaned_name,
            email=cleaned_email,
            marketing_consent=lead_in.marketing_consent,
            tier=lead_in.tier or "demo",
            document_name=lead_in.document_name,
            document_type=lead_in.document_type,
            extra_metadata=lead_in.extra_metadata or {},
        )
        db.add(lead)
        logger.info(f"Created new lead {lead.id} ({lead.email})")

    await db.commit()
    await db.refresh(lead)

    # Dispatch email sync in background
    sync_service = EmailSyncService()
    background_tasks.add_task(sync_service.sync_lead, lead.id)

    return lead.to_dict()


@router.get(
    "",
    response_model=LeadListResponse,
    summary="List all captured leads",
    description="Returns paginated leads with optional search and tier filtering.",
)
async def list_leads(
    skip: int = Query(0, ge=0, description="Offset for pagination"),
    limit: int = Query(50, ge=1, le=500, description="Limit for pagination"),
    tier: Optional[str] = Query(None, description="Filter by tier ('demo', 'pro')"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search query across email and name"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Lead)

    if tier:
        query = query.where(Lead.tier == tier)
    if status:
        query = query.where(Lead.status == status)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.where(or_(Lead.name.ilike(search_term), Lead.email.ilike(search_term)))

    # Total count query
    count_query = select(func.count()).select_from(query.subquery())
    total_res = await db.execute(count_query)
    total_count = total_res.scalar() or 0

    # Paginated results ordered by creation descending
    paginated_query = query.order_by(desc(Lead.created_at)).offset(skip).limit(limit)
    res = await db.execute(paginated_query)
    leads = res.scalars().all()

    return {
        "total": total_count,
        "skip": skip,
        "limit": limit,
        "leads": [lead.to_dict() for lead in leads],
    }


@router.get(
    "/stats/summary",
    response_model=LeadStatsSummary,
    summary="Get aggregated lead statistics",
    description="Returns aggregate counts and conversion metrics.",
)
async def get_lead_stats(db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count(Lead.id))) or 0
    demo_count = await db.scalar(select(func.count(Lead.id)).where(Lead.tier == "demo")) or 0
    from app.core.security import PAID_TIERS
    pro_count = await db.scalar(select(func.count(Lead.id)).where(Lead.tier.in_(PAID_TIERS))) or 0
    consent_count = await db.scalar(select(func.count(Lead.id)).where(Lead.marketing_consent.is_(True))) or 0
    synced_count = await db.scalar(select(func.count(Lead.id)).where(Lead.email_marketing_status == "synced")) or 0
    failed_count = await db.scalar(select(func.count(Lead.id)).where(Lead.email_marketing_status == "failed")) or 0

    # Recent 24h count
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_count = await db.scalar(select(func.count(Lead.id)).where(Lead.created_at >= cutoff)) or 0

    return {
        "total_leads": total,
        "demo_tier_count": demo_count,
        "pro_tier_count": pro_count,
        "marketing_consented_count": consent_count,
        "email_synced_count": synced_count,
        "email_failed_count": failed_count,
        "recent_24h_count": recent_count,
    }


@router.get(
    "/{lead_id}",
    response_model=LeadDetailResponse,
    summary="Get single lead details",
    description="Returns comprehensive details including parsing jobs and email sync history.",
)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with id '{lead_id}' not found.",
        )

    data = lead.to_dict()
    data["jobs"] = [job.to_dict() for job in lead.jobs] if lead.jobs else []
    data["email_sync_logs"] = [log.to_dict() for log in lead.email_sync_logs] if lead.email_sync_logs else []
    return data


@router.post(
    "/{lead_id}/resync",
    summary="Trigger email sync for lead",
    description="Manually re-attempts synchronization with configured email marketing provider.",
)
async def resync_lead(
    lead_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Lead).where(Lead.id == lead_id)
    result = await db.execute(stmt)
    lead = result.scalar_one_or_none()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with id '{lead_id}' not found.",
        )

    sync_service = EmailSyncService()
    # Run sync synchronously or in background
    sync_res = await sync_service.sync_lead(lead.id)
    return {
        "lead_id": lead.id,
        "sync_result": sync_res.to_dict(),
    }
