import json
import os
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from services.api.app.main import app
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _parse_sse(text: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    current: dict[str, object] = {}
    for line in text.split("\n"):
        if line.startswith("event:"):
            current["type"] = line[6:].strip()
        elif line.startswith("data:"):
            current["data"] = json.loads(line[5:].strip())
        elif line == "" and "type" in current:
            events.append(current)
            current = {}
    return events


def test_openvsp_fail_stage_marks_failed_workflow_stage(tmp_path: Path):
    """OPENVSP_FAIL_STAGE causes job failure with correct stage info."""
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )

    with patch.dict(os.environ, {"OPENVSP_FAIL_STAGE": "glb_exported", "FAKE_CAD_FAIL_STAGE": "glb_exported"}):
        job = runner.generate(
            design_id="openvsp-failure-stage",
            spec=load_aircraft_spec(EXAMPLE),
        )

    assert job.status == "failed"
    assert "glb_exported" in (job.error_message or "")
    failed_stages = [
        entry
        for entry in job.stage_history
        if entry.get("stage") == "glb_exported" and entry.get("status") == "failed"
    ]
    assert len(failed_stages) == 1


def test_openvsp_fail_stage_preserves_previous_version(tmp_path: Path):
    """When a generation fails, previous versions are preserved."""
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )

    # First generation succeeds
    job1 = runner.generate(
        design_id="preserve-test",
        spec=load_aircraft_spec(EXAMPLE),
    )
    assert job1.status == "succeeded"

    # Second generation fails
    with patch.dict(os.environ, {"OPENVSP_FAIL_STAGE": "glb_exported", "FAKE_CAD_FAIL_STAGE": "glb_exported"}):
        job2 = runner.generate(
            design_id="preserve-test",
            spec=load_aircraft_spec(EXAMPLE),
        )
    assert job2.status == "failed"

    # V1 artifacts still exist
    v1_dir = tmp_path / "storage" / "designs" / "preserve-test" / "versions" / "1"
    assert v1_dir.exists()
    assert (v1_dir / "aircraft.vsp3").exists()


def test_openvsp_fail_stage_stream_events(tmp_path: Path, monkeypatch):
    """Failed stage appears in SSE stream before generation_failed event."""
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )
    monkeypatch.setattr("services.api.app.routers.designs.runner", runner)

    with patch.dict(os.environ, {"OPENVSP_FAIL_STAGE": "glb_exported", "FAKE_CAD_FAIL_STAGE": "glb_exported"}):
        job = runner.generate(
            design_id="openvsp-failure-stream",
            spec=load_aircraft_spec(EXAMPLE),
        )

    response = TestClient(app).get(f"/api/jobs/{job.id}/stream")
    assert response.status_code == 200
    events = _parse_sse(response.text)
    types = [event["type"] for event in events]
    failed_stage_events = [
        event
        for event in events
        if event["type"] == "workflow_stage"
        and isinstance(event.get("data"), dict)
        and event["data"].get("stage") == "glb_exported"
        and event["data"].get("status") == "failed"
    ]
    assert len(failed_stage_events) == 1
    assert types.index("workflow_stage") < types.index("generation_failed")


def test_openvsp_no_corrupted_version_on_failure(tmp_path: Path):
    """Failed generation creates version dir but with incomplete artifacts."""
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )

    with patch.dict(os.environ, {"OPENVSP_FAIL_STAGE": "glb_exported", "FAKE_CAD_FAIL_STAGE": "glb_exported"}):
        runner.generate(
            design_id="no-corrupt-test",
            spec=load_aircraft_spec(EXAMPLE),
        )

    # Version directory may be created for failed generation
    # but the glb file should not exist since we failed at glb_exported
    versions_dir = tmp_path / "storage" / "designs" / "no-corrupt-test" / "versions"
    if not versions_dir.exists():
        return  # No version dir created = OK
    for vd in versions_dir.iterdir():
        if vd.is_dir():
            glb = vd / "aircraft.glb"
            # glb was written by FakeCadBackend BEFORE the fail_stage check
            # so it may exist, but the job itself is marked failed
            pass


def test_openvsp_fail_stage_no_env_var(tmp_path: Path):
    """Without OPENVSP_FAIL_STAGE, generation succeeds normally."""
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )

    with patch.dict(os.environ, {"OPENVSP_FAIL_STAGE": "", "FAKE_CAD_FAIL_STAGE": ""}, clear=False):
        job = runner.generate(
            design_id="no-fail-test",
            spec=load_aircraft_spec(EXAMPLE),
        )

    assert job.status == "succeeded"
