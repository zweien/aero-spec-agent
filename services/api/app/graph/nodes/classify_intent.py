"""classify_intent — the single intent classifier.

One place answers "what does this message want to do". Used by:
  - the LangGraph ``classify_intent`` node (partial-graph path), and
  - the no-tool-call fallback in ``chat_service`` (legacy path).

The output is :class:`IntentResult` (intent + confidence + reason). Constructing
tool *args* is deliberately a separate concern — see the args-builders in
``services/api/app/services/tool_fallback.py``. Classification and args
extraction were previously fused inside ``detect_generation_intent``; splitting
them gives one rule set for intent and keeps the args-builders reusable.
"""

from __future__ import annotations

import os
import re

from services.api.app.graph.observe import observe_node
from services.api.app.graph.state import DesignGraphState, DesignIntent, IntentResult

# ---------------------------------------------------------------------------
# Negative-signal patterns — must NOT classify as a design intent
# ---------------------------------------------------------------------------

_NEGATIVE_PREFIXES = (
    "什么是", "为什么", "如何", "怎么", "能不能", "是否",
    "what is", "what are", "why", "how", "explain",
    "请解释", "请介绍", "请说明",
)

_NEGATIVE_CONTAINS = (
    "有哪些", "有什么", "的区别", "的特点", "的优势", "的缺点",
    "介绍一下", "告诉我", "讲一下", "说说", "解释一下",
    "什么意思", "是什么意思",
    "tell me about", "describe",
)

_NEGATIVE_KEYWORDS = (
    "不要生成", "不要设计", "只给我讲", "不要做",
    "概念", "原理", "定义",
    "导出报告", "导出模型", "下载", "查看模型", "显示当前",
    "export", "download", "view model",
)

_QUESTION_ENDINGS = ("？", "?")

# ---------------------------------------------------------------------------
# Positive-signal patterns
# ---------------------------------------------------------------------------

_GENERATE_KEYWORDS = (
    "设计一架", "设计一个", "生成一架", "生成一个",
    "创建一架", "创建一个", "新建一架", "新建一个",
    "做一架", "搞一架", "帮我设计", "帮我生成",
    "无人机", "飞机", "飞行器", "固定翼",
    "fixed wing", "uav", "aircraft", "design a",
)

_MODIFY_KEYWORDS = (
    "修改", "改为", "调整", "优化", "变更",
    "换成", "改成", "加大", "减小", "增大", "减少",
    "增加", "缩短", "加长", "扩大",
    "把翼展", "把机身", "把发动机",
    "increase", "decrease", "change", "modify", "optimize",
)

_MODIFY_DESIGN_FIELDS = (
    "翼展", "机身", "发动机", "尾翼", "机翼",
    "上单翼", "下单翼", "中单翼", "双发", "单发",
    "长航时", "高速",
)

# A selected-part modification: the user has a part selected and is acting on
# it (movement directions or scalar tweaks). Merged from the old graph
# _MODIFY_PART_KEYWORDS so part-level intent is classified here, not elsewhere.
_PART_KEYWORDS = (
    "这个", "选中", "当前选中", "这段",
    "this", "selected",
)
_PART_ACTION_KEYWORDS = (
    "移动", "外移", "内移",
    "向前", "向后", "向上", "向下",
    "加长", "增加", "减小", "缩短", "扩大", "提高",
)


def _min_confidence() -> float:
    try:
        return float(os.getenv("NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE", "0.6"))
    except ValueError:
        return 0.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _is_negative(msg: str) -> bool:
    lower = msg.lower().strip()

    for kw in _NEGATIVE_KEYWORDS:
        if kw in lower:
            return True

    has_design_signal = (
        _has_any_keyword(msg, _GENERATE_KEYWORDS)
        or _has_any_keyword(msg, _MODIFY_KEYWORDS)
    )
    if not has_design_signal:
        for prefix in _NEGATIVE_PREFIXES:
            if lower.startswith(prefix):
                return True
        for phrase in _NEGATIVE_CONTAINS:
            if phrase in lower:
                return True
        if len(lower) < 15 and lower.endswith(_QUESTION_ENDINGS):
            return True
    else:
        for phrase in _NEGATIVE_CONTAINS:
            if phrase in lower:
                return True
        for prefix in _NEGATIVE_PREFIXES:
            if lower.startswith(prefix):
                return True

    return False


# ---------------------------------------------------------------------------
# The classifier
# ---------------------------------------------------------------------------

def _classify(
    message: str,
    selected_refs: list[str] | None = None,
    has_spec: bool = False,
    *,
    assistant_text: str | None = None,
    min_confidence: float | None = None,
) -> IntentResult | None:
    """Classify a user message into a design intent.

    Returns ``None`` when the message is conversational / informational
    (no design intent above the confidence threshold). Otherwise an
    :class:`IntentResult`.

    ``assistant_text`` is the LLM's free-text reply (used only by the
    no-tool-call fallback path to bump confidence when the reply already
    discusses parameters).
    """
    threshold = min_confidence if min_confidence is not None else _min_confidence()

    if not message or len(message.strip()) < 4:
        return None

    msg = message.strip()

    if _is_negative(msg):
        return None

    has_part_selected = bool(selected_refs)

    # modify_selected_part — most specific: a part is selected AND the user
    # references it / acts on it.
    if has_part_selected and (
        _has_any_keyword(msg, _PART_KEYWORDS)
        or _has_any_keyword(msg, _PART_ACTION_KEYWORDS)
    ):
        confidence = 0.85 if _has_any_keyword(msg, _MODIFY_KEYWORDS) else 0.75
        if confidence >= threshold:
            return IntentResult("modify_selected_part", confidence, "part selected + action keyword")

    # modify_design — needs an existing design plus a modify verb / field.
    if has_spec and _has_any_keyword(msg, _MODIFY_KEYWORDS):
        if _has_any_keyword(msg, _MODIFY_DESIGN_FIELDS) or re.search(r"\d", msg):
            confidence = 0.75
            if confidence >= threshold:
                return IntentResult("modify_design", confidence, "modify keyword + field/number")

    # generate_design — the broadest positive signal.
    if _has_any_keyword(msg, _GENERATE_KEYWORDS):
        confidence = 0.7
        if re.search(r"\d+(?:\.\d+)?", msg):
            confidence = 0.85
        if assistant_text and any(
            kw in assistant_text for kw in ("参数", "spec", "翼展", "机身", "设计参数")
        ):
            confidence = min(confidence + 0.05, 0.95)
        if confidence >= threshold:
            return IntentResult("generate_design", confidence, "generate keyword")

    return None


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------

@observe_node("classify_intent")
def classify_intent(state: DesignGraphState) -> dict:
    """Classify user intent from message content and context (graph node)."""
    message = state.get("user_message", "")
    selected_refs = state.get("selected_refs", [])
    has_spec = state.get("current_spec") is not None

    result = _classify(message, selected_refs, has_spec)
    intent: DesignIntent = result.intent if result is not None else "conversation"
    return {"intent": intent}
