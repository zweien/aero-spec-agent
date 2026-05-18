"""DeepDesignGraph — multi-variant design exploration prototype.

Phase 1 flow (no optimization loop):
    START → parse_requirements → explore_variants → compare_results → synthesize_report → END

parse_requirements extracts design constraints from natural language.
explore_variants fans out N variant specs using CompareGraph dispatch.
compare_results aggregates variant outcomes.
synthesize_report generates a comparison report.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from services.api.app.graph.observe import observe_node
from services.api.app.services.job_events import (
    JobEvent,
    JobEventType,
    get_job_event_bus,
)

logger = logging.getLogger(__name__)

# Default variant strategies: vary key parameters
DEFAULT_STRATEGIES = [
    {"label": "compact", "changes": [
        {"path": "wing.span.value", "value": -2, "op": "relative"},
    ]},
    {"label": "standard", "changes": []},
    {"label": "extended", "changes": [
        {"path": "wing.span.value", "value": 2, "op": "relative"},
    ]},
]


class DeepDesignState(TypedDict, total=False):
    # Input
    user_description: str
    constraints: dict[str, Any]

    # Parsed
    requirements: dict[str, Any]

    # Base spec
    base_spec: dict[str, Any] | None
    design_id: str

    # Variants
    variant_strategies: list[dict[str, Any]]
    variant_jobs: Annotated[list[dict[str, Any]], __import__("operator").add]

    # Results
    results: list[dict[str, Any]]
    comparison: dict[str, Any] | None
    report: str

    # Status
    status: str
    error_message: str | None


@observe_node("parse_requirements")
def parse_requirements(state: DeepDesignState) -> dict:
    """Parse user description into structured requirements.

    Phase 1 uses simple keyword extraction. Future phases will use LLM.
    """
    description = state.get("user_description", "")
    constraints = state.get("constraints", {})

    # Extract basic requirements from description
    requirements: dict[str, Any] = {
        "description": description,
        "variant_count": constraints.get("variant_count", 3),
    }

    # Parse range if mentioned
    import re
    range_match = re.search(r"(\d+)\s*km", description)
    if range_match:
        requirements["range_km"] = int(range_match.group(1))

    payload_match = re.search(r"(\d+)\s*kg", description)
    if payload_match:
        requirements["payload_kg"] = int(payload_match.group(1))

    return {"requirements": requirements}


def make_explore_variants_node(job_runner: Any):
    """Factory: generate variant specs and dispatch as parallel jobs."""

    @observe_node("explore_variants")
    def explore_variants(state: DeepDesignState) -> dict:
        base_spec = state.get("base_spec")
        design_id = state.get("design_id", "")
        constraints = state.get("constraints", {})
        variant_count = constraints.get("variant_count", 3)

        if not base_spec:
            return {
                "status": "failed",
                "error_message": "no base_spec provided for exploration",
            }

        from services.api.app.schemas.aircraft_spec import AircraftSpec

        # Use default strategies, capped to variant_count
        strategies = DEFAULT_STRATEGIES[:variant_count]
        if len(strategies) < variant_count:
            # Pad with copies of standard
            while len(strategies) < variant_count:
                strategies.append({
                    "label": f"variant_{len(strategies) + 1}",
                    "changes": [],
                })

        jobs = []
        for i, strategy in enumerate(strategies):
            patched = json.loads(json.dumps(base_spec))

            # Apply relative changes
            for change in strategy.get("changes", []):
                if change.get("op") == "relative":
                    path = change["path"]
                    delta = change["value"]
                    _apply_relative(patched, path, delta)
                else:
                    _set_nested(patched, change["path"], change["value"])

            try:
                spec = AircraftSpec.model_validate(patched)
            except Exception as e:
                logger.warning("variant %d spec invalid: %s", i, e)
                continue

            job = job_runner.enqueue_generate(design_id=design_id, spec=spec)
            jobs.append({
                "label": strategy.get("label", f"variant_{i + 1}"),
                "job_id": job.id,
                "version_no": job.version_no,
                "changes": strategy.get("changes", []),
                "status": "queued",
            })

        return {"variant_jobs": jobs, "status": "running"}

    return explore_variants


def make_compare_results_node(
    job_runner: Any,
    timeout_seconds: float = 120,
    poll_interval: float = 0.1,
):
    """Factory: wait for all variant jobs and compare results."""

    @observe_node("compare_results")
    def compare_results(state: DeepDesignState) -> dict:
        if state.get("status") == "failed":
            return {"results": [], "comparison": None}

        variant_jobs = state.get("variant_jobs", [])
        if not variant_jobs:
            return {"results": [], "comparison": None}

        # Event-driven collection
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

            results: list[dict[str, Any]] = []
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
                        "duration_ms": ev.duration_ms,
                        "error_message": ev.error_message,
                    })
                else:
                    job = job_runner.get(jid)
                    status = job.status if job else "failed"
                    results.append({
                        "label": label,
                        "version_no": vno,
                        "status": status,
                        "error_message": getattr(job, "error_message", None) if job else "not found",
                    })

            succeeded = sum(1 for r in results if r["status"] == "succeeded")
            comparison = {
                "total": len(results),
                "succeeded": succeeded,
                "failed": len(results) - succeeded,
                "variants": results,
            }
            return {"results": results, "comparison": comparison}
        finally:
            bus.unsubscribe(_on_event)

    return compare_results


@observe_node("synthesize_report")
def synthesize_report(state: DeepDesignState) -> dict:
    """Generate a design exploration report."""
    requirements = state.get("requirements", {})
    comparison = state.get("comparison")

    if not comparison:
        return {"report": "探索未完成，无法生成报告。", "status": "failed"}

    desc = requirements.get("description", "未指定")
    total = comparison.get("total", 0)
    succeeded = comparison.get("succeeded", 0)

    lines = [
        f"# 设计探索报告",
        f"",
        f"**需求描述：** {desc}",
        f"",
        f"共探索 {total} 个变体，其中 {succeeded} 个成功。",
        f"",
        f"| 变体 | 状态 | 耗时 |",
        f"|------|------|------|",
    ]

    for v in comparison.get("variants", []):
        label = v.get("label", "?")
        status = v.get("status", "?")
        duration = v.get("duration_ms")
        dur_str = f"{duration:.0f}ms" if duration else "-"
        lines.append(f"| {label} | {status} | {dur_str} |")

    # Recommend fastest successful variant
    successful = [v for v in comparison.get("variants", []) if v.get("status") == "succeeded"]
    if successful:
        best = min(successful, key=lambda v: v.get("duration_ms", float("inf")))
        lines.append(f"")
        lines.append(f"**推荐：** {best['label']}（最快完成）")

    return {"report": "\n".join(lines), "status": "completed"}


def build_deep_design_graph(
    job_runner: Any,
    timeout_seconds: float = 120,
) -> StateGraph:
    """Build the DeepDesignGraph for multi-variant exploration.

    Args:
        job_runner: JobRunner instance.
        timeout_seconds: Max wait time for all variants.

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(DeepDesignState)

    graph.add_node("parse_requirements", parse_requirements)
    graph.add_node("explore_variants", make_explore_variants_node(job_runner))
    graph.add_node("compare_results", make_compare_results_node(
        job_runner, timeout_seconds=timeout_seconds,
    ))
    graph.add_node("synthesize_report", synthesize_report)

    graph.add_edge(START, "parse_requirements")
    graph.add_edge("parse_requirements", "explore_variants")
    graph.add_edge("explore_variants", "compare_results")
    graph.add_edge("compare_results", "synthesize_report")
    graph.add_edge("synthesize_report", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_nested(d: dict, path: str, value: Any) -> None:
    keys = path.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def _apply_relative(d: dict, path: str, delta: float) -> None:
    """Apply a relative change to a numeric value in a nested dict."""
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

    last_key = keys[-1]
    if last_key in current and isinstance(current[last_key], dict):
        # Scalar field: {value: X, ...}
        if "value" in current[last_key]:
            current[last_key]["value"] = current[last_key]["value"] + delta
    elif last_key in current:
        if isinstance(current[last_key], (int, float)):
            current[last_key] = current[last_key] + delta
