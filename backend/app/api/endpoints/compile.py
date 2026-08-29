"""
POST /api/compile
Accepts a DocumentAST payload and compiles it into multiple formats (PDF, DOCX, MD, EPUB).
"""
from __future__ import annotations
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from app.models.document_ast import DocumentAST
from app.models.job import JobStatus, create_job, update_job
from app.services.compilers import compile_all_formats

logger = logging.getLogger("bookcraft.compile")

router = APIRouter()


class CompileRequest(DocumentAST):
    """Compile request — same shape as DocumentAST."""
    pass


@router.post(
    "/compile",
    summary="Compile DocumentAST to Multi-Format Outputs (PDF, DOCX, MD, EPUB)",
    description=(
        "Accepts a fully-structured DocumentAST JSON body and compiles it "
        "into publication-ready outputs: PDF, DOCX (Word), Markdown (.md), and EPUB3. "
        "Returns a job_id to poll for completion. Paid Pro users (via Bearer token) "
        "compile full manuscripts with zero limits."
    ),
    status_code=202,
)
async def compile_document(
    body: CompileRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None, description="Optional Pro JWT bearer token"),
    tier: Optional[str] = None,
):
    from app.core.security import get_current_tier, PAID_TIERS
    active_tier = get_current_tier(authorization=authorization, tier=tier)
    is_demo = (active_tier not in PAID_TIERS)

    job = create_job(
        file_name=f"{body.metadata.title}.pdf",
        file_type="multi-format",
    )

    background_tasks.add_task(
        _run_compile_job,
        job_id=job.job_id,
        ast=body,
        is_demo=is_demo,
        tier=active_tier,
    )

    return {
        "job_id": job.job_id,
        "status": job.status,
        "tier": active_tier,
        "is_demo": is_demo,
        "message": f"Compilation started for PDF, DOCX, MD, and EPUB ({active_tier.upper()} tier). Poll /api/status/{{job_id}} for progress.",
        "book_title": body.metadata.title,
    }


async def _run_compile_job(
    job_id: str,
    ast: DocumentAST,
    is_demo: bool = False,
    tier: str = "pro",
) -> None:
    """Background task that compiles the DocumentAST into all formats."""
    update_job(job_id, status=JobStatus.processing, progress=5, message="Starting multi-format compilation…")
    try:
        # If demo, enforce demo slicing if not already sliced
        if is_demo:
            from app.services.restriction_engine import slice_ast_for_demo
            ast = slice_ast_for_demo(ast, is_demo=True)

        results = await compile_all_formats(
            ast=ast,
            job_id=job_id,
        )

        pdf_info = results.get("pdf", {})
        pdf_path = pdf_info.get("path")
        pdf_url = pdf_info.get("url")

        download_urls = {fmt: data["url"] for fmt, data in results.items() if "url" in data}

        update_job(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="All formats compiled successfully.",
            output_path=pdf_path,
            download_url=pdf_url,
            download_urls=download_urls,
            result={
                "output_path": pdf_path,
                "download_url": pdf_url,
                "download_urls": download_urls,
                "formats": {fmt: {"path": data["path"], "url": data["url"], "size_bytes": data.get("size_bytes", 0)} for fmt, data in results.items()},
            },
        )
        logger.info("Compile job %s completed all formats: %s", job_id, list(results.keys()))
    except Exception as exc:
        logger.exception("Compile job %s failed: %s", job_id, exc)
        update_job(
            job_id,
            status=JobStatus.failed,
            progress=0,
            message="Compilation failed.",
            error=str(exc),
        )
