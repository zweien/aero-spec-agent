"""Tests for workflow failure events and error handling."""

import json
import pytest

from fastapi.testclient import TestClient
from services.api.app.main import app
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_events import (
    JobEvent, JobEventType, get_job_event_bus, reset_job_event_bus,
)
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


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


def test_failed_job_emits_failed_event():
    """When generation fails, a FAILED event should be emitted."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("CAD generation failed: invalid geometry")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    job = runner.generate(design_id="test-fail", spec=_make_spec())

    assert job.status == "failed"
    assert "CAD generation failed" in (job.error_message or "")

    types = [e.type for e in collected]
    assert JobEventType.FAILED in types
    assert JobEventType.STARTED in types

    failed_event = [e for e in collected if e.type == JobEventType.FAILED][0]
    assert "CAD generation failed" in (failed_event.error_message or "")


def test_failed_job_stream_includes_error():
    """SSE stream for failed job should include error information."""
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("OpenVSP error: invalid wing span")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    job = runner.generate(design_id="test-fail-stream", spec=_make_spec())

    client = TestClient(app)
    resp = client.get(f"/api/jobs/{job.id}/stream")
    assert resp.status_code == 200

    body = resp.text
    assert "generation_failed" in body
    assert "OpenVSP error" in body


def test_failed_job_has_workflow_stages_before_failure():
    """Even when generation fails, workflow stages before the failure should be recorded."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("CAD failure")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    job = runner.generate(design_id="test-fail-stages", spec=_make_spec())

    # Should have at least generating_spec and validating_parameters before failure
    ws_events = [e for e in collected if e.type == JobEventType.WORKFLOW_STAGE]
    ws_stages = [e.stage for e in ws_events]

    assert "generating_spec" in ws_stages, f"Missing generating_spec, got: {ws_stages}"
    assert "validating_parameters" in ws_stages, f"Missing validating_parameters, got: {ws_stages}"

    # Failed event should come after workflow stages
    types = [e.type for e in collected]
    last_ws_idx = max(i for i, t in enumerate(types) if t == JobEventType.WORKFLOW_STAGE)
    failed_idx = types.index(JobEventType.FAILED)
    assert last_ws_idx < failed_idx


def test_failed_job_replays_stages_in_stream():
    """Failed job SSE stream should replay recorded stages before generation_failed."""
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("Export failed")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    job = runner.generate(design_id="test-fail-replay", spec=_make_spec())

    client = TestClient(app)
    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = []
    current = {}
    for line in resp.text.split("\n"):
        if line.startswith("event:"):
            current["type"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif line == "" and "type" in current:
            events.append(current)
            current = {}

    types = [e["type"] for e in events]
    assert "workflow_stage" in types
    assert "generation_failed" in types

    # workflow_stage should come before generation_failed
    ws_idx = types.index("workflow_stage")
    gf_idx = types.index("generation_failed")
    assert ws_idx < gf_idx


def test_failed_job_records_stage_history():
    """Failed job should record partial stage history."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("CAD failure in stage")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    job = runner.generate(design_id="test-fail-history", spec=_make_spec())

    # stage_history should include pre-failure stages
    assert len(job.stage_history) >= 2
    stages_in_history = [e.get("stage") for e in job.stage_history]
    assert "generating_spec" in stages_in_history
    assert "validating_parameters" in stages_in_history


def test_failed_job_stream_contains_error_message():
    """The generation_failed SSE event should carry the error message."""
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("specific error: wing too small")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    job = runner.generate(design_id="test-fail-err-msg", spec=_make_spec())

    client = TestClient(app)
    resp = client.get(f"/api/jobs/{job.id}/stream")
    events = []
    current = {}
    for line in resp.text.split("\n"):
        if line.startswith("event:"):
            current["type"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif line == "" and "type" in current:
            events.append(current)
            current = {}

    failed_events = [e for e in events if e["type"] == "generation_failed"]
    assert len(failed_events) == 1
    data = failed_events[0]["data"]
    assert "specific error" in data.get("error_message", "")


def test_failed_job_has_started_event():
    """A failed job should still emit a STARTED event before FAILED."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir, **kwargs):
            raise RuntimeError("boom")

    runner = JobRunner(store=VersionStore(), backend=FailingBackend())
    runner.generate(design_id="test-fail-started", spec=_make_spec())

    types = [e.type for e in collected]
    assert JobEventType.STARTED in types
    assert JobEventType.FAILED in types
    started_idx = types.index(JobEventType.STARTED)
    failed_idx = types.index(JobEventType.FAILED)
    assert started_idx < failed_idx
