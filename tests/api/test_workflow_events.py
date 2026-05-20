"""Tests for workflow_events helper module."""

import pytest
from services.api.app.services.job_events import (
    JobEvent,
    JobEventType,
    get_job_event_bus,
    reset_job_event_bus,
)
from services.api.app.services.workflow_events import (
    CAD_STAGE_LABELS,
    publish_artifact_generated,
    publish_workflow_stage,
)


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_job_event_bus()
    yield
    reset_job_event_bus()


def test_publish_workflow_stage_emits_both_events():
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    publish_workflow_stage(bus, "job1", "d1", 1, "generating_spec", "生成飞机参数", progress=10)

    types = [e.type for e in collected]
    assert JobEventType.WORKFLOW_STAGE in types
    assert JobEventType.PROGRESS in types

    ws = [e for e in collected if e.type == JobEventType.WORKFLOW_STAGE][0]
    assert ws.stage == "generating_spec"
    assert ws.label == "生成飞机参数"
    assert ws.progress == 10


def test_publish_workflow_stage_without_progress_only_emits_workflow_stage():
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    publish_workflow_stage(bus, "job1", "d1", 1, "some_stage", "Some Stage")

    types = [e.type for e in collected]
    assert types == [JobEventType.WORKFLOW_STAGE]


def test_publish_workflow_stage_includes_metadata():
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    publish_workflow_stage(bus, "job1", "d1", 1, "s1", "l1", progress=50, metadata={"key": "val"})

    ws = [e for e in collected if e.type == JobEventType.WORKFLOW_STAGE][0]
    assert ws.metadata == {"key": "val"}


def test_publish_artifact_generated_emits_event():
    bus = get_job_event_bus()
    collected: list[JobEvent] = []
    bus.subscribe(collected.append)

    publish_artifact_generated(bus, "job1", "d1", 1, "glb", "/path/to/aircraft.glb")

    assert len(collected) == 1
    event = collected[0]
    assert event.type == JobEventType.ARTIFACT_GENERATED
    assert event.metadata["artifact_key"] == "glb"
    assert event.metadata["artifact_path"] == "/path/to/aircraft.glb"


def test_cad_stage_labels_has_expected_entries():
    assert "fuselage_created" in CAD_STAGE_LABELS
    assert "wing_created" in CAD_STAGE_LABELS
    assert "preview_ready" in CAD_STAGE_LABELS
    assert len(CAD_STAGE_LABELS) == 8
