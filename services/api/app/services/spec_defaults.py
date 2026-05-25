"""Spec default value management for rule-based parameter completion."""

from __future__ import annotations

from typing import Any


# Each entry: dotted spec path → default scalar dict + display metadata
REQUIRED_DEFAULTS: dict[str, dict[str, Any]] = {
    "fuselage.length": {
        "value": 5.0,
        "unit": "m",
        "source": "rule_default",
        "confidence": 0.5,
        "label": "机身长度",
        "reason": "LLM 未提供，系统按规则补全",
    },
    "wing.position": {
        "value": "mid",
        "source": "rule_default",
        "confidence": 0.5,
        "label": "机翼位置",
        "reason": "LLM 未提供，系统按规则补全",
    },
    "wing.span": {
        "value": 6.0,
        "unit": "m",
        "source": "rule_default",
        "confidence": 0.5,
        "label": "翼展",
        "reason": "LLM 未提供，系统按规则补全",
    },
    "wing.root_chord": {
        "value": 1.0,
        "unit": "m",
        "source": "rule_default",
        "confidence": 0.5,
        "label": "翼根弦长",
        "reason": "LLM 未提供，系统按规则补全",
    },
    "wing.tip_chord": {
        "value": 0.6,
        "unit": "m",
        "source": "rule_default",
        "confidence": 0.5,
        "label": "翼尖弦长",
        "reason": "LLM 未提供，系统按规则补全",
    },
    "tail.type": {
        "value": "conventional",
        "source": "rule_default",
        "confidence": 0.5,
        "label": "尾翼类型",
        "reason": "LLM 未提供，系统按规则补全",
    },
    "wing.sections": {
        "value": 1,
        "source": "rule_default",
        "confidence": 0.5,
        "label": "机翼段数",
        "reason": "LLM 未提供，系统按规则补全",
    },
}

# Keys that go into the actual spec (exclude display-only metadata)
_SPEC_KEYS = {"value", "unit", "source", "confidence", "reason"}


def _spec_scalar(default: dict[str, Any]) -> dict[str, Any]:
    """Return only spec-compatible keys from a default entry."""
    return {k: v for k, v in default.items() if k in _SPEC_KEYS}


def _resolve(spec_data: dict[str, Any], dotted_path: str) -> dict[str, Any] | None:
    """Navigate nested dict by dotted path, return leaf or None."""
    keys = dotted_path.split(".")
    target: Any = spec_data
    for key in keys:
        if not isinstance(target, dict) or key not in target:
            return None
        target = target[key]
    return target if isinstance(target, dict) else None


def _layout_aware_defaults(spec_data: dict[str, Any]) -> None:
    """Add layout-specific sections when the layout requires them but they are absent."""
    layout = ""
    aircraft = spec_data.get("aircraft")
    if isinstance(aircraft, dict):
        layout = str(aircraft.get("layout", "")).lower()

    if not layout:
        return

    # Canard / three_surface → need canard section
    if layout in ("canard", "three_surface") and "canard" not in spec_data:
        span = spec_data.get("wing", {}).get("span", {}).get("value", 6.0)
        spec_data["canard"] = {
            "span": _spec_scalar({"value": round(span * 0.4, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
            "chord": _spec_scalar({"value": 0.5, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }

    # Tandem wing / joined wing → need rear_wing section
    if layout in ("tandem_wing", "joined_wing") and "rear_wing" not in spec_data:
        span = spec_data.get("wing", {}).get("span", {}).get("value", 6.0)
        spec_data["rear_wing"] = {
            "span": _spec_scalar({"value": round(span * 0.7, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
            "chord": _spec_scalar({"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }

    # Biplane → need second_wing section
    if layout == "biplane" and "second_wing" not in spec_data:
        span = spec_data.get("wing", {}).get("span", {}).get("value", 6.0)
        spec_data["second_wing"] = {
            "span": _spec_scalar({"value": round(span * 0.85, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
            "chord": _spec_scalar({"value": 0.8, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
            "gap": _spec_scalar({"value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }

    # Multi-fuselage → need multi_fuselage section
    if layout == "multi_fuselage" and "multi_fuselage" not in spec_data:
        span = spec_data.get("wing", {}).get("span", {}).get("value", 6.0)
        spec_data["multi_fuselage"] = {
            "spacing": _spec_scalar({"value": round(span * 0.5, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }

    # Box wing → need box_wing_config section
    if layout == "box_wing" and "box_wing_config" not in spec_data:
        spec_data["box_wing_config"] = {
            "gap": _spec_scalar({"value": 1.5, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }

    # Twin boom → need boom section
    if layout == "twin_boom" and "boom" not in spec_data:
        span = spec_data.get("wing", {}).get("span", {}).get("value", 6.0)
        spec_data["boom"] = {
            "length": _spec_scalar({"value": 2.0, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
            "span": _spec_scalar({"value": round(span * 0.6, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }

    # Blended wing body → need body section
    if layout == "blended_wing_body" and "body" not in spec_data:
        spec_data["body"] = {
            "width": _spec_scalar({"value": 2.0, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
            "height": _spec_scalar({"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        }


def ensure_required_defaults(spec_data: dict[str, Any]) -> None:
    """Fill missing required fields with rule defaults (in-place)."""
    for dotted_path, default in REQUIRED_DEFAULTS.items():
        keys = dotted_path.split(".")
        target = spec_data
        for key in keys[:-1]:
            target = target.setdefault(key, {})
        last_key = keys[-1]
        if last_key not in target or not target[last_key]:
            target[last_key] = _spec_scalar(default)
    _layout_aware_defaults(spec_data)


def collect_defaulted_fields(spec_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return list of fields that were filled by rule defaults."""
    result: list[dict[str, Any]] = []
    for dotted_path, default in REQUIRED_DEFAULTS.items():
        leaf = _resolve(spec_data, dotted_path)
        if leaf and leaf.get("source") == "rule_default":
            entry: dict[str, Any] = {
                "path": dotted_path,
                "label": default.get("label", dotted_path),
                "value": default["value"],
            }
            if "unit" in default:
                entry["unit"] = default["unit"]
            entry["reason"] = default.get("reason", "")
            result.append(entry)
    return result
