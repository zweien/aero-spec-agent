"""No-tool-call fallback — rule-based intent detection for models without function calling.

When the LLM does not return tool_calls (e.g. MiniMax-M2.5 on VLLM), this module
detects user intent from keywords and constructs minimal tool args so the existing
generation pipeline can proceed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

# ---------------------------------------------------------------------------
# Negative-signal patterns (must NOT trigger fallback)
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

_PART_KEYWORDS = (
    "这个", "选中", "当前选中", "这段",
    "this", "selected",
)

# ---------------------------------------------------------------------------
# Dimension extraction patterns
# ---------------------------------------------------------------------------

_DIM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("wing_span", re.compile(r"翼展\s*(\d+(?:\.\d+)?)\s*米?", re.I)),
    ("wing_span", re.compile(r"wingspan\s*(\d+(?:\.\d+)?)\s*m", re.I)),
    ("fuselage_length", re.compile(r"机身(?:长度)?\s*(\d+(?:\.\d+)?)\s*米?", re.I)),
    ("fuselage_length", re.compile(r"fuselage\s*(?:length)?\s*(\d+(?:\.\d+)?)\s*m", re.I)),
    ("engine_count", re.compile(r"(\d+)\s*发", re.I)),
    ("engine_count", re.compile(r"(?:twin|dual|single|triple)\s*engine", re.I)),
    ("wing_position", re.compile(r"(上单翼|下单翼|中单翼)", re.I)),
    ("wing_position", re.compile(r"(high|low|mid)\s*wing", re.I)),
    ("tail_type", re.compile(r"(v尾|v形尾|v字尾)", re.I)),
    ("tail_type", re.compile(r"(v.tail)", re.I)),
    ("payload", re.compile(r"(?:载荷|载重|有效载荷)\s*(\d+(?:\.\d+)?)\s*kg", re.I)),
    ("cruise_speed", re.compile(r"(?:巡航速度|速度)\s*(\d+(?:\.\d+)?)\s*km/h", re.I)),
    ("priority", re.compile(r"(长航时|long endurance|endurance)", re.I)),
]

_ENGINE_COUNT_MAP = {
    "single": 1, "twin": 2, "dual": 2, "triple": 3,
}

_LAYOUT_MAP = {
    "上单翼": "high", "下单翼": "low", "中单翼": "mid",
    "high wing": "high", "low wing": "low", "mid wing": "mid",
}

_MODIFY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("wing_span", re.compile(r"翼展.*?(\d+(?:\.\d+)?)\s*米?", re.I)),
    ("fuselage_length", re.compile(r"机身(?:长度)?.*?(\d+(?:\.\d+)?)\s*米?", re.I)),
]


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ToolFallbackIntent:
    tool_name: str
    args: dict[str, Any]
    confidence: float
    source: str = "no_tool_call_fallback"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def is_fallback_enabled() -> bool:
    return os.getenv("NO_TOOL_CALL_FALLBACK", "true").strip().lower() in ("true", "1", "yes")


def _min_confidence() -> float:
    try:
        return float(os.getenv("NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE", "0.6"))
    except ValueError:
        return 0.6


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def detect_generation_intent(
    user_message: str,
    assistant_text: str | None = None,
    has_current_design: bool = False,
    selected_part: str | None = None,
) -> ToolFallbackIntent | None:
    if not user_message or len(user_message.strip()) < 4:
        return None

    msg = user_message.strip()

    if _is_negative(msg):
        return None

    # Try modify_selected_part first (most specific)
    if selected_part and _has_any_keyword(msg, _PART_KEYWORDS):
        confidence = 0.75
        if _has_any_keyword(msg, _MODIFY_KEYWORDS):
            confidence = 0.85
        if confidence >= _min_confidence():
            return ToolFallbackIntent(
                tool_name="modify_selected_part",
                args=build_modify_selected_part_args(selected_part, msg),
                confidence=confidence,
            )

    # Try modify_design
    if has_current_design and _has_any_keyword(msg, _MODIFY_KEYWORDS):
        if _has_any_keyword(msg, _MODIFY_DESIGN_FIELDS) or re.search(r"\d", msg):
            confidence = 0.75
            if confidence >= _min_confidence():
                return ToolFallbackIntent(
                    tool_name="modify_design",
                    args=build_modify_design_args(msg),
                    confidence=confidence,
                )

    # Try generate_design
    if _has_any_keyword(msg, _GENERATE_KEYWORDS):
        confidence = 0.7
        if re.search(r"\d+(?:\.\d+)?", msg):
            confidence = 0.85
        if assistant_text and any(
            kw in assistant_text for kw in ("参数", "spec", "翼展", "机身", "设计参数")
        ):
            confidence = min(confidence + 0.05, 0.95)
        if confidence >= _min_confidence():
            return ToolFallbackIntent(
                tool_name="generate_design",
                args=build_generate_design_args(msg, assistant_text),
                confidence=confidence,
            )

    return None


# ---------------------------------------------------------------------------
# Args builders
# ---------------------------------------------------------------------------

def build_generate_design_args(
    user_message: str,
    assistant_text: str | None = None,
) -> dict[str, Any]:
    args: dict[str, Any] = {
        "name": "fallback_uav",
        "source": "no_tool_call_fallback",
    }
    inferred: list[str] = []

    for field_name, pattern in _DIM_PATTERNS:
        m = pattern.search(user_message)
        if not m:
            if assistant_text:
                m = pattern.search(assistant_text)
        if m:
            if field_name == "engine_count":
                val = m.group(1)
                if val in _ENGINE_COUNT_MAP:
                    args[field_name] = _ENGINE_COUNT_MAP[val]
                else:
                    try:
                        args[field_name] = int(val)
                    except ValueError:
                        pass
            elif field_name == "wing_position":
                layout = _LAYOUT_MAP.get(m.group(1).lower(), m.group(1))
                args[field_name] = layout
                inferred.append(field_name)
            elif field_name == "tail_type":
                args[field_name] = "v_tail"
                inferred.append(field_name)
            elif field_name == "priority":
                args[field_name] = "endurance"
                inferred.append(field_name)
            else:
                try:
                    args[field_name] = float(m.group(1))
                except ValueError:
                    pass

    # Default layout detection from keywords
    if "wing_position" not in args:
        for kw, pos in _LAYOUT_MAP.items():
            if kw in user_message.lower():
                args["wing_position"] = pos
                inferred.append("wing_position")
                break

    # Default engine count from keywords
    if "engine_count" not in args:
        if "双发" in user_message or "twin engine" in user_message.lower():
            args["engine_count"] = 2
        elif "单发" in user_message or "single engine" in user_message.lower():
            args["engine_count"] = 1

    args["inferred_fields"] = inferred
    return args


def build_modify_design_args(user_message: str) -> dict[str, Any]:
    changes: list[dict[str, Any]] = []

    for field_name, pattern in _MODIFY_PATTERNS:
        m = pattern.search(user_message)
        if m:
            try:
                changes.append({"field": field_name, "value": float(m.group(1))})
            except ValueError:
                pass

    return {
        "changes": changes,
        "instruction": user_message,
        "source": "no_tool_call_fallback",
    }


def build_modify_selected_part_args(
    selected_part: str,
    user_message: str,
) -> dict[str, Any]:
    part_ref = selected_part
    if ":" in selected_part:
        part_ref = selected_part.split(":", 1)[1]

    value = None
    m = re.search(r"(\d+(?:\.\d+)?)", user_message)
    if m:
        try:
            value = float(m.group(1))
        except ValueError:
            pass

    if any(kw in user_message for kw in ("加长", "增加", "加大", "增大", "扩大", "提高")):
        operation = "increase"
    elif any(kw in user_message for kw in ("缩短", "减小", "减小", "降低")):
        operation = "decrease"
    elif any(kw in user_message for kw in ("改为", "设置为", "设为")):
        operation = "set"
    else:
        operation = "adjust"

    args: dict[str, Any] = {
        "part_ref": part_ref,
        "operation": operation,
        "source": "no_tool_call_fallback",
    }
    if value is not None:
        args["value"] = value
    return args


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _has_any_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in keywords)


def _is_negative(msg: str) -> bool:
    lower = msg.lower().strip()

    # Explicit refusal
    for kw in _NEGATIVE_KEYWORDS:
        if kw in lower:
            return True

    # Question patterns that are purely informational
    # Only negative if the message doesn't ALSO contain design keywords
    has_design_signal = _has_any_keyword(msg, _GENERATE_KEYWORDS) or _has_any_keyword(msg, _MODIFY_KEYWORDS)
    if not has_design_signal:
        for prefix in _NEGATIVE_PREFIXES:
            if lower.startswith(prefix):
                return True
        for phrase in _NEGATIVE_CONTAINS:
            if phrase in lower:
                return True
        # Short question ending without design intent
        if len(lower) < 15 and lower.endswith(_QUESTION_ENDINGS):
            return True
    else:
        # Even with design keywords, informational patterns are negative
        for phrase in _NEGATIVE_CONTAINS:
            if phrase in lower:
                return True
        for prefix in _NEGATIVE_PREFIXES:
            if lower.startswith(prefix):
                return True

    return False
