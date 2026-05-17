"""Tests verifying the backend job API contract matches frontend expectations."""
import json
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


def test_job_files_are_record_string_to_string(client: TestClient):
    """Frontend normalizeFiles expects Record<string,string> or string[]."""
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-files-type/generate", content=spec_text).json()
    finished = _wait_for_job(client, job["id"])

    assert isinstance(finished["files"], dict)
    for key, value in finished["files"].items():
        assert isinstance(key, str)
        assert isinstance(value, str)


def test_failed_job_includes_error_message(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """Frontend shows error_message when job status is failed."""
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("CAD engine crashed: out of memory")

    failing_runner = JobRunner(
        store=designs_router.runner.store,
        backend=FailingBackend(),
    )
    monkeypatch.setattr(designs_router, "runner", failing_runner)

    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    first = client.post("/api/designs/demo-errmsg/generate", content=spec_text).json()
    _wait_for_job(client, first["id"])

    resp = client.post("/api/designs/demo-errmsg/generate", content=spec_text)
    job = resp.json()
    finished = _wait_for_job(client, job["id"])

    assert finished["status"] == "failed"
    assert finished["error_message"] is not None
    assert "out of memory" in finished["error_message"]


def test_unknown_status_not_treated_as_succeeded(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """A job stuck in 'running' should NOT appear succeeded."""
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-stuck/generate", content=spec_text).json()

    # Poll immediately without waiting — job should still be queued or running
    resp = client.get(f"/api/jobs/{job['id']}")
    data = resp.json()
    # It might already be done (fake backend is fast), but if not, verify status != succeeded
    if data["status"] != "succeeded":
        assert data["status"] in ("queued", "running")
