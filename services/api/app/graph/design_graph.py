from __future__ import annotations

from typing import Any, Literal, TypedDict


DesignIntent = Literal["generate_design", "modify_design", "modify_selected_part", "unknown"]

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


_GENERATE_KEYWORDS = ("生成", "设计", "创建", "新建", "做一架", "搞一架")
_MODIFY_PART_KEYWORDS = (
    "这个",
    "选中",
    "移动",
    "外移",
    "内移",
    "向前",
    "向后",
    "向上",
    "向下",
    "加长",
    "增加",
    "减小",
    "缩短",
    "扩大",
    "提高",
)


def classify_message_intent(
    message: str,
    selected_refs: list[str] | None = None,
    has_current_spec: bool = False,
) -> DesignIntent:
    if not has_current_spec:
        return "generate_design"
    if any(kw in message for kw in _GENERATE_KEYWORDS):
        return "generate_design"
    if selected_refs and any(kw in message for kw in _MODIFY_PART_KEYWORDS):
        return "modify_selected_part"
    return "modify_design"


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
