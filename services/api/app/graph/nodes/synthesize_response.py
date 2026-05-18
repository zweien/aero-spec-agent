"""synthesize_response node — placeholder for LLM final response."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def synthesize_response(state: DesignGraphState) -> dict:
    """Placeholder for the final LLM response synthesis.

    In shadow mode, this node is not executed (the old ChatService handles
    the final response). When fully migrated, this node will make the LLM call.
    """
    return {"assistant_message": ""}
