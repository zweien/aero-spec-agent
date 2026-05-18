"""CompareGraph — multi-variant comparison via graph-native aggregation.

Flow:
    START → dispatch_variants → wait_all_variants → compare_metrics → synthesize_summary → END

dispatch_variants fans out N variant jobs via JobRunner.
wait_all_variants observes job lifecycle via JobEventBus.
compare_metrics produces comparison data.
synthesize_summary generates a human-readable summary.
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from services.api.app.services.job_events import (
    JobEvent,
    JobEventType,
    get_job_event_bus,
)

logger = logging.getLogger(__name__)


class CompareState(TypedDict, total=False):
    """State for the variant comparison graph."""

    design_id: str
    base_spec: dict[str, Any]
    variants: list[dict[str, Any]]
    variant_jobs: Annotated[list[dict[str, Any]], __import__("operator").add]
    results: list[dict[str, Any]]
    comparison: dict[str, Any] | None
    summary: str
    status: str
    error_message: str | None


def make_dispatch_variants_node(job_runner: Any):
    """Factory: dispatch each variant as a separate generation job."""

    def dispatch_variants(state: CompareState) -> dict:
        design_id = state.get("design_id", "")
        base_spec = state.get("base_spec", {})
        variants = state.get("variants", [])

        if not variants:
            return {
                "status": "failed",
                "error_message": "no variants provided",
            }

        from services.api.app.schemas.aircraft_spec import AircraftSpec

        jobs = []
        for i, variant in enumerate(variants):
            patched = json.loads(json.dumps(base_spec))
            for change in variant.get("changes", []):
                _set_nested(patched, change["path"], change["value"])

            try:
                spec = AircraftSpec.model_validate(patched)
            except Exception as e:
                return {
                    "status": "failed",
                    "error_message": f"variant {i} invalid spec: {e}",
                }

            job = job_runner.enqueue_generate(design_id=design_id, spec=spec)
            jobs.append({
                "label": variant.get("label", f"variant_{i + 1}"),
                "job_id": job.id,
                "version_no": job.version_no,
                "changes": variant.get("changes", []),
                "status": "queued",
            })

        return {"variant_jobs": jobs, "status": "running"}

    return dispatch_variants


def make_wait_all_variants_node(
    job_runner: Any,
    timeout_seconds: float = 120,
    poll_interval: float = 0.1,
):
    """Factory: wait for all variant jobs to complete via JobEventBus.

    Uses event-driven observation with polling fallback.
    """

    def wait_all_variants(state: CompareState) -> dict:
        if state.get("status") == "failed":
            return {"results": [], "status": "failed"}

        variant_jobs = state.get("variant_jobs", [])
        if not variant_jobs:
            return {"results": [], "status": "completed"}

        job_ids = {vj["job_id"] for vj in variant_jobs}
        completed: dict[str, JobEvent] = {}
        event_received = threading.Event()

        def _on_event(event: JobEvent) -> None:
            if event.job_id in job_ids and event.type in (
                JobEventType.COMPLETED, JobEventType.FAILED,
            ):
                completed[event.job_id] = event
                if len(completed) >= len(job_ids):
                    event_received.set()

        bus = get_job_event_bus()
        bus.subscribe(_on_event)
        try:
            deadline = time.monotonic() + timeout_seconds
            while not event_received.is_set() and time.monotonic() < deadline:
                event_received.wait(poll_interval)

            # Build results from completed events + fallback polling
            results: list[dict[str, Any]] = []
            all_terminal = True
            for vj in variant_jobs:
                jid = vj["job_id"]
                label = vj.get("label", "unknown")
                vno = vj.get("version_no", 0)

                ev = completed.get(jid)
                if ev is not None:
                    results.append({
                        "label": label,
                        "version_no": vno,
                        "status": "succeeded" if ev.type == JobEventType.COMPLETED else "failed",
                        "files": ev.files if ev.type == JobEventType.COMPLETED else {},
                        "error_message": ev.error_message,
                        "duration_ms": ev.duration_ms,
                    })
                else:
                    # Fallback: check job directly
                    job = job_runner.get(jid)
                    if job is None:
                        results.append({
                            "label": label,
                            "version_no": vno,
                            "status": "failed",
                            "error_message": "job not found",
                        })
                    elif job.status in ("succeeded", "failed"):
                        entry = {"label": label, "version_no": job.version_no, "status": job.status}
                        if job.status == "succeeded":
                            entry["files"] = job.files
                        if job.error_message:
                            entry["error_message"] = job.error_message
                        results.append(entry)
                    else:
                        all_terminal = False
                        results.append({
                            "label": label,
                            "version_no": vno,
                            "status": job.status,
                        })

            terminal_status = "completed" if all_terminal else "running"
            return {"results": results, "status": terminal_status}
        finally:
            bus.unsubscribe(_on_event)

    return wait_all_variants


def compare_metrics(state: CompareState) -> dict:
    """Compare metrics across variant results."""
    results = state.get("results", [])
    if not results:
        return {"comparison": None}

    comparison = {
        "total_variants": len(results),
        "succeeded": sum(1 for r in results if r.get("status") == "succeeded"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "variants": results,
    }
    return {"comparison": comparison}


def synthesize_summary(state: CompareState) -> dict:
    """Generate a human-readable comparison summary."""
    comparison = state.get("comparison")
    if comparison is None:
        return {"summary": ""}

    total = comparison.get("total_variants", 0)
    succeeded = comparison.get("succeeded", 0)
    failed = comparison.get("failed", 0)

    if total == 0:
        return {"summary": "无变体可比较。"}

    lines = [f"共 {total} 个变体：{succeeded} 个成功，{failed} 个失败。"]

    for variant in comparison.get("variants", []):
        label = variant.get("label", "unknown")
        status = variant.get("status", "unknown")
        duration = variant.get("duration_ms")
        duration_str = f" ({duration:.0f}ms)" if duration else ""
        lines.append(f"  - {label}: {status}{duration_str}")

    return {"summary": "\n".join(lines)}


def build_compare_graph(
    job_runner: Any,
    poll_interval: float = 0.3,
    max_poll_seconds: float = 0,
    timeout_seconds: float = 120,
) -> StateGraph:
    """Build the variant comparison graph with graph-native aggregation.

    Args:
        job_runner: JobRunner instance for dispatching and observing jobs.
        poll_interval: Seconds between polls (fallback mode).
        max_poll_seconds: Legacy polling timeout (unused in event-driven mode).
        timeout_seconds: Maximum wait time for all variants via events.

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(CompareState)

    graph.add_node("dispatch_variants", make_dispatch_variants_node(job_runner))
    graph.add_node("wait_all_variants", make_wait_all_variants_node(
        job_runner, timeout_seconds=timeout_seconds, poll_interval=poll_interval,
    ))
    graph.add_node("compare_metrics", compare_metrics)
    graph.add_node("synthesize_summary", synthesize_summary)

    graph.add_edge(START, "dispatch_variants")
    graph.add_edge("dispatch_variants", "wait_all_variants")
    graph.add_edge("wait_all_variants", "compare_metrics")
    graph.add_edge("compare_metrics", "synthesize_summary")
    graph.add_edge("synthesize_summary", END)

    return graph.compile()


def _set_nested(d: dict, path: str, value: Any) -> None:
    """Set a nested dict value by dot-separated path."""
    keys = path.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value
