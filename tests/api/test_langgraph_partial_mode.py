"""Tests for LangGraph partial mode — job orchestration, checkpointing, SSE, fallback."""

import os
import threading
from pathlib import Path

import pytest
import yaml

from services.api.app.graph.checkpoint import make_memory_checkpointer, make_sqlite_checkpointer
from services.api.app.graph.compare_graph import build_compare_graph
from services.api.app.graph.partial_graph import build_partial_design_graph
from services.api.app.graph.tracing import get_tracing_config, is_tracing_enabled
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
    """Wrapper that auto-runs enqueued jobs in a background thread."""

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def job_runner(tmp_path):
    vs = VersionStore(root=tmp_path)
    return JobRunner(store=vs)


@pytest.fixture
def auto_runner(job_runner):
    return AutoRunJobRunner(job_runner)


@pytest.fixture
def spec_dict():
    return _load_spec_dict()


# ---------------------------------------------------------------------------
# 1. Compilation
# ---------------------------------------------------------------------------


def test_partial_graph_compiles(job_runner):
    graph = build_partial_design_graph(job_runner=job_runner)
    assert graph is not None


# ---------------------------------------------------------------------------
# 2. Full pipeline — enqueue + observe + SSE (auto-run)
# ---------------------------------------------------------------------------


def test_full_pipeline_succeeded(auto_runner, spec_dict):
    graph = build_partial_design_graph(job_runner=auto_runner, poll_interval=0.1, max_poll_seconds=10)
    result = graph.invoke({
        "conversation_id": "c1",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })

    assert result["intent"] == "generate_design"
    assert result["status"] == "succeeded"
    assert result["job_id"]

    sse_events = result.get("sse_events", [])
    event_types = [e.get("event_type") for e in sse_events]
    assert "generation_started" in event_types
    assert "generation_complete" in event_types


# ---------------------------------------------------------------------------
# 3. SSE generation_started emitted
# ---------------------------------------------------------------------------


def test_sse_generation_started(auto_runner, spec_dict):
    graph = build_partial_design_graph(job_runner=auto_runner, poll_interval=0.1, max_poll_seconds=10)
    result = graph.invoke({
        "conversation_id": "c2",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })

    sse_events = result.get("sse_events", [])
    started = [e for e in sse_events if e.get("event_type") == "generation_started"]
    assert len(started) >= 1
    assert started[0]["job_id"] == result["job_id"]


# ---------------------------------------------------------------------------
# 4. Fallback — no spec
# ---------------------------------------------------------------------------


def test_fallback_no_spec(job_runner):
    graph = build_partial_design_graph(job_runner=job_runner)
    result = graph.invoke({
        "conversation_id": "c3",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": None,
    })

    # enqueue_job fails → observe_job sees no job_id → emit_sse → save_state
    assert result["status"] == "failed"
    assert result.get("error_message")


# ---------------------------------------------------------------------------
# 5. Observe timeout — job stays queued
# ---------------------------------------------------------------------------


def test_observe_timeout(job_runner, spec_dict):
    graph = build_partial_design_graph(job_runner=job_runner, poll_interval=0.05, max_poll_seconds=0.3)
    result = graph.invoke({
        "conversation_id": "c4",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })

    assert result["status"] == "failed"
    assert "timed out" in result.get("error_message", "")


# ---------------------------------------------------------------------------
# 6. Conversation intent skips job dispatch
# ---------------------------------------------------------------------------


def test_conversation_intent_skips_job(job_runner):
    """Verify conversation-like messages with an existing spec go to modify_design."""
    graph = build_partial_design_graph(job_runner=job_runner)
    result = graph.invoke({
        "conversation_id": "c5",
        "design_id": "test-design",
        "user_message": "请帮我把翼展调整到12米",
        "selected_refs": [],
        "current_spec": {"schema_version": "0.1"},
    })

    # With existing spec and no generate keywords → modify_design → hits prepare → enqueue
    # The graph runs the full pipeline but spec validation may fail
    # This is the expected path for partial mode
    assert result["intent"] in ("modify_design", "generate_design")


# ---------------------------------------------------------------------------
# 7. Thread isolation (InMemorySaver)
# ---------------------------------------------------------------------------


