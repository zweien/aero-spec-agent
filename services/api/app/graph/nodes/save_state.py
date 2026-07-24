"""save_state node — persist conversation state to storage."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def save_state(state: DesignGraphState) -> dict:
    """Terminal node in the partial design graph.

    State persistence is handled by ChatService / the partial-graph job path;
    this node exists as the graph's END-adjacent step and is a passthrough.
    """
    return {}
