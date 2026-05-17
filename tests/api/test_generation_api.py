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


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200
    return response.json()


def test_generate_endpoint_returns_accepted_job(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")

    response = client.post("/api/designs/demo/generate", content=spec_text)

    assert response.status_code == 202
    data = response.json()
    assert data["id"]
    assert data["status"] == "queued"
    assert data["version_no"] >= 1
    assert data["progress"] == 0
    finished = _wait_for_job(client, data["id"])
    assert finished["status"] == "succeeded"
    assert finished["progress"] == 100
    assert finished["version_no"] == data["version_no"]


def test_version_endpoint_returns_files(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-api/generate", content=spec_text).json()
    _wait_for_job(client, job["id"])

    response = client.get(f"/api/designs/demo-api/versions/{job['version_no']}")

    assert response.status_code == 200
    assert "aircraft_spec.yaml" in response.json()["files"]
    assert response.json()["validation_report"]["engine.count"]["status"] == "pass"


def test_version_file_endpoint_returns_generated_artifact(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-file/generate", content=spec_text).json()
    _wait_for_job(client, job["id"])

    response = client.get(f"/api/designs/demo-file/versions/{job['version_no']}/files/aircraft.vsp3")

    assert response.status_code == 200
    assert response.text.startswith("fake vsp3 for twin_engine_uav")


def test_version_file_endpoint_rejects_path_traversal(client: TestClient):
    response = client.get("/api/designs/demo-file/versions/1/files/..%2F..%2F.env")

    assert response.status_code == 400


def test_patch_spec_endpoint_returns_accepted_job_and_new_version(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    first_job = client.post("/api/designs/demo-patch/generate", content=spec_text).json()
    _wait_for_job(client, first_job["id"])

    response = client.patch(
        "/api/designs/demo-patch/spec",
        json={"changes": [{"path": "fuselage.length.value", "value": 8.0}]},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["id"]
    assert data["status"] == "queued"
    assert data["version_no"] == first_job["version_no"] + 1

    finished = _wait_for_job(client, data["id"])
    assert finished["status"] == "succeeded"
    assert finished["progress"] == 100
    assert finished["version_no"] == data["version_no"]

    version_response = client.get(f"/api/designs/demo-patch/versions/{data['version_no']}")
    assert version_response.status_code == 200
    spec_echo = version_response.json()["validation_report"]["spec_echo"]
    assert spec_echo["fuselage"]["length"]["value"] == 8.0


def test_failed_backend_job_is_queryable_but_not_listed_as_usable_version(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad failed")

    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    first_job = client.post("/api/designs/demo-failed/generate", content=spec_text).json()
    _wait_for_job(client, first_job["id"])

    failing_runner = JobRunner(
        store=designs_router.runner.store,
        backend=FailingBackend(),
    )
    monkeypatch.setattr(designs_router, "runner", failing_runner)

    response = client.post("/api/designs/demo-failed/generate", content=spec_text)

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "queued"
    assert data["version_no"] == first_job["version_no"] + 1

    failed = _wait_for_job(client, data["id"])
    assert failed["status"] == "failed"
    assert failed["error_message"] == "cad failed"

    versions_response = client.get("/api/designs/demo-failed/versions")
    assert versions_response.status_code == 200
    assert versions_response.json() == [{"version_no": first_job["version_no"]}]


def test_version_file_endpoint_returns_404_for_missing_file(client: TestClient):
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-missing-file/generate", content=spec_text).json()
    _wait_for_job(client, job["id"])

    response = client.get(f"/api/designs/demo-missing-file/versions/{job['version_no']}/files/missing.glb")

    assert response.status_code == 404


def test_cors_allows_configured_local_web_origin(client: TestClient):
    response = client.options(
        "/api/designs/demo/generate",
        headers={
            "Origin": "http://127.0.0.1:3900",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:3900"
