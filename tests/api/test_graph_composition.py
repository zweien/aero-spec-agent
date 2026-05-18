"""Tests for graph-of-graphs composition.

Validates:
  - VariantSubgraph: single variant generation subgraph
  - CompareGraph with VariantSubgraph composition
  - DeepDesignGraph → CompareGraph → VariantSubgraph nested composition
  - Variant thread_id isolation
  - State transformation between parent and child graphs
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.compare_graph import build_compare_graph
from services.api.app.graph.deep_design_graph import build_deep_design_graph
from services.api.app.graph.variant_subgraph import build_variant_subgraph
from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
    """Wraps JobRunner to auto-execute enqueued jobs in background threads."""

    def __init__(self, jr: JobRunner) -> None:
        self._jr = jr

    def enqueue_generate(self, design_id, spec):
        job = self._jr.enqueue_generate(design_id=design_id, spec=spec)
        t = threading.Thread(target=self._jr.run_queued_job, args=(job.id, spec), daemon=True)
        t.start()
        return job

    def get(self, job_id):
        return self._jr.get(job_id)

    @property
    def store(self):
        return self._jr.store

    def __getattr__(self, name):
        return getattr(self._jr, name)


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_job_event_bus()
    yield
    reset_job_event_bus()


@pytest.fixture
def spec_dict():
    return _load_spec_dict()


@pytest.fixture
def job_runner(tmp_path):
    return AutoRunJobRunner(JobRunner(store=VersionStore(root=tmp_path)))


# ---------------------------------------------------------------------------
# VariantSubgraph
# ---------------------------------------------------------------------------


class TestVariantSubgraph:
    def test_single_variant_succeeds(self, job_runner, spec_dict):
        subgraph = build_variant_subgraph(job_runner=job_runner, timeout_seconds=30)

        result = subgraph.invoke({
            "design_id": "variant-test",
            "spec": spec_dict,
            "label": "test-variant",
        })

        assert result["status"] == "succeeded"
        assert result["job_id"]
        assert result["version_no"] >= 1
        assert result["duration_ms"] is not None

    def test_invalid_spec_fails(self, job_runner):
        subgraph = build_variant_subgraph(job_runner=job_runner, timeout_seconds=5)

        result = subgraph.invoke({
            "design_id": "bad-spec",
            "spec": {"invalid": True},
            "label": "bad",
        })

        assert result["status"] == "failed"
        assert result["error_message"]

    def test_variant_subgraph_state_keys(self, job_runner, spec_dict):
        subgraph = build_variant_subgraph(job_runner=job_runner, timeout_seconds=30)

        result = subgraph.invoke({
            "design_id": "keys-test",
            "spec": spec_dict,
            "label": "keys",
        })

        assert "design_id" in result
        assert "label" in result
        assert "status" in result
        assert "job_id" in result

    def test_thread_id_isolation(self, job_runner, spec_dict):
        """Different thread_ids produce independent subgraph runs."""
        subgraph = build_variant_subgraph(job_runner=job_runner, timeout_seconds=30)

        result_a = subgraph.invoke(
            {"design_id": "iso", "spec": spec_dict, "label": "a"},
            config={"configurable": {"thread_id": "iso-a"}},
        )
        result_b = subgraph.invoke(
            {"design_id": "iso", "spec": spec_dict, "label": "b"},
            config={"configurable": {"thread_id": "iso-b"}},
        )

        assert result_a["status"] == "succeeded"
        assert result_b["status"] == "succeeded"
        assert result_a["job_id"] != result_b["job_id"]


# ---------------------------------------------------------------------------
# CompareGraph with VariantSubgraph
# ---------------------------------------------------------------------------


class TestCompareGraphComposition:
    def test_dispatch_invokes_subgraph_per_variant(self, job_runner, spec_dict):
        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "design_id": "compare-test",
            "base_spec": spec_dict,
            "variants": [
                {"label": "v1", "changes": []},
                {"label": "v2", "changes": []},
            ],
        })

        assert result["status"] == "completed"
        assert len(result["results"]) == 2
        # Each result should have subgraph output fields
        for r in result["results"]:
            assert r["status"] in ("succeeded", "failed")
            assert "thread_id" in r

    def test_compare_metrics_aggregation(self, job_runner, spec_dict):
        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "design_id": "agg-test",
            "base_spec": spec_dict,
            "variants": [
                {"label": "a", "changes": []},
            ],
        })

        comparison = result["comparison"]
        assert comparison is not None
        assert comparison["total_variants"] == 1
        assert comparison["succeeded"] >= 0

    def test_variant_thread_isolation_in_compare(self, job_runner, spec_dict):
        """Each variant gets its own thread_id namespace."""
        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "design_id": "thread-iso",
            "base_spec": spec_dict,
            "variants": [
                {"label": "va", "changes": []},
                {"label": "vb", "changes": []},
            ],
        })

        thread_ids = [r["thread_id"] for r in result["results"]]
        assert len(set(thread_ids)) == 2  # All different

    def test_no_variants_fails(self, job_runner):
        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=5)

        result = graph.invoke({
            "design_id": "empty",
            "base_spec": {},
            "variants": [],
        })

        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Nested graph state transformation
# ---------------------------------------------------------------------------


class TestNestedStateTransformation:
    def test_deep_design_to_compare_state_transform(self, job_runner, spec_dict):
        """DeepDesignGraph transforms its state for CompareGraph subgraph."""
        graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "user_description": "设计一架无人机",
            "design_id": "nested-test",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        # DeepDesignGraph state has report and comparison
        assert result["status"] == "completed"
        assert result["report"]
        assert result["comparison"] is not None
        # CompareGraph subgraph produced variant results
        assert len(result["results"]) == 2

    def test_full_three_level_composition(self, job_runner, spec_dict):
        """DeepDesignGraph → CompareGraph → VariantSubgraph three-level nesting."""
        graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "user_description": "设计一架 500km 无人机",
            "design_id": "three-level",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        assert result["status"] == "completed"
        # VariantSubgraph results bubbled up through CompareGraph to DeepDesignGraph
        for r in result["results"]:
            assert "label" in r
            assert "status" in r


# ---------------------------------------------------------------------------
# Variant failure isolation
# ---------------------------------------------------------------------------


class TestVariantFailureIsolation:
    def test_one_invalid_spec_doesnt_crash_others(self, job_runner, spec_dict):
        """One variant with bad spec doesn't prevent others from succeeding."""
        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "design_id": "partial-fail",
            "base_spec": spec_dict,
            "variants": [
                {"label": "good", "changes": []},
                {"label": "bad", "changes": [
                    {"path": "wing.span.value", "value": "not_a_number"},
                ]},
            ],
        })

        # Overall graph should still complete (not crash)
        assert result["status"] == "completed"
        results = result["results"]
        # At least the "good" variant should have a result
        labels = {r["label"] for r in results}
        assert "good" in labels

    def test_all_variants_fail_still_completes(self, job_runner):
        """All variants failing still returns completed status with comparison."""
        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=5)

        result = graph.invoke({
            "design_id": "all-fail",
            "base_spec": {"invalid": True},
            "variants": [
                {"label": "v1", "changes": []},
            ],
        })

        assert result["status"] == "completed"
        assert result["comparison"]["failed"] >= 1


