"""VariantSubgraph — single variant generation subgraph.

Flow:
    START → validate_and_enqueue → wait_for_completion → END

This subgraph is invoked per-variant from CompareGraph,
providing thread_id isolation for each variant run.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from services.api.app.graph.observe import observe_node
from services.api.app.services.job_events import (
    JobEvent,
    JobEventType,
    get_job_event_bus,
)

logger = logging.getLogger(__name__)


class VariantSubgraphState(TypedDict, total=False):
    design_id: str
    spec: dict[str, Any]
    label: str

    job_id: str
    version_no: int
    status: str
    duration_ms: float | None
    files: dict[str, Any]
    error_message: str | None


def make_validate_and_enqueue_node(job_runner: Any):
    """Factory: validate spec and enqueue generation job."""

    @observe_node("validate_and_enqueue")
    def validate_and_enqueue(state: VariantSubgraphState) -> dict:
        from services.api.app.schemas.aircraft_spec import AircraftSpec

        spec_dict = state.get("spec")
        if not spec_dict:
            return {"status": "failed", "error_message": "no spec provided"}

        design_id = state.get("design_id", "")

        try:
            spec = AircraftSpec.model_validate(spec_dict)
        except Exception as e:
            return {"status": "failed", "error_message": f"invalid spec: {e}"}

        try:
            job = job_runner.enqueue_generate(design_id=design_id, spec=spec)
            return {
                "job_id": job.id,
                "version_no": job.version_no,
                "status": "queued",
            }
        except Exception as e:
            return {"status": "failed", "error_message": str(e)}

    return validate_and_enqueue


def make_wait_for_completion_node(
    job_runner: Any,
    timeout_seconds: float = 120,
    poll_interval: float = 0.1,
):
    """Factory: wait for job completion via JobEventBus."""

    @observe_node("wait_for_completion")
    def wait_for_completion(state: VariantSubgraphState) -> dict:
        job_id = state.get("job_id")
        if not job_id:
            return {
                "status": state.get("status", "failed"),
                "error_message": state.get("error_message", "no job_id"),
            }

        completed_event: JobEvent | None = None
        event_received = threading.Event()

        def _on_event(event: JobEvent) -> None:
            nonlocal completed_event
            if event.job_id == job_id and event.type in (
                JobEventType.COMPLETED, JobEventType.FAILED,
            ):
                completed_event = event
                event_received.set()

        bus = get_job_event_bus()
        bus.subscribe(_on_event)
        try:
            deadline = time.monotonic() + timeout_seconds
            while not event_received.is_set() and time.monotonic() < deadline:
                event_received.wait(poll_interval)

            if completed_event is not None:
                return {
                    "status": "succeeded" if completed_event.type == JobEventType.COMPLETED else "failed",
                    "duration_ms": completed_event.duration_ms,
                    "files": completed_event.files if completed_event.type == JobEventType.COMPLETED else {},
                    "error_message": completed_event.error_message,
                }

            # Fallback: check job directly
            job = job_runner.get(job_id)
            if job is None:
                return {"status": "failed", "error_message": "job not found after timeout"}
            return {
                "status": job.status,
                "error_message": getattr(job, "error_message", None),
            }
        finally:
            bus.unsubscribe(_on_event)

    return wait_for_completion


def build_variant_subgraph(
    job_runner: Any,
    timeout_seconds: float = 120,
) -> StateGraph:
    """Build a single-variant generation subgraph.

    Args:
        job_runner: JobRunner instance.
        timeout_seconds: Max wait for job completion.

    Returns:
        Compiled subgraph StateGraph.
    """
    graph = StateGraph(VariantSubgraphState)

    graph.add_node("validate_and_enqueue", make_validate_and_enqueue_node(job_runner))
    graph.add_node("wait_for_completion", make_wait_for_completion_node(
        job_runner, timeout_seconds=timeout_seconds,
    ))

    graph.add_edge(START, "validate_and_enqueue")
    graph.add_edge("validate_and_enqueue", "wait_for_completion")
    graph.add_edge("wait_for_completion", END)

    return graph.compile()
