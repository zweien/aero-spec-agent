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
    "engine.count": {
        "value": 1,
        "source": "rule_default",
        "confidence": 0.5,
        "label": "发动机数量",
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
    """Add layout-specific sections when the layout requires them but they are absent.

    Which sections a layout needs is declared by LayoutPlan.extra_sections
    (single source of truth). The scalar defaults per section live in the
    _SECTION_DEFAULTS dispatch below — keyed by the same section names.
    """
    aircraft = spec_data.get("aircraft")
    layout = ""
    if isinstance(aircraft, dict):
        layout = str(aircraft.get("layout", "")).lower()
    if not layout:
        return

    # Late import avoids a services→workers cycle at module load.
    from services.workers.cad_worker.openvsp_generator.layout_plan import get_layout_plan

    plan = get_layout_plan(layout)
    wing_span = spec_data.get("wing", {}).get("span", {}).get("value", 6.0)

    for section in plan.extra_sections:
        if section in spec_data:
            continue  # already provided
        builder = _SECTION_DEFAULTS.get(section)
        if builder is not None:
            spec_data[section] = builder(wing_span)


def _canard_defaults(span: float) -> dict[str, Any]:
    return {
        "span": _spec_scalar({"value": round(span * 0.4, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        "chord": _spec_scalar({"value": 0.5, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


def _rear_wing_defaults(span: float) -> dict[str, Any]:
    return {
        "span": _spec_scalar({"value": round(span * 0.7, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        "chord": _spec_scalar({"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


def _second_wing_defaults(span: float) -> dict[str, Any]:
    return {
        "span": _spec_scalar({"value": round(span * 0.85, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        "chord": _spec_scalar({"value": 0.8, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        "gap": _spec_scalar({"value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


def _multi_fuselage_defaults(span: float) -> dict[str, Any]:
    return {
        "spacing": _spec_scalar({"value": round(span * 0.5, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


def _box_wing_config_defaults(span: float) -> dict[str, Any]:
    return {
        "gap": _spec_scalar({"value": 1.5, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


def _boom_defaults(span: float) -> dict[str, Any]:
    return {
        "length": _spec_scalar({"value": 2.0, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        "span": _spec_scalar({"value": round(span * 0.6, 2), "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


def _body_defaults(span: float) -> dict[str, Any]:
    return {
        "width": _spec_scalar({"value": 2.0, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
        "height": _spec_scalar({"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.5, "reason": "LLM 未提供，系统按规则补全"}),
    }


# section name → default-value generator (takes wing span). Keyed by the same
# section names declared in LayoutPlan.extra_sections.
_SECTION_DEFAULTS: dict[str, "Any"] = {
    "canard": _canard_defaults,
    "rear_wing": _rear_wing_defaults,
    "second_wing": _second_wing_defaults,
    "multi_fuselage": _multi_fuselage_defaults,
    "box_wing_config": _box_wing_config_defaults,
    "boom": _boom_defaults,
    "body": _body_defaults,
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
