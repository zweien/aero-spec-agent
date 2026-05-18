"""Tests for graph mode switch, SSE adapter, tracing metadata, SQLite recovery."""

import os
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.checkpoint import make_sqlite_checkpointer
from services.api.app.graph.mode import get_graph_mode
from services.api.app.graph.partial_graph import build_partial_design_graph
from services.api.app.graph.sse_adapter import convert_sse_events, sse_event
from services.api.app.graph.tracing import get_tracing_config, is_tracing_enabled
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Graph mode switch
# ---------------------------------------------------------------------------


def test_default_mode_is_legacy():
    assert get_graph_mode() == "legacy"


def test_shadow_mode():
    os.environ["CHAT_GRAPH_MODE"] = "shadow"
    try:
        assert get_graph_mode() == "shadow"
    finally:
        del os.environ["CHAT_GRAPH_MODE"]


def test_partial_mode():
    os.environ["CHAT_GRAPH_MODE"] = "partial"
    try:
        assert get_graph_mode() == "partial"
    finally:
        del os.environ["CHAT_GRAPH_MODE"]


def test_invalid_mode_falls_back_to_legacy():
    os.environ["CHAT_GRAPH_MODE"] = "invalid"
    try:
        assert get_graph_mode() == "legacy"
    finally:
        del os.environ["CHAT_GRAPH_MODE"]


# ---------------------------------------------------------------------------
# SSE adapter
# ---------------------------------------------------------------------------


def test_sse_event_format():
    result = sse_event("generation_started", {"job_id": "abc", "status": "queued"})
    assert result.startswith("event: generation_started\n")
    assert "data: " in result
    assert result.endswith("\n\n")


def test_convert_sse_events_generation_started():
    events = [{
        "event_type": "generation_started",
        "job_id": "job-1",
        "design_id": "d1",
        "version_no": 3,
        "status": "queued",
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    }]
    result = convert_sse_events(events)
    assert len(result) == 1
    assert "event: generation_started" in result[0]
    assert '"job_id": "job-1"' in result[0]
    assert '"version_no": 3' in result[0]


def test_convert_sse_events_complete():
    events = [{
        "event_type": "generation_complete",
        "job_id": "job-2",
        "design_id": "d1",
        "version_no": 4,
        "status": "succeeded",
        "duration_ms": 1200.5,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:01",
    }]
    result = convert_sse_events(events)
    assert "event: generation_complete" in result[0]
    assert '"duration_ms": 1200.5' in result[0]


def test_convert_sse_events_failed():
    events = [{
        "event_type": "generation_failed",
        "job_id": "job-3",
        "design_id": "d1",
        "version_no": 5,
        "status": "failed",
        "error_message": "CAD error",
        "created_at": "",
        "updated_at": "",
    }]
    result = convert_sse_events(events)
    assert "event: generation_failed" in result[0]
    assert '"error_message": "CAD error"' in result[0]


def test_convert_sse_events_empty():
    assert convert_sse_events([]) == []


def test_sse_payload_fields_match_frontend_contract():
    """Verify all fields expected by the frontend are present."""
    events = [{
        "event_type": "generation_started",
        "job_id": "j1",
        "design_id": "d1",
        "version_no": 1,
        "status": "queued",
        "created_at": "2026-01-01",
        "updated_at": "2026-01-01",
    }]
    result = convert_sse_events(events)
    import json
    data_line = [l for l in result[0].split("\n") if l.startswith("data: ")][0]
    payload = json.loads(data_line[6:])
    for key in ("job_id", "status", "version_no", "design_id", "created_at", "updated_at"):
        assert key in payload, f"missing key: {key}"


# ---------------------------------------------------------------------------
# Tracing metadata
# ---------------------------------------------------------------------------


