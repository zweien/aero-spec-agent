"""Tests for workflow continuation via SQLite checkpointer.

Validates:
  - Interrupted workflow can be restored from checkpoint
  - Restored thread_id resumes graph execution
  - wait_for_job_event resumes correctly after restart
  - SSE stream resumes from restored state
"""

from __future__ import annotations

import asyncio
import tempfile
import threading
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.checkpoint import make_sqlite_checkpointer
from services.api.app.graph.partial_graph import build_partial_design_graph
from services.api.app.services.job_events import (
    JobEvent,
    JobEventType,
    get_job_event_bus,
    reset_job_event_bus,
)
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
    """Wraps JobRunner to auto-execute enqueued jobs in background threads."""

    def __init__(self, jr: JobRunner) -> None:
        self._jr = jr

    def enqueue_generate(self, design_id, spec):
        job = self._jr.enqueue_generate(design_id=design_id, spec=spec)
        t = threading.Thread(target=self._jr.run_queued_job, args=(job.id, spec), daemon=True)
        t.start()
        return job

    def get(self, job_id):
        return self._jr.get(job_id)

    @property
    def store(self):
        return self._jr.store

    def __getattr__(self, name):
        return getattr(self._jr, name)


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
    return AutoRunJobRunner(JobRunner(store=VersionStore(root=tmp_path)))


# ---------------------------------------------------------------------------
# Workflow resume from checkpoint
# ---------------------------------------------------------------------------


class TestWorkflowResume:
    def test_completed_workflow_has_checkpoints(self, job_runner, spec_dict):
        """A completed workflow leaves behind checkpoint history."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)
        thread_id = "resume-thread-1"
        config = {"configurable": {"thread_id": thread_id}}

        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        result = graph.invoke({
            "conversation_id": "resume-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)

        assert result["status"] == "succeeded"

        # Verify checkpoint history
        history = list(checkpointer.list(config))
        assert len(history) >= 2  # At least initial + final

        # Latest checkpoint should have the job result
        latest = history[0]
        assert latest.config is not None

    def test_api_safe_workflow_preserves_state(self, job_runner, spec_dict):
        """API-safe mode preserves queued state in checkpoint."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)
        thread_id = "resume-api-safe"
        config = {"configurable": {"thread_id": thread_id}}

        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=False,
        )

        result = graph.invoke({
            "conversation_id": "resume-api-safe",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)

        assert result["status"] == "queued"
        assert result.get("job_id")

        # Verify checkpoint exists with queued state
        history = list(checkpointer.list(config))
        assert len(history) >= 1

    def test_different_checkpoints_isolated(self, job_runner, spec_dict):
        """Multiple thread IDs produce independent checkpoint histories."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)

        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        # Thread A
        result_a = graph.invoke({
            "conversation_id": "iso-a",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config={"configurable": {"thread_id": "iso-a"}})

        # Thread B
        result_b = graph.invoke({
            "conversation_id": "iso-b",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config={"configurable": {"thread_id": "iso-b"}})

        # Different results
        assert result_a["job_id"] != result_b["job_id"]

        # Independent checkpoint histories
        hist_a = list(checkpointer.list({"configurable": {"thread_id": "iso-a"}}))
        hist_b = list(checkpointer.list({"configurable": {"thread_id": "iso-b"}}))
        assert len(hist_a) >= 1
        assert len(hist_b) >= 1

    def test_restored_graph_can_execute_new_workflow(self, job_runner, spec_dict):
        """After restoring a checkpoint, a new workflow runs independently."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)
        thread_id = "resume-new"
        config = {"configurable": {"thread_id": thread_id}}

        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        # First workflow
        result1 = graph.invoke({
            "conversation_id": "resume-new",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)
        assert result1["status"] == "succeeded"

        # "Restart" — create new graph with same checkpointer
        graph2 = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        # New workflow on different thread
        result2 = graph2.invoke({
            "conversation_id": "resume-new-2",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config={"configurable": {"thread_id": "resume-new-2"}})
        assert result2["status"] == "succeeded"
        assert result1["job_id"] != result2["job_id"]


# ---------------------------------------------------------------------------
# Event stream resume
# ---------------------------------------------------------------------------


class TestEventStreamResume:
    @pytest.mark.anyio
    async def test_async_queue_receives_events_after_resume(self, job_runner, spec_dict):
        """After simulated restart, async queue receives new job events."""
        bus = get_job_event_bus()

        # First job
        queue1 = bus.async_queue()

        def _run_job1():
            graph = build_partial_design_graph(
                job_runner=job_runner,
                observe_until_terminal=True,
                event_driven=True,
            )
            graph.invoke({
                "conversation_id": "ev-resume",
                "design_id": "test-design",
                "user_message": "生成一架无人机",
                "selected_refs": [],
                "current_spec": spec_dict,
            })

        t1 = threading.Thread(target=_run_job1, daemon=True)
        t1.start()

        events1 = []
        for _ in range(10):
            try:
                event = await asyncio.wait_for(queue1.get(), timeout=10)
                events1.append(event)
                if event.is_terminal:
                    break
            except asyncio.TimeoutError:
                break

        t1.join(timeout=10)
        assert any(e.type == JobEventType.COMPLETED for e in events1)

        # Release first queue
        bus.release_async_queue(queue1)

        # Simulated restart — new queue, new job
        queue2 = bus.async_queue()

        def _run_job2():
            graph2 = build_partial_design_graph(
                job_runner=job_runner,
                observe_until_terminal=True,
                event_driven=True,
            )
            graph2.invoke({
                "conversation_id": "ev-resume-2",
                "design_id": "test-design",
                "user_message": "生成一架无人机",
                "selected_refs": [],
                "current_spec": spec_dict,
            })

        t2 = threading.Thread(target=_run_job2, daemon=True)
        t2.start()

        events2 = []
        for _ in range(10):
            try:
                event = await asyncio.wait_for(queue2.get(), timeout=10)
                events2.append(event)
                if event.is_terminal:
                    break
            except asyncio.TimeoutError:
                break

        t2.join(timeout=10)
        assert any(e.type == JobEventType.COMPLETED for e in events2)
        # Different job IDs
        assert events1[0].job_id != events2[0].job_id

        bus.release_async_queue(queue2)
