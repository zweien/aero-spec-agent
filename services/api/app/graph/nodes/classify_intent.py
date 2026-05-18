"""classify_intent node — route user message to the correct tool path."""

from __future__ import annotations

from services.api.app.graph.observe import observe_node
from services.api.app.graph.state import DesignGraphState, DesignIntent

_GENERATE_KEYWORDS = ("生成", "设计", "创建", "新建", "做一架", "搞一架")
_MODIFY_PART_KEYWORDS = (
    "这个", "选中", "移动", "外移", "内移",
    "向前", "向后", "向上", "向下",
    "加长", "增加", "减小", "缩短", "扩大", "提高",
)


@observe_node("classify_intent")
def classify_intent(state: DesignGraphState) -> dict:
    """Classify user intent from message content and context."""
    message = state.get("user_message", "")
    selected_refs = state.get("selected_refs", [])
    has_spec = state.get("current_spec") is not None

    intent = _classify(message, selected_refs, has_spec)
    return {"intent": intent}


def _classify(
    message: str,
    selected_refs: list[str] | None = None,
    has_spec: bool = False,
) -> DesignIntent:
    if not has_spec:
        return "generate_design"
    if any(kw in message for kw in _GENERATE_KEYWORDS):
        return "generate_design"
    if selected_refs and any(kw in message for kw in _MODIFY_PART_KEYWORDS):
        return "modify_selected_part"
    return "modify_design"
