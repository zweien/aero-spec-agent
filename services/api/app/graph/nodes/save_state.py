"""save_state node — persist conversation state to storage."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def save_state(state: DesignGraphState) -> dict:
    """Persist state to storage.

    In shadow mode, state is saved by the old ChatService.
    This node is a passthrough.
    """
    return {}
