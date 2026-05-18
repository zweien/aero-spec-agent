"""Tests for DeepDesignGraph — multi-variant design exploration.

Validates:
  - parse_requirements extracts range/payload from natural language
  - explore_variants dispatches N variant jobs
  - compare_results collects outcomes via JobEventBus
  - synthesize_report generates comparison report
  - Full graph end-to-end with AutoRunJobRunner
  - POST /api/deep-design endpoint
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from services.api.app.graph.deep_design_graph import (
    DeepDesignState,
    build_deep_design_graph,
    parse_requirements,
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
        assert result["comparison"]["total"] == 2
        assert result["comparison"]["succeeded"] >= 1

    def test_three_variants_default(self, job_runner, spec_dict):
        graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=30)

        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "deep-3v",
            "base_spec": spec_dict,
            "constraints": {},
        })

        assert result["status"] == "completed"
        assert result["comparison"]["total"] == 3

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
