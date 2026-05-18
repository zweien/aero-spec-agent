"""generate_design node — shadow-mode metadata for generation intent."""

from __future__ import annotations

from services.api.app.graph.state import DesignGraphState


def generate_design(state: DesignGraphState) -> dict:
    """Record would-call metadata for generate_design.

    In shadow mode, this node never dispatches real jobs.
    It writes would_call_tool/would_call_args for divergence comparison,
    and preserves tool_name/tool_args for backward compatibility.
    """
    return {
        "tool_name": "generate_design",
        "tool_args": {},
        "would_call_tool": "generate_design",
        "would_call_args": {
            "design_id": state.get("design_id", ""),
            "message": state.get("user_message", ""),
        },
    }
