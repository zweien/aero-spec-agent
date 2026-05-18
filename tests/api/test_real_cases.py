"""Real case tests — execute test plan cases 1 & 2, validate results."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

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
# Case 1: Long-range recon UAV (3 variants)
# ---------------------------------------------------------------------------


class TestCase1LongRangeReconUAV:
    """Case 1 from real-case-test-plan.md: 500km range, 20kg payload, 3 variants."""

    def test_3_variants_complete(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "recon-uav-endurance",
            "description": "设计一款长航时侦察无人机，航程 500km，载荷 20kg，优先考虑续航时间",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 3, "max_iterations": 1},
        })
        assert resp.status_code == 200
        data = resp.json()

        # Status must be completed
        assert data["status"] == "completed"

        # 3 variants explored
        assert data["comparison"]["total_variants"] == 3

        # Report contains variant table
        assert "| 变体 |" in data["report"]
        assert "compact" in data["report"]
        assert "standard" in data["report"]
        assert "extended" in data["report"]

    def test_requirements_parsed(self, client, spec_dict):
        """Description with 500km and 20kg should be parsed."""
        resp = client.post("/api/deep-design", json={
            "design_id": "recon-uav-parse",
            "description": "设计一款长航时侦察无人机，航程 500km，载荷 20kg",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "500km" in data["report"]

    def test_stream_has_graph_nodes(self, client, spec_dict):
        """Stream endpoint should emit graph_node events for all nodes."""
        resp = client.post("/api/deep-design/stream", json={
            "design_id": "recon-uav-stream",
            "description": "设计一款长航时侦察无人机，航程 500km",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 3},
        })
        assert resp.status_code == 200
        text = resp.text

        # Should have graph_node events
        assert "graph_node" in text
        assert "parse_requirements" in text
        assert "run_compare" in text
        assert "synthesize_report" in text


# ---------------------------------------------------------------------------
# Case 2: Small logistics UAV (1 variant)
# ---------------------------------------------------------------------------


class TestCase2SmallLogisticsUAV:
    """Case 2: small logistics UAV, single variant, minimal constraints."""

    def test_single_variant_completes(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "logistics-uav",
            "description": "设计一架小型物流无人机，载荷 5kg，航程 50km",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["comparison"]["total_variants"] == 1

    def test_report_has_description(self, client, spec_dict):
        resp = client.post("/api/deep-design", json={
            "design_id": "logistics-desc",
            "description": "设计一架小型物流无人机，载荷 5kg，航程 50km",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })
        data = resp.json()
        assert "50km" in data["report"]

    def test_metrics_updated_after_run(self, client, spec_dict):
        """After running case 2, metrics should reflect the run."""
        from services.api.app.graph.metrics import get_metrics_collector

        before = get_metrics_collector().snapshot()
        runs_before = before.deep_design_runs

        client.post("/api/deep-design", json={
            "design_id": "metrics-case2",
            "description": "小型物流无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })

        after = get_metrics_collector().snapshot()
        assert after.deep_design_runs == runs_before + 1
        assert after.total_variants >= runs_before * 1 + 1
