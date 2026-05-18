"""modify_selected_part node — shadow-mode metadata for selected-part modification."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def modify_selected_part(state: DesignGraphState) -> dict:
    """Record would-call metadata for modify_selected_part.

    In shadow mode, this node never applies real patches.
    It writes would_call_tool/would_call_args for divergence comparison.
    """
    return {
        "tool_name": "modify_selected_part",
        "tool_args": {},
        "would_call_tool": "modify_selected_part",
        "would_call_args": {
            "design_id": state.get("design_id", ""),
            "message": state.get("user_message", ""),
            "selected_refs": state.get("selected_refs", []),
        },
    }
