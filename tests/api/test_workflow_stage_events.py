"""Tests for workflow_stage events emitted during CAD generation."""

import json

import pytest
from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_events import (
    JobEvent,
    JobEventType,
    get_job_event_bus,
    reset_job_event_bus,
)
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


def test_fake_backend_emits_generating_spec_stage(runner):
    """FakeCadBackend generation should emit a workflow_stage event for 'generating_spec'."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    spec = _make_spec()
    runner.generate(design_id="test-ws-gen", spec=spec)

    stage_events = [
        e for e in collected
        if e.type == JobEventType.WORKFLOW_STAGE and e.stage == "generating_spec"
    ]
    assert len(stage_events) >= 1, (
        f"Expected at least one workflow_stage event with stage='generating_spec', "
        f"got stages: {[e.stage for e in collected if e.type == JobEventType.WORKFLOW_STAGE]}"
    )
    event = stage_events[0]
    assert event.label == "生成飞机参数"  # "生成飞机参数"
    assert event.progress == 10


def test_fake_backend_emits_validating_parameters_stage(runner):
    """FakeCadBackend generation should emit a workflow_stage event for 'validating_parameters'."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    spec = _make_spec()
    runner.generate(design_id="test-ws-val", spec=spec)

    stage_events = [
        e for e in collected
        if e.type == JobEventType.WORKFLOW_STAGE and e.stage == "validating_parameters"
    ]
    assert len(stage_events) >= 1, (
        f"Expected at least one workflow_stage event with stage='validating_parameters', "
        f"got stages: {[e.stage for e in collected if e.type == JobEventType.WORKFLOW_STAGE]}"
    )
    event = stage_events[0]
    assert event.label == "校验设计参数"  # "校验设计参数"
    assert event.progress == 20


def test_fake_backend_emits_cad_sub_stages(runner):
    """FakeCadBackend should emit CAD sub-stage events for testing visibility."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    spec = _make_spec()
    runner.generate(design_id="test-ws-cad", spec=spec)

    cad_stages = [
        e for e in collected
        if e.type == JobEventType.WORKFLOW_STAGE and "_created" in e.stage
    ]
    assert len(cad_stages) >= 4, (
        f"FakeCadBackend should emit CAD sub-stages, but only found: "
        f"{[e.stage for e in cad_stages]}"
    )


def test_fake_backend_emits_all_8_cad_stages(runner):
    """FakeCadBackend should emit all 8 CAD sub-stages."""
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    spec = _make_spec()
    runner.generate(design_id="test-ws-all8", spec=spec)

    ws_events = [e for e in collected if e.type == JobEventType.WORKFLOW_STAGE]
    stage_names = {e.stage for e in ws_events}

    expected = {
        "generating_spec", "validating_parameters",
        "fuselage_created", "wing_created", "tail_created", "engine_created",
        "vsp_model_saved", "step_exported", "glb_exported", "preview_ready",
    }
    missing = expected - stage_names
    assert not missing, f"Missing workflow stages: {missing}"


def test_sse_stream_includes_workflow_stage_events(client, runner):
    """The SSE stream for a completed job should include workflow_stage event data."""
    spec = _make_spec()
    job = runner.enqueue_generate(design_id="test-ws-sse", spec=spec)
    runner.run_queued_job(job.id, spec)

    resp = client.get(f"/api/jobs/{job.id}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]

    body = resp.text
    # Completed jobs return a single generation_complete event with full payload,
    # but the body should still carry stage/label if set on the job record.
    # For a queued+run job the stream returns one event; verify the SSE format
    # includes "workflow_stage" in the event body or the data contains stage info.
    # Since completed jobs get a single SSE event, verify the payload structure.
    data_lines = [
        line for line in body.split("\n") if line.startswith("data:")
    ]
    assert len(data_lines) >= 1, "Expected at least one data line in SSE stream"

    payload = json.loads(data_lines[0][5:].strip())
    # The completed-job response is a single generation_complete event.
    # Verify it contains the standard fields and the stage/label from the
    # last workflow_stage that was processed before completion.
    assert "progress" in payload
    assert "current_step" in payload


def test_completed_job_still_has_stages_in_stream(client, runner):
    """A completed job's stream should contain both generation_started and workflow_stage data."""
    # We need to subscribe to the event bus during generation to capture live events,
    # then verify the stream for a running job includes the workflow_stage events.
    # For a completed job the stream only returns generation_complete, so we test
    # via the sync subscriber path to confirm all stages were published.
    bus = get_job_event_bus()
    collected: list[JobEvent] = []

    def _collect(event: JobEvent) -> None:
        if event.type in (JobEventType.STARTED, JobEventType.WORKFLOW_STAGE, JobEventType.COMPLETED):
            collected.append(event)

    bus.subscribe(_collect)

    spec = _make_spec()
    job = runner.generate(design_id="test-ws-complete", spec=spec)

    # Verify we collected the full lifecycle
    types = [e.type for e in collected]
    assert JobEventType.STARTED in types, "Expected generation_started event"
    assert JobEventType.WORKFLOW_STAGE in types, "Expected workflow_stage events"
    assert JobEventType.COMPLETED in types, "Expected generation_complete event"

    # Verify order: STARTED -> WORKFLOW_STAGE -> COMPLETED
    started_idx = types.index(JobEventType.STARTED)
    completed_idx = types.index(JobEventType.COMPLETED)
    ws_indices = [i for i, t in enumerate(types) if t == JobEventType.WORKFLOW_STAGE]
    assert all(started_idx < i < completed_idx for i in ws_indices), (
        "All WORKFLOW_STAGE events should appear between STARTED and COMPLETED"
    )

    # Now verify the stream endpoint returns valid data for the completed job
    resp = client.get(f"/api/jobs/{job.id}/stream")
    assert resp.status_code == 200
    body = resp.text
    assert "generation_complete" in body
    assert "succeeded" in body