# ---------------------------------------------------------------------------
# Refinement iteration limits
# ---------------------------------------------------------------------------


class TestRefinementIterationLimits:
    def test_refine_respects_max_iterations(self, job_runner, spec_dict):
        """refine_variants never exceeds max_iterations."""
        graph = build_deep_design_graph(
            job_runner=job_runner, timeout_seconds=30, enable_refinement=True,
        )
        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "max-iter-test",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2, "max_iterations": 2},
        })

        assert result["status"] == "completed"
        assert result["iteration"] <= 2
        assert len(result.get("refinement_history", [])) <= 2

    def test_single_iteration_no_loop(self, job_runner, spec_dict):
        """max_iterations=1 means no refinement loop at all."""
        graph = build_deep_design_graph(
            job_runner=job_runner, timeout_seconds=30, enable_refinement=True,
        )
        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "single-iter",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2, "max_iterations": 1},
        })

        assert result["status"] == "completed"
        assert len(result.get("refinement_history", [])) <= 1

    def test_refinement_disabled_single_pass(self, job_runner, spec_dict):
        """enable_refinement=False means no refine_variants node."""
        graph = build_deep_design_graph(
            job_runner=job_runner, timeout_seconds=30, enable_refinement=False,
        )
        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "no-refine",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        assert result["status"] == "completed"
        assert result.get("iteration", 0) == 0
