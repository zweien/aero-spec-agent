"""DesignGraphState — shared state for the LangGraph design orchestration graph."""

from __future__ import annotations

import operator
from typing import Any, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, TypedDict

DesignIntent = Literal[
    "generate_design",
    "modify_design",
    "modify_selected_part",
    "conversation",
    "unknown",
]


class DesignGraphState(TypedDict, total=False):
    """State flowing through the design graph nodes.

    Uses Annotated reducers for accumulation fields:
      - messages: add_messages reducer (dedup, ID-based update, shorthand support)
      - graph_errors: operator.add reducer (append-only error accumulation)
    """

    # Identity
    conversation_id: str
    design_id: str

    # Input
    user_message: str
    selected_refs: list[str]

    # Context
    current_spec: dict[str, Any] | None
    messages: Annotated[list[AnyMessage], add_messages]

    # Intent classification
    intent: DesignIntent

    # Tool execution results
    tool_name: str
    tool_args: dict[str, Any]
    proposed_spec: dict[str, Any] | None
    patch_changes: list[dict[str, Any]]

    # Shadow-mode metadata (written but never executed)
    would_call_tool: str
    would_call_args: dict[str, Any]

    # Generation
    generation_job: dict[str, Any] | None
    job_id: str
    version_no: int
    status: str

    # Response
    assistant_message: str
    error_message: str | None

    # Error accumulation across nodes
    graph_errors: Annotated[list[str], operator.add]
