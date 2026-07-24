"""No-tool-call fallback — args-builders for models without function calling.

When the LLM does not return tool_calls, the intent is classified by the
single classifier in ``services/api/app/graph/nodes/classify_intent.py``
(:func:`_classify` → :class:`IntentResult`). This module then constructs the
matching tool *arguments* (extracting dimensions, engine count, etc.) so the
existing generation pipeline can proceed.

Classification and args extraction used to be fused in one function
(``detect_generation_intent``). They are now separate: one rule set answers
"what intent", these builders answer "what args for that intent".
"""

from __future__ import annotations

import os
import re
from typing import Any

# ---------------------------------------------------------------------------
# Dimension extraction patterns (used by args-builders, not by classification)
# ---------------------------------------------------------------------------

_DIM_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("wing_span", re.compile(r"翼展\s*(\d+(?:\.\d+)?)\s*米?", re.I)),
    ("wing_span", re.compile(r"wingspan\s*(\d+(?:\.\d+)?)\s*m", re.I)),
    ("fuselage_length", re.compile(r"机身(?:长度)?\s*(\d+(?:\.\d+)?)\s*米?", re.I)),
    ("fuselage_length", re.compile(r"fuselage\s*(?:length)?\s*(\d+(?:\.\d+)?)\s*m", re.I)),
    ("engine_count", re.compile(r"(\d+)\s*发", re.I)),
    ("engine_count", re.compile(r"(twin|dual|single|triple)\s*engine", re.I)),
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
# Config
# ---------------------------------------------------------------------------

def is_fallback_enabled() -> bool:
    return os.getenv("NO_TOOL_CALL_FALLBACK", "true").strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Args-builders — one per intent. Pure: message (+assistant text) → args dict.
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


def build_args_for_intent(
    intent: str,
    user_message: str,
    assistant_text: str | None = None,
    selected_part: str | None = None,
) -> dict[str, Any]:
    """Dispatch to the right args-builder for a classified intent.

    Convenience entry point for the fallback path: after
    :func:`classify_intent._classify` returns an intent, call this to get the
    matching tool args.
    """
    if intent == "generate_design":
        return build_generate_design_args(user_message, assistant_text)
    if intent == "modify_design":
        return build_modify_design_args(user_message)
    if intent == "modify_selected_part":
        return build_modify_selected_part_args(selected_part or "", user_message)
    raise ValueError(f"no args-builder for intent: {intent}")
