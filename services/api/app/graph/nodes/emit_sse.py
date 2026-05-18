"""emit_sse node — format SSE events from state for client delivery."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def emit_sse(state: DesignGraphState) -> dict:
    """Format accumulated SSE events for client delivery.

    This node is a passthrough — SSE events are already accumulated
    in state.sse_events by enqueue_job and observe_job. It serves
    as the architectural boundary where streaming would be initiated.
    """
    return {}
