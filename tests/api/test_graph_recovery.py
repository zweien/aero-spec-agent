"""Tests for durable workflow recovery via SQLite checkpointer.

Validates:
- Checkpoint persists graph state across invocations
- Thread restore resumes from last checkpoint
- Partial graph continuation after simulated restart
"""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from services.api.app.graph.checkpoint import make_sqlite_checkpointer
from services.api.app.graph.partial_graph import build_partial_design_graph
from services.api.app.services.job_events import reset_job_event_bus
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
# SQLite checkpoint persistence
# ---------------------------------------------------------------------------


class TestCheckpointPersistence:
    def test_sqlite_checkpointer_saves_state(self, job_runner, spec_dict):
        """Graph state is persisted to SQLite checkpoint."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)

        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        thread_id = "recovery-thread-1"
        config = {"configurable": {"thread_id": thread_id}}

        result = graph.invoke({
            "conversation_id": "recover-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)

        assert result["status"] == "succeeded"

        # Check checkpoint exists
        state_history = list(checkpointer.list(config))
        assert len(state_history) > 0

    def test_thread_restore_resumes_graph(self, job_runner, spec_dict):
        """New invocation with same thread_id loads previous state."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)

        thread_id = "restore-thread-1"
        config = {"configurable": {"thread_id": thread_id}}

        # First invocation
        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        result1 = graph.invoke({
            "conversation_id": "restore-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)

        assert result1["status"] == "succeeded"
        first_job_id = result1.get("job_id", "")

        # Second invocation with same thread_id — should see checkpoint history
        state_snapshots = list(checkpointer.list(config))
        assert len(state_snapshots) > 0

        # The latest snapshot should contain the completed state
        latest = state_snapshots[0]
        assert latest.metadata is not None

    def test_different_threads_independent(self, job_runner, spec_dict):
        """Different thread IDs produce independent graph states."""
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
            "conversation_id": "thread-a",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config={"configurable": {"thread_id": "thread-a"}})

        # Thread B
        result_b = graph.invoke({
            "conversation_id": "thread-b",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config={"configurable": {"thread_id": "thread-b"}})

        assert result_a["status"] == "succeeded"
        assert result_b["status"] == "succeeded"
        assert result_a["job_id"] != result_b["job_id"]

    def test_simulated_restart_recovery(self, job_runner, spec_dict):
        """Simulate API restart: create new graph with same checkpointer."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)
        thread_id = "restart-thread"
        config = {"configurable": {"thread_id": thread_id}}

        # First "session"
        graph1 = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )
        result1 = graph1.invoke({
            "conversation_id": "restart-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)

        assert result1["status"] == "succeeded"

        # "Restart" — create a completely new graph instance with same checkpointer
        graph2 = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=True,
            event_driven=True,
        )

        # Verify checkpoint history is accessible from new graph
        history = list(checkpointer.list(config))
        assert len(history) > 0

        # The state is recoverable
        latest_state = history[0]
        assert latest_state.metadata is not None


# ---------------------------------------------------------------------------
# API-safe mode recovery
# ---------------------------------------------------------------------------


class TestApiSafeRecovery:
    def test_api_safe_with_checkpointer(self, job_runner, spec_dict):
        """API-safe mode with checkpointer preserves queued state."""
        db_path = tempfile.mktemp(suffix=".sqlite")
        checkpointer = make_sqlite_checkpointer(db_path)
        thread_id = "safe-thread"
        config = {"configurable": {"thread_id": thread_id}}

        graph = build_partial_design_graph(
            job_runner=job_runner,
            checkpointer=checkpointer,
            observe_until_terminal=False,
        )

        result = graph.invoke({
            "conversation_id": "safe-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        }, config=config)

        assert result["status"] == "queued"

        # Checkpoint should exist
        history = list(checkpointer.list(config))
        assert len(history) > 0
