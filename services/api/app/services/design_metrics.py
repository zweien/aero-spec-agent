"""DesignMetrics — unified metric computation for aircraft designs.

Computes design_metrics from AircraftSpec (or spec_echo dict) and optional
defaulted_fields, producing a stable dict suitable for embedding in
validation_report.json and serving to the Compare View frontend.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass
class DesignMetrics:
    wingspan_m: float | None
    fuselage_length_m: float | None
    wing_area_m2: float | None
    aspect_ratio: float | None
    estimated_lift_to_drag: float | None
    estimated_range_km: float | None
    estimated_endurance_h: float | None
    wing_loading_kg_m2: float | None
    thrust_to_weight: float | None
    risk_level: Literal["low", "medium", "high", "unknown"]
    warnings: list[str] = field(default_factory=list)
    confidence: Literal["heuristic", "partial", "low"] = "heuristic"


def _val(d: Any) -> float | None:
    """Extract numeric value from a spec field (plain number or {value: N} dict)."""
    if d is None:
        return None
    if isinstance(d, (int, float)):
        return float(d)
    if isinstance(d, dict):
        v = d.get("value")
        return float(v) if v is not None else None
    return None


def compute_design_metrics(
    spec: dict[str, Any],
    defaulted_fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute design metrics from a spec dict (spec_echo or AircraftSpec-like).

    Returns a dict matching DesignMetrics fields.
    """
    wing = spec.get("wing", spec.get("wings", {}))
    fuse = spec.get("fuselage", {})
    engines = spec.get("engines", [])
    if isinstance(engines, dict):
        engines = [engines]

    span = _val(wing.get("span"))
    root_chord = _val(wing.get("root_chord"))
    tip_chord = _val(wing.get("tip_chord"))
    fuse_len = _val(fuse.get("length"))

    # Wing area
    wing_area: float | None = None
    if span and root_chord is not None and tip_chord is not None:
        wing_area = span * (root_chord + tip_chord) / 2

    # Aspect ratio
    ar: float | None = None
    if span and wing_area and wing_area > 0:
        ar = (span ** 2) / wing_area

    # Estimated L/D (heuristic: Raymer-style)
    ld: float | None = None
    if ar and ar > 0:
        ld = max(8.0, min(8 + ar * 0.7, 22.0))

    # Wing loading
    mtow = _val(spec.get("performance", {}).get("mtow")) or _val(spec.get("mtow"))
    wing_loading: float | None = None
    if mtow and wing_area and wing_area > 0:
        wing_loading = mtow / wing_area

    # Thrust-to-weight
    total_thrust: float | None = None
    if engines:
        thrusts = []
        for eng in engines:
            t = _val(eng.get("thrust"))
            if t is not None:
                thrusts.append(t)
        if thrusts:
            total_thrust = sum(thrusts)
    tw: float | None = None
    if total_thrust and mtow and mtow > 0:
        g = 9.81
        tw = total_thrust / (mtow * g)

    # Range / endurance — null for MVP (no reliable data)
    range_km: float | None = None
    endurance_h: float | None = None

    # Warnings
    warnings: list[str] = []
    if wing_area is None:
        warnings.append("翼面积缺失，无法计算展弦比")
    if ar is not None and ar < 5:
        warnings.append("展弦比较低，长航时任务可能不利")
    if range_km is None:
        warnings.append("航程估算缺失，需后续接入任务剖面或 VSPAERO 分析")
    defaulted_count = len(defaulted_fields) if defaulted_fields else 0
    if defaulted_count >= 5:
        warnings.append("默认补全参数较多，建议确认关键尺寸")

    # Risk level
    missing_core = sum(1 for v in [span, fuse_len, wing_area, ar] if v is None)
    if wing_area is None:
        risk: Literal["low", "medium", "high", "unknown"] = "unknown"
    elif defaulted_count >= 5 or missing_core >= 5:
        risk = "medium"
    elif ar is not None and ar < 5:
        risk = "medium"
    else:
        risk = "low"

    # Confidence
    present = sum(1 for v in [span, fuse_len, wing_area, ar, ld] if v is not None)
    if present >= 4:
        conf: Literal["heuristic", "partial", "low"] = "heuristic"
    elif present >= 2:
        conf = "partial"
    else:
        conf = "low"

    metrics = DesignMetrics(
        wingspan_m=round(span, 2) if span is not None else None,
        fuselage_length_m=round(fuse_len, 2) if fuse_len is not None else None,
        wing_area_m2=round(wing_area, 2) if wing_area is not None else None,
        aspect_ratio=round(ar, 2) if ar is not None else None,
        estimated_lift_to_drag=round(ld, 1) if ld is not None else None,
        estimated_range_km=round(range_km, 1) if range_km is not None else None,
        estimated_endurance_h=round(endurance_h, 1) if endurance_h is not None else None,
        wing_loading_kg_m2=round(wing_loading, 1) if wing_loading is not None else None,
        thrust_to_weight=round(tw, 3) if tw is not None else None,
        risk_level=risk,
        warnings=warnings,
        confidence=conf,
    )
    return asdict(metrics)
