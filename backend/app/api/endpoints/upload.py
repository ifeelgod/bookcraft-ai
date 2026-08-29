"""
POST /api/upload
Accepts .doc, .docx, .pdf, and .md files along with Lead Capture details (Name, Email, Marketing Consent).
Enforces 15-page demo tier restrictions, persists leads into PostgreSQL/SQLite, and launches parsing.
GET  /api/ast/{job_id}
Returns the full DocumentAST for a completed job.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Header,
    UploadFile,
    status,
)
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import async_session_factory
from app.db.models import Lead, Job as DBJob
from app.db.session import get_db, get_db_context
from app.models.job import JobStatus, create_job, update_job, get_job
from app.models.ast_cache import get_ast, store_ast
from app.services.parser import ParseError, CorruptFileError, UnsupportedFormatError
from app.services.restriction_engine import (
    preflight_check_and_slice,
    slice_ast_for_demo,
    PreflightResult,
)
from app.services.email.sync_service import sync_lead_email_background

logger = logging.getLogger("bookcraft.upload")

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "application/pdf": "pdf",
    "text/markdown": "md",
}

ALLOWED_EXTENSIONS = {".doc", ".docx", ".pdf", ".md"}
EMAIL_REGEX = re.compile(r"^[\w\.\+-]+@[\w\.-]+\.\w+$")


@router.post(
    "/upload",
    summary="Upload a manuscript with lead capture details",
    description=(
        "Accepts a Word (.doc, .docx), PDF, or Markdown (.md) file along with user name, email, "
        "and marketing consent. Restricts demo tier manuscripts to 15 pages, persists lead to SQL "
        "database, and launches asynchronous parsing."
    ),
    status_code=202,
)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="The manuscript file (.doc, .docx, .pdf, .md)"),
    name: Optional[str] = Form(None, description="Full name of author/user"),
    email: Optional[str] = Form(None, description="Valid email address"),
    marketing_consent: bool = Form(True, description="Opt-in consent for marketing"),
    tier: str = Form("demo", description="Tier identifier ('demo' or 'pro')"),
    authorization: Optional[str] = Header(None, description="Optional Pro JWT bearer token"),
    db: AsyncSession = Depends(get_db),
):
    # ── Verify tier authorization if token supplied ──────────────────────────
    active_tier = tier.lower().strip() if tier else "demo"
    jwt_claims = None

    if authorization and authorization.strip().lower().startswith("bearer "):
        token = authorization.strip()[7:].strip()
        try:
            from app.core.security import PAID_TIERS, verify_access_token
            jwt_claims = verify_access_token(token)
            token_tier = jwt_claims.get("tier", "pro").lower().strip()
            if token_tier in PAID_TIERS:
                active_tier = token_tier
        except Exception as exc:
            logger.warning("Invalid JWT bearer token during upload: %s", exc)

    from app.core.security import PAID_TIERS
    is_demo = (active_tier not in PAID_TIERS)

    # ── Validate Lead details for Demo tier ───────────────────────────────────
    cleaned_name = (name or "").strip()
    cleaned_email = (email or "").strip().lower()

    if not is_demo:
        # For Pro uploads, use token claims if form fields are omitted
        if not cleaned_name and jwt_claims and jwt_claims.get("name"):
            cleaned_name = jwt_claims["name"]
        elif not cleaned_name:
            cleaned_name = "Pro Author"

        if not cleaned_email and jwt_claims and jwt_claims.get("sub"):
            cleaned_email = jwt_claims["sub"].strip().lower()
        elif not cleaned_email:
            cleaned_email = "pro@bookcraft.ai"

    if is_demo:
        if not cleaned_name or len(cleaned_name) < 2:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "missing_name",
                    "message": "Please provide your full name to generate your free 15-page preview.",
                },
            )
        if not cleaned_email or not EMAIL_REGEX.match(cleaned_email):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "error": "invalid_email",
                    "message": f"'{email}' is not a valid email address.",
                },
            )

    # ── Validate extension ────────────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_file_type",
                "message": f"'{suffix}' is not supported. Please upload a .doc, .docx, .pdf, or .md file.",
                "allowed": [".doc", ".docx", ".pdf", ".md"],
            },
        )

    file_type = suffix.lstrip(".")

    # ── Validate MIME (best-effort) ───────────────────────────────────────────
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        logger.warning(
            "Unexpected content-type '%s' for '%s' — proceeding by extension.",
            file.content_type, file.filename,
        )

    # ── Read + size-check ─────────────────────────────────────────────────────
    content = await file.read()
    size_bytes = len(content)

    if size_bytes == 0:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "empty_file",
                "message": "The uploaded file is empty. Please upload a valid manuscript.",
            },
        )

    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "message": (
                    f"File is {size_bytes / 1_048_576:.1f} MB — "
                    f"maximum allowed is {settings.MAX_UPLOAD_SIZE_MB} MB."
                ),
            },
        )

    # ── In-Memory Job Creation ────────────────────────────────────────────────
    job = create_job(file_name=file.filename, file_type=file_type)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{job.job_id}_{Path(file.filename or 'upload').name}"
    dest_path = upload_dir / safe_name

    async with aiofiles.open(dest_path, "wb") as fh:
        await fh.write(content)

    logger.info("Saved upload '%s' → %s (%d bytes)", file.filename, dest_path, size_bytes)

    # ── Stage 1: Ingestion Pre-Flight Slicing ──────────────────────────────────
    preflight: PreflightResult = preflight_check_and_slice(
        file_path=str(dest_path),
        file_type=file_type,
        is_demo=is_demo,
    )

    # ── Database: Upsert Lead & Record Job ─────────────────────────────────────
    lead_stmt = select(Lead).where(Lead.email == cleaned_email)
    res = await db.execute(lead_stmt)
    lead = res.scalar_one_or_none()

    if lead:
        # Check Tier 2 monthly limit: up to 9 books / month
        if active_tier == "tier_2_monthly":
            from datetime import timedelta
            from sqlalchemy import func
            from app.db.models import Job
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            jobs_stmt = select(func.count(Job.id)).where(
                Job.lead_id == lead.id,
                Job.created_at >= thirty_days_ago
            )
            jobs_res = await db.execute(jobs_stmt)
            jobs_count = jobs_res.scalar_one() or 0
            if jobs_count >= 9:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "tier_limit_reached",
                        "message": "Tier 2 monthly limit reached (9 books / month). Please upgrade to Tier 3 for unlimited books."
                    }
                )

        lead.name = cleaned_name
        lead.marketing_consent = marketing_consent
        lead.document_name = file.filename
        lead.document_type = file_type
        lead.document_size_bytes = size_bytes
        lead.page_count = preflight.original_pages or preflight.sliced_pages
        lead.word_count = preflight.original_words or preflight.sliced_words
        lead.is_truncated = preflight.is_truncated
        lead.updated_at = datetime.now(timezone.utc)
    else:
        lead = Lead(
            name=cleaned_name,
            email=cleaned_email,
            marketing_consent=marketing_consent,
            tier=active_tier,
            document_name=file.filename,
            document_type=file_type,
            document_size_bytes=size_bytes,
            page_count=preflight.original_pages or preflight.sliced_pages,
            word_count=preflight.original_words or preflight.sliced_words,
            is_truncated=preflight.is_truncated,
            source="demo_upload" if is_demo else "pro_upload",
            extra_metadata={
                "upload_ip": "127.0.0.1",
                "preflight_message": preflight.message,
            },
        )
        db.add(lead)

    await db.commit()
    await db.refresh(lead)

    # Create persistent DB Job record
    db_job = DBJob(
        id=job.job_id,
        lead_id=lead.id,
        job_type="parse",
        status="pending",
        progress=0,
        message="Upload received, queued for AI parsing.",
        file_name=file.filename,
        file_type=file_type,
        input_path=preflight.file_path,
        is_demo=is_demo,
        is_truncated=preflight.is_truncated,
    )
    db.add(db_job)
    await db.commit()

    # ── Asynchronous Background Tasks ─────────────────────────────────────────
    # 1. Asynchronous Email Provider Sync
    background_tasks.add_task(sync_lead_email_background, lead.id)

    # 2. Background Parsing & AST Normalization Pipeline
    background_tasks.add_task(
        _run_parse_job,
        job_id=job.job_id,
        file_path=preflight.file_path,
        file_type=file_type,
        is_demo=is_demo,
        lead_id=lead.id,
    )

    return {
        "job_id": job.job_id,
        "lead_id": lead.id,
        "tier": active_tier,
        "status": job.status,
        "is_truncated": preflight.is_truncated,
        "preflight_message": preflight.message,
        "message": (
            "File received and validated. AI parsing has started. "
            "Poll GET /api/status/{job_id} for progress."
        ),
        "file_name": file.filename,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / 1_048_576, 2),
    }


async def _run_parse_job(
    job_id: str,
    file_path: str,
    file_type: str,
    is_demo: bool = True,
    lead_id: Optional[str] = None,
) -> None:
    """Background task — runs extraction + AI normalization + Stage 2 AST demo slicing."""
    from app.services.parser import parse_document

    update_job(job_id, status=JobStatus.processing, progress=5, message="Initializing parser…")
    await _update_db_job(job_id, status="processing", progress=5, message="Initializing parser…")

    try:
        # Step 1: Run Parser
        ast = await parse_document(file_path=file_path, file_type=file_type, job_id=job_id)

        # Step 2: Stage 2 Restriction Engine — Slice AST for Demo Tier
        if is_demo:
            ast = slice_ast_for_demo(ast, is_demo=True)
            # Re-store sliced AST in cache
            store_ast(job_id, ast)

        summary_data = {
            "title": ast.metadata.title,
            "author": ast.metadata.author,
            "genre": ast.metadata.genre,
            "chapters": len(ast.chapters),
            "total_blocks": sum(len(c.content) for c in ast.chapters),
            "total_words": sum(c.word_count or 0 for c in ast.chapters),
            "is_demo": is_demo,
        }

        # Update in-memory job
        update_job(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="Document parsed and structured successfully.",
            result={
                "ast_summary": summary_data,
                "ast": ast.model_dump(),
            },
        )

        # Update DB job
        await _update_db_job(
            job_id,
            status="completed",
            progress=100,
            message="Document parsed and structured successfully.",
            ast_json=ast.model_dump(),
        )

        logger.info("Job %s complete: %d chapters (demo=%s)", job_id, len(ast.chapters), is_demo)

    except CorruptFileError as exc:
        await _fail_job_both(job_id, "corrupt_file", str(exc))
    except UnsupportedFormatError as exc:
        await _fail_job_both(job_id, "unsupported_format", str(exc))
    except ParseError as exc:
        await _fail_job_both(job_id, "parse_error", str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in job %s", job_id)
        await _fail_job_both(
            job_id,
            "internal_error",
            "An unexpected error occurred during parsing. Please try again or contact support.",
        )


async def _update_db_job(
    job_id: str,
    status: str,
    progress: int,
    message: str,
    ast_json: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> None:
    """Safely update persistent DBJob record."""
    try:
        async with get_db_context() as db:
            stmt = select(DBJob).where(DBJob.id == job_id)
            res = await db.execute(stmt)
            db_job = res.scalar_one_or_none()
            if db_job:
                db_job.status = status
                db_job.progress = progress
                db_job.message = message
                if ast_json is not None:
                    db_job.ast_json = ast_json
                if error_message is not None:
                    db_job.error_message = error_message
                db_job.updated_at = datetime.now(timezone.utc)
                await db.commit()
    except Exception as exc:
        logger.warning(f"Could not update DB job {job_id}: {exc}")


async def _fail_job_both(job_id: str, error_code: str, message: str) -> None:
    logger.error("Job %s failed [%s]: %s", job_id, error_code, message)
    update_job(
        job_id,
        status=JobStatus.failed,
        progress=0,
        message=message,
        error=message,
    )
    await _update_db_job(
        job_id,
        status="failed",
        progress=0,
        message=message,
        error_message=message,
    )


# ── GET /api/ast/{job_id} ─────────────────────────────────────────────────────

@router.get(
    "/ast/{job_id}",
    summary="Retrieve parsed DocumentAST",
    description="Returns the full DocumentAST for a completed parse job.",
)
async def get_document_ast(job_id: str, db: AsyncSession = Depends(get_db)):
    job = get_job(job_id)
    if not job:
        # Check database if not in memory
        stmt = select(DBJob).where(DBJob.id == job_id)
        res = await db.execute(stmt)
        db_job = res.scalar_one_or_none()
        if not db_job:
            raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

        if db_job.status == "failed":
            raise HTTPException(
                status_code=422,
                detail={"error": "job_failed", "message": db_job.error_message or "Parsing failed.", "job_id": job_id},
            )
        if db_job.status != "completed":
            raise HTTPException(
                status_code=202,
                detail={"error": "job_not_ready", "message": f"Job is {db_job.status}.", "job_id": job_id},
            )
        if db_job.ast_json:
            return {"job_id": job_id, "ast": db_job.ast_json}

    if job and job.status == JobStatus.failed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "job_failed",
                "message": job.error or "Parsing failed.",
                "job_id": job_id,
            },
        )

    if job and job.status != JobStatus.completed:
        raise HTTPException(
            status_code=202,
            detail={
                "error": "job_not_ready",
                "message": f"Job is still {job.status} ({job.progress}%). Please wait.",
                "job_id": job_id,
                "status": job.status,
                "progress": job.progress,
            },
        )

    ast = get_ast(job_id)
    if not ast:
        # Fallback: try to reconstruct from job result or DB
        if job and job.result and "ast" in job.result:
            return {"job_id": job_id, "ast": job.result["ast"]}
        raise HTTPException(
            status_code=404,
            detail="AST not found in cache. The job may have expired.",
        )

    return {
        "job_id": job_id,
        "ast": ast.model_dump(),
        "summary": {
            "title": ast.metadata.title,
            "author": ast.metadata.author,
            "genre": ast.metadata.genre,
            "chapters": len(ast.chapters),
            "total_words": sum(c.word_count or 0 for c in ast.chapters),
        },
    }
