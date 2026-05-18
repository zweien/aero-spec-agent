import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from services.api.app.services.design_controller import DesignControllerService
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend


def _load_spec():
    from pathlib import Path
    return load_aircraft_spec(
        Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")
    )


def _spec_to_dict(spec):
    return json.loads(spec.model_dump_json())


def test_compare_dispatches_three_variants(tmp_path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = _load_spec()
    base = _spec_to_dict(spec)

    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    job = controller.compare_variants(
        design_id="demo",
        base_spec=base,
        variants=[
            {"label": "12m", "changes": [{"path": "wing.span.value", "value": 12}]},
            {"label": "15m", "changes": [{"path": "wing.span.value", "value": 15}]},
            {"label": "18m", "changes": [{"path": "wing.span.value", "value": 18}]},
        ],
        job_runner=runner,
        version_store=store,
    )

    assert job.status == "running"
    assert len(job.variants) == 3
    assert job.variants[0]["label"] == "12m"
    assert job.variants[1]["label"] == "15m"
    assert job.variants[2]["label"] == "18m"
    version_nos = [v["version_no"] for v in job.variants]
    assert len(set(version_nos)) == 3


def test_compare_unique_version_numbers(tmp_path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = _load_spec()
    base = _spec_to_dict(spec)

    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    job = controller.compare_variants(
        design_id="demo",
        base_spec=base,
        variants=[
            {"label": "a", "changes": [{"path": "wing.span.value", "value": 10}]},
            {"label": "b", "changes": [{"path": "wing.span.value", "value": 11}]},
        ],
        job_runner=runner,
        version_store=store,
    )

    version_nos = [v["version_no"] for v in job.variants]
    assert version_nos[0] != version_nos[1]


def test_aggregate_after_completion(tmp_path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = _load_spec()
    base = _spec_to_dict(spec)

    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    job = controller.compare_variants(
        design_id="demo",
        base_spec=base,
        variants=[
            {"label": "v1", "changes": [{"path": "wing.span.value", "value": 12}]},
            {"label": "v2", "changes": [{"path": "wing.span.value", "value": 15}]},
        ],
        job_runner=runner,
        version_store=store,
    )

    # Run the queued jobs
    for variant in job.variants:
        runner.run_queued_job(variant["job_id"], spec)

    # Aggregate results
    result = controller.aggregate(job.id, runner)
    assert result is not None
    assert result.status == "completed"
    assert len(result.results) == 2
    for r in result.results:
        assert r["status"] == "succeeded"


def test_aggregate_handles_failed_variant(tmp_path):
    class FailingBackend(FakeCadBackend):
        def generate(self, spec, output_dir):
            raise RuntimeError("cad failed")

    store = VersionStore(root=tmp_path / "storage")
    runner_ok = JobRunner(store=store, backend=FakeCadBackend())
    runner_fail = JobRunner(store=store, backend=FailingBackend())
    spec = _load_spec()
    base = _spec_to_dict(spec)

    # Create a succeeded version first
    runner_ok.generate(design_id="demo", spec=spec)

    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    job = controller.compare_variants(
        design_id="demo",
        base_spec=base,
        variants=[
            {"label": "ok", "changes": [{"path": "wing.span.value", "value": 12}]},
            {"label": "fail", "changes": [{"path": "wing.span.value", "value": 99}]},
        ],
        job_runner=runner_fail,
        version_store=store,
    )

    # Run the queued jobs (will fail with FailingBackend)
    for variant in job.variants:
        runner_fail.run_queued_job(variant["job_id"], spec)

    result = controller.aggregate(job.id, runner_fail)
    assert result is not None
    assert result.status == "completed"
    failed_results = [r for r in result.results if r["status"] == "failed"]
    assert len(failed_results) == 2


def test_get_returns_none_for_missing_job(tmp_path):
    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    assert controller.get("nonexistent") is None


def test_aggregate_returns_none_for_missing_job(tmp_path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    assert controller.aggregate("nonexistent", runner) is None


def test_compare_persists_controller_job(tmp_path):
    store = VersionStore(root=tmp_path / "storage")
    runner = JobRunner(store=store, backend=FakeCadBackend())
    spec = _load_spec()
    base = _spec_to_dict(spec)

    controller = DesignControllerService(storage_root=tmp_path / "ctrl")
    job = controller.compare_variants(
        design_id="demo",
        base_spec=base,
        variants=[
            {"label": "a", "changes": [{"path": "wing.span.value", "value": 12}]},
        ],
        job_runner=runner,
        version_store=store,
    )

    reloaded = controller.get(job.id)
    assert reloaded is not None
    assert reloaded.id == job.id
    assert reloaded.design_id == "demo"
