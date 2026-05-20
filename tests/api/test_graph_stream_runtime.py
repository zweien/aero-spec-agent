"""Tests for graph-native full lifecycle SSE streaming runtime.

Validates the full event flow:
  JobRunner → JobEventBus → async queue → SSE adapter → frontend

Covers:
  - full lifecycle streaming (started → progress → completed)
  - progress events received
  - terminal events (completed/failed)
  - stream cancellation via disconnect
"""

from __future__ import annotations

import asyncio
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
# Full lifecycle streaming
# ---------------------------------------------------------------------------


class TestFullLifecycleStreaming:
    @pytest.mark.anyio
    async def test_full_lifecycle_events_received(self, job_runner, spec_dict):
        """Full lifecycle: started → progress → completed events via async queue."""
        bus = get_job_event_bus()
        queue = bus.async_queue()

        # Run graph in background thread
        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=True,
        )

        result_holder = {}
        exc_holder = {}

        def _run_graph():
            try:
                result = graph.invoke({
                    "conversation_id": "stream-1",
                    "design_id": "test-design",
                    "user_message": "生成一架无人机",
                    "selected_refs": [],
                    "current_spec": spec_dict,
                })
                result_holder["result"] = result
            except Exception as e:
                exc_holder["exc"] = e

        t = threading.Thread(target=_run_graph, daemon=True)
        t.start()

        # Collect events from async queue
        events = []
        for _ in range(30):  # enough for all workflow_stage + progress events
            try:
                event = await asyncio.wait_for(queue.get(), timeout=10)
                events.append(event)
                if event.is_terminal:
                    break
            except asyncio.TimeoutError:
                break

        t.join(timeout=10)

        event_types = [e.type for e in events]
        assert JobEventType.STARTED in event_types
        assert JobEventType.PROGRESS in event_types
        assert JobEventType.COMPLETED in event_types

        # Verify terminal event has duration
        completed = [e for e in events if e.type == JobEventType.COMPLETED]
        assert len(completed) == 1
        assert completed[0].duration_ms is not None

        bus.release_async_queue(queue)

    @pytest.mark.anyio
    async def test_progress_events_contain_step_info(self, job_runner, spec_dict):
        """Progress events include current_step and progress percentage."""
        bus = get_job_event_bus()
        queue = bus.async_queue()

        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=True,
        )

        def _run():
            graph.invoke({
                "conversation_id": "stream-2",
                "design_id": "test-design",
                "user_message": "生成一架无人机",
                "selected_refs": [],
                "current_spec": spec_dict,
            })

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        events = []
        for _ in range(10):
            try:
                event = await asyncio.wait_for(queue.get(), timeout=10)
                events.append(event)
                if event.is_terminal:
                    break
            except asyncio.TimeoutError:
                break

        t.join(timeout=10)

        progress_events = [e for e in events if e.type == JobEventType.PROGRESS]
        assert len(progress_events) >= 1
        pe = progress_events[0]
        assert pe.progress > 0
        assert pe.current_step

        bus.release_async_queue(queue)

    @pytest.mark.anyio
    async def test_terminal_event_to_sse(self, job_runner, spec_dict):
        """Terminal event converts to correct SSE format."""
        bus = get_job_event_bus()
        queue = bus.async_queue()

        graph = build_partial_design_graph(
            job_runner=job_runner,
            observe_until_terminal=True,
            event_driven=True,
        )

        def _run():
            graph.invoke({
                "conversation_id": "stream-3",
                "design_id": "test-design",
                "user_message": "生成一架无人机",
                "selected_refs": [],
                "current_spec": spec_dict,
            })

        t = threading.Thread(target=_run, daemon=True)
        t.start()

        events = []
        for _ in range(10):
            try:
                event = await asyncio.wait_for(queue.get(), timeout=10)
                events.append(event)
                if event.is_terminal:
                    break
            except asyncio.TimeoutError:
                break

        t.join(timeout=10)

        # Convert all events to SSE
        for event in events:
            ev_dict = {
                "event_type": event.type.value,
                "job_id": event.job_id,
                "design_id": event.design_id,
                "version_no": event.version_no,
                "status": "succeeded" if event.type == JobEventType.COMPLETED else "failed",
                "progress": event.progress,
                "current_step": event.current_step,
                "duration_ms": event.duration_ms,
                "created_at": event.timestamp,
                "updated_at": event.timestamp,
            }
            sse_lines = convert_sse_events([ev_dict])
            assert len(sse_lines) == 1
            assert "event:" in sse_lines[0]
            assert "data:" in sse_lines[0]

        bus.release_async_queue(queue)


# ---------------------------------------------------------------------------
# Stream cancellation
# ---------------------------------------------------------------------------


class TestStreamCancellation:
    @pytest.mark.anyio
    async def test_queue_cleanup_on_release(self):
        """Releasing an async queue stops event delivery."""
        bus = get_job_event_bus()
        queue = bus.async_queue()

        # Publish before release
        bus.publish(JobEvent(
            type=JobEventType.STARTED,
            job_id="j1",
            design_id="d1",
            version_no=1,
        ))
        event = await asyncio.wait_for(queue.get(), timeout=1)
        assert event.job_id == "j1"

        # Release
        bus.release_async_queue(queue)

        # Publish after release — queue should not receive
        bus.publish(JobEvent(
            type=JobEventType.COMPLETED,
            job_id="j1",
            design_id="d1",
            version_no=1,
        ))

        # Old queue should not receive the event
        assert queue.empty()

    @pytest.mark.anyio
    async def test_astream_yields_events(self):
        """bus.astream() yields events as async iterator."""
        bus = get_job_event_bus()

        async def _publish_after_delay():
            await asyncio.sleep(0.1)
            bus.publish(JobEvent(
                type=JobEventType.STARTED,
                job_id="j-async",
                design_id="d1",
                version_no=1,
            ))
            bus.publish(JobEvent(
                type=JobEventType.COMPLETED,
                job_id="j-async",
                design_id="d1",
                version_no=1,
            ))

        asyncio.create_task(_publish_after_delay())

        events = []
        async for event in bus.astream(job_id="j-async"):
            events.append(event)
            if event.is_terminal:
                break

        assert len(events) == 2
        assert events[0].type == JobEventType.STARTED
        assert events[1].type == JobEventType.COMPLETED


# ---------------------------------------------------------------------------
# Event ordering
# ---------------------------------------------------------------------------


class TestEventOrdering:
    def test_events_arrive_in_order(self, tmp_path):
        """JobRunner publishes events in lifecycle order."""
        from services.api.app.schemas.aircraft_spec import AircraftSpec
        bus = get_job_event_bus()
        events = []
        bus.subscribe(events.append)

        store = VersionStore(root=tmp_path)
        runner = JobRunner(store=store)
        spec = AircraftSpec.model_validate(_load_spec_dict())
        runner.generate("order-test", spec)

        types = [e.type for e in events]
        # Order: started → (multiple progress) → completed
        assert types[0] == JobEventType.STARTED
        assert types[-1] == JobEventType.COMPLETED
        assert JobEventType.PROGRESS in types
