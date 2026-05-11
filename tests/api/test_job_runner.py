from pathlib import Path

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
