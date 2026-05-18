"""Tests for graph-driven job lifecycle with JobEventBus.

Validates that the graph observes job lifecycle events and emits
generation_complete/generation_failed SSE via event-driven observation.
"""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from services.api.app.graph.partial_graph import build_partial_design_graph
from services.api.app.graph.sse_adapter import convert_sse_events
from services.api.app.services.job_events import (
    JobEvent,
    JobEventBus,
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
# Event-driven observation
# ---------------------------------------------------------------------------


class TestEventDrivenObservation:
    def test_event_driven_emits_generation_complete(self, job_runner, spec_dict):
        """Event-driven graph emits generation_complete via JobEventBus."""
        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=True,
            max_poll_seconds=30,
        )
        result = graph.invoke({
            "conversation_id": "ev-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        })

        assert result["status"] == "succeeded"
        sse_events = result.get("sse_events", [])
        event_types = [e.get("event_type") for e in sse_events]
        assert "generation_started" in event_types
        assert "generation_complete" in event_types

    def test_event_driven_vs_polling_same_result(self, job_runner, spec_dict):
        """Event-driven and polling modes produce the same final state."""
        # Event-driven
        graph_ev = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=True,
            max_poll_seconds=30,
        )
        result_ev = graph_ev.invoke({
            "conversation_id": "ev-vs-poll-1",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        })

        # Polling
        graph_poll = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=False,
            poll_interval=0.1,
            max_poll_seconds=30,
        )
        result_poll = graph_poll.invoke({
            "conversation_id": "ev-vs-poll-2",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        })

        assert result_ev["status"] == result_poll["status"] == "succeeded"
        assert len(result_ev.get("sse_events", [])) == len(result_poll.get("sse_events", []))

    def test_event_driven_api_safe_mode(self, job_runner, spec_dict):
        """API-safe mode with event_driven=True still skips observation."""
        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=False,
            event_driven=True,
        )
        result = graph.invoke({
            "conversation_id": "ev-safe",
            "design_id": "test-design",
            "user_message": "生成一架无人机",
            "selected_refs": [],
            "current_spec": spec_dict,
        })

        assert result["status"] == "queued"
        event_types = [e.get("event_type") for e in result.get("sse_events", [])]
        assert "generation_started" in event_types
        assert "generation_complete" not in event_types


# ---------------------------------------------------------------------------
# JobEventBus unit tests
# ---------------------------------------------------------------------------


class TestJobEventBus:
    def test_subscribe_and_publish(self):
        bus = JobEventBus()
        events = []
        bus.subscribe(events.append)

        bus.publish(JobEvent(
            type=JobEventType.STARTED,
            job_id="j1",
            design_id="d1",
            version_no=1,
        ))
        assert len(events) == 1
        assert events[0].type == JobEventType.STARTED

    def test_unsubscribe(self):
        bus = JobEventBus()
        events = []
        listener = events.append
        bus.subscribe(listener)
        bus.unsubscribe(listener)

        bus.publish(JobEvent(
            type=JobEventType.STARTED,
            job_id="j1",
            design_id="d1",
            version_no=1,
        ))
        assert len(events) == 0

    def test_listener_error_doesnt_stop_others(self):
        bus = JobEventBus()
        good_events = []

        def bad_listener(e):
            raise ValueError("boom")

        bus.subscribe(bad_listener)
        bus.subscribe(good_events.append)

        bus.publish(JobEvent(
            type=JobEventType.STARTED,
            job_id="j1",
            design_id="d1",
            version_no=1,
        ))
        assert len(good_events) == 1

    def test_job_runner_publishes_events(self, tmp_path):
        """JobRunner generates events via the global bus."""
        bus = get_job_event_bus()
        events = []
        bus.subscribe(events.append)

        runner = JobRunner(store=VersionStore(root=tmp_path))
        spec_dict = _load_spec_dict()
        from services.api.app.schemas.aircraft_spec import AircraftSpec
        spec = AircraftSpec.model_validate(spec_dict)

        runner.generate("ev-design", spec)

        types = [e.type for e in events]
        assert JobEventType.STARTED in types
        assert JobEventType.PROGRESS in types
        assert JobEventType.COMPLETED in types


# ---------------------------------------------------------------------------
# Handle job failure node
# ---------------------------------------------------------------------------


class TestHandleJobFailure:
    def test_failure_emits_sse_when_no_prior_failure_event(self):
        from services.api.app.graph.nodes.handle_job_failure import handle_job_failure

        state = {
            "error_message": "CAD generation error",
            "job_id": "j-fail",
            "design_id": "d1",
            "version_no": 3,
            "sse_events": [],
        }
        result = handle_job_failure(state)
        assert result["status"] == "failed"
        sse_events = result.get("sse_events", [])
        assert len(sse_events) == 1
        assert sse_events[0]["event_type"] == "generation_failed"

    def test_failure_skips_when_already_emitted(self):
        from services.api.app.graph.nodes.handle_job_failure import handle_job_failure

        state = {
            "error_message": "error",
            "job_id": "j-fail",
            "sse_events": [{"event_type": "generation_failed"}],
        }
        result = handle_job_failure(state)
        assert result == {}
