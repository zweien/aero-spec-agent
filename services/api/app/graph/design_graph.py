from __future__ import annotations

from typing import Any, Literal, TypedDict


DesignIntent = Literal["generate_design", "modify_design", "unknown"]

DESIGN_GRAPH_NODES = (
    "load_context",
    "classify_intent",
    "generate_design",
    "modify_design",
    "submit_generation",
    "interpret_result",
)


class DesignGraphState(TypedDict, total=False):
    conversation_id: str
    design_id: str
    user_message: str
    selected_refs: list[str]
    current_spec: dict[str, Any] | None
    intent: DesignIntent
    proposed_spec: dict[str, Any] | None
    patch_changes: list[dict[str, Any]]
    generation_job: dict[str, Any] | None
    assistant_message: str
    error_message: str | None


def load_context(state: DesignGraphState) -> DesignGraphState:
    return state


def classify_intent(state: DesignGraphState) -> DesignGraphState:
    return state


def generate_design(state: DesignGraphState) -> DesignGraphState:
    return state


def modify_design(state: DesignGraphState) -> DesignGraphState:
    return state


def submit_generation(state: DesignGraphState) -> DesignGraphState:
    return state


def interpret_result(state: DesignGraphState) -> DesignGraphState:
    return state
