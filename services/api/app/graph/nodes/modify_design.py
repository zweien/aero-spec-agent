"""modify_design node — dispatch modification of an existing spec."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def modify_design(state: DesignGraphState) -> dict:
    """Prepare a modify_design tool call.

    This node records the intent; actual spec patching happens in ChatService.
    """
    return {
        "tool_name": "modify_design",
        "tool_args": {},
    }
