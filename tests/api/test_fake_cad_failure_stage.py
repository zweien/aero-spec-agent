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


def test_fake_cad_fail_stage_marks_failed_workflow_stage(tmp_path: Path):
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )

    with patch.dict(os.environ, {"FAKE_CAD_FAIL_STAGE": "glb_exported"}):
        job = runner.generate(
            design_id="fake-failure-stage",
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
    assert "glb_exported" in failed_stages[0].get("error_message", "")


def test_fake_cad_fail_stage_replays_failed_stage_before_generation_failed(tmp_path: Path, monkeypatch):
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )
    monkeypatch.setattr("services.api.app.routers.designs.runner", runner)

    with patch.dict(os.environ, {"FAKE_CAD_FAIL_STAGE": "glb_exported"}):
        job = runner.generate(
            design_id="fake-failure-stream",
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
    assert "glb_exported" in failed_stage_events[0]["data"].get("error_message", "")
    assert types.index("workflow_stage") < types.index("generation_failed")
