"""Tests for /api/deep-design/stream SSE endpoint."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml
from fastapi.testclient import TestClient

from services.api.app.services.job_events import reset_job_event_bus
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore

EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


class AutoRunJobRunner:
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


@pytest.fixture
def client(job_runner):
    from services.api.app.main import app
    with patch("services.api.app.routers.designs._get_job_runner", return_value=job_runner):
        yield TestClient(app)


def _parse_sse_events(text: str) -> list[dict]:
    """Parse SSE text into list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None
    for line in text.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:]
        elif line.startswith("data: "):
            current_data = json.loads(line[6:])
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None
    return events


class TestDeepDesignStream:
    def test_stream_returns_sse_events(self, client, spec_dict):
        resp = client.post("/api/deep-design/stream", json={
            "design_id": "stream-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        events = _parse_sse_events(resp.text)
        assert len(events) > 0

        event_types = [e["event"] for e in events]
        # Should have at least graph_node events and message events
        assert "message" in event_types

    def test_stream_emits_graph_node_events(self, client, spec_dict):
        resp = client.post("/api/deep-design/stream", json={
            "design_id": "graph-node-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        events = _parse_sse_events(resp.text)
        graph_nodes = [e for e in events if e["event"] == "graph_node"]
        assert len(graph_nodes) > 0

        # Check node names appear (each node emits started + completed = 2 events)
        node_names = set(e["data"]["node"] for e in graph_nodes)
        assert "parse_requirements" in node_names
        assert "prepare_variants" in node_names
        assert "run_compare" in node_names
        assert "synthesize_report" in node_names

    def test_stream_graph_node_completed(self, client, spec_dict):
        resp = client.post("/api/deep-design/stream", json={
            "design_id": "node-status-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })
        events = _parse_sse_events(resp.text)
        completed = [e for e in events if e["event"] == "graph_node" and e["data"]["status"] == "completed"]
        assert len(completed) > 0
        # Completed nodes have latency_ms
        for node in completed:
            assert "latency_ms" in node["data"]

    def test_stream_final_message_has_status(self, client, spec_dict):
        resp = client.post("/api/deep-design/stream", json={
            "design_id": "final-msg-test",
            "description": "设计一架无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 1},
        })
        events = _parse_sse_events(resp.text)
        messages = [e for e in events if e["event"] == "message"]
        final = messages[-1]
        assert final["data"]["status"] == "completed"
        assert "design_id" in final["data"]

    def test_stream_empty_spec(self, client):
        resp = client.post("/api/deep-design/stream", json={
            "design_id": "empty-stream",
            "description": "test",
            "base_spec": {},
            "constraints": {"variant_count": 1},
        })
        assert resp.status_code == 200
        events = _parse_sse_events(resp.text)
        assert len(events) > 0


class TestDeepDesignStreamIntegration:
    def test_stream_vs_sync_consistent_results(self, client, spec_dict):
        """Stream and sync endpoints should produce consistent status."""
        # Sync
        sync_resp = client.post("/api/deep-design", json={
            "design_id": "sync-cmp",
            "description": "设计一架 300km 无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        assert sync_resp.status_code == 200
        sync_status = sync_resp.json()["status"]

        # Stream
        stream_resp = client.post("/api/deep-design/stream", json={
            "design_id": "stream-cmp",
            "description": "设计一架 300km 无人机",
            "base_spec": spec_dict,
            "constraints": {"variant_count": 2},
        })
        events = _parse_sse_events(stream_resp.text)
        messages = [e for e in events if e["event"] == "message"]
        final = messages[-1]
        stream_status = final["data"]["status"]

        assert sync_status == stream_status
