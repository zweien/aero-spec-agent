from pathlib import Path

from fastapi.testclient import TestClient

from services.api.app.main import app


def test_generate_endpoint_returns_ready_job():
    client = TestClient(app)
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")

    response = client.post("/api/designs/demo/generate", content=spec_text)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["version_no"] >= 1
    assert data["progress"] == 100


def test_version_endpoint_returns_files():
    client = TestClient(app)
    spec_text = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml").read_text(encoding="utf-8")
    job = client.post("/api/designs/demo-api/generate", content=spec_text).json()

    response = client.get(f"/api/designs/demo-api/versions/{job['version_no']}")

    assert response.status_code == 200
    assert "aircraft_spec.yaml" in response.json()["files"]
    assert response.json()["validation_report"]["engine.count"]["status"] == "pass"
