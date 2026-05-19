"""VariantSubgraph — single variant generation subgraph.

Flow:
    START → validate_and_generate → END

This subgraph is invoked per-variant from CompareGraph,
running generation synchronously and returning the result.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from services.api.app.graph.observe import observe_node

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


def make_validate_and_generate_node(job_runner: Any):
    """Factory: validate spec and run generation synchronously."""

    @observe_node("validate_and_generate")
    def validate_and_generate(state: VariantSubgraphState) -> dict:
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
            job = job_runner.generate(design_id=design_id, spec=spec)
            return {
                "job_id": job.id,
                "version_no": job.version_no,
                "status": job.status,
                "duration_ms": job.duration_ms,
                "files": job.files or {},
                "error_message": getattr(job, "error_message", None),
            }
        except Exception as e:
            return {"status": "failed", "error_message": str(e)}

    return validate_and_generate


def build_variant_subgraph(
    job_runner: Any,
    timeout_seconds: float = 120,
) -> StateGraph:
    """Build a single-variant generation subgraph.

    Args:
        job_runner: JobRunner instance.
        timeout_seconds: Unused, kept for API compatibility.

    Returns:
        Compiled subgraph StateGraph.
    """
    graph = StateGraph(VariantSubgraphState)

    graph.add_node("validate_and_generate", make_validate_and_generate_node(job_runner))

    graph.add_edge(START, "validate_and_generate")
    graph.add_edge("validate_and_generate", END)

    return graph.compile()
