"""observe_job node — poll job status until terminal."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

from services.api.app.graph.state import DesignGraphState

if TYPE_CHECKING:
    from services.api.app.services.job_runner import JobRunner

logger = logging.getLogger(__name__)

TERMINAL_STATES = ("succeeded", "failed")
POLL_INTERVAL = 0.3
MAX_POLL_SECONDS = 120


def _job_to_event(job: Any, event_type: str) -> dict[str, Any]:
    """Convert a JobRecord to an SSE-event dict."""
    event: dict[str, Any] = {
        "event_type": event_type,
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if job.duration_ms is not None:
        event["duration_ms"] = job.duration_ms
    if job.error_message:
        event["error_message"] = job.error_message
    return event


def make_observe_job_node(
    job_runner: JobRunner,
    poll_interval: float = POLL_INTERVAL,
    max_poll_seconds: float = MAX_POLL_SECONDS,
):
    """Factory: returns an observe_job node with JobRunner injected."""

    def observe_job(state: DesignGraphState) -> dict:
        job_id = state.get("job_id", "")
        if not job_id:
            return {
                "status": "failed",
                "error_message": "no job_id to observe",
                "graph_errors": ["observe_job: missing job_id"],
            }

        # If already terminal, skip polling
        if state.get("status") in TERMINAL_STATES:
            job = job_runner.get(job_id)
            if job and job.status in TERMINAL_STATES:
                event_type = (
                    "generation_complete" if job.status == "succeeded"
                    else "generation_failed"
                )
                return {
                    "status": job.status,
                    "sse_events": [_job_to_event(job, event_type)],
                }

        deadline = time.monotonic() + max_poll_seconds
        while time.monotonic() < deadline:
            job = job_runner.get(job_id)
            if job is None:
                return {
                    "status": "failed",
                    "error_message": f"job {job_id} not found",
                    "graph_errors": [f"observe_job: job {job_id} not found"],
                }

            if job.status in TERMINAL_STATES:
                event_type = (
                    "generation_complete" if job.status == "succeeded"
                    else "generation_failed"
                )
                logger.info(
                    "job %s reached terminal state: %s", job_id, job.status,
                )
                return {
                    "status": job.status,
                    "error_message": job.error_message,
                    "sse_events": [_job_to_event(job, event_type)],
                }

            time.sleep(poll_interval)

        logger.warning("job %s polling timed out after %ss", job_id, max_poll_seconds)
        return {
            "status": "failed",
            "error_message": "observation timed out",
            "graph_errors": [f"observe_job: timed out for {job_id}"],
        }

    return observe_job
