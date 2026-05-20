"""Tests for FAKE_CAD_STEP_DELAY_MS slow-progress mode."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


def _spec() -> object:
    return load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))


def test_slow_progress_stages_order(tmp_path: Path):
    """With FAKE_CAD_STEP_DELAY_MS set, stages still arrive in order."""
    stages: list[str] = []

    def capture(stage: str, progress: int) -> None:
        stages.append(stage)

    backend = FakeCadBackend()
    with patch.dict(os.environ, {"FAKE_CAD_STEP_DELAY_MS": "10"}):
        backend.generate(_spec(), tmp_path / "out", on_progress=capture)

    assert stages == [
        "fuselage_created",
        "wing_created",
        "tail_created",
        "engine_created",
        "vsp_model_saved",
        "step_exported",
        "glb_exported",
        "preview_ready",
    ]


def test_slow_progress_monotonic(tmp_path: Path):
    """Progress values are strictly non-decreasing."""
    progresses: list[int] = []

    def capture(_stage: str, progress: int) -> None:
        progresses.append(progress)

    backend = FakeCadBackend()
    with patch.dict(os.environ, {"FAKE_CAD_STEP_DELAY_MS": "10"}):
        backend.generate(_spec(), tmp_path / "out", on_progress=capture)

    for i in range(1, len(progresses)):
        assert progresses[i] >= progresses[i - 1], f"regression at index {i}: {progresses}"


def test_slow_progress_no_delay_by_default(tmp_path: Path):
    """Default (FAKE_CAD_STEP_DELAY_MS=0) completes fast — no unnecessary sleeps."""
    import time

    backend = FakeCadBackend()
    t0 = time.monotonic()
    backend.generate(_spec(), tmp_path / "out", on_progress=lambda s, p: None)
    elapsed = time.monotonic() - t0
    assert elapsed < 1.0, f"unexpectedly slow with default delay: {elapsed:.2f}s"


def test_slow_progress_artifacts_still_created(tmp_path: Path):
    """Artifacts are still created correctly with delay enabled."""
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = _spec()

    with patch.dict(os.environ, {"FAKE_CAD_STEP_DELAY_MS": "20"}):
        job = runner.generate(design_id="slow-test", spec=spec)

    assert job.status == "succeeded"
    assert job.version_no == 1
    vdir = tmp_path / "storage/designs/slow-test/versions/1"
    assert (vdir / "aircraft_spec.yaml").exists()
    assert (vdir / "aircraft.vsp3").exists()
    assert (vdir / "aircraft.glb").exists()
    assert (vdir / "validation_report.json").exists()


def test_slow_progress_with_job_events(tmp_path: Path):
    """JobRunner with slow backend emits all workflow_stage events via EventBus."""
    from services.api.app.services.job_events import JobEventType, get_job_event_bus

    bus = get_job_event_bus()
    events: list[object] = []
    bus.subscribe(events.append)

    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = _spec()

    with patch.dict(os.environ, {"FAKE_CAD_STEP_DELAY_MS": "20"}):
        job = runner.generate(design_id="slow-stream", spec=spec)

    bus.unsubscribe(events.append)
    assert job.status == "succeeded"

    stage_events = [e for e in events if getattr(e, "type", None) == JobEventType.WORKFLOW_STAGE]
    # 2 pre-CAD stages + 8 CAD sub-stages = 10
    assert len(stage_events) >= 10, f"expected >= 10 stage events, got {len(stage_events)}"

    progress_values = [e.progress for e in stage_events]
    for i in range(1, len(progress_values)):
        assert progress_values[i] >= progress_values[i - 1]

    completed = [e for e in events if getattr(e, "type", None) == JobEventType.COMPLETED]
    assert len(completed) == 1
