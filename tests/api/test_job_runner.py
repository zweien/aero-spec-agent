import json
from pathlib import Path

import pytest

from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


def test_sync_generate_returns_succeeded_not_ready(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "succeeded"


def test_job_runner_creates_version_files(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "succeeded"
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

    assert first_job.status == "succeeded"
    assert first_job.version_no == 1
    assert second_job.status == "succeeded"
    assert second_job.version_no == 2
    assert (tmp_path / "storage/designs/demo/versions/1/aircraft_spec.yaml").exists()
    assert (tmp_path / "storage/designs/demo/versions/2/aircraft_spec.yaml").exists()


def test_job_runner_enqueue_persists_queued_job(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.enqueue_generate(design_id="demo", spec=spec)

    assert job.status == "queued"
    assert job.progress == 0
    job_path = tmp_path / "storage/jobs" / f"{job.id}.json"
    assert job_path.exists()

    reloaded = JobRunner(store=store, backend=FakeCadBackend()).get(job.id)
    assert reloaded is not None
    assert reloaded.status == "queued"
    assert reloaded.version_no == job.version_no


def test_job_runner_run_queued_job_succeeds_and_persists(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    job = runner.enqueue_generate(design_id="demo", spec=spec)

    runner.run_queued_job(job.id, spec)

    finished = JobRunner(store=store, backend=FakeCadBackend()).get(job.id)
    assert finished is not None
    assert finished.status == "succeeded"
    assert finished.progress == 100
    assert (tmp_path / "storage/designs/demo/versions/1/validation_report.json").exists()


def test_enqueue_generate_sets_timestamps(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.enqueue_generate(design_id="demo", spec=spec)

    assert job.created_at
    assert job.updated_at
    assert job.duration is None
    assert job.version_status == "pending"


def test_failed_async_job_is_not_listed_as_usable_version(tmp_path: Path):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad failed")

    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)
    runner = JobRunner(store=store, backend=FailingBackend())
    job = runner.enqueue_generate(design_id="demo", spec=spec)

    runner.run_queued_job(job.id, spec)

    failed = runner.get(job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert store.list_versions("demo") == [{"version_no": 1}]


def test_successful_job_writes_succeeded_version_status(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    job = runner.generate(design_id="demo", spec=spec)

    status_path = tmp_path / "storage/designs/demo/versions/1/version_status.json"
    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["status"] == "succeeded"
    assert data["job_id"] == job.id
    assert store.read_version_status("demo", 1) == "succeeded"


def test_failed_job_writes_failed_version_status(tmp_path: Path):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad failed")

    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)
    runner = JobRunner(store=store, backend=FailingBackend())

    job = runner.enqueue_generate(design_id="demo", spec=spec)
    runner.run_queued_job(job.id, spec)

    status_path = tmp_path / "storage/designs/demo/versions/2/version_status.json"
    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["status"] == "failed"
    assert store.read_version_status("demo", 2) == "failed"


def test_list_versions_excludes_failed_and_pending(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    # Version 1: succeeded
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    # Version 2: failed
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("fail")

    runner_fail = JobRunner(store=store, backend=FailingBackend())
    job = runner_fail.enqueue_generate(design_id="demo", spec=spec)
    runner_fail.run_queued_job(job.id, spec)

    # Version 3: succeeded
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    versions = store.list_versions("demo")
    version_nos = [v["version_no"] for v in versions]
    assert version_nos == [1, 3]


def test_list_versions_includes_legacy_dirs_without_version_status(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    versions_root = tmp_path / "storage/designs/demo/versions"
    versions_root.mkdir(parents=True)

    # Legacy version dir: no version_status.json, no validation_report.json
    (versions_root / "1").mkdir()
    # Legacy version dir: no version_status.json, has validation_report.json
    v2 = versions_root / "2"
    v2.mkdir()
    (v2 / "validation_report.json").write_text("{}", encoding="utf-8")

    versions = store.list_versions("demo")
    version_nos = [v["version_no"] for v in versions]
    assert version_nos == [1, 2]
    store = VersionStore(root=tmp_path / "storage")

    version_no, path = store.create_version_dir("demo")

    status_path = path / "version_status.json"
    assert status_path.exists()
    data = json.loads(status_path.read_text())
    assert data["status"] == "pending"
    assert data["job_id"] is None
    assert store.read_version_status("demo", version_no) == "pending"
