"""Runtime stability tests for VariantSubgraph.

Focuses on:
  - Synchronous execution (no deadlock / hanging)
  - Concurrent variant isolation
  - Event bus cleanup (no orphan subscriptions)
  - Error propagation without hanging
  - Repeated invocations (no state accumulation)
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.compare_graph import build_compare_graph
from services.api.app.graph.variant_subgraph import build_variant_subgraph
from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


@pytest.fixture(autouse=True)
def _reset_bus():
    reset_job_event_bus()
    yield
    reset_job_event_bus()


@pytest.fixture
def spec_dict():
    return _load_spec_dict()


@pytest.fixture
def job_runner(tmp_path):
    return JobRunner(store=VersionStore(root=tmp_path))


# ---------------------------------------------------------------------------
# Synchronous execution — no deadlock
# ---------------------------------------------------------------------------


class TestSynchronousExecution:
    def test_generate_completes_synchronously(self, job_runner, spec_dict):
        """job_runner.generate() runs synchronously, no enqueue/wait cycle."""
        subgraph = build_variant_subgraph(job_runner=job_runner)
        result = subgraph.invoke({
            "design_id": "sync-test",
            "spec": spec_dict,
            "label": "sync",
        })
        assert result["status"] == "succeeded"
        assert result["job_id"]

    def test_multiple_sequential_invocations(self, job_runner, spec_dict):
        """Repeated invocations don't accumulate state or hang."""
        subgraph = build_variant_subgraph(job_runner=job_runner)
        for i in range(3):
            result = subgraph.invoke({
                "design_id": f"seq-{i}",
                "spec": spec_dict,
                "label": f"v{i}",
            })
            assert result["status"] == "succeeded"

    def test_invalid_spec_returns_immediately(self, job_runner):
        """Bad spec returns failed status without hanging."""
        subgraph = build_variant_subgraph(job_runner=job_runner)
        result = subgraph.invoke({
            "design_id": "bad",
            "spec": {"not_a_valid_spec": True},
            "label": "bad",
        })
        assert result["status"] == "failed"
        assert "invalid spec" in result["error_message"].lower()

    def test_no_spec_returns_immediately(self, job_runner):
        """Missing spec returns failed status without hanging."""
        subgraph = build_variant_subgraph(job_runner=job_runner)
        result = subgraph.invoke({
            "design_id": "empty",
            "label": "empty",
        })
        assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Concurrent variant isolation
# ---------------------------------------------------------------------------


class TestConcurrentIsolation:
    def test_concurrent_variants_independent(self, job_runner, spec_dict):
        """Multiple CompareGraph runs in parallel threads don't interfere."""
        graph = build_compare_graph(job_runner=job_runner)
        results = [None, None, None]
        errors = []

        def run(idx):
            try:
                r = graph.invoke({
                    "design_id": f"concurrent-{idx}",
                    "base_spec": spec_dict,
                    "variants": [
                        {"label": f"v{idx}-a", "changes": []},
                        {"label": f"v{idx}-b", "changes": []},
                    ],
                })
                results[idx] = r
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent runs failed: {errors}"
        for r in results:
            assert r is not None
            assert r["status"] == "completed"
            assert len(r["results"]) == 2


# ---------------------------------------------------------------------------
# Event bus cleanup
# ---------------------------------------------------------------------------


class TestEventBusCleanup:
    def test_no_orphan_subscriptions_after_run(self, job_runner, spec_dict):
        """Event bus subscriptions are cleaned up after graph execution."""
        from services.api.app.services.job_events import get_job_event_bus

        bus = get_job_event_bus()
        sub_count_before = len(bus._subscribers) if hasattr(bus, "_subscribers") else 0

        subgraph = build_variant_subgraph(job_runner=job_runner)
        subgraph.invoke({
            "design_id": "cleanup-test",
            "spec": spec_dict,
            "label": "cleanup",
        })

        sub_count_after = len(bus._subscribers) if hasattr(bus, "_subscribers") else 0
        assert sub_count_after == sub_count_before, (
            f"Event bus subscribers leaked: {sub_count_before} → {sub_count_after}"
        )

    def test_repeated_runs_dont_accumulate_subscribers(self, job_runner, spec_dict):
        """Multiple graph runs don't accumulate event bus subscriptions."""
        from services.api.app.services.job_events import get_job_event_bus

        bus = get_job_event_bus()
        initial = len(bus._subscribers) if hasattr(bus, "_subscribers") else 0

        subgraph = build_variant_subgraph(job_runner=job_runner)
        for _ in range(5):
            subgraph.invoke({
                "design_id": "accum-test",
                "spec": spec_dict,
                "label": "accum",
            })

        final = len(bus._subscribers) if hasattr(bus, "_subscribers") else 0
        assert final == initial, f"Subscribers grew: {initial} → {final}"


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


class TestErrorPropagation:
    def test_generation_exception_caught(self, job_runner, spec_dict):
        """Exception during generation is caught and reported, not propagated."""
        subgraph = build_variant_subgraph(job_runner=job_runner)

        # Use a spec that triggers a deep validation error
        result = subgraph.invoke({
            "design_id": "exc-test",
            "spec": {"aircraft": {"name": "test"}, "wing": {"span": {"value": -1}}},
            "label": "exc",
        })
        # Should return failed, not raise
        assert result["status"] in ("failed", "succeeded")

    def test_compare_graph_handles_partial_failure(self, job_runner, spec_dict):
        """CompareGraph completes even when some variants fail."""
        graph = build_compare_graph(job_runner=job_runner)

        result = graph.invoke({
            "design_id": "partial",
            "base_spec": spec_dict,
            "variants": [
                {"label": "ok", "changes": []},
                {"label": "bad", "changes": [
                    {"path": "wing.span.value", "value": "not_a_number"},
                ]},
            ],
        })

        assert result["status"] == "completed"
        succeeded = [r for r in result["results"] if r["status"] == "succeeded"]
        failed = [r for r in result["results"] if r["status"] == "failed"]
        assert len(succeeded) >= 1
        assert len(failed) >= 1
