from pathlib import Path

import pytest

from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend

EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def test_succeeded_job_version_status_consistency(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = load_aircraft_spec(EXAMPLE)

    job = runner.generate(design_id="demo", spec=spec)

    assert job.status == "succeeded"
    assert store.version_status.read("demo", job.version_no) == "succeeded"
    assert job.version_status == "succeeded"
    assert store.list_versions("demo") == [{"version_no": 1}]


def test_failed_job_version_status_consistency(tmp_path: Path):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("boom")

    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(EXAMPLE)
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    runner = JobRunner(store=store, backend=FailingBackend())
    job = runner.enqueue_generate(design_id="demo", spec=spec)
    runner.run_queued_job(job.id, spec)

    failed = runner.get(job.id)
    assert failed is not None
    assert failed.status == "failed"
    assert store.version_status.read("demo", 2) == "failed"
    assert failed.version_status == "failed"
    assert store.list_versions("demo") == [{"version_no": 1}]


def test_pending_version_not_in_list_versions(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    store.create_version_dir("demo")

    assert store.list_versions("demo") == []


def test_mixed_statuses_list_versions_only_succeeded(tmp_path: Path):
    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(EXAMPLE)

    # v1: succeeded
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)
    # v2: pending (just create dir)
    store.create_version_dir("demo")
    # v3: failed
    class Fail(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("x")
    runner = JobRunner(store=store, backend=Fail())
    job = runner.enqueue_generate(design_id="demo", spec=spec)
    runner.run_queued_job(job.id, spec)
    # v4: succeeded
    JobRunner(store=store, backend=FakeCadBackend()).generate(design_id="demo", spec=spec)

    assert store.list_versions("demo") == [{"version_no": 1}, {"version_no": 4}]
