"""SSE adapter — convert state.sse_events to SSE text/event-stream format.

Compatible with the frontend ChatPanel protocol:
  event: generation_started   → {job_id, status, version_no, design_id, ...}
  event: generation_progress  → {job_id, status, progress, current_step, ...}
  event: generation_complete  → {job_id, status, version_no, design_id, ...}
  event: generation_failed    → {job_id, status, version_no, error_message}
  event: message              → {content, intent, job_id, status}
"""

from __future__ import annotations

import json
from typing import Any


def sse_event(event_type: str, data: dict[str, Any]) -> str:
    """Format a single SSE event string."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def convert_sse_events(state_events: list[dict[str, Any]]) -> list[str]:
    """Convert state.sse_events to SSE-formatted strings.

    Each state event has: event_type, job_id, design_id, version_no, status, ...
    Maps to the frontend SSE protocol.
    """
    output = []
    for ev in state_events:
        event_type = ev.get("event_type", "unknown")
        sse_type = _map_event_type(event_type)
        payload = _build_payload(ev)
        output.append(sse_event(sse_type, payload))
    return output


def sse_message_event(content: str, **metadata) -> str:
    """Create a message SSE event with content and metadata."""
    data = {"content": content, **metadata}
    return sse_event("message", data)


def convert_job_event_to_sse(event_dict: dict[str, Any]) -> str:
    """Convert a single JobEvent dict to SSE format.

    Used for streaming progress events from JobEventBus.
    """
    event_type = _map_event_type(event_dict.get("type", "unknown"))
    payload = _build_payload(event_dict)
    return sse_event(event_type, payload)


def _map_event_type(event_type: str) -> str:
    """Map internal event types to frontend SSE event names."""
    mapping = {
        "generation_started": "generation_started",
        "generation_progress": "generation_progress",
        "generation_complete": "generation_complete",
        "generation_failed": "generation_failed",
        "job_started": "generation_progress",
        "job_progress": "generation_progress",
        "job_completed": "generation_complete",
        "job_failed": "generation_failed",
        "workflow_stage": "workflow_stage",
    }
    return mapping.get(event_type, event_type)


def _build_payload(ev: dict[str, Any]) -> dict[str, Any]:
    """Build the SSE payload compatible with the frontend protocol."""
    payload: dict[str, Any] = {
        "job_id": ev.get("job_id", ""),
        "status": ev.get("status", ""),
        "version_no": ev.get("version_no", 0),
        "design_id": ev.get("design_id", ""),
        "created_at": ev.get("created_at", ""),
        "updated_at": ev.get("updated_at", ""),
    }
    if ev.get("error_message"):
        payload["error_message"] = ev["error_message"]
    if ev.get("duration_ms") is not None:
        payload["duration_ms"] = ev["duration_ms"]
    if ev.get("progress") is not None:
        payload["progress"] = ev["progress"]
    if ev.get("current_step"):
        payload["current_step"] = ev["current_step"]
    if ev.get("stage"):
        payload["stage"] = ev["stage"]
    if ev.get("label"):
        payload["label"] = ev["label"]
    if ev.get("metadata"):
        payload["metadata"] = ev["metadata"]
    return payload
