"""load_context node — hydrate state from conversation storage."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def load_context(state: DesignGraphState) -> dict:
    """Load conversation context into graph state.

    In shadow mode, the context is already provided by ChatService.
    This node is a passthrough that validates required fields exist.
    """
    if not state.get("conversation_id"):
        return {"error_message": "missing conversation_id"}
    return {}
