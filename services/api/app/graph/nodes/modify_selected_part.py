"""modify_selected_part node — dispatch selected-part modification."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def modify_selected_part(state: DesignGraphState) -> dict:
    """Prepare a modify_selected_part tool call.

    This node records the intent; actual patching happens in ChatService.
    """
    return {
        "tool_name": "modify_selected_part",
        "tool_args": {},
    }
