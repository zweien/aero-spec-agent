"""Tests for stage_history replay in SSE stream for completed jobs."""

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


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into list of {type, data} dicts."""
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


def test_completed_job_replays_all_stages(client, runner):
    """After FakeCadBackend completes, SSE stream replays all workflow_stage events."""
    spec = _make_spec()
    job = runner.generate(design_id="test-replay", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    assert resp.status_code == 200

    events = _parse_sse_events(resp.text)
    event_types = [e["type"] for e in events]

    assert "workflow_stage" in event_types
    assert "generation_complete" in event_types

    ws_events = [e for e in events if e["type"] == "workflow_stage"]
    ws_stages = [e["data"].get("stage") for e in ws_events]

    expected_stages = [
        "generating_spec", "validating_parameters",
        "fuselage_created", "wing_created", "tail_created", "engine_created",
        "vsp_model_saved", "step_exported", "glb_exported", "preview_ready",
    ]
    for stage in expected_stages:
        assert stage in ws_stages, f"Missing stage: {stage}"


def test_replayed_stages_have_correct_order(client, runner):
    """Replayed stages should appear in the correct order."""
    spec = _make_spec()
    job = runner.generate(design_id="test-order", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse_events(resp.text)

    ws_events = [e for e in events if e["type"] == "workflow_stage"]
    ws_stages = [e["data"].get("stage") for e in ws_events]

    # generation_complete should be last
    all_types = [e["type"] for e in events]
    gc_idx = all_types.index("generation_complete")
    last_ws_idx = len(all_types) - 1 - all_types[::-1].index("workflow_stage")
    assert last_ws_idx < gc_idx

    # Stages should be in expected order
    order = {stage: i for i, stage in enumerate(ws_stages)}
    assert order.get("generating_spec", 999) < order.get("fuselage_created", 0)
    assert order.get("fuselage_created", 999) < order.get("preview_ready", 0)


def test_replayed_stages_progress_monotonically_increasing(client, runner):
    """Progress values in replayed stages should be monotonically increasing."""
    spec = _make_spec()
    job = runner.generate(design_id="test-progress", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse_events(resp.text)

    ws_events = [e for e in events if e["type"] == "workflow_stage"]
    progresses = [e["data"].get("progress", 0) for e in ws_events]

    for i in range(1, len(progresses)):
        assert progresses[i] > progresses[i - 1], (
            f"Progress not monotonically increasing: {progresses}"
        )


def test_completed_job_stream_has_chinese_labels(client, runner):
    """Replayed stages should have Chinese labels."""
    spec = _make_spec()
    job = runner.generate(design_id="test-labels", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse_events(resp.text)

    ws_events = [e for e in events if e["type"] == "workflow_stage"]
    for event in ws_events:
        label = event["data"].get("label", "")
        assert label, f"Missing label for stage {event['data'].get('stage')}"
        # Should not be the raw stage key
        stage = event["data"].get("stage", "")
        if stage in ("generating_spec", "validating_parameters", "fuselage_created",
                     "wing_created", "tail_created", "engine_created", "vsp_model_saved",
                     "step_exported", "glb_exported", "preview_ready"):
            assert label != stage, f"Label not translated for {stage}"


def test_completed_job_stream_includes_design_id(client, runner):
    """Replayed events should include design_id."""
    spec = _make_spec()
    job = runner.generate(design_id="test-did", spec=spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = _parse_sse_events(resp.text)

    for event in events:
        assert event["data"].get("design_id") == "test-did"
