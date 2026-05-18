"""Tests for /api/chat graph mode switch and SSE adapter integration."""

import json
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from services.api.app.graph.mode import get_graph_mode
from services.api.app.graph.partial_graph import build_partial_design_graph
from services.api.app.graph.sse_adapter import convert_sse_events, sse_event
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
    def __init__(self, jr):
        self._jr = jr

    def enqueue_generate(self, design_id, spec):
        job = self._jr.enqueue_generate(design_id=design_id, spec=spec)
        t = threading.Thread(target=self._jr.run_queued_job, args=(job.id, spec), daemon=True)
        t.start()
        return job

    def get(self, job_id):
        return self._jr.get(job_id)

    def __getattr__(self, name):
        return getattr(self._jr, name)


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
# Graph mode defaults
# ---------------------------------------------------------------------------


def test_default_mode_is_legacy():
    assert get_graph_mode() == "legacy"


def test_env_sets_partial():
    os.environ["CHAT_GRAPH_MODE"] = "partial"
    try:
        assert get_graph_mode() == "partial"
    finally:
        del os.environ["CHAT_GRAPH_MODE"]


# ---------------------------------------------------------------------------
# API-safe mode (observe_until_terminal=False)
# ---------------------------------------------------------------------------


def test_api_safe_mode_enqueue_only(job_runner, spec_dict):
    """observe_until_terminal=False: enqueue returns immediately, no polling."""
    graph = build_partial_design_graph(
        job_runner=job_runner,
        observe_until_terminal=False,
    )
    result = graph.invoke({
        "conversation_id": "c1",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })

    assert result["intent"] == "generate_design"
    assert result["job_id"]
    # Status should be "queued" (skip_observe), not blocking
    assert result["status"] == "queued"

    # SSE should contain generation_started only
    sse_events = result.get("sse_events", [])
    event_types = [e.get("event_type") for e in sse_events]
    assert "generation_started" in event_types
    assert "generation_complete" not in event_types


def test_api_safe_vs_full_pipeline(auto_runner, spec_dict):
    """Full pipeline produces generation_complete, API-safe does not."""
    # API-safe
    graph_safe = build_partial_design_graph(
        job_runner=auto_runner, observe_until_terminal=False,
    )
    safe_result = graph_safe.invoke({
        "conversation_id": "cs",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })
    assert safe_result["status"] == "queued"

    # Full pipeline
    graph_full = build_partial_design_graph(
        job_runner=auto_runner, observe_until_terminal=True,
        poll_interval=0.1, max_poll_seconds=10,
    )
    full_result = graph_full.invoke({
        "conversation_id": "cf",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })
    assert full_result["status"] == "succeeded"
    full_types = [e.get("event_type") for e in full_result.get("sse_events", [])]
    assert "generation_complete" in full_types


# ---------------------------------------------------------------------------
# SSE contract tests
# ---------------------------------------------------------------------------


def test_sse_generation_started_contract(job_runner, spec_dict):
    """Verify generation_started event matches frontend contract."""
    graph = build_partial_design_graph(
        job_runner=job_runner, observe_until_terminal=False,
    )
    result = graph.invoke({
        "conversation_id": "c2",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": spec_dict,
    })

    sse_events = result.get("sse_events", [])
    started = [e for e in sse_events if e["event_type"] == "generation_started"]
    assert len(started) == 1

    ev = started[0]
    sse_output = convert_sse_events([ev])
    assert len(sse_output) == 1

    # Parse the SSE text
    lines = sse_output[0].strip().split("\n")
    assert lines[0] == "event: generation_started"
    data = json.loads(lines[1][6:])

    # Frontend expects these fields
    assert "job_id" in data
    assert "status" in data
    assert "version_no" in data
    assert "design_id" in data


def test_sse_generation_complete_contract():
    """Verify generation_complete SSE format."""
    ev = {
        "event_type": "generation_complete",
        "job_id": "j-complete",
        "design_id": "d1",
        "version_no": 5,
        "status": "succeeded",
        "duration_ms": 3400.0,
        "created_at": "2026-01-01T00:00:00",
        "updated_at": "2026-01-01T00:00:03",
    }
    sse_output = convert_sse_events([ev])
    lines = sse_output[0].strip().split("\n")
    assert lines[0] == "event: generation_complete"
    data = json.loads(lines[1][6:])
    assert data["status"] == "succeeded"
    assert data["duration_ms"] == 3400.0


def test_sse_generation_failed_contract():
    """Verify generation_failed SSE format."""
    ev = {
        "event_type": "generation_failed",
        "job_id": "j-fail",
        "design_id": "d1",
        "version_no": 6,
        "status": "failed",
        "error_message": "CAD generation error",
        "created_at": "",
        "updated_at": "",
    }
    sse_output = convert_sse_events([ev])
    lines = sse_output[0].strip().split("\n")
    assert lines[0] == "event: generation_failed"
    data = json.loads(lines[1][6:])
    assert data["error_message"] == "CAD generation error"


# ---------------------------------------------------------------------------
# Fallback — no spec in API-safe mode
# ---------------------------------------------------------------------------


def test_api_safe_fallback_no_spec(job_runner):
    graph = build_partial_design_graph(
        job_runner=job_runner, observe_until_terminal=False,
    )
    result = graph.invoke({
        "conversation_id": "c3",
        "design_id": "test-design",
        "user_message": "生成一架无人机",
        "selected_refs": [],
        "current_spec": None,
    })

    assert result["status"] == "failed"
    assert result.get("error_message")
