from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api.app.main import app
import services.api.app.routers.designs as designs_router
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    isolated_runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )
    monkeypatch.setattr(designs_router, "runner", isolated_runner)
    return TestClient(app)


def _wait_for_job(client: TestClient, job_id: str) -> dict:
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    return resp.json()


def _generate(client: TestClient, design_id: str = "test") -> dict:
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post(f"/api/designs/{design_id}/generate", content=spec_text).json()
    _wait_for_job(client, job["id"])
    return job


def test_diagnostics_returns_all_fields_for_succeeded_job(client: TestClient):
    job = _generate(client, "diag-ok")

    resp = client.get(f"/api/jobs/{job['id']}/diagnostics")

    assert resp.status_code == 200
    data = resp.json()
    assert data["job"]["id"] == job["id"]
    assert data["job"]["status"] == "succeeded"
    assert data["version_status"]["status"] == "succeeded"
    assert data["validation_report"] is not None
    assert isinstance(data["files_exist"], dict)
    assert data["files_exist"]["aircraft_spec.yaml"] is True
    assert data["files_exist"]["aircraft.vsp3"] is True
    assert data["files_exist"]["generation_log.json"] is True


def test_diagnostics_for_failed_job_shows_error(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    _generate(client, "diag-fail")

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad exploded")

    monkeypatch.setattr(
        designs_router,
        "runner",
        JobRunner(store=designs_router.runner.store, backend=FailingBackend()),
    )

    job = client.post("/api/designs/diag-fail/generate", content=Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text()).json()
    _wait_for_job(client, job["id"])

    resp = client.get(f"/api/jobs/{job['id']}/diagnostics")

    assert resp.status_code == 200
    data = resp.json()
    assert data["job"]["status"] == "failed"
    assert data["version_status"]["status"] == "failed"
    assert data["job"]["error_message"] is not None
    assert "cad exploded" in data["job"]["error_message"]


def test_diagnostics_returns_404_for_missing_job(client: TestClient):
    resp = client.get("/api/jobs/nonexistent-id/diagnostics")
    assert resp.status_code == 404


def test_diagnostics_files_exist_reflects_actual_state(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    job = _generate(client, "diag-files")

    resp = client.get(f"/api/jobs/{job['id']}/diagnostics")
    data = resp.json()

    expected_true = ["aircraft_spec.yaml", "aircraft.vsp3", "validation_report.json", "generation_log.json"]
    for name in expected_true:
        assert data["files_exist"][name] is True

    # .step file may or may not exist with fake backend, just check it's a boolean
    assert isinstance(data["files_exist"].get("aircraft.step", False), bool)
    assert isinstance(data["files_exist"].get("aircraft.glb", False), bool)
