"""handle_job_failure node — clean up and emit failure SSE event."""

from __future__ import annotations

import logging
from typing import Any

from services.api.app.graph.state import DesignGraphState

logger = logging.getLogger(__name__)


def handle_job_failure(state: DesignGraphState) -> dict:
    """Handle job failure: log, emit failure SSE if not already emitted."""
    error_message = state.get("error_message", "")
    job_id = state.get("job_id", "")

    logger.warning("handling job failure: job_id=%s error=%s", job_id, error_message)

    # If SSE failure already emitted (by wait_for_job_event), skip
    sse_events = state.get("sse_events", [])
    if any(e.get("event_type") == "generation_failed" for e in sse_events):
        return {}

    # Emit a generation_failed event
    return {
        "status": "failed",
        "sse_events": [{
            "event_type": "generation_failed",
            "job_id": job_id,
            "design_id": state.get("design_id", ""),
            "version_no": state.get("version_no", 0),
            "status": "failed",
            "error_message": error_message or "generation failed",
            "created_at": "",
            "updated_at": "",
        }],
    }