def test_tracing_config_with_metadata():
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "test-proj"
    try:
        config = get_tracing_config(
            design_id="d1",
            conversation_id="c1",
            graph_mode="partial",
        )
        assert config["metadata"]["design_id"] == "d1"
        assert config["metadata"]["conversation_id"] == "c1"
        assert config["metadata"]["graph_mode"] == "partial"
    finally:
        del os.environ["LANGCHAIN_TRACING_V2"]
        del os.environ["LANGCHAIN_PROJECT"]


def test_tracing_disabled_no_metadata():
    config = get_tracing_config(design_id="d1", conversation_id="c1")
    assert config == {}


def test_tracing_partial_metadata():
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    try:
        config = get_tracing_config(design_id="d1")
        assert config["metadata"]["design_id"] == "d1"
        assert "conversation_id" not in config["metadata"]
    finally:
        del os.environ["LANGCHAIN_TRACING_V2"]


# ---------------------------------------------------------------------------
# SQLite checkpoint recovery — cross-instance
# ---------------------------------------------------------------------------


def test_sqlite_recovery_cross_instance(tmp_path):
    """Graph A writes state, Graph B reads it from the same SQLite file."""
    import threading

    db = tmp_path / "recovery.sqlite"
    vs = VersionStore(root=tmp_path)
    jr = JobRunner(store=vs)
    spec_dict = _load_spec_dict()

    class _AutoRun:
        def __init__(self, jr):
            self._jr = jr
        def enqueue_generate(self, design_id, spec):
            job = self._jr.enqueue_generate(design_id=design_id, spec=spec)
            t = threading.Thread(target=self._jr.run_queued_job, args=(job.id, spec), daemon=True)
            t.start()
            return job
        def get(self, job_id):
            return self._jr.get(job_id)

    auto = _AutoRun(jr)

    # Instance A
    cp_a = make_sqlite_checkpointer(db)
    graph_a = build_partial_design_graph(
        job_runner=auto, checkpointer=cp_a,
        poll_interval=0.1, max_poll_seconds=10,
    )
    config = {"configurable": {"thread_id": "recovery-x"}}
    result_a = graph_a.invoke({
        "conversation_id": "rc",
        "design_id": "test-recovery",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config)

    job_id_a = result_a["job_id"]
    assert job_id_a

    # Instance B — same DB, new graph
    cp_b = make_sqlite_checkpointer(db)
    graph_b = build_partial_design_graph(job_runner=auto, checkpointer=cp_b)
    snapshot_b = graph_b.get_state(config)

    assert snapshot_b.values["job_id"] == job_id_a
    assert snapshot_b.values["intent"] == "generate_design"
    assert snapshot_b.values["status"] == "succeeded"


def test_sqlite_thread_isolation(tmp_path):
    """Different thread_ids have independent state in SQLite."""
    import threading

    db = tmp_path / "isolation.sqlite"
    vs = VersionStore(root=tmp_path / "iso_store")
    jr = JobRunner(store=vs)
    spec_dict = _load_spec_dict()

    class _AutoRun:
        def __init__(self, jr):
            self._jr = jr
        def enqueue_generate(self, design_id, spec):
            job = self._jr.enqueue_generate(design_id=design_id, spec=spec)
            t = threading.Thread(target=self._jr.run_queued_job, args=(job.id, spec), daemon=True)
            t.start()
            return job
        def get(self, job_id):
            return self._jr.get(job_id)

    auto = _AutoRun(jr)
    cp = make_sqlite_checkpointer(db)
    graph = build_partial_design_graph(
        job_runner=auto, checkpointer=cp,
        poll_interval=0.1, max_poll_seconds=10,
    )

    config_1 = {"configurable": {"thread_id": "iso-1"}}
    config_2 = {"configurable": {"thread_id": "iso-2"}}

    r1 = graph.invoke({
        "conversation_id": "c1",
        "design_id": "test-iso",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config_1)

    r2 = graph.invoke({
        "conversation_id": "c2",
        "design_id": "test-iso",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config_2)

    assert r1["job_id"] != r2["job_id"]

    s1 = graph.get_state(config_1)
    s2 = graph.get_state(config_2)
    assert s1.values["job_id"] != s2.values["job_id"]
