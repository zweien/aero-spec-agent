from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobResponse(BaseModel):
    id: str
    job_id: str = Field(description="Alias for id, kept for frontend compat")
    design_id: str
    version_no: int
    status: JobStatus
    progress: int = 0
    current_step: str = ""
    error_message: str | None = None
    files: dict[str, str] = Field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    duration: float | None = None
    version_status: str = "pending"

    model_config = {"from_attributes": True}


def job_to_response(job: Any) -> dict[str, Any]:
    """Convert a JobRecord (dataclass) to a JobResponse-compatible dict."""
    data = {
        "id": job.id,
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
        "status": job.status,
        "progress": job.progress,
        "current_step": job.current_step,
        "error_message": job.error_message,
        "files": job.files,
        "created_at": getattr(job, "created_at", ""),
        "updated_at": getattr(job, "updated_at", ""),
        "duration": getattr(job, "duration", None),
        "version_status": getattr(job, "version_status", "pending"),
    }
    return JobResponse.model_validate(data).model_dump()
