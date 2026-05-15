from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml

from services.api.app.schemas.aircraft_spec import AircraftSpec

_CONFIG_PATH = Path(__file__).resolve().parents[4] / "packages" / "aircraft-schema" / "design_rules.yaml"

_BUILTIN_DEFAULTS: dict[str, Any] = {
    "wing_span_range": {
        "label": "翼展范围",
        "type": "range",
        "pass": [3.0, 30.0],
        "warn": [2.0, 40.0],
        "unit": "m",
    },
    "fuselage_length_range": {
        "label": "机身长度范围",
        "type": "range",
        "pass": [2.0, 15.0],
        "warn": [1.0, 20.0],
        "unit": "m",
    },
    "span_length_ratio": {
        "label": "翼展/机长比",
        "type": "range",
        "pass": [1.0, 2.5],
        "warn": [0.8, 3.0],
    },
    "aspect_ratio": {
        "label": "展弦比",
        "type": "range",
        "pass": [6.0, 15.0],
        "warn": [4.0, 20.0],
    },
    "taper_ratio": {
        "label": "梢比",
        "type": "range",
        "pass": [0.3, 1.0],
        "warn": [0.2, 1.1],
    },
    "engine_count": {
        "label": "发动机数量",
        "type": "discrete",
        "valid": [1, 2],
    },
    "engine_position": {
        "label": "发动机位置",
        "type": "engine_position",
        "mapping": {1: ["nose", "tail"], 2: ["under_wing", "tail"]},
    },
    "wing_position": {
        "label": "机翼位置",
        "type": "discrete",
        "valid": ["high", "mid", "low"],
    },
    "tail_type": {
        "label": "尾翼类型",
        "type": "discrete",
        "valid": ["conventional"],
    },
    "wing_loading": {
        "label": "翼载荷",
        "type": "range",
        "pass": [2.0, 50.0],
        "warn": [1.0, 100.0],
        "unit": "kg/m²",
    },
}

Status = Literal["pass", "warn", "fail", "skip"]


@dataclass(frozen=True)
class DesignRuleResult:
    rule_id: str
    label: str
    status: Status
    value: float | str
    expected: str
    message: str


@dataclass
class DesignRuleReport:
    rules: list[DesignRuleResult] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
        for r in self.rules:
            counts[r.status] += 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "label": r.label,
                    "status": r.status,
                    "value": r.value,
                    "expected": r.expected,
                    "message": r.message,
                }
                for r in self.rules
            ],
            "summary": self.summary,
        }


def load_rules_config(aircraft_type: str | None = None) -> dict[str, Any]:
    source = _BUILTIN_DEFAULTS
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        file_defaults = data.get("defaults") or {}
        if file_defaults:
            merged = {**source, **file_defaults}
            source = merged
        if aircraft_type:
            overrides = data.get("overrides") or {}
            type_overrides = overrides.get(aircraft_type) or {}
            for rule_id, rule_overrides in type_overrides.items():
                if rule_id in source:
                    source[rule_id] = {**source[rule_id], **rule_overrides}
    return source


def _range_status(
    value: float,
    pass_range: list[float],
    warn_range: list[float],
) -> tuple[Status, str]:
    lo_pass, hi_pass = pass_range
    lo_warn, hi_warn = warn_range
    if lo_pass <= value <= hi_pass:
        return "pass", f"{lo_pass} ~ {hi_pass}"
    if lo_warn <= value < lo_pass or hi_pass < value <= hi_warn:
        return "warn", f"{lo_pass} ~ {hi_pass}"
    return "fail", f"{lo_pass} ~ {hi_pass}"


