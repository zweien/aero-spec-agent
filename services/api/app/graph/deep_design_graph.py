"""DeepDesignGraph — multi-variant design exploration via subgraph composition.

Flow (single pass):
    START → parse_requirements → prepare_variants → run_compare → synthesize_report → END

Flow (iterative, max_iterations > 1):
    START → parse_requirements → prepare_variants → run_compare → refine_variants
          → prepare_variants → run_compare → ... → synthesize_report → END

refine_variants decides whether to loop back or proceed to synthesize_report
based on iteration count and results quality.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import Annotated, TypedDict

from services.api.app.graph.compare_graph import build_compare_graph
from services.api.app.graph.observe import observe_node
from services.api.app.graph.deep_design_streaming import observe_node_sse

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

LAYOUT_STRATEGIES: dict[str, list[dict]] = {
    "conventional": DEFAULT_STRATEGIES,
    "canard": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "canard.span.value", "value": -0.5, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "canard.span.value", "value": 0.5, "op": "relative"},
        ]},
    ],
    "three_surface": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "canard.span.value", "value": -0.5, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "canard.span.value", "value": 0.5, "op": "relative"},
        ]},
    ],
    "tandem_wing": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": -1, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": 1, "op": "relative"},
        ]},
    ],
    "joined_wing": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": -1, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "rear_wing.span.value", "value": 1, "op": "relative"},
        ]},
    ],
    "biplane": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "second_wing.gap.value", "value": -0.2, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "second_wing.gap.value", "value": 0.2, "op": "relative"},
        ]},
    ],
    "box_wing": [
        {"label": "compact", "changes": [
            {"path": "wing.span.value", "value": -2, "op": "relative"},
            {"path": "box_wing_config.gap.value", "value": -0.3, "op": "relative"},
        ]},
        {"label": "standard", "changes": []},
        {"label": "extended", "changes": [
            {"path": "wing.span.value", "value": 2, "op": "relative"},
            {"path": "box_wing_config.gap.value", "value": 0.3, "op": "relative"},
        ]},
    ],
    "twin_boom": DEFAULT_STRATEGIES,
    "flying_wing": DEFAULT_STRATEGIES,
    "blended_wing_body": DEFAULT_STRATEGIES,
    "multi_fuselage": DEFAULT_STRATEGIES,
}


class DeepDesignState(TypedDict, total=False):
    # Input
    user_description: str
    constraints: dict[str, Any]

    # Parsed
    requirements: dict[str, Any]

    # Base spec
    base_spec: dict[str, Any] | None
    design_id: str

    # Variants prepared for CompareGraph
    variants: list[dict[str, Any]]

    # Subgraph results
    comparison: dict[str, Any] | None
    results: list[dict[str, Any]]
    report: str

    # Iterative loop control
    iteration: int
    max_iterations: int
    refinement_history: list[dict[str, Any]]

    # Status
    status: str
    error_message: str | None


@observe_node("parse_requirements")
def parse_requirements(state: DeepDesignState) -> dict:
    """Parse user description into structured requirements."""
    description = state.get("user_description", "")
    constraints = state.get("constraints", {})

    requirements: dict[str, Any] = {
        "description": description,
        "variant_count": constraints.get("variant_count", 3),
    }

    import re
    range_match = re.search(r"(\d+)\s*km", description)
    if range_match:
        requirements["range_km"] = int(range_match.group(1))

    payload_match = re.search(r"(\d+)\s*kg", description)
    if payload_match:
        requirements["payload_kg"] = int(payload_match.group(1))

    max_iterations = constraints.get("max_iterations", 1)
    return {
        "requirements": requirements,
        "iteration": 0,
        "max_iterations": max_iterations,
        "refinement_history": [],
    }


@observe_node("prepare_variants")
def prepare_variants(state: DeepDesignState) -> dict:
    """Build variant specs from base spec and default strategies."""
    base_spec = state.get("base_spec")
    constraints = state.get("constraints", {})
    variant_count = constraints.get("variant_count", 3)

    if not base_spec:
        return {
            "status": "failed",
            "error_message": "no base_spec provided for exploration",
        }

    strategies = DEFAULT_STRATEGIES[:variant_count]
    while len(strategies) < variant_count:
        strategies.append({
            "label": f"variant_{len(strategies) + 1}",
            "changes": [],
        })

    variants = []
    for strategy in strategies:
        changes = strategy.get("changes", [])
        if any(c.get("op") == "relative" for c in changes):
            patched = json.loads(json.dumps(base_spec))
            for change in changes:
                if change.get("op") == "relative":
                    _apply_relative(patched, change["path"], change["value"])
                else:
                    _set_nested(patched, change["path"], change["value"])
            variants.append({"label": strategy["label"], "changes": [
                {"path": c["path"], "value": c["value"]}
                for c in changes if c.get("op") != "relative"
            ], "patched_spec": patched})
        else:
            variants.append({"label": strategy["label"], "changes": changes})

    return {"variants": variants, "status": "running"}


def make_run_compare_node(job_runner: Any, timeout_seconds: float = 120, streaming: bool = False):
    """Factory: invoke CompareGraph subgraph with prepared variants."""
    obs = observe_node_sse if streaming else observe_node

    @obs("run_compare")
    def run_compare(state: DeepDesignState) -> dict:
        if state.get("status") == "failed":
            return {"results": [], "comparison": None}

        base_spec = state.get("base_spec")
        design_id = state.get("design_id", "")
        variants_raw = state.get("variants", [])

        if not variants_raw:
            return {"results": [], "comparison": None}

        compare_variants = []
        for v in variants_raw:
            if "patched_spec" in v:
                compare_variants.append({
                    "label": v["label"],
                    "changes": [{"path": "__use_patched__", "value": v["patched_spec"]}],
                })
            else:
                compare_variants.append(v)

        compare_graph = build_compare_graph(
            job_runner=job_runner,
            timeout_seconds=timeout_seconds,
        )

        subgraph_input = {
            "design_id": design_id,
            "base_spec": base_spec,
            "variants": compare_variants,
        }

        try:
            sub_result = compare_graph.invoke(subgraph_input)
            return {
                "results": sub_result.get("results", []),
                "comparison": sub_result.get("comparison"),
                "status": sub_result.get("status", "completed"),
            }
        except Exception as e:
            logger.exception("CompareGraph subgraph failed")
            return {
                "results": [],
                "comparison": None,
                "status": "failed",
                "error_message": f"compare subgraph error: {e}",
            }

    return run_compare


@observe_node("refine_variants")
def refine_variants(state: DeepDesignState) -> dict:
    """Decide whether to iterate again or proceed to report.

    Refinement strategy (Phase 1 — simple):
      - If iteration >= max_iterations → stop
      - If all variants succeeded → stop
      - If some failed → widen delta for next iteration

    This is NOT autonomous optimization. It's a bounded retry with
    strategy adjustment. Human review via max_iterations=1 to disable.
    """
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 1)
    results = state.get("results", [])
    comparison = state.get("comparison")

    # Record this iteration's results
    history = list(state.get("refinement_history", []))
    history.append({
        "iteration": iteration,
        "total": comparison.get("total_variants", 0) if comparison else 0,
        "succeeded": comparison.get("succeeded", 0) if comparison else 0,
    })

    # Check stopping conditions
    should_stop = False
    if iteration + 1 >= max_iterations:
        should_stop = True
        logger.info("refine_variants: max_iterations=%d reached", max_iterations)
    elif all(r.get("status") == "succeeded" for r in results):
        should_stop = True
        logger.info("refine_variants: all variants succeeded, stopping")

    if should_stop:
        return {
            "iteration": iteration + 1,
            "refinement_history": history,
            "status": "completed",
        }

    # Prepare refined variants: widen the delta for failed variants
    base_spec = state.get("base_spec")
    constraints = state.get("constraints", {})
    variant_count = constraints.get("variant_count", 3)

    # Increase delta by 50% for next iteration
    delta_multiplier = 1.5
    refined_strategies = []
    for strategy in DEFAULT_STRATEGIES[:variant_count]:
        refined_changes = []
        for change in strategy.get("changes", []):
            if change.get("op") == "relative":
                refined_changes.append({
                    "path": change["path"],
                    "value": change["value"] * delta_multiplier,
                    "op": "relative",
                })
            else:
                refined_changes.append(change)
        refined_strategies.append({"label": strategy["label"], "changes": refined_changes})

    # Pad if needed
    while len(refined_strategies) < variant_count:
        refined_strategies.append({
            "label": f"variant_{len(refined_strategies) + 1}",
            "changes": [],
        })

    # Build variants from refined strategies
    variants = []
    for strategy in refined_strategies:
        changes = strategy.get("changes", [])
        if any(c.get("op") == "relative" for c in changes):
            patched = json.loads(json.dumps(base_spec))
            for change in changes:
                if change.get("op") == "relative":
                    _apply_relative(patched, change["path"], change["value"])
                else:
                    _set_nested(patched, change["path"], change["value"])
            variants.append({"label": strategy["label"], "changes": [
                {"path": c["path"], "value": c["value"]}
                for c in changes if c.get("op") != "relative"
            ], "patched_spec": patched})
        else:
            variants.append({"label": strategy["label"], "changes": changes})

    return {
        "iteration": iteration + 1,
        "refinement_history": history,
        "variants": variants,
        "status": "running",
    }


def _should_refine(state: DeepDesignState) -> str:
    """Conditional edge: decide whether to refine or synthesize report."""
    iteration = state.get("iteration", 0)
    max_iterations = state.get("max_iterations", 1)
    results = state.get("results", [])

    # If we just came from run_compare and iteration < max_iterations and not all succeeded
    if iteration < max_iterations and not all(r.get("status") == "succeeded" for r in results):
        return "prepare_variants"

    return "synthesize_report"


@observe_node("synthesize_report")
def synthesize_report(state: DeepDesignState) -> dict:
    """Generate a design exploration report."""
    requirements = state.get("requirements", {})
    comparison = state.get("comparison")
    history = state.get("refinement_history", [])

    if not comparison:
        return {"report": "探索未完成，无法生成报告。", "status": "failed"}

    desc = requirements.get("description", "未指定")
    total = comparison.get("total", 0) or comparison.get("total_variants", 0)
    succeeded = comparison.get("succeeded", 0)

    lines = [
        f"# 设计探索报告",
        f"",
        f"**需求描述：** {desc}",
        f"",
        f"共探索 {total} 个变体，其中 {succeeded} 个成功。",
    ]

    if history:
        lines.append(f"迭代次数：{len(history)}")
        for h in history:
            lines.append(f"  第 {h['iteration'] + 1} 轮：{h['succeeded']}/{h['total']} 成功")

    lines.extend([
        f"",
        f"| 变体 | 状态 | 耗时 |",
        f"|------|------|------|",
    ])

    for v in comparison.get("variants", []):
        label = v.get("label", "?")
        status = v.get("status", "?")
        duration = v.get("duration_ms")
        dur_str = f"{duration:.0f}ms" if duration else "-"
        lines.append(f"| {label} | {status} | {dur_str} |")

    successful = [v for v in comparison.get("variants", []) if v.get("status") == "succeeded"]
    if successful:
        best = min(successful, key=lambda v: v.get("duration_ms", float("inf")))
        lines.append(f"")
        lines.append(f"**推荐：** {best['label']}（最快完成）")

    return {"report": "\n".join(lines), "status": "completed"}


def build_deep_design_graph(
    job_runner: Any,
    timeout_seconds: float = 120,
    enable_refinement: bool = False,
    streaming: bool = False,
) -> StateGraph:
    """Build the DeepDesignGraph using CompareGraph as subgraph.

    Args:
        job_runner: JobRunner instance.
        timeout_seconds: Max wait time for all variants.
        enable_refinement: If True, add refine_variants loop.
        streaming: If True, emit graph_node SSE events via observe_node_sse.

    Returns:
        Compiled StateGraph.
    """
    if streaming:
        # Unwrap observe_node, re-wrap with observe_node_sse for SSE emission
        _parse = observe_node_sse("parse_requirements")(parse_requirements.__wrapped__)
        _prepare = observe_node_sse("prepare_variants")(prepare_variants.__wrapped__)
        _report = observe_node_sse("synthesize_report")(synthesize_report.__wrapped__)
    else:
        _parse = parse_requirements
        _prepare = prepare_variants
        _report = synthesize_report

    graph = StateGraph(DeepDesignState)

    graph.add_node("parse_requirements", _parse)
    graph.add_node("prepare_variants", _prepare)
    graph.add_node("run_compare", make_run_compare_node(
        job_runner, timeout_seconds=timeout_seconds, streaming=streaming,
    ))
    graph.add_node("synthesize_report", _report)

    graph.add_edge(START, "parse_requirements")
    graph.add_edge("parse_requirements", "prepare_variants")
    graph.add_edge("prepare_variants", "run_compare")

    if enable_refinement:
        if streaming:
            _refine = observe_node_sse("refine_variants")(refine_variants.__wrapped__)
        else:
            _refine = refine_variants
        graph.add_node("refine_variants", _refine)
        graph.add_edge("run_compare", "refine_variants")
        graph.add_conditional_edges(
            "refine_variants",
            _should_refine,
            {
                "prepare_variants": "prepare_variants",
                "synthesize_report": "synthesize_report",
            },
        )
    else:
        graph.add_edge("run_compare", "synthesize_report")

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
        if "value" in current[last_key]:
            current[last_key]["value"] = current[last_key]["value"] + delta
    elif last_key in current:
        if isinstance(current[last_key], (int, float)):
            current[last_key] = current[last_key] + delta
