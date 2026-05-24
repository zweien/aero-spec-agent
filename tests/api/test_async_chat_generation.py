import asyncio
import json
import threading
from pathlib import Path

import pytest

from services.api.app.services.chat_service import ChatService
from services.api.app.services.job_runner import JobRecord


MINIMAL_FLAT_ARGS = {
    "name": "async_uav",
    "fuselage_length": 5.0,
    "wing_position": "high",
    "wing_span": 10.0,
    "wing_root_chord": 1.0,
    "wing_tip_chord": 0.5,
    "tail_type": "conventional",
    "engine_count": 2,
}


class RecordingJobRunner:
    def __init__(self) -> None:
        self.run_started = threading.Event()
        self.generated_specs = []
        self.created_job = JobRecord(
            id="async-job-id",
            design_id="async-chat",
            version_no=1,
            status="running",
            progress=10,
            current_step="writing_spec",
        )

    def create_job(self, design_id: str) -> JobRecord:
        self.created_job.design_id = design_id
        return self.created_job

    def run_job_generation(self, job: JobRecord, spec) -> None:
        self.run_started.set()
        self.generated_specs.append(spec)
        job.status = "succeeded"
        job.progress = 100
        job.current_step = "succeeded"
        job.files = {"glb": "/tmp/fake.glb"}


def _sse_payload(event: str) -> dict[str, object]:
    data_line = next(line for line in event.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


@pytest.mark.anyio
async def test_generate_design_async_mode_returns_started_before_background_run(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CHAT_GENERATION_MODE", "async")
    runner = RecordingJobRunner()
    service = ChatService(storage_root=tmp_path)
    service.set_job_runner(runner)
    state = service.get_or_create_state("async-chat")

    stream = service._handle_generate_design(
        state,
        MINIMAL_FLAT_ARGS,
        "tc-async-generate",
    )

    first_event = await anext(stream)
    assert first_event.startswith("event: generation_started")
    payload = _sse_payload(first_event)
    assert payload["job_id"] == "async-job-id"
    assert payload["design_id"] == "async-chat"
    assert runner.generated_specs == []

    with pytest.raises(StopAsyncIteration):
        await anext(stream)

    await asyncio.wait_for(asyncio.to_thread(runner.run_started.wait), timeout=1)
    assert len(runner.generated_specs) == 1
    assert state.current_spec is not None


@pytest.mark.anyio
async def test_generate_design_sync_mode_keeps_legacy_generation_complete(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("CHAT_GENERATION_MODE", "sync")
    runner = RecordingJobRunner()
    service = ChatService(storage_root=tmp_path)
    service.set_job_runner(runner)
    state = service.get_or_create_state("sync-chat")

    events = [
        event
        async for event in service._handle_generate_design(
            state,
            MINIMAL_FLAT_ARGS,
            "tc-sync-generate",
        )
    ]

    assert [event.splitlines()[0] for event in events] == [
        "event: generation_started",
        "event: generation_complete",
    ]
    assert len(runner.generated_specs) == 1


def test_spec_defaults_module_collects_defaulted_fields():
    from services.api.app.services.spec_defaults import (
        collect_defaulted_fields,
        ensure_required_defaults,
    )

    spec_data: dict = {
        "schema_version": "0.1",
        "aircraft": {"name": "test", "type": "fixed_wing_uav", "layout": "conventional"},
        "mission": {},
        "fuselage": {},
        "wing": {"span": {"value": 12.0, "unit": "m", "source": "user", "confidence": 1.0}},
        "tail": {},
        "engine": {},
    }
    ensure_required_defaults(spec_data)

    defaulted = collect_defaulted_fields(spec_data)
    paths = {f["path"] for f in defaulted}
    assert "fuselage.length" in paths
    assert "wing.position" in paths
    assert "tail.type" in paths
    # wing.span was user-provided, should NOT be in defaulted
    assert "wing.span" not in paths
    # Each entry has required keys
    for f in defaulted:
        assert "label" in f
        assert "value" in f
        assert "reason" in f


def test_spec_defaults_no_defaults_when_all_provided():
    from services.api.app.services.spec_defaults import (
        collect_defaulted_fields,
        ensure_required_defaults,
    )

    spec_data: dict = {
        "fuselage": {"length": {"value": 5.0, "source": "user", "confidence": 1.0}},
        "wing": {
            "position": {"value": "high", "source": "user", "confidence": 1.0},
            "span": {"value": 12.0, "source": "user", "confidence": 1.0},
            "root_chord": {"value": 1.0, "source": "user", "confidence": 1.0},
            "tip_chord": {"value": 0.5, "source": "user", "confidence": 1.0},
            "sections": {"value": 1, "source": "user", "confidence": 1.0},
        },
        "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1.0}},
    }
    ensure_required_defaults(spec_data)
    defaulted = collect_defaulted_fields(spec_data)
    assert defaulted == []
