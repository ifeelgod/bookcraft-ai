"""
POST /api/upload
Accepts .docx and .pdf files, saves them, and launches an async parsing job.
GET  /api/ast/{job_id}
Returns the full DocumentAST for a completed job.
"""
from __future__ import annotations
import logging
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.models.job import JobStatus, create_job, update_job
from app.models.ast_cache import get_ast
from app.services.parser import ParseError, CorruptFileError, UnsupportedFormatError

logger = logging.getLogger("bookcraft.upload")

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "docx",
    "application/pdf": "pdf",
}

ALLOWED_EXTENSIONS = {".docx", ".pdf"}

# ── Friendly error messages for known error classes ───────────────────────────
_ERROR_HINTS = {
    "CorruptFileError": "The file appears to be corrupted or password-protected.",
    "UnsupportedFormatError": "Only .docx and .pdf files are supported.",
    "ParseError": "The document could not be parsed. Please check the file and try again.",
}


@router.post(
    "/upload",
    summary="Upload a .docx or .pdf file",
    description=(
        "Accepts a Word (.docx) or PDF file, saves it to disk, and returns a job_id "
        "to poll via GET /api/status/{job_id}. When status is 'completed', retrieve "
        "the parsed DocumentAST via GET /api/ast/{job_id}."
    ),
    status_code=202,
)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="The .docx or .pdf manuscript file"),
):
    # ── Validate extension ────────────────────────────────────────────────────
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_file_type",
                "message": f"'{suffix}' is not supported. Please upload a .docx or .pdf file.",
                "allowed": [".docx", ".pdf"],
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

    # ── Create job + persist file ─────────────────────────────────────────────
    job = create_job(file_name=file.filename, file_type=file_type)

    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{job.job_id}_{Path(file.filename or 'upload').name}"
    dest_path = upload_dir / safe_name

    async with aiofiles.open(dest_path, "wb") as fh:
        await fh.write(content)

    logger.info("Saved upload '%s' → %s (%d bytes)", file.filename, dest_path, size_bytes)

    # ── Launch background parse ───────────────────────────────────────────────
    background_tasks.add_task(
        _run_parse_job,
        job_id=job.job_id,
        file_path=str(dest_path),
        file_type=file_type,
    )

    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": (
            "File received. AI parsing has started. "
            "Poll GET /api/status/{job_id} for progress."
        ),
        "file_name": file.filename,
        "size_bytes": size_bytes,
        "size_mb": round(size_bytes / 1_048_576, 2),
    }


async def _run_parse_job(job_id: str, file_path: str, file_type: str) -> None:
    """Background task — runs the full extraction + AI normalization pipeline."""
    from app.services.parser import parse_document

    update_job(job_id, status=JobStatus.processing, progress=5, message="Initializing parser…")
    try:
        ast = await parse_document(file_path=file_path, file_type=file_type, job_id=job_id)
        update_job(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="Document parsed and structured successfully.",
            result={
                "ast_summary": {
                    "title": ast.metadata.title,
                    "author": ast.metadata.author,
                    "genre": ast.metadata.genre,
                    "chapters": len(ast.chapters),
                    "total_blocks": sum(len(c.content) for c in ast.chapters),
                    "total_words": sum(c.word_count or 0 for c in ast.chapters),
                },
                "ast": ast.model_dump(),
            },
        )
        logger.info("Job %s complete: %d chapters", job_id, len(ast.chapters))

    except CorruptFileError as exc:
        _fail_job(job_id, "corrupt_file", str(exc))
    except UnsupportedFormatError as exc:
        _fail_job(job_id, "unsupported_format", str(exc))
    except ParseError as exc:
        _fail_job(job_id, "parse_error", str(exc))
    except Exception as exc:
        logger.exception("Unexpected error in job %s", job_id)
        _fail_job(
            job_id,
            "internal_error",
            "An unexpected error occurred during parsing. "
            "Please try again or contact support if the issue persists.",
        )


def _fail_job(job_id: str, error_code: str, message: str) -> None:
    logger.error("Job %s failed [%s]: %s", job_id, error_code, message)
    update_job(
        job_id,
        status=JobStatus.failed,
        progress=0,
        message=message,
        error=message,
    )


# ── GET /api/ast/{job_id} ─────────────────────────────────────────────────────

@router.get(
    "/ast/{job_id}",
    summary="Retrieve parsed DocumentAST",
    description="Returns the full DocumentAST for a completed parse job.",
)
async def get_document_ast(job_id: str):
    from app.models.job import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    if job.status == JobStatus.failed:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "job_failed",
                "message": job.error or "Parsing failed.",
                "job_id": job_id,
            },
        )

    if job.status != JobStatus.completed:
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
        # Fallback: try to reconstruct from job result
        if job.result and "ast" in job.result:
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
