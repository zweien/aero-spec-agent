"""Metrics runtime validation — verify counters increment after deep-design runs."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from services.api.app.graph.metrics import get_metrics_collector, reset_metrics_collector
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
def _reset():
    reset_job_event_bus()
    reset_metrics_collector()
    yield
    reset_job_event_bus()
    reset_metrics_collector()


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


class TestMetricsRuntime:
    def test_deep_design_increments_counters(self, client, spec_dict):
        mc = get_metrics_collector()
        before = mc.snapshot()
        assert before.deep_design_runs == 0
        assert before.total_variants == 0

        resp = client.post("/api/deep-design", json={
            "design_id": "metrics-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        assert resp.status_code == 200

        after = mc.snapshot()
        assert after.deep_design_runs == 1
        assert after.total_variants == 2
        assert after.succeeded_variants >= 0

    def test_metrics_endpoint_shows_counters(self, client, spec_dict):
        client.post("/api/deep-design", json={
            "design_id": "prom-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })

        metrics_resp = client.get("/api/metrics")
        text = metrics_resp.text
        assert "deep_design_runs_total 1" in text
        assert "variants_total 1" in text

    def test_variant_success_rate_updated(self, client, spec_dict):
        client.post("/api/deep-design", json={
            "design_id": "rate-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })

        mc = get_metrics_collector()
        snap = mc.snapshot()
        assert snap.total_variants == 2
        # Success rate should be between 0 and 1
        assert 0.0 <= snap.variant_success_rate <= 1.0

        metrics_text = client.get("/api/metrics").text
        assert "variant_success_rate" in metrics_text

    def test_multiple_runs_accumulate(self, client, spec_dict):
        for i in range(3):
            client.post("/api/deep-design", json={
                "design_id": f"multi-{i}",
                "description": "设计一架无人机",
                "base_spec": spec_dict,
                "constraints": {"variant_count": 1},
            })

        mc = get_metrics_collector()
        snap = mc.snapshot()
        assert snap.deep_design_runs == 3
        assert snap.total_variants == 3
