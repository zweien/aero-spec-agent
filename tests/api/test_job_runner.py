from pathlib import Path

import pytest

from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


def test_job_runner_creates_version_files(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "ready"
    assert job.version_no == 1
    assert (tmp_path / "storage/designs/demo/versions/1/aircraft_spec.yaml").exists()
    assert (tmp_path / "storage/designs/demo/versions/1/validation_report.json").exists()


def test_job_runner_preserves_falsy_backend_injection(tmp_path: Path):
    class FalsyBackend(FakeCadBackend):
        def __bool__(self) -> bool:
            return False

    backend = FalsyBackend()
    runner = JobRunner(store=VersionStore(root=tmp_path / "storage"), backend=backend)

    assert runner.backend is backend


@pytest.mark.parametrize("design_id", ["../escape", "/tmp/escape", ".", ""])
def test_version_store_rejects_invalid_design_id(tmp_path: Path, design_id: str):
    store = VersionStore(root=tmp_path / "storage")

    with pytest.raises(ValueError):
        store.version_dir(design_id, 1)

    assert not (tmp_path / "escape").exists()


def test_job_runner_creates_incrementing_versions(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    first_job = runner.generate(design_id="demo", spec=spec)
    second_job = runner.generate(design_id="demo", spec=spec)

    assert first_job.status == "ready"
    assert first_job.version_no == 1
    assert second_job.status == "ready"
    assert second_job.version_no == 2
    assert (tmp_path / "storage/designs/demo/versions/1/aircraft_spec.yaml").exists()
    assert (tmp_path / "storage/designs/demo/versions/2/aircraft_spec.yaml").exists()
