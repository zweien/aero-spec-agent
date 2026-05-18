"""DesignGraphState — shared state for the LangGraph design orchestration graph."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

DesignIntent = Literal[
    "generate_design",
    "modify_design",
    "modify_selected_part",
    "conversation",
    "unknown",
]


class DesignGraphState(TypedDict, total=False):
    """State flowing through the design graph nodes."""

    # Identity
    conversation_id: str
    design_id: str

    # Input
    user_message: str
    selected_refs: list[str]

    # Context
    current_spec: dict[str, Any] | None
    messages: list[dict[str, Any]]

    # Intent classification
    intent: DesignIntent

    # Tool execution results
    tool_name: str
    tool_args: dict[str, Any]
    proposed_spec: dict[str, Any] | None
    patch_changes: list[dict[str, Any]]

    # Generation
    generation_job: dict[str, Any] | None
    job_id: str
    version_no: int
    status: str

    # Response
    assistant_message: str
    error_message: str | None
