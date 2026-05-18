"""CompareGraph — multi-variant comparison via subgraph composition.

Flow:
    START → dispatch_variants → compare_metrics → synthesize_summary → END

dispatch_variants invokes VariantSubgraph per variant via graph.invoke,
providing thread_id isolation for each variant run.
compare_metrics aggregates results across variants.
synthesize_summary generates a human-readable summary.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from services.api.app.graph.observe import observe_node
from services.api.app.graph.variant_subgraph import build_variant_subgraph

logger = logging.getLogger(__name__)


class CompareState(TypedDict, total=False):
    """State for the variant comparison graph."""

    design_id: str
    base_spec: dict[str, Any]
    variants: list[dict[str, Any]]
    variant_results: Annotated[list[dict[str, Any]], __import__("operator").add]
    results: list[dict[str, Any]]
    comparison: dict[str, Any] | None
    summary: str
    status: str
    error_message: str | None


def make_dispatch_variants_node(job_runner: Any, timeout_seconds: float = 120):
    """Factory: invoke VariantSubgraph per variant with thread_id isolation."""

    @observe_node("dispatch_variants")
    def dispatch_variants(state: CompareState) -> dict:
        design_id = state.get("design_id", "")
        base_spec = state.get("base_spec", {})
        variants = state.get("variants", [])

        if not variants:
            return {
                "status": "failed",
                "error_message": "no variants provided",
            }

        subgraph = build_variant_subgraph(
            job_runner=job_runner,
            timeout_seconds=timeout_seconds,
        )

        results: list[dict[str, Any]] = []
        for i, variant in enumerate(variants):
            # Check for pre-patched spec from parent graph
            changes = variant.get("changes", [])
            has_patched = any(c.get("path") == "__use_patched__" for c in changes)
            if has_patched:
                patched = next(
                    c["value"] for c in changes if c.get("path") == "__use_patched__"
                )
            else:
                patched = json.loads(json.dumps(base_spec))
                for change in changes:
                    _set_nested(patched, change["path"], change["value"])

            subgraph_input = {
                "design_id": design_id,
                "spec": patched,
                "label": variant.get("label", f"variant_{i + 1}"),
            }

            thread_id = f"{design_id}_variant_{i}"
            config = {"configurable": {"thread_id": thread_id}}

            try:
                sub_result = subgraph.invoke(subgraph_input, config=config)
                results.append({
                    "label": subgraph_input["label"],
                    "version_no": sub_result.get("version_no", 0),
                    "job_id": sub_result.get("job_id", ""),
                    "status": sub_result.get("status", "unknown"),
                    "duration_ms": sub_result.get("duration_ms"),
                    "files": sub_result.get("files", {}),
                    "error_message": sub_result.get("error_message"),
                    "thread_id": thread_id,
                })
            except Exception as e:
                logger.exception("variant %d subgraph failed", i)
                results.append({
                    "label": subgraph_input["label"],
                    "status": "failed",
                    "error_message": str(e),
                    "thread_id": thread_id,
                })

        return {"results": results, "status": "completed"}

    return dispatch_variants


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
    timeout_seconds: float = 120,
) -> StateGraph:
    """Build the variant comparison graph with subgraph composition.

    Args:
        job_runner: JobRunner instance for dispatching and observing jobs.
        timeout_seconds: Maximum wait time per variant subgraph.

    Returns:
        Compiled StateGraph.
    """
    graph = StateGraph(CompareState)

    graph.add_node("dispatch_variants", make_dispatch_variants_node(
        job_runner, timeout_seconds=timeout_seconds,
    ))
    graph.add_node("compare_metrics", compare_metrics)
    graph.add_node("synthesize_summary", synthesize_summary)

    graph.add_edge(START, "dispatch_variants")
    graph.add_edge("dispatch_variants", "compare_metrics")
    graph.add_edge("compare_metrics", "synthesize_summary")
    graph.add_edge("synthesize_summary", END)

    return graph.compile()


def _set_nested(d: dict, path: str, value: Any) -> None:
    """Set a nested dict value by dot-separated path."""
    keys = path.split(".")
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value
