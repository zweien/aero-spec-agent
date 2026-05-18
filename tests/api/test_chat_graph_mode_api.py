"""API-level tests for /api/chat graph mode switch (legacy / shadow / partial).

Uses FastAPI TestClient to exercise the full request pipeline including
SSE streaming, shadow logging, partial mode job dispatch, and fallback.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from services.api.app.main import app
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
def _clean_env():
    """Ensure CHAT_GRAPH_MODE is unset between tests."""
    orig = os.environ.pop("CHAT_GRAPH_MODE", None)
    yield
    if orig is not None:
        os.environ["CHAT_GRAPH_MODE"] = orig
    else:
        os.environ.pop("CHAT_GRAPH_MODE", None)


@pytest.fixture
def spec_dict():
    return _load_spec_dict()


@pytest.fixture
def job_runner(tmp_path):
    return AutoRunJobRunner(JobRunner(store=VersionStore(root=tmp_path)))


def _collect_sse(body: bytes) -> list[dict]:
    """Parse SSE text into list of {event, data} dicts."""
    events = []
    current_event = None
    for line in body.decode("utf-8").split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            try:
                data = json.loads(line[6:])
            except json.JSONDecodeError:
                data = {"raw": line[6:]}
            events.append({"event": current_event, "data": data})
    return events


def _fake_chat_stream(**kw):
    """Yield a simple SSE message stream."""
    yield 'event: message\ndata: {"content":"hello from legacy"}\n\n'


# ---------------------------------------------------------------------------
# Legacy mode
# ---------------------------------------------------------------------------


class TestLegacyMode:
    def test_legacy_streams_messages(self, job_runner):
        """Legacy mode should stream SSE events via ChatService."""
        os.environ["CHAT_GRAPH_MODE"] = "legacy"

        with (
            patch("services.api.app.routers.designs.runner", job_runner),
            patch("services.api.app.routers.chat.chat_service.chat_stream", _fake_chat_stream),
        ):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "legacy-conv",
                "message": "你好",
            })
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")


# ---------------------------------------------------------------------------
# Shadow mode
# ---------------------------------------------------------------------------


class TestShadowMode:
    def test_shadow_writes_logs(self, job_runner, tmp_path):
        """Shadow mode should write divergence to shadow_logs."""
        os.environ["CHAT_GRAPH_MODE"] = "shadow"

        from services.api.app.services.shadow_logger import ShadowLogger
        log_dir = tmp_path / "shadow_logs"
        logger = ShadowLogger(storage_root=log_dir)

        with (
            patch("services.api.app.routers.designs.runner", job_runner),
            patch("services.api.app.routers.chat.shadow_logger", logger),
            patch("services.api.app.routers.chat.chat_service.chat_stream", _fake_chat_stream),
        ):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "shadow-conv",
                "message": "生成一架无人机",
            })
            assert resp.status_code == 200

        log_files = list(log_dir.glob("*.jsonl"))
        assert len(log_files) >= 1

    def test_shadow_returns_legacy_stream(self, job_runner, tmp_path):
        """Shadow mode should still return the legacy SSE stream to user."""
        os.environ["CHAT_GRAPH_MODE"] = "shadow"

        from services.api.app.services.shadow_logger import ShadowLogger
        logger = ShadowLogger(storage_root=tmp_path / "shadow_logs")

        with (
            patch("services.api.app.routers.designs.runner", job_runner),
            patch("services.api.app.routers.chat.shadow_logger", logger),
            patch("services.api.app.routers.chat.chat_service.chat_stream", _fake_chat_stream),
        ):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "shadow-conv-2",
                "message": "你好",
            })
            assert resp.status_code == 200
            events = _collect_sse(resp.content)
            assert any(e["event"] == "message" for e in events)


# ---------------------------------------------------------------------------
# Partial mode
# ---------------------------------------------------------------------------


class TestPartialMode:
    def test_partial_returns_generation_started(self, job_runner, spec_dict):
        """Partial mode with spec should return generation_started SSE event."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        from services.api.app.schemas.aircraft_spec import AircraftSpec
        spec = AircraftSpec.model_validate(spec_dict)

        # Pre-create conversation state with spec
        from services.api.app.routers.chat import chat_service
        state = chat_service.get_or_create_state("partial-conv")
        state.current_spec = spec
        state.design_id = "partial-conv"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "partial-conv",
                "message": "生成一架无人机",
            })
            assert resp.status_code == 200
            events = _collect_sse(resp.content)
            event_types = [e["event"] for e in events]
            assert "generation_started" in event_types

    def test_partial_includes_message_event(self, job_runner, spec_dict):
        """Partial mode stream should include a message event with content.

        Task 2 will add content field. For now verify message event exists
        and contains job metadata.
        """
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        from services.api.app.schemas.aircraft_spec import AircraftSpec
        spec = AircraftSpec.model_validate(spec_dict)

        from services.api.app.routers.chat import chat_service
        state = chat_service.get_or_create_state("partial-msg-conv")
        state.current_spec = spec
        state.design_id = "partial-msg-conv"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "partial-msg-conv",
                "message": "生成一架无人机",
            })
            assert resp.status_code == 200
            events = _collect_sse(resp.content)
            message_events = [e for e in events if e["event"] == "message"]
            assert len(message_events) >= 1
            msg_data = message_events[0]["data"]
            # Task 2: content field will be added
            assert "content" in msg_data, "message event must include content field"
            assert "job_id" in msg_data
            assert "status" in msg_data

    def test_partial_exception_falls_back(self, job_runner):
        """Partial mode exception should fall back to legacy stream."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        with (
            patch("services.api.app.routers.designs.runner", job_runner),
            patch(
                "services.api.app.graph.partial_graph.build_partial_design_graph",
                side_effect=RuntimeError("graph crash"),
            ),
            patch("services.api.app.routers.chat.chat_service.chat_stream", _fake_chat_stream),
        ):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "fallback-conv",
                "message": "生成一架无人机",
            })
            assert resp.status_code == 200
            events = _collect_sse(resp.content)
            assert any(e["event"] == "message" for e in events)

    def test_partial_conversation_intent_falls_back(self, job_runner):
        """Partial mode with conversation intent should fall back to legacy."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        with (
            patch("services.api.app.routers.designs.runner", job_runner),
            patch(
                "services.api.app.graph.nodes.classify_intent._classify",
                return_value="conversation",
            ),
            patch("services.api.app.routers.chat.chat_service.chat_stream", _fake_chat_stream),
        ):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "conv-intent-conv",
                "message": "你好，请介绍一下这个工具",
            })
            assert resp.status_code == 200
            events = _collect_sse(resp.content)
            assert any(e["event"] == "message" for e in events)

    def test_partial_no_spec_falls_back(self, job_runner):
        """Partial mode with no spec and generate_design intent falls back."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        from services.api.app.routers.chat import chat_service
        state = chat_service.get_or_create_state("nospec-conv")
        state.current_spec = None

        with (
            patch("services.api.app.routers.designs.runner", job_runner),
            patch("services.api.app.routers.chat.chat_service.chat_stream", _fake_chat_stream),
        ):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "nospec-conv",
                "message": "生成一架无人机",
            })
            assert resp.status_code == 200
            # Should use legacy stream (not the graph path)
            events = _collect_sse(resp.content)
            assert any(e["event"] == "message" for e in events)

    def test_partial_modify_with_spec_uses_graph(self, job_runner, spec_dict):
        """Partial mode with modify_design + current_spec should use graph path."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        from services.api.app.schemas.aircraft_spec import AircraftSpec
        spec = AircraftSpec.model_validate(spec_dict)

        from services.api.app.routers.chat import chat_service
        state = chat_service.get_or_create_state("modify-conv")
        state.current_spec = spec
        state.design_id = "modify-conv"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "modify-conv",
                "message": "把翼展改为10米",
                "selected_refs": [],
            })
            assert resp.status_code == 200
            # modify_design with spec should produce generation_started via graph
            events = _collect_sse(resp.content)
            event_types = [e["event"] for e in events]
            assert "generation_started" in event_types

    def test_partial_selected_refs_with_spec_uses_graph(self, job_runner, spec_dict):
        """Partial mode with selected_refs + current_spec should use graph path."""
        os.environ["CHAT_GRAPH_MODE"] = "partial"

        from services.api.app.schemas.aircraft_spec import AircraftSpec
        spec = AircraftSpec.model_validate(spec_dict)

        from services.api.app.routers.chat import chat_service
        state = chat_service.get_or_create_state("selref-conv")
        state.current_spec = spec
        state.design_id = "selref-conv"

        with patch("services.api.app.routers.designs.runner", job_runner):
            client = TestClient(app)
            resp = client.post("/api/chat", json={
                "conversation_id": "selref-conv",
                "message": "向外移动0.5米",
                "selected_refs": ["part:right_engine"],
            })
            assert resp.status_code == 200
            events = _collect_sse(resp.content)
            event_types = [e["event"] for e in events]
            assert "generation_started" in event_types
