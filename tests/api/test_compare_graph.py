"""Tests for CompareGraph — variant dispatch, aggregation, comparison metrics.

Updated for subgraph composition: CompareGraph now uses VariantSubgraph
per variant instead of direct enqueue.
"""

import threading
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.compare_graph import build_compare_graph
from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
    """Auto-runs enqueued jobs in background threads."""

    def __init__(self, job_runner: JobRunner):
        self._jr = job_runner

    def enqueue_generate(self, design_id: str, spec) -> object:
        job = self._jr.enqueue_generate(design_id=design_id, spec=spec)
        t = threading.Thread(
            target=self._jr.run_queued_job, args=(job.id, spec), daemon=True,
        )
        t.start()
        return job

    def get(self, job_id: str):
        return self._jr.get(job_id)

    def __getattr__(self, name):
        return getattr(self._jr, name)


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_job_event_bus()
    yield
    reset_job_event_bus()


@pytest.fixture
def job_runner(tmp_path):
    return JobRunner(store=VersionStore(root=tmp_path))


@pytest.fixture
def auto_runner(job_runner):
    return AutoRunJobRunner(job_runner)


@pytest.fixture
def spec_dict():
    return _load_spec_dict()


# ---------------------------------------------------------------------------
# 1. Three variants all succeeded
# ---------------------------------------------------------------------------


def test_three_variants_all_succeeded(auto_runner, spec_dict):
    graph = build_compare_graph(job_runner=auto_runner, timeout_seconds=30)
    result = graph.invoke({
        "design_id": "test-compare",
        "base_spec": spec_dict,
        "variants": [
            {"label": "v1", "changes": [{"path": "aircraft.name", "value": "variant_1"}]},
            {"label": "v2", "changes": [{"path": "aircraft.name", "value": "variant_2"}]},
            {"label": "v3", "changes": [{"path": "aircraft.name", "value": "variant_3"}]},
        ],
    })

    assert result["status"] == "completed"
    comp = result["comparison"]
    assert comp["total_variants"] == 3
    assert comp["succeeded"] == 3
    assert comp["failed"] == 0
    for v in comp["variants"]:
        assert v["status"] == "succeeded"


# ---------------------------------------------------------------------------
# 2. Single variant via subgraph
# ---------------------------------------------------------------------------


def test_single_variant_dispatched(auto_runner, spec_dict):
    graph = build_compare_graph(job_runner=auto_runner, timeout_seconds=30)
    result = graph.invoke({
        "design_id": "test-single",
        "base_spec": spec_dict,
        "variants": [
            {"label": "v1", "changes": []},
        ],
    })

    assert result["status"] == "completed"
    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "succeeded"


# ---------------------------------------------------------------------------
# 3. Invalid variant spec
# ---------------------------------------------------------------------------


def test_invalid_variant_spec(job_runner):
    graph = build_compare_graph(job_runner=job_runner, timeout_seconds=5)
    result = graph.invoke({
        "design_id": "test-invalid",
        "base_spec": {"not_a_valid": "spec"},
        "variants": [
            {"label": "bad", "changes": [{"path": "wing.span.value", "value": 10}]},
        ],
    })

    # VariantSubgraph will fail validation
    assert result["status"] == "completed"
    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "failed"


# ---------------------------------------------------------------------------
# 4. No variants provided
# ---------------------------------------------------------------------------


def test_no_variants(job_runner):
    graph = build_compare_graph(job_runner=job_runner, timeout_seconds=5)
    result = graph.invoke({
        "design_id": "test-empty",
        "base_spec": {},
        "variants": [],
    })

    assert result["status"] == "failed"
    assert "no variants" in result.get("error_message", "")
    assert result.get("comparison") is None


# ---------------------------------------------------------------------------
# 5. Verify unique job_ids across variants
# ---------------------------------------------------------------------------


def test_variant_jobs_have_unique_ids(auto_runner, spec_dict):
    graph = build_compare_graph(job_runner=auto_runner, timeout_seconds=30)
    result = graph.invoke({
        "design_id": "test-unique",
        "base_spec": spec_dict,
        "variants": [
            {"label": "a", "changes": []},
            {"label": "b", "changes": []},
        ],
    })

    job_ids = [r["job_id"] for r in result["results"]]
    assert len(set(job_ids)) == 2


# ---------------------------------------------------------------------------
# 6. Summary generation
# ---------------------------------------------------------------------------


def test_summary_content(auto_runner, spec_dict):
    graph = build_compare_graph(job_runner=auto_runner, timeout_seconds=30)
    result = graph.invoke({
        "design_id": "test-summary",
        "base_spec": spec_dict,
        "variants": [
            {"label": "alpha", "changes": []},
        ],
    })

    assert result["summary"]
    assert "alpha" in result["summary"]
    assert "成功" in result["summary"]


# ---------------------------------------------------------------------------
# 7. Thread isolation
# ---------------------------------------------------------------------------


def test_variant_thread_isolation(auto_runner, spec_dict):
    graph = build_compare_graph(job_runner=auto_runner, timeout_seconds=30)
    result = graph.invoke({
        "design_id": "thread-test",
        "base_spec": spec_dict,
        "variants": [
            {"label": "ta", "changes": []},
            {"label": "tb", "changes": []},
        ],
    })

    thread_ids = [r.get("thread_id", "") for r in result["results"]]
    assert len(set(thread_ids)) == 2
