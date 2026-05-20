"""Tests for artifact_generated events in SSE stream."""

import json
import pytest
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend


def _make_spec():
    return AircraftSpec.model_validate({
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
    })


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


def _parse_sse(text):
    events = []
    current = {}
    for line in text.split("\n"):
        if line.startswith("event:"):
            current["type"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif line == "" and "type" in current:
            events.append(current)
            current = {}
    return events


def test_completed_job_replays_artifact_generated_events(client, runner):
    spec = _make_spec()
    job = runner.generate(design_id="test-art", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse(resp.text)

    art_events = [e for e in events if e["type"] == "artifact_generated"]
    assert len(art_events) >= 3, f"Expected >= 3 artifact events, got {len(art_events)}"

    artifacts = [e["data"].get("artifact") for e in art_events]
    assert "vsp3" in artifacts
    assert "step" in artifacts
    assert "glb" in artifacts


def test_artifact_events_have_chinese_labels(client, runner):
    spec = _make_spec()
    job = runner.generate(design_id="test-art-labels", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse(resp.text)

    art_events = [e for e in events if e["type"] == "artifact_generated"]
    for event in art_events:
        label = event["data"].get("label", "")
        assert label, f"Missing label for artifact {event['data'].get('artifact')}"


def test_artifact_events_appear_before_completion(client, runner):
    spec = _make_spec()
    job = runner.generate(design_id="test-art-order", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse(resp.text)

    types = [e["type"] for e in events]
    if "artifact_generated" in types:
        art_idx = types.index("artifact_generated")
        gc_idx = types.index("generation_complete")
        assert art_idx < gc_idx, "artifact_generated should appear before generation_complete"


def test_artifact_events_include_metadata(client, runner):
    spec = _make_spec()
    job = runner.generate(design_id="test-art-meta", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse(resp.text)

    art_events = [e for e in events if e["type"] == "artifact_generated"]
    for event in art_events:
        data = event["data"]
        assert "metadata" in data
        assert data["metadata"].get("artifact_key"), "Missing artifact_key in metadata"
        assert data["metadata"].get("artifact_path"), "Missing artifact_path in metadata"
