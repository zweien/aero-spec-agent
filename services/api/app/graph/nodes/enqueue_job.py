"""enqueue_job node — dispatch generation job via JobRunner."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from services.api.app.graph.observe import observe_node
from services.api.app.graph.state import DesignGraphState

if TYPE_CHECKING:
    from services.api.app.schemas.aircraft_spec import AircraftSpec
    from services.api.app.services.job_runner import JobRunner

logger = logging.getLogger(__name__)


def _job_to_event(job: Any, event_type: str) -> dict[str, Any]:
    """Convert a JobRecord to an SSE-event dict."""
    return {
        "event_type": event_type,
        "job_id": job.id,
        "design_id": job.design_id,
        "version_no": job.version_no,
        "status": job.status,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


def make_enqueue_job_node(job_runner: JobRunner):
    """Factory: returns an enqueue_job node with JobRunner injected."""

    @observe_node("enqueue_job")
    def enqueue_job(state: DesignGraphState) -> dict:
        spec_dict = state.get("aircraft_spec")
        design_id = state.get("design_id", "")
        intent = state.get("intent", "unknown")

        if not spec_dict:
            return {
                "status": "failed",
                "error_message": f"cannot enqueue {intent}: no aircraft_spec",
                "graph_errors": [f"enqueue_job: no spec for intent={intent}"],
            }

        try:
            from services.api.app.schemas.aircraft_spec import AircraftSpec

            spec = AircraftSpec.model_validate(spec_dict)
        except Exception as e:
            return {
                "status": "failed",
                "error_message": f"invalid spec: {e}",
                "graph_errors": [f"enqueue_job: spec validation failed: {e}"],
            }

        try:
            job = job_runner.enqueue_generate(design_id=design_id, spec=spec)
            logger.info("enqueued job %s for design %s (intent=%s)", job.id, design_id, intent)
            return {
                "job_id": job.id,
                "version_no": job.version_no,
                "status": job.status,
                "sse_events": [_job_to_event(job, "generation_started")],
            }
        except Exception as e:
            logger.exception("enqueue_generate failed for design %s", design_id)
            return {
                "status": "failed",
                "error_message": str(e),
                "graph_errors": [f"enqueue_job: {e}"],
            }

    return enqueue_job
