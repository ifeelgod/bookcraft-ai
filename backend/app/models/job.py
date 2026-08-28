"""
Job state management — in-memory store for upload/compile job tracking.
In production, replace with Redis or a database-backed queue.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.pending
    progress: int = Field(default=0, ge=0, le=100, description="0–100 percent complete")
    message: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    # Input info
    file_name: Optional[str] = None
    file_type: Optional[str] = None  # "docx" | "pdf"

    # Output info
    output_path: Optional[str] = None
    download_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Simple in-memory job store (thread-safe enough for dev)
# ---------------------------------------------------------------------------

_jobs: Dict[str, JobRecord] = {}


def create_job(file_name: str | None = None, file_type: str | None = None) -> JobRecord:
    job = JobRecord(file_name=file_name, file_type=file_type)
    _jobs[job.job_id] = job
    return job


def get_job(job_id: str) -> Optional[JobRecord]:
    return _jobs.get(job_id)


def update_job(
    job_id: str,
    *,
    status: Optional[JobStatus] = None,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    output_path: Optional[str] = None,
    download_url: Optional[str] = None,
) -> Optional[JobRecord]:
    job = _jobs.get(job_id)
    if not job:
        return None
    if status is not None:
        job.status = status
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.message = message
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error
    if output_path is not None:
        job.output_path = output_path
    if download_url is not None:
        job.download_url = download_url
    job.updated_at = datetime.now(timezone.utc)
    return job


def list_jobs() -> list[JobRecord]:
    return list(_jobs.values())
