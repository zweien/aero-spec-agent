import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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


def test_concurrent_mixed_success_failure_isolation(tmp_path: Path):
    """6 concurrent jobs: 4 succeed, 2 fail. Verify isolation."""
    store = VersionStore(root=tmp_path / "storage")
    spec = load_aircraft_spec(EXAMPLE)

    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("intentional failure")

    results: list[tuple[str, int, str]] = []  # (job_id, version_no, status)
    lock = threading.Lock()

    def run_job(backend: FakeCadBackend) -> None:
        runner = JobRunner(store=store, backend=backend)
        job = runner.enqueue_generate(design_id="demo", spec=spec)
        runner.run_queued_job(job.id, spec)
        finished = runner.get(job.id)
        assert finished is not None
        with lock:
            results.append((finished.id, finished.version_no, finished.status))

    backends = (
        [FakeCadBackend()] * 4 + [FailingBackend()] * 2
    )

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(run_job, be) for be in backends]
        for f in as_completed(futures):
            f.result()  # raise if any thread failed

    assert len(results) == 6
    version_nos = sorted(r[1] for r in results)
    assert version_nos == list(range(1, 7))
    assert len(set(r[1] for r in results)) == 6  # all unique

    succeeded = [r for r in results if r[2] == "succeeded"]
    failed = [r for r in results if r[2] == "failed"]
    assert len(succeeded) == 4
    assert len(failed) == 2

    # list_versions only shows succeeded
    versions = store.list_versions("demo")
    succeeded_nos = sorted(r[1] for r in succeeded)
    assert [v["version_no"] for v in versions] == succeeded_nos

    # failed versions have diagnostics
    for job_id, vno, status in failed:
        raw = store.version_status.read_raw("demo", vno)
        assert raw is not None
        assert raw["status"] == "failed"
        assert raw["error_message"] == "intentional failure"
