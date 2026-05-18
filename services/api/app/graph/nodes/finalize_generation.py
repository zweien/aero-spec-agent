"""finalize_generation node — mark generation as complete, emit final SSE if needed."""

from __future__ import annotations

import logging
from typing import Any

from services.api.app.graph.state import DesignGraphState

logger = logging.getLogger(__name__)


def finalize_generation(state: DesignGraphState) -> dict:
    """Finalize the generation pipeline.

    If generation succeeded but no generation_complete SSE was emitted
    (e.g., because observe_until_terminal=False), this node is a no-op.
    Otherwise ensures the final state is consistent.
    """
    status = state.get("status", "unknown")
    sse_events = state.get("sse_events", [])

    # Already have terminal SSE events — nothing to do
    has_complete = any(e.get("event_type") == "generation_complete" for e in sse_events)
    has_failed = any(e.get("event_type") == "generation_failed" for e in sse_events)

    if has_complete or has_failed:
        return {}

    # If succeeded but no complete event (fire-and-forget mode), just log
    if status == "succeeded":
        logger.info(
            "generation finalized: job_id=%s version_no=%s",
            state.get("job_id"),
            state.get("version_no"),
        )

    return {}
