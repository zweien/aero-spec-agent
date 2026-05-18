"""Tests for DeepDesignGraph — multi-variant design exploration via subgraph composition.

Validates:
  - parse_requirements extracts range/payload from natural language
  - prepare_variants builds variant specs
  - synthesize_report generates comparison report
  - Full graph end-to-end with AutoRunJobRunner
  - POST /api/deep-design endpoint
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.deep_design_graph import (
    DeepDesignState,
    build_deep_design_graph,
    parse_requirements,
    prepare_variants,
    refine_variants,
    synthesize_report,
)
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
# parse_requirements
# ---------------------------------------------------------------------------


class TestParseRequirements:
    def test_extracts_range_km(self):
        state: DeepDesignState = {"user_description": "设计一架 500km 航程的无人机", "constraints": {}}
        result = parse_requirements(state)
        assert result["requirements"]["range_km"] == 500

    def test_extracts_payload_kg(self):
        state: DeepDesignState = {"user_description": "载荷 100kg 的运输机", "constraints": {}}
        result = parse_requirements(state)
        assert result["requirements"]["payload_kg"] == 100

    def test_extracts_both(self):
        state: DeepDesignState = {"user_description": "航程 800km 载荷 50kg", "constraints": {}}
        result = parse_requirements(state)
        assert result["requirements"]["range_km"] == 800
        assert result["requirements"]["payload_kg"] == 50

    def test_default_variant_count(self):
        state: DeepDesignState = {"user_description": "test", "constraints": {}}
        result = parse_requirements(state)
        assert result["requirements"]["variant_count"] == 3

    def test_custom_variant_count(self):
        state: DeepDesignState = {"user_description": "test", "constraints": {"variant_count": 5}}
        result = parse_requirements(state)
        assert result["requirements"]["variant_count"] == 5


# ---------------------------------------------------------------------------
# prepare_variants
# ---------------------------------------------------------------------------


class TestPrepareVariants:
    def test_builds_correct_variant_count(self, spec_dict):
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        }
        result = prepare_variants(state)
        assert len(result["variants"]) == 2
        assert result["status"] == "running"

    def test_pads_to_variant_count(self, spec_dict):
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 5},
        }
        result = prepare_variants(state)
        assert len(result["variants"]) == 5

    def test_no_base_spec_fails(self):
        state: DeepDesignState = {
            "base_spec": None,
            "constraints": {"variant_count": 2},
        }
        result = prepare_variants(state)
        assert result["status"] == "failed"

    def test_compact_variant_has_patched_spec(self, spec_dict):
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        }
        result = prepare_variants(state)
        variant = result["variants"][0]
        assert variant["label"] == "compact"
        assert "patched_spec" in variant


# ---------------------------------------------------------------------------
# synthesize_report
# ---------------------------------------------------------------------------


class TestSynthesizeReport:
    def test_report_with_successful_variants(self):
        state: DeepDesignState = {
            "requirements": {"description": "测试无人机"},
            "comparison": {
                "total": 3,
                "succeeded": 2,
                "failed": 1,
                "variants": [
                    {"label": "compact", "status": "succeeded", "duration_ms": 120.5},
                    {"label": "standard", "status": "succeeded", "duration_ms": 95.3},
                    {"label": "extended", "status": "failed", "duration_ms": None},
                ],
            },
        }
        result = synthesize_report(state)
        assert "设计探索报告" in result["report"]
        assert "compact" in result["report"]
        assert "standard" in result["report"]
        assert "推荐" in result["report"]
        assert result["status"] == "completed"

    def test_report_no_comparison(self):
        state: DeepDesignState = {"requirements": {}, "comparison": None}
        result = synthesize_report(state)
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Full graph end-to-end
# ---------------------------------------------------------------------------


class TestDeepDesignGraphE2E:
    def test_full_graph_succeeds(self, job_runner, spec_dict):
        graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "user_description": "设计一架 300km 航程的无人机",
            "design_id": "deep-test",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        assert result["status"] == "completed"
        assert result["report"]
        assert result["comparison"] is not None
        assert result["comparison"]["total_variants"] == 2
        assert result["comparison"]["succeeded"] >= 1

    def test_two_variants_explicit(self, job_runner, spec_dict):
        graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "deep-2v",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        assert result["status"] == "completed"
        assert result["comparison"]["total_variants"] == 2

    def test_no_base_spec_fails(self, job_runner):
        graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=5)

        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "deep-nospec",
            "base_spec": None,
            "constraints": {},
        })

        assert result["status"] == "failed"
        assert result["error_message"]


# ---------------------------------------------------------------------------
# POST /api/deep-design endpoint
# ---------------------------------------------------------------------------


class TestDeepDesignEndpoint:
    def test_endpoint_returns_report(self, spec_dict):
        from fastapi.testclient import TestClient

        from services.api.app.main import app
        client = TestClient(app)

        resp = client.post("/api/deep-design", json={
            "design_id": "endpoint-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["design_id"] == "endpoint-test"
        assert data["status"] == "completed"
        assert data["report"]
        assert data["comparison"] is not None


# ---------------------------------------------------------------------------
# Iterative refinement loop
# ---------------------------------------------------------------------------


class TestIterativeRefinement:
    def test_refine_variants_records_history(self, spec_dict):
        """refine_variants records iteration history."""
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
            "iteration": 0,
            "max_iterations": 3,
            "results": [
                {"label": "compact", "status": "failed"},
                {"label": "extended", "status": "succeeded"},
            ],
            "comparison": {"total_variants": 2, "succeeded": 1},
            "refinement_history": [],
        }
        result = refine_variants(state)
        assert result["iteration"] == 1
        assert len(result["refinement_history"]) == 1
        assert result["refinement_history"][0]["succeeded"] == 1

    def test_refine_stops_at_max_iterations(self, spec_dict):
        """refine_variants stops when max_iterations reached."""
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
            "iteration": 2,
            "max_iterations": 3,
            "results": [
                {"label": "compact", "status": "failed"},
            ],
            "comparison": {"total_variants": 1, "succeeded": 0},
            "refinement_history": [],
        }
        result = refine_variants(state)
        assert result["iteration"] == 3
        assert result["status"] == "completed"

    def test_refine_stops_when_all_succeed(self, spec_dict):
        """refine_variants stops when all variants succeeded."""
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
            "iteration": 0,
            "max_iterations": 5,
            "results": [
                {"label": "compact", "status": "succeeded"},
                {"label": "extended", "status": "succeeded"},
            ],
            "comparison": {"total_variants": 2, "succeeded": 2},
            "refinement_history": [],
        }
        result = refine_variants(state)
        assert result["status"] == "completed"

    def test_refine_produces_wider_variants(self, spec_dict):
        """refine_variants produces variants with wider deltas."""
        state: DeepDesignState = {
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
            "iteration": 0,
            "max_iterations": 3,
            "results": [
                {"label": "compact", "status": "failed"},
            ],
            "comparison": {"total_variants": 1, "succeeded": 0},
            "refinement_history": [],
        }
        result = refine_variants(state)
        assert result["status"] == "running"
        assert result["variants"] is not None
        assert len(result["variants"]) == 2

    def test_graph_with_refinement_enabled(self, job_runner, spec_dict):
        """Full graph with refinement loop runs multiple iterations."""
        graph = build_deep_design_graph(
            job_runner=job_runner,
            timeout_seconds=30,
            enable_refinement=True,
        )
        result = graph.invoke({
            "user_description": "设计一架无人机",
            "design_id": "refine-test",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2, "max_iterations": 2},
        })

        assert result["status"] == "completed"
        assert result["report"]
        assert result["iteration"] >= 1
        assert len(result["refinement_history"]) >= 1

    def test_graph_without_refinement_single_pass(self, job_runner, spec_dict):
        """Graph without refinement runs single pass (default)."""
        graph = build_deep_design_graph(
            job_runner=job_runner,
            timeout_seconds=30,
            enable_refinement=False,
        )
        result = graph.invoke({
            "user_description": "设计一架无人机",
            "design_id": "no-refine",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        assert result["status"] == "completed"
        assert result["iteration"] == 0
