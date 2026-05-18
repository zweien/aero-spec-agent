"""CompareGraph — multi-variant comparison via DesignGraph subgraphs.

Flow:
    START → dispatch_variants → aggregate_results → compare_metrics → END

dispatch_variants fans out N variant jobs via JobRunner.
aggregate_results collects job outcomes.
compare_metrics produces comparison data.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

logger = logging.getLogger(__name__)


class CompareState(TypedDict, total=False):
    """State for the variant comparison graph."""

    design_id: str
    base_spec: dict[str, Any]
    variants: list[dict[str, Any]]
    variant_jobs: Annotated[list[dict[str, Any]], __import__("operator").add]
    results: list[dict[str, Any]]
    comparison: dict[str, Any] | None
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


def make_aggregate_results_node(
    job_runner: Any,
    poll_interval: float = 0.3,
    max_poll_seconds: float = 0,
):
    """Factory: collect results from all variant jobs.

    Args:
        job_runner: JobRunner instance.
        poll_interval: Seconds between polls when waiting for terminal states.
        max_poll_seconds: If > 0, poll until all jobs are terminal or timeout.
            If 0 (default), do a single snapshot aggregation.
    """

    def aggregate_results(state: CompareState) -> dict:
        import time

        if state.get("status") == "failed":
            return {"results": [], "status": "failed"}

        variant_jobs = state.get("variant_jobs", [])
        if not variant_jobs:
            return {"results": [], "status": "completed"}

        deadline = time.monotonic() + max_poll_seconds if max_poll_seconds > 0 else 0

        while True:
            results: list[dict[str, Any]] = []
            all_terminal = True

            for vj in variant_jobs:
                job = job_runner.get(vj["job_id"])
                label = vj.get("label", "unknown")
                vno = vj.get("version_no", 0)

                if job is None:
                    results.append({
                        "label": label,
                        "version_no": vno,
                        "status": "failed",
                        "error_message": "job not found",
                    })
                elif job.status in ("succeeded", "failed"):
                    entry: dict[str, Any] = {
                        "label": label,
                        "version_no": getattr(job, "version_no", vno),
                        "status": job.status,
                    }
                    if job.status == "succeeded":
                        entry["files"] = getattr(job, "files", {})
                    if getattr(job, "error_message", None):
                        entry["error_message"] = job.error_message
                    results.append(entry)
                else:
                    all_terminal = False
                    results.append({
                        "label": label,
                        "version_no": vno,
                        "status": job.status,
                    })

            if all_terminal or max_poll_seconds <= 0 or time.monotonic() >= deadline:
                break
            time.sleep(poll_interval)

        terminal_status = "completed" if all_terminal else "running"
        return {"results": results, "status": terminal_status}

    return aggregate_results


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


def build_compare_graph(
    job_runner: Any,
    poll_interval: float = 0.3,
    max_poll_seconds: float = 0,
) -> StateGraph:
    """Build the variant comparison graph.

    Args:
        job_runner: JobRunner instance for dispatching and observing jobs.
        poll_interval: Seconds between polls when waiting for terminal states.
        max_poll_seconds: If > 0, poll until all jobs are terminal or timeout.

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(CompareState)

    graph.add_node("dispatch_variants", make_dispatch_variants_node(job_runner))
    graph.add_node("aggregate_results", make_aggregate_results_node(
        job_runner, poll_interval=poll_interval, max_poll_seconds=max_poll_seconds,
    ))
    graph.add_node("compare_metrics", compare_metrics)

    graph.add_edge(START, "dispatch_variants")
    graph.add_edge("dispatch_variants", "aggregate_results")
    graph.add_edge("aggregate_results", "compare_metrics")
    graph.add_edge("compare_metrics", END)

    return graph.compile()


def _set_nested(d: dict, path: str, value: Any) -> None:
    """Set a nested dict value by dot-separated path."""
    keys = path.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value
