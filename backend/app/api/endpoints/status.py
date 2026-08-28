"""
GET /api/status/{job_id}
Returns the current status and progress of a job.
"""
from fastapi import APIRouter, HTTPException
from app.models.job import get_job, list_jobs

router = APIRouter()


@router.get(
    "/status/{job_id}",
    summary="Check job status",
    description="Poll this endpoint to track upload parsing or PDF compilation progress.",
)
async def get_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

    response = {
        "job_id": job.job_id,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "file_name": job.file_name,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }

    if job.status == "completed":
        response["result"] = job.result
        if job.download_url:
            response["download_url"] = job.download_url

    if job.status == "failed":
        response["error"] = job.error

    return response


@router.get(
    "/jobs",
    summary="List all jobs",
    description="Returns a summary of all jobs (useful for debugging).",
)
async def list_all_jobs():
    jobs = list_jobs()
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": j.job_id,
                "status": j.status,
                "progress": j.progress,
                "file_name": j.file_name,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
    }
