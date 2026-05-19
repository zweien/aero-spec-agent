"""Tests for GET /api/jobs/{job_id}/stream SSE endpoint."""

import json
import threading

import pytest
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend


def _make_spec(overrides=None):
    base = {
        "schema_version": "0.1",
        "aircraft": {"name": "test", "type": "fixed_wing_uav", "layout": "conventional"},
        "wing": {
            "position": {"value": "high", "source": "user", "confidence": 1.0},
            "span": {"value": 10, "unit": "m", "source": "user", "confidence": 1.0},
            "root_chord": {"value": 1, "unit": "m", "source": "rule_default", "confidence": 0.7},
            "tip_chord": {"value": 0.5, "unit": "m", "source": "rule_default", "confidence": 0.7},
        },
        "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1.0}},
        "engine": {"count": {"value": 1, "source": "user", "confidence": 1.0}},
        "fuselage": {
            "length": {"value": 6, "unit": "m", "source": "rule_default", "confidence": 0.7},
            "max_diameter": {"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.7},
        },
    }
    if overrides:
        import copy
        base = copy.deepcopy(base)
        for k, v in overrides.items():
            base[k] = v
    return AircraftSpec.model_validate(base)


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_job_event_bus()
    yield
    reset_job_event_bus()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def runner():
    return JobRunner(store=VersionStore(), backend=get_cad_backend("fake"))


class TestJobStream:
    def test_returns_404_for_unknown_job(self, client):
        resp = client.get("/api/jobs/nonexistent/stream")
        assert resp.status_code == 404

    def test_returns_single_event_for_completed_job(self, client, runner):
        spec = _make_spec()
        job = runner.enqueue_generate(design_id="test-stream", spec=spec)
        runner.run_queued_job(job.id, spec)

        resp = client.get(f"/api/jobs/{job.id}/stream")
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        body = resp.text
        assert "generation_complete" in body
        assert "succeeded" in body

    def test_completed_job_payload_has_version_no(self, client, runner):
        spec = _make_spec()
        job = runner.enqueue_generate(design_id="test-stream-v2", spec=spec)
        runner.run_queued_job(job.id, spec)

        resp = client.get(f"/api/jobs/{job.id}/stream")
        assert resp.status_code == 200
        body = resp.text
        # Verify payload contains version_no and files
        for line in body.split("\n"):
            if line.startswith("data:"):
                data = json.loads(line[5:].strip())
                assert "version_no" in data
                break
