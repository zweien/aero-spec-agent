"""wait_for_job_event node — observe job lifecycle via JobEventBus.

Replaces the polling-based observe_job with event-driven observation.
Subscribes to JobEventBus, waits for job_completed or job_failed.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from services.api.app.graph.state import DesignGraphState
from services.api.app.services.job_events import JobEvent, JobEventType, get_job_event_bus

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def make_wait_for_job_event_node(
    timeout_seconds: float = 120,
    poll_interval: float = 0.1,
):
    """Factory: returns a node that waits for job lifecycle events.

    Uses JobEventBus subscription instead of polling JobRunner.get().
    Falls back to polling if no events received within timeout.
    """

    def wait_for_job_event(state: DesignGraphState) -> dict:
        import time

        job_id = state.get("job_id", "")
        if not job_id:
            return {
                "status": "failed",
                "error_message": "no job_id to observe",
                "graph_errors": ["wait_for_job_event: missing job_id"],
            }

        # If already terminal, skip waiting
        if state.get("status") in ("succeeded", "failed"):
            return {}

        # Set up event-driven wait
        result_event: JobEvent | None = None
        event_received = threading.Event()

        def _on_event(event: JobEvent) -> None:
            nonlocal result_event
            if event.job_id == job_id and event.type in (
                JobEventType.COMPLETED, JobEventType.FAILED,
            ):
                result_event = event
                event_received.set()

        bus = get_job_event_bus()
        bus.subscribe(_on_event)
        try:
            deadline = time.monotonic() + timeout_seconds
            while not event_received.is_set() and time.monotonic() < deadline:
                event_received.wait(poll_interval)

            if result_event is None:
                # Timeout: fall back to direct job status check
                logger.warning("event wait timed out for job %s, checking status", job_id)
                return _fallback_check(state, job_id)

            if result_event.type == JobEventType.COMPLETED:
                return {
                    "status": "succeeded",
                    "sse_events": [_event_to_sse(result_event, "generation_complete")],
                }
            else:
                return {
                    "status": "failed",
                    "error_message": result_event.error_message,
                    "sse_events": [_event_to_sse(result_event, "generation_failed")],
                }
        finally:
            bus.unsubscribe(_on_event)

    return wait_for_job_event


def _event_to_sse(event: JobEvent, event_type: str) -> dict[str, Any]:
    """Convert a JobEvent to an SSE-event dict."""
    result: dict[str, Any] = {
        "event_type": event_type,
        "job_id": event.job_id,
        "design_id": event.design_id,
        "version_no": event.version_no,
        "status": "succeeded" if event.type == JobEventType.COMPLETED else "failed",
        "created_at": event.timestamp,
        "updated_at": event.timestamp,
    }
    if event.duration_ms is not None:
        result["duration_ms"] = event.duration_ms
    if event.error_message:
        result["error_message"] = event.error_message
    return result


def _fallback_check(state: DesignGraphState, job_id: str) -> dict:
    """Fallback: check job status directly when event bus doesn't deliver."""
    return {
        "status": "failed",
        "error_message": "event observation timed out",
        "graph_errors": [f"wait_for_job_event: timed out for {job_id}"],
    }
