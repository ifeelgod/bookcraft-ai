"""
POST /api/compile
Accepts a DocumentAST payload and compiles it into a formatted PDF.
"""
from __future__ import annotations
import logging
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.models.document_ast import DocumentAST
from app.models.job import JobStatus, create_job, update_job
from app.services.compiler import compile_pdf

logger = logging.getLogger("bookcraft.compile")

router = APIRouter()


class CompileRequest(DocumentAST):
    """Compile request — same shape as DocumentAST."""
    pass


@router.post(
    "/compile",
    summary="Compile DocumentAST to PDF",
    description=(
        "Accepts a fully-structured DocumentAST JSON body and compiles it "
        "into a publication-ready PDF. Returns a job_id to poll for completion."
    ),
    status_code=202,
)
async def compile_document(
    body: CompileRequest,
    background_tasks: BackgroundTasks,
):
    job = create_job(
        file_name=f"{body.metadata.title}.pdf",
        file_type="pdf",
    )

    background_tasks.add_task(
        _run_compile_job,
        job_id=job.job_id,
        ast=body,
    )

    return {
        "job_id": job.job_id,
        "status": job.status,
        "message": "Compilation started. Poll /api/status/{job_id} for progress.",
        "book_title": body.metadata.title,
    }


async def _run_compile_job(job_id: str, ast: DocumentAST) -> None:
    """Background task that compiles the DocumentAST into a PDF."""
    update_job(job_id, status=JobStatus.processing, progress=5, message="Starting compilation…")
    try:
        output_path, download_url = await compile_pdf(
            ast=ast,
            job_id=job_id,
        )
        update_job(
            job_id,
            status=JobStatus.completed,
            progress=100,
            message="PDF compiled successfully.",
            output_path=output_path,
            download_url=download_url,
            result={"output_path": output_path, "download_url": download_url},
        )
        logger.info("Compile job %s completed → %s", job_id, output_path)
    except Exception as exc:
        logger.exception("Compile job %s failed: %s", job_id, exc)
        update_job(
            job_id,
            status=JobStatus.failed,
            progress=0,
            message="Compilation failed.",
            error=str(exc),
        )
