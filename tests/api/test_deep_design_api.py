"""Enhanced DeepDesign API tests — variant counts, iterations, failures, report content."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from services.api.app.graph.deep_design_graph import build_deep_design_graph
from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
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


@pytest.fixture
def client(job_runner):
    from services.api.app.main import app
    with patch("services.api.app.routers.designs._get_job_runner", return_value=job_runner):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# variant_count variations
# ---------------------------------------------------------------------------


class TestVariantCount:
    def test_variant_count_3(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "vc-3",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 3},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison"]["total_variants"] == 3

    def test_variant_count_1(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "vc-1",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison"]["total_variants"] == 1

    def test_variant_count_5_exceeds_strategies(self, client, spec_dict):
        """Requesting more variants than default strategies pads with standard copies."""
        resp = client.post("/api/deep-design", json={
            "design_id": "vc-5",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 5},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["comparison"]["total_variants"] == 5


# ---------------------------------------------------------------------------
# max_iterations variations
# ---------------------------------------------------------------------------


class TestMaxIterations:
    def test_max_iterations_1_single_pass(self, job_runner, spec_dict):
        graph = build_deep_design_graph(
            job_runner=job_runner, timeout_seconds=30, enable_refinement=True,
        )
        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "iter-1",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2, "max_iterations": 1},
        })
        assert result["status"] == "completed"
        # max_iterations=1 means at most 1 refinement pass
        assert result["iteration"] <= 1

    def test_max_iterations_2_runs_refinement(self, job_runner, spec_dict):
        graph = build_deep_design_graph(
            job_runner=job_runner, timeout_seconds=30, enable_refinement=True,
        )
        result = graph.invoke({
            "user_description": "设计无人机",
            "design_id": "iter-2",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2, "max_iterations": 2},
        })
        assert result["status"] == "completed"
        assert len(result.get("refinement_history", [])) >= 1


# ---------------------------------------------------------------------------
# Invalid base_spec
# ---------------------------------------------------------------------------


class TestInvalidSpec:
    def test_null_base_spec(self, client):
        """null base_spec is rejected by Pydantic validation (422)."""
        resp = client.post("/api/deep-design", json={
            "design_id": "null-spec",
            "description": "设计一架无人机",
            "base_spec": None,
            "constraints": {},
        })
        # Pydantic rejects None for a required dict field
        assert resp.status_code == 422

    def test_empty_base_spec(self, client):
        resp = client.post("/api/deep-design", json={
            "design_id": "empty-spec",
            "description": "设计一架无人机",
            "base_spec": {},
            "constraints": {"variant_count": 2},
        })
        assert resp.status_code == 200
        data = resp.json()
        # Should still return a result (variants may fail validation)
        assert data["status"] in ("completed", "failed")


# ---------------------------------------------------------------------------
# Report content validation
# ---------------------------------------------------------------------------


class TestReportContent:
    def test_report_has_table(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "report-table",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        data = resp.json()
        assert data["status"] == "completed"
        report = data["report"]
        assert "| 变体 |" in report
        assert "|------|" in report
        assert "compact" in report or "standard" in report

    def test_report_includes_description(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "report-desc",
            "description": "设计一架 300km 航程的无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        data = resp.json()
        assert "300km" in data["report"]

    def test_report_with_all_succeeded(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "report-ok",
            "description": "设计无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        data = resp.json()
        if data["comparison"]["succeeded"] > 0:
            assert "推荐" in data["report"]
