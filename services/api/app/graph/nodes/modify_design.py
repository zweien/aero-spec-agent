"""modify_design node — shadow-mode metadata for modification intent."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def modify_design(state: DesignGraphState) -> dict:
    """Record would-call metadata for modify_design.

    In shadow mode, this node never applies real patches.
    It writes would_call_tool/would_call_args for divergence comparison.
    """
    return {
        "tool_name": "modify_design",
        "tool_args": {},
        "would_call_tool": "modify_design",
        "would_call_args": {
            "design_id": state.get("design_id", ""),
            "message": state.get("user_message", ""),
            "current_spec": state.get("current_spec"),
        },
    }
