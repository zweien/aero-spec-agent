"""Integration tests for no-tool-call fallback in chat_stream."""

import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from services.api.app.main import app
import services.api.app.routers.chat as chat_router
import services.api.app.routers.designs as designs_router
from services.api.app.services.chat_service import ChatService
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend

EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


class _AsyncChunks:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for chunk in self._chunks:
            yield chunk


class _NoToolCallCompletions:
    """Simulates a model that returns text but never tool_calls."""

    def __init__(self, text: str = "好的，我来帮你设计一架无人机。"):
        self._text = text

    async def create(self, *, tools=None, **kwargs):
        # Returns text content, no tool_calls, finish_reason="stop"
        return _AsyncChunks([
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=self._text, tool_calls=None),
                        finish_reason="stop",
                    )
                ]
            )
        ])


def _sse_type(event: str) -> str:
    for line in event.splitlines():
        if line.startswith("event: "):
            return line.removeprefix("event: ")
    return ""


def _sse_data(event: str) -> dict:
    for line in event.splitlines():
        if line.startswith("data: "):
            return json.loads(line.removeprefix("data: "))
    return {}


def _make_svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, completions):
    runner = JobRunner(
        store=VersionStore(root=tmp_path / "storage"),
        backend=FakeCadBackend(),
    )
    svc = ChatService(storage_root=tmp_path / "conv")
    svc.set_job_runner(runner)
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    monkeypatch.setattr(svc, "_get_client", lambda: fake_client)
    return svc, runner


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_fallback_triggers_generation_on_design_request(tmp_path, monkeypatch):
    """LLM returns no tool_call, but user says '设计一架无人机' → fallback generate."""
    svc, runner = _make_svc(tmp_path, monkeypatch, _NoToolCallCompletions())
    monkeypatch.setattr(chat_router, "chat_service", svc)
    monkeypatch.setattr(designs_router, "runner", runner)

    events_text = [
        e
        async for e in svc.chat_stream(
            conversation_id="fallback-gen",
            message="设计一架翼展12米、双发、上单翼的固定翼无人机",
        )
    ]
    event_types = [_sse_type(e) for e in events_text]

    assert "message" in event_types
    assert "fallback_tool_detected" in event_types
    assert "tool_call" in event_types
    assert "generation_started" in event_types

    fallback_event = next(e for e in events_text if _sse_type(e) == "fallback_tool_detected")
    fb_data = _sse_data(fallback_event)
    assert fb_data["tool_name"] == "generate_design"
    assert fb_data["confidence"] >= 0.6


@pytest.mark.anyio
async def test_fallback_not_triggered_for_concept_question(tmp_path, monkeypatch):
    """User asks a concept question → no fallback, just text response."""
    svc, runner = _make_svc(tmp_path, monkeypatch, _NoToolCallCompletions())
    monkeypatch.setattr(chat_router, "chat_service", svc)
    monkeypatch.setattr(designs_router, "runner", runner)

    events_text = [
        e
        async for e in svc.chat_stream(
            conversation_id="fallback-no",
            message="什么是展弦比？",
        )
    ]
    event_types = [_sse_type(e) for e in events_text]

    assert "fallback_tool_detected" not in event_types
    assert "tool_call" not in event_types
    assert "generation_started" not in event_types
    assert "message" in event_types


@pytest.mark.anyio
async def test_fallback_disabled_by_env(tmp_path, monkeypatch):
    """NO_TOOL_CALL_FALLBACK=false → fallback not triggered."""
    monkeypatch.setenv("NO_TOOL_CALL_FALLBACK", "false")
    svc, runner = _make_svc(tmp_path, monkeypatch, _NoToolCallCompletions())
    monkeypatch.setattr(chat_router, "chat_service", svc)
    monkeypatch.setattr(designs_router, "runner", runner)

    events_text = [
        e
        async for e in svc.chat_stream(
            conversation_id="fallback-disabled",
            message="设计一架无人机",
        )
    ]
    event_types = [_sse_type(e) for e in events_text]

    assert "fallback_tool_detected" not in event_types
    assert "generation_started" not in event_types


@pytest.mark.anyio
async def test_normal_tool_call_not_affected_by_fallback(tmp_path, monkeypatch, caplog):
    """Model returns actual tool_call → fallback NOT triggered, normal path used."""

    class _ToolCallCompletions:
        async def create(self, *, tools=None, **kwargs):
            if tools:
                return _AsyncChunks([
                    SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                delta=SimpleNamespace(
                                    content=None,
                                    tool_calls=[
                                        SimpleNamespace(
                                            index=0,
                                            id="tc-real",
                                            function=SimpleNamespace(
                                                name="generate_design",
                                                arguments=json.dumps({
                                                    "name": "test_uav",
                                                    "wing_span": 10.0,
                                                    "fuselage_length": 5.0,
                                                    "wing_position": "high",
                                                    "wing_root_chord": 1.0,
                                                    "wing_tip_chord": 0.5,
                                                    "tail_type": "conventional",
                                                    "engine_count": 2,
                                                }),
                                            ),
                                        )
                                    ],
                                ),
                                finish_reason="tool_calls",
                            )
                        ]
                    )
                ])
            return _AsyncChunks([
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="设计已提交。"),
                            finish_reason="stop",
                        )
                    ]
                )
            ])

    svc, runner = _make_svc(tmp_path, monkeypatch, _ToolCallCompletions())
    monkeypatch.setattr(chat_router, "chat_service", svc)
    monkeypatch.setattr(designs_router, "runner", runner)

    with caplog.at_level(logging.INFO, logger="services.api.app.services.chat_service"):
        events_text = [
            e
            async for e in svc.chat_stream(
                conversation_id="normal-tc",
                message="设计一架无人机",
            )
        ]

    event_types = [_sse_type(e) for e in events_text]

    # Normal tool_call path, no fallback
    assert "tool_call" in event_types
    assert "fallback_tool_detected" not in event_types
    assert "generation_started" in event_types

    # No fallback log message
    assert "no-tool-call fallback" not in caplog.text


@pytest.mark.anyio
async def test_fallback_modify_requires_existing_design(tmp_path, monkeypatch):
    """Modify intent without current_spec → fallback not triggered."""
    svc, runner = _make_svc(tmp_path, monkeypatch, _NoToolCallCompletions())
    monkeypatch.setattr(chat_router, "chat_service", svc)
    monkeypatch.setattr(designs_router, "runner", runner)

    events_text = [
        e
        async for e in svc.chat_stream(
            conversation_id="no-design-mod",
            message="把翼展改为15米",
        )
    ]
    event_types = [_sse_type(e) for e in events_text]

    # No current design, modify_design shouldn't trigger
    # (may or may not trigger generate_design depending on keywords,
    #  but modify_design specifically should not)
    fallback_events = [e for e in events_text if _sse_type(e) == "fallback_tool_detected"]
    if fallback_events:
        fb_data = _sse_data(fallback_events[0])
        assert fb_data["tool_name"] != "modify_design"