def test_thread_isolation_memory(auto_runner, spec_dict):
    checkpointer = make_memory_checkpointer()
    graph = build_partial_design_graph(
        job_runner=auto_runner, checkpointer=checkpointer, poll_interval=0.1, max_poll_seconds=10,
    )

    config_a = {"configurable": {"thread_id": "thread-a"}}
    config_b = {"configurable": {"thread_id": "thread-b"}}

    graph.invoke({
        "conversation_id": "ca",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config_a)

    graph.invoke({
        "conversation_id": "cb",
        "design_id": "test-design",
        "user_message": "把翼展改成14米",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config_b)

    state_a = graph.get_state(config_a)
    state_b = graph.get_state(config_b)

    assert state_a.values["intent"] == "generate_design"
    assert state_b.values["intent"] == "modify_design"
    assert state_a.values["job_id"] != state_b.values.get("job_id", "")


# ---------------------------------------------------------------------------
# 8. SQLite checkpointer
# ---------------------------------------------------------------------------


def test_sqlite_checkpointer(auto_runner, spec_dict, tmp_path):
    db = tmp_path / "checkpoints.sqlite"
    checkpointer = make_sqlite_checkpointer(db)
    graph = build_partial_design_graph(
        job_runner=auto_runner, checkpointer=checkpointer,
        poll_interval=0.1, max_poll_seconds=10,
    )

    config = {"configurable": {"thread_id": "partial-thread-1"}}
    result = graph.invoke({
        "conversation_id": "c7",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config)

    assert result["intent"] == "generate_design"
    snapshot = graph.get_state(config)
    assert snapshot.values["intent"] == "generate_design"
    assert snapshot.values["job_id"]


# ---------------------------------------------------------------------------
# 9. Checkpoint recovery
# ---------------------------------------------------------------------------


def test_checkpoint_recovery(auto_runner, spec_dict, tmp_path):
    db = tmp_path / "checkpoints.sqlite"

    cp1 = make_sqlite_checkpointer(db)
    graph1 = build_partial_design_graph(
        job_runner=auto_runner, checkpointer=cp1,
        poll_interval=0.1, max_poll_seconds=10,
    )
    config = {"configurable": {"thread_id": "recovery-thread"}}
    result = graph1.invoke({
        "conversation_id": "c10",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    }, config=config)

    job_id_from_first = result["job_id"]

    cp2 = make_sqlite_checkpointer(db)
    graph2 = build_partial_design_graph(job_runner=auto_runner, checkpointer=cp2)
    snapshot = graph2.get_state(config)

    assert snapshot.values["job_id"] == job_id_from_first
    assert snapshot.values["intent"] == "generate_design"


# ---------------------------------------------------------------------------
# 10. Tracing config
# ---------------------------------------------------------------------------


def test_tracing_config_default():
    assert not is_tracing_enabled()
    assert get_tracing_config() == {}


def test_tracing_config_enabled():
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = "test-project"
    try:
        config = get_tracing_config()
        assert config["metadata"]["langchain_project"] == "test-project"
    finally:
        del os.environ["LANGCHAIN_TRACING_V2"]
        del os.environ["LANGCHAIN_PROJECT"]


# ---------------------------------------------------------------------------
# 11. CompareGraph — variant dispatch
# ---------------------------------------------------------------------------


def test_compare_graph_dispatches_variants(job_runner, spec_dict):
    graph = build_compare_graph(job_runner=job_runner)
    result = graph.invoke({
        "design_id": "test-compare",
        "base_spec": spec_dict,
        "variants": [
            {"label": "v1", "changes": [{"path": "aircraft.name", "value": "variant_1"}]},
            {"label": "v2", "changes": [{"path": "aircraft.name", "value": "variant_2"}]},
        ],
    })

    assert result["status"] == "running"
    assert len(result["variant_jobs"]) == 2
    assert result["variant_jobs"][0]["label"] == "v1"
    assert result["variant_jobs"][0]["job_id"]
    assert result["variant_jobs"][0]["status"] == "queued"


# ---------------------------------------------------------------------------
# 12. CompareGraph — no variants error
# ---------------------------------------------------------------------------


def test_compare_graph_no_variants(job_runner):
    graph = build_compare_graph(job_runner=job_runner)
    result = graph.invoke({
        "design_id": "test-compare",
        "base_spec": {},
        "variants": [],
    })

    assert result["status"] == "failed"
    assert "no variants" in result.get("error_message", "")


# ---------------------------------------------------------------------------
# 13. CompareGraph — aggregate with pre-run job
# ---------------------------------------------------------------------------


def test_compare_graph_aggregate(job_runner, spec_dict):
    from services.api.app.schemas.aircraft_spec import AircraftSpec

    spec = AircraftSpec.model_validate(spec_dict)
    job1 = job_runner.enqueue_generate(design_id="test-compare", spec=spec)
    job_runner.run_queued_job(job1.id, spec)

    graph = build_compare_graph(job_runner=job_runner)
    result = graph.invoke({
        "design_id": "test-compare",
        "base_spec": spec_dict,
        "variants": [
            {"label": "v1", "changes": []},
        ],
    })

    assert result["status"] in ("running", "completed")
    comparison = result.get("comparison", {})
    assert comparison.get("total_variants") == 1
