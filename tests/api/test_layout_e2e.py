"""End-to-end tests for all new layout types through the full API pipeline."""

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


def _generate_and_wait(client: TestClient, design_id: str, yaml_path: str) -> dict:
    spec_text = Path(yaml_path).read_text(encoding="utf-8")
    response = client.post(f"/api/designs/{design_id}/generate", content=spec_text)
    assert response.status_code == 202, f"Generate failed: {response.text}"
    job = response.json()
    assert job["status"] == "queued"

    # Poll until done
    import time
    for _ in range(20):
        poll = client.get(f"/api/jobs/{job['id']}").json()
        if poll["status"] in ("succeeded", "failed"):
            break
        time.sleep(0.05)

    assert poll["status"] == "succeeded", f"Job failed: {poll.get('error', 'unknown')}"
    return poll


def _get_version(client: TestClient, design_id: str, version_no: int) -> dict:
    response = client.get(f"/api/designs/{design_id}/versions/{version_no}")
    assert response.status_code == 200
    return response.json()


# ─── V-tail conventional layout ───


def test_v_tail_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "vtail-e2e", "packages/aircraft-schema/examples/v_tail_single_uav.yaml")
    version = _get_version(client, "vtail-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.vsp3" in version["files"]
    assert "aircraft.glb" in version["files"]

    # Verify design metrics present
    dm = version["validation_report"]["design_metrics"]
    assert dm["wingspan_m"] == 8.0
    assert dm["fuselage_length_m"] == 4.5

    # Verify generation log exists and has components
    log_response = client.get(f"/api/designs/vtail-e2e/versions/{job['version_no']}/files/generation_log.json")
    assert log_response.status_code == 200
    log = json.loads(log_response.text)
    assert "components" in log
    assert "applied_parameters" in log


# ─── Twin boom layout ───


def test_twin_boom_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "twinboom-e2e", "packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml")
    version = _get_version(client, "twinboom-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    dm = version["validation_report"]["design_metrics"]
    assert dm["wingspan_m"] == 12.0
    assert dm["fuselage_length_m"] == 3.0

    # Verify spec stored has layout=twin_boom
    spec_response = client.get(f"/api/designs/twinboom-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "twin_boom" in spec_response.text


# ─── Flying wing layout ───


def test_flying_wing_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "flywing-e2e", "packages/aircraft-schema/examples/flying_wing_uav.yaml")
    version = _get_version(client, "flywing-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    dm = version["validation_report"]["design_metrics"]
    assert dm["wingspan_m"] == 6.0
    assert dm["fuselage_length_m"] == 3.0

    spec_response = client.get(f"/api/designs/flywing-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "flying_wing" in spec_response.text


# ─── BWB layout ───


def test_bwb_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "bwb-e2e", "packages/aircraft-schema/examples/bwb_uav.yaml")
    version = _get_version(client, "bwb-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    dm = version["validation_report"]["design_metrics"]
    assert dm["wingspan_m"] == 8.0
    assert dm["fuselage_length_m"] == 4.0

    spec_response = client.get(f"/api/designs/bwb-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "blended_wing_body" in spec_response.text
    # Body fields should be present
    assert "body:" in spec_response.text
    assert "width" in spec_response.text


# ─── Canard layout ───


def test_canard_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "canard-e2e", "packages/aircraft-schema/examples/canard_uav.yaml")
    version = _get_version(client, "canard-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/canard-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "canard" in spec_response.text
    assert "canard:" in spec_response.text


# ─── Three-surface layout ───


def test_three_surface_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "3surf-e2e", "packages/aircraft-schema/examples/three_surface_uav.yaml")
    version = _get_version(client, "3surf-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/3surf-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "three_surface" in spec_response.text


# ─── Tandem wing layout ───


def test_tandem_wing_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "tandem-e2e", "packages/aircraft-schema/examples/tandem_wing_uav.yaml")
    version = _get_version(client, "tandem-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/tandem-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "tandem_wing" in spec_response.text


# ─── Biplane layout ───


def test_biplane_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "biplane-e2e", "packages/aircraft-schema/examples/biplane_uav.yaml")
    version = _get_version(client, "biplane-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/biplane-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "biplane" in spec_response.text


# ─── Joined wing layout ───


def test_joined_wing_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "joined-e2e", "packages/aircraft-schema/examples/joined_wing_uav.yaml")
    version = _get_version(client, "joined-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/joined-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "joined_wing" in spec_response.text


# ─── Box wing layout ───


def test_box_wing_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "boxwing-e2e", "packages/aircraft-schema/examples/box_wing_uav.yaml")
    version = _get_version(client, "boxwing-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/boxwing-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "box_wing" in spec_response.text


# ─── Multi-fuselage layout ───


def test_multi_fuselage_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "mfuse-e2e", "packages/aircraft-schema/examples/multi_fuselage_uav.yaml")
    version = _get_version(client, "mfuse-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/mfuse-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "multi_fuselage" in spec_response.text


# ─── Delta wing planform ───


def test_delta_wing_full_pipeline(client: TestClient):
    job = _generate_and_wait(client, "delta-e2e", "packages/aircraft-schema/examples/delta_wing_uav.yaml")
    version = _get_version(client, "delta-e2e", job["version_no"])

    assert "aircraft_spec.yaml" in version["files"]
    assert "aircraft.glb" in version["files"]

    spec_response = client.get(f"/api/designs/delta-e2e/versions/{job['version_no']}/files/aircraft_spec.yaml")
    assert spec_response.status_code == 200
    assert "delta" in spec_response.text


# ─── Multi-version generation ───


def test_multiple_layouts_same_design(client: TestClient):
    """Generate conventional then flying_wing for same design_id — versions increment."""
    # Version 1: conventional
    job1 = _generate_and_wait(client, "multi-layout", "packages/aircraft-schema/examples/twin_engine_uav.yaml")
    assert job1["version_no"] == 1

    # Version 2: flying wing
    job2 = _generate_and_wait(client, "multi-layout", "packages/aircraft-schema/examples/flying_wing_uav.yaml")
    assert job2["version_no"] == 2

    # Both versions accessible
    v1 = _get_version(client, "multi-layout", 1)
    v2 = _get_version(client, "multi-layout", 2)

    # Fetch actual spec files to verify layout
    spec1 = client.get(f"/api/designs/multi-layout/versions/1/files/aircraft_spec.yaml").text
    spec2 = client.get(f"/api/designs/multi-layout/versions/2/files/aircraft_spec.yaml").text
    assert "conventional" in spec1
    assert "flying_wing" in spec2


# ─── Version listing ───


def test_version_list_includes_all_layouts(client: TestClient):
    """Generate multiple versions and verify list endpoint returns them all."""
    _generate_and_wait(client, "list-test", "packages/aircraft-schema/examples/v_tail_single_uav.yaml")
    _generate_and_wait(client, "list-test", "packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml")
    _generate_and_wait(client, "list-test", "packages/aircraft-schema/examples/bwb_uav.yaml")

    response = client.get("/api/designs/list-test/versions")
    assert response.status_code == 200
    versions = response.json()  # returns a list directly
    assert len(versions) == 3
