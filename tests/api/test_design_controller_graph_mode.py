"""Tests for DesignController graph mode integration.

Validates that CompareGraph dispatch creates ControllerJob-compatible data,
and GET /api/design-controller/{id} correctly aggregates variant job results.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.services.design_controller import DesignControllerService
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
def _clean_env():
    orig = os.environ.pop("CHAT_GRAPH_MODE", None)
    yield
    if orig is not None:
        os.environ["CHAT_GRAPH_MODE"] = orig
    else:
        os.environ.pop("CHAT_GRAPH_MODE", None)


@pytest.fixture
def spec_dict():
    return _load_spec_dict()


@pytest.fixture
def job_runner(tmp_path):
    return AutoRunJobRunner(JobRunner(store=VersionStore(root=tmp_path)))


@pytest.fixture
def controller_svc(tmp_path):
    return DesignControllerService(storage_root=tmp_path)


# ---------------------------------------------------------------------------
# CompareGraph dispatch → ControllerJob schema
# ---------------------------------------------------------------------------


class TestCompareGraphDispatch:
    def test_dispatch_creates_valid_controller_job(self, job_runner, spec_dict):
        """CompareGraph dispatch should create data matching ControllerJob schema."""
        from services.api.app.graph.compare_graph import build_compare_graph

        graph = build_compare_graph(job_runner=job_runner, timeout_seconds=30)
        result = graph.invoke({
            "design_id": "test-design",
            "base_spec": spec_dict,
            "variants": [
                {"label": "variant_a", "changes": [{"path": "wing.span.value", "value": 15}]},
                {"label": "variant_b", "changes": [{"path": "fuselage.length.value", "value": 6}]},
            ],
        })

        assert result["status"] in ("running", "completed")
        variant_jobs = result.get("variant_jobs", [])
        assert len(variant_jobs) == 2

        # Each variant should have required fields
        for vj in variant_jobs:
            assert "label" in vj
            assert "job_id" in vj
            assert "version_no" in vj
            assert "changes" in vj
            assert "status" in vj

    def test_dispatch_no_variants_fails(self, job_runner, spec_dict):
        """CompareGraph with no variants should return failed status."""
        from services.api.app.graph.compare_graph import build_compare_graph

        graph = build_compare_graph(job_runner=job_runner)
        result = graph.invoke({
            "design_id": "test-design",
            "base_spec": spec_dict,
            "variants": [],
        })
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Aggregation via DesignControllerService
# ---------------------------------------------------------------------------


class TestAggregation:
    def test_aggregate_running_jobs(self, job_runner, spec_dict, controller_svc):
        """Aggregate should report running status for incomplete jobs."""
        from services.api.app.graph.compare_graph import build_compare_graph

        graph = build_compare_graph(job_runner=job_runner)
        result = graph.invoke({
            "design_id": "agg-design",
            "base_spec": spec_dict,
            "variants": [
                {"label": "v1", "changes": [{"path": "wing.span.value", "value": 12}]},
            ],
        })

        # Save as ControllerJob
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        controller_data = {
            "id": uuid.uuid4().hex[:12],
            "design_id": "agg-design",
            "status": "running",
            "variants": result["variant_jobs"],
            "results": [],
            "created_at": now,
            "updated_at": now,
        }
        controller_svc._save_from_dict(controller_data)

        # Aggregate should show jobs as running (background thread may not be done)
        aggregated = controller_svc.aggregate(controller_data["id"], job_runner)
        assert aggregated is not None
        assert aggregated.status in ("running", "completed")

    def test_aggregate_completes_when_jobs_finish(self, job_runner, spec_dict, controller_svc):
        """Aggregate should report completed when all jobs finish."""
        import time
        from services.api.app.graph.compare_graph import build_compare_graph

        graph = build_compare_graph(job_runner=job_runner)
        result = graph.invoke({
            "design_id": "agg-done-design",
            "base_spec": spec_dict,
            "variants": [
                {"label": "v1", "changes": [{"path": "wing.span.value", "value": 11}]},
            ],
        })

        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        controller_data = {
            "id": uuid.uuid4().hex[:12],
            "design_id": "agg-done-design",
            "status": "running",
            "variants": result["variant_jobs"],
            "results": [],
            "created_at": now,
            "updated_at": now,
        }
        controller_svc._save_from_dict(controller_data)

        # Wait for background job to complete
        time.sleep(2)

        aggregated = controller_svc.aggregate(controller_data["id"], job_runner)
        assert aggregated is not None
        assert aggregated.status == "completed"
        assert len(aggregated.results) == 1
        assert aggregated.results[0]["status"] == "succeeded"

    def test_aggregate_no_duplicate_results(self, job_runner, spec_dict, controller_svc):
        """Calling aggregate twice should not duplicate results."""
        import time
        from services.api.app.graph.compare_graph import build_compare_graph

        graph = build_compare_graph(job_runner=job_runner)
        result = graph.invoke({
            "design_id": "dedup-design",
            "base_spec": spec_dict,
            "variants": [
                {"label": "v1", "changes": [{"path": "wing.span.value", "value": 10}]},
            ],
        })

        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        controller_data = {
            "id": uuid.uuid4().hex[:12],
            "design_id": "dedup-design",
            "status": "running",
            "variants": result["variant_jobs"],
            "results": [],
            "created_at": now,
            "updated_at": now,
        }
        controller_svc._save_from_dict(controller_data)

        time.sleep(2)

        # Call aggregate twice
        controller_svc.aggregate(controller_data["id"], job_runner)
        aggregated = controller_svc.aggregate(controller_data["id"], job_runner)
        assert len(aggregated.results) == 1

    def test_aggregate_not_found(self, controller_svc, job_runner):
        """Aggregate for non-existent ID should return None."""
        result = controller_svc.aggregate("nonexistent-id", job_runner)
        assert result is None


# ---------------------------------------------------------------------------
# API endpoint integration
# ---------------------------------------------------------------------------


class TestDesignControllerAPI:
    def test_compare_endpoint_graph_mode(self, job_runner, spec_dict):
        """POST /compare with graph mode should use CompareGraph."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            resp = client.post("/api/design-controller/compare", json={
                "design_id": "api-test-design",
                "base_spec": spec_dict,
                "variants": [
                    {"label": "v1", "changes": [{"path": "wing.span.value", "value": 14}]},
                ],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert len(data["variants"]) == 1
            assert "job_id" in data["variants"][0]

    def test_get_controller_job_endpoint(self, job_runner, spec_dict):
        """GET /api/design-controller/{id} should aggregate results."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            # Create a controller job
            resp = client.post("/api/design-controller/compare", json={
                "design_id": "get-test-design",
                "base_spec": spec_dict,
                "variants": [
                    {"label": "v1", "changes": [{"path": "wing.span.value", "value": 13}]},
                ],
            })
            assert resp.status_code == 200
            job_id = resp.json()["id"]

            # Get the controller job
            import time
            time.sleep(2)
            get_resp = client.get(f"/api/design-controller/{job_id}")
            assert get_resp.status_code == 200
            result = get_resp.json()
            assert result["status"] in ("running", "completed", "failed")

    def test_compare_endpoint_legacy_mode(self, job_runner, spec_dict):
        """POST /compare in legacy mode should use DesignControllerService."""
        os.environ["CHAT_GRAPH_MODE"] = "legacy"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            resp = client.post("/api/design-controller/compare", json={
                "design_id": "legacy-test-design",
                "base_spec": spec_dict,
                "variants": [
                    {"label": "v1", "changes": [{"path": "wing.span.value", "value": 16}]},
                ],
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "running"
            assert len(data["variants"]) == 1
