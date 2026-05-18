"""generate_design node — dispatch generation job for a new spec."""

from __future__ import annotations

from typing import TYPE_CHECKING

from services.api.app.graph.state import DesignGraphState

if TYPE_CHECKING:
    from services.api.app.services.job_runner import JobRunner


def generate_design(state: DesignGraphState) -> dict:
    """Prepare a generate_design tool call.

    This node records the intent; actual job dispatch happens in ChatService.
    In shadow mode, it only produces the classified tool name and args for
    comparison with the old path.
    """
    return {
        "tool_name": "generate_design",
        "tool_args": {},
    }