def _check_wing_span_range(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    val = float(spec.wing.span.value)
    unit = cfg.get("unit", "m")
    status, expected = _range_status(val, cfg["pass"], cfg["warn"])
    status_msg = {
        "pass": f"翼展 {val} {unit} 在典型范围内",
        "warn": f"翼展 {val} {unit} 偏离典型范围",
        "fail": f"翼展 {val} {unit} 超出合理范围",
    }
    return DesignRuleResult(
        rule_id="wing_span_range",
        label=cfg.get("label", "翼展范围"),
        status=status,
        value=val,
        expected=f"{expected} {unit}",
        message=status_msg[status],
    )


def _check_fuselage_length_range(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    val = float(spec.fuselage.length.value)
    unit = cfg.get("unit", "m")
    status, expected = _range_status(val, cfg["pass"], cfg["warn"])
    status_msg = {
        "pass": f"机身长度 {val} {unit} 在典型范围内",
        "warn": f"机身长度 {val} {unit} 偏离典型范围",
        "fail": f"机身长度 {val} {unit} 超出合理范围",
    }
    return DesignRuleResult(
        rule_id="fuselage_length_range",
        label=cfg.get("label", "机身长度范围"),
        status=status,
        value=val,
        expected=f"{expected} {unit}",
        message=status_msg[status],
    )


def _check_span_length_ratio(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    span = float(spec.wing.span.value)
    length = float(spec.fuselage.length.value)
    val = span / length
    status, expected = _range_status(val, cfg["pass"], cfg["warn"])
    status_msg = {
        "pass": f"翼展/机长比 {val:.2f} 在典型范围内",
        "warn": f"翼展/机长比 {val:.2f} 偏离典型范围",
        "fail": f"翼展/机长比 {val:.2f} 超出合理范围",
    }
    return DesignRuleResult(
        rule_id="span_length_ratio",
        label=cfg.get("label", "翼展/机长比"),
        status=status,
        value=round(val, 3),
        expected=expected,
        message=status_msg[status],
    )


def _check_aspect_ratio(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    span = float(spec.wing.span.value)
    root = float(spec.wing.root_chord.value)
    tip = float(spec.wing.tip_chord.value)
    mean_chord = (root + tip) / 2.0
    if mean_chord <= 0:
        return DesignRuleResult(
            rule_id="aspect_ratio",
            label=cfg.get("label", "展弦比"),
            status="fail",
            value=0,
            expected="N/A",
            message="平均弦长为零或负，无法计算展弦比",
        )
    val = span / mean_chord
    status, expected = _range_status(val, cfg["pass"], cfg["warn"])
    status_msg = {
        "pass": f"展弦比 {val:.1f} 在典型范围内",
        "warn": f"展弦比 {val:.1f} 偏离典型范围",
        "fail": f"展弦比 {val:.1f} 超出合理范围",
    }
    return DesignRuleResult(
        rule_id="aspect_ratio",
        label=cfg.get("label", "展弦比"),
        status=status,
        value=round(val, 2),
        expected=expected,
        message=status_msg[status],
    )


def _check_taper_ratio(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    root = float(spec.wing.root_chord.value)
    tip = float(spec.wing.tip_chord.value)
    if root <= 0:
        return DesignRuleResult(
            rule_id="taper_ratio",
            label=cfg.get("label", "梢比"),
            status="fail",
            value=0,
            expected="N/A",
            message="根弦长为零或负，无法计算梢比",
        )
    val = tip / root
    status, expected = _range_status(val, cfg["pass"], cfg["warn"])
    status_msg = {
        "pass": f"梢比 {val:.2f} 在典型范围内",
        "warn": f"梢比 {val:.2f} 偏离典型范围",
        "fail": f"梢比 {val:.2f} 超出合理范围",
    }
    return DesignRuleResult(
        rule_id="taper_ratio",
        label=cfg.get("label", "梢比"),
        status=status,
        value=round(val, 3),
        expected=expected,
        message=status_msg[status],
    )


def _check_engine_count(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    val = int(spec.engine.count.value)
    valid = cfg.get("valid", [1, 2])
    status: Status = "pass" if val in valid else "fail"
    expected = ", ".join(str(v) for v in valid)
    msg = (
        f"发动机数量 {val} 在支持范围内"
        if status == "pass"
        else f"发动机数量 {val} 不在支持范围 ({expected}) 内"
    )
    return DesignRuleResult(
        rule_id="engine_count",
        label=cfg.get("label", "发动机数量"),
        status=status,
        value=val,
        expected=expected,
        message=msg,
    )


def _check_engine_position(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    count = int(spec.engine.count.value)
    position = spec.engine.position
    if position is None:
        return DesignRuleResult(
            rule_id="engine_position",
            label=cfg.get("label", "发动机位置"),
            status="skip",
            value="N/A",
            expected="N/A",
            message="未指定发动机位置",
        )
    pos_val = position.value
    mapping = cfg.get("mapping", {})
    valid_positions = mapping.get(count, [])
    if not valid_positions:
        return DesignRuleResult(
            rule_id="engine_position",
            label=cfg.get("label", "发动机位置"),
            status="warn",
            value=pos_val,
            expected="N/A",
            message=f"发动机数量 {count} 无对应位置配置",
        )
    status: Status = "pass" if pos_val in valid_positions else "fail"
    expected = ", ".join(valid_positions)
    msg = (
        f"{count} 发位置 {pos_val} 合理"
        if status == "pass"
        else f"{count} 发位置 {pos_val} 不在合理范围 ({expected}) 内"
    )
    return DesignRuleResult(
        rule_id="engine_position",
        label=cfg.get("label", "发动机位置"),
        status=status,
        value=pos_val,
        expected=expected,
        message=msg,
    )


def _check_wing_position(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    val = spec.wing.position.value
    valid = cfg.get("valid", ["high", "mid", "low"])
    status: Status = "pass" if val in valid else "fail"
    expected = ", ".join(valid)
    msg = (
        f"机翼位置 {val} 在支持范围内"
        if status == "pass"
        else f"机翼位置 {val} 不在支持范围 ({expected}) 内"
    )
    return DesignRuleResult(
        rule_id="wing_position",
        label=cfg.get("label", "机翼位置"),
        status=status,
        value=val,
        expected=expected,
        message=msg,
    )


def _check_tail_type(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    val = spec.tail.type.value
    valid = cfg.get("valid", ["conventional"])
    status: Status = "pass" if val in valid else "fail"
    expected = ", ".join(valid)
    msg = (
        f"尾翼类型 {val} 在支持范围内"
        if status == "pass"
        else f"尾翼类型 {val} 不在支持范围 ({expected}) 内"
    )
    return DesignRuleResult(
        rule_id="tail_type",
        label=cfg.get("label", "尾翼类型"),
        status=status,
        value=val,
        expected=expected,
        message=msg,
    )


def _check_wing_loading(spec: AircraftSpec, cfg: dict[str, Any]) -> DesignRuleResult:
    if spec.mission.payload is None:
        return DesignRuleResult(
            rule_id="wing_loading",
            label=cfg.get("label", "翼载荷"),
            status="skip",
            value="N/A",
            expected="N/A",
            message="载荷数据缺失，跳过翼载荷检查",
        )
    payload = float(spec.mission.payload.value)
    span = float(spec.wing.span.value)
    root = float(spec.wing.root_chord.value)
    tip = float(spec.wing.tip_chord.value)
    wing_area = span * (root + tip) / 2.0
    if wing_area <= 0:
        return DesignRuleResult(
            rule_id="wing_loading",
            label=cfg.get("label", "翼载荷"),
            status="fail",
            value=0,
            expected="N/A",
            message="翼面积为零或负，无法计算翼载荷",
        )
    val = payload / wing_area
    unit = cfg.get("unit", "kg/m²")
    status, expected = _range_status(val, cfg["pass"], cfg["warn"])
    status_msg = {
        "pass": f"翼载荷 {val:.1f} {unit} 在典型范围内",
        "warn": f"翼载荷 {val:.1f} {unit} 偏离典型范围",
        "fail": f"翼载荷 {val:.1f} {unit} 超出合理范围",
    }
    return DesignRuleResult(
        rule_id="wing_loading",
        label=cfg.get("label", "翼载荷"),
        status=status,
        value=round(val, 2),
        expected=f"{expected} {unit}",
        message=status_msg[status],
    )


_RULE_FUNCTIONS = {
    "wing_span_range": _check_wing_span_range,
    "fuselage_length_range": _check_fuselage_length_range,
    "span_length_ratio": _check_span_length_ratio,
    "aspect_ratio": _check_aspect_ratio,
    "taper_ratio": _check_taper_ratio,
    "engine_count": _check_engine_count,
    "engine_position": _check_engine_position,
    "wing_position": _check_wing_position,
    "tail_type": _check_tail_type,
    "wing_loading": _check_wing_loading,
}


def run_design_rules(spec: AircraftSpec) -> DesignRuleReport:
    aircraft_type = spec.aircraft.type
    config = load_rules_config(aircraft_type)
    rules: list[DesignRuleResult] = []
    for rule_id, rule_fn in _RULE_FUNCTIONS.items():
        cfg = config.get(rule_id, {})
        rules.append(rule_fn(spec, cfg))
    return DesignRuleReport(rules=rules)
