"""Extended design metrics: volume / loading / stealth.

Layer 4 estimates that complement performance_estimate.py. Each metric is
computed from spec fields when available, otherwise from empirical fallbacks.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from services.api.app.schemas.aircraft_spec import AircraftSpec

Status = Literal["reasonable", "warning", "unusual"]
Confidence = Literal["high", "medium", "low"]
Category = Literal["volume", "loading", "stealth"]


@dataclass(frozen=True)
class ExtendedMetric:
    metric_id: str
    category: Category
    label: str
    value: float
    unit: str
    confidence: Confidence
    method: str
    status: Status
    typical_range: str
    message: str


@dataclass
class ExtendedMetricsReport:
    metrics: list[ExtendedMetric] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"reasonable": 0, "warning": 0, "unusual": 0}
        for m in self.metrics:
            counts[m.status] = counts.get(m.status, 0) + 1
        return counts

    def by_category(self) -> dict[str, list[ExtendedMetric]]:
        grouped: dict[str, list[ExtendedMetric]] = {"volume": [], "loading": [], "stealth": []}
        for m in self.metrics:
            grouped[m.category].append(m)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": [
                {
                    "metric_id": m.metric_id,
                    "category": m.category,
                    "label": m.label,
                    "value": round(m.value, 6),
                    "unit": m.unit,
                    "confidence": m.confidence,
                    "method": m.method,
                    "status": m.status,
                    "typical_range": m.typical_range,
                    "message": m.message,
                }
                for m in self.metrics
            ],
            "summary": self.summary,
        }


def _num(spec_val: Any, fallback: float | None = None) -> float | None:
    if spec_val is None:
        return fallback
    v = getattr(spec_val, "value", spec_val)
    if v is None:
        return fallback
    try:
        f = float(v)
    except (TypeError, ValueError):
        return fallback
    if f != f:  # nan
        return fallback
    return f


def _text(spec_val: Any, fallback: str = "") -> str:
    v = getattr(spec_val, "value", None)
    return str(v).strip().lower() if v else fallback


def _status(value: float, lo: float, hi: float) -> Status:
    if value <= 0:
        return "unusual"
    if lo <= value <= hi:
        return "reasonable"
    if lo * 0.6 <= value <= hi * 1.4:
        return "warning"
    return "unusual"


# ---------------------------------------------------------------------------
# Constants — cross-checked against Raymer (Aircraft Design: A Conceptual Approach)
# Chapter 6 (weights), Chapter 11 (volume), and conceptual stealth references.
# ---------------------------------------------------------------------------

PAYLOAD_FRACTION_DEFAULT = 0.15  # UAV typical payload fraction (Raymer Ch.6)
EMPTY_FRACTION_DEFAULT = 0.55
FUEL_DENSITY_KG_M3 = 800.0  # Jet-A, kg/m^3

# Material RCS multipliers (relative to bare metal baseline)
RCS_MATERIAL_FACTOR = {
    "metal": 1.0,
    "aluminum": 1.0,
    "composite": 0.5,
    "ram": 0.15,  # radar absorbing material
    "stealth_composite": 0.1,
}

# Shaping level — reduction factor on projected-area baseline
RCS_SHAPING_FACTOR = {
    "none": 1.0,
    "low": 0.6,
    "medium": 0.25,
    "high": 0.05,  # F-22/B-2 class, conceptual
}


def _wing_area(root_chord: float, tip_chord: float, span: float) -> float:
    return span * (root_chord + tip_chord) / 2.0


# ---------------------------------------------------------------------------
# Volume metrics
# ---------------------------------------------------------------------------

def _fuselage_volume(length: float, diameter: float) -> float:
    if length <= 0 or diameter <= 0:
        return 0.0
    r = diameter / 2.0
    return math.pi * r * r * length * 0.85  # 0.85 fineness correction


def _payload_bay_volume(length: float | None, diameter: float | None) -> float:
    if not length or not diameter or length <= 0 or diameter <= 0:
        return 0.0
    r = diameter / 2.0
    return math.pi * r * r * length


def _fuel_volume_from_weight(fuel_weight_kg: float) -> float:
    return fuel_weight_kg / FUEL_DENSITY_KG_M3 if fuel_weight_kg > 0 else 0.0


def _build_volume_metrics(
    spec: AircraftSpec,
    fuselage_volume: float,
    payload_bay_volume: float,
    fuel_volume: float,
) -> list[ExtendedMetric]:
    metrics: list[ExtendedMetric] = []

    metrics.append(ExtendedMetric(
        metric_id="fuselage_volume",
        category="volume",
        label="机身容积",
        value=fuselage_volume,
        unit="m³",
        confidence="medium",
        method="V ≈ π·(D/2)²·L·0.85 (含细长比修正)",
        status=_status(fuselage_volume, 0.5, 50.0),
        typical_range="0.5 ~ 50 m³",
        message="基于机身长度与最大直径的等效圆柱估算",
    ))

    if payload_bay_volume > 0:
        utilisation = payload_bay_volume / fuselage_volume if fuselage_volume > 0 else 0.0
        metrics.append(ExtendedMetric(
            metric_id="payload_bay_volume",
            category="volume",
            label="有效载荷舱容积",
            value=payload_bay_volume,
            unit="m³",
            confidence="medium",
            method="V = π·(D/2)²·L (载荷舱)",
            status=_status(payload_bay_volume, 0.05, 20.0),
            typical_range="0.05 ~ 20 m³",
            message=f"载荷舱占机身体积 {utilisation:.0%}" if fuselage_volume > 0 else "载荷舱体积",
        ))
        metrics.append(ExtendedMetric(
            metric_id="payload_volume_ratio",
            category="volume",
            label="载荷舱/机身体积比",
            value=utilisation,
            unit="",
            confidence="medium",
            method="V_bay / V_fuselage",
            status=_status(utilisation, 0.15, 0.6),
            typical_range="0.15 ~ 0.60",
            message="典型固定翼无人机载荷舱占机身体积的 15%-60%",
        ))
    else:
        metrics.append(ExtendedMetric(
            metric_id="payload_bay_volume",
            category="volume",
            label="有效载荷舱容积",
            value=0.0,
            unit="m³",
            confidence="low",
            method="未指定 fuselage.payload_bay_*",
            status="unusual",
            typical_range="0.05 ~ 20 m³",
            message="缺少载荷舱尺寸,无法估算容积",
        ))

    fuel_tank_vol = _num(getattr(spec.fuselage, "fuel_tank_volume", None))
    if fuel_tank_vol is None or fuel_tank_vol <= 0:
        fuel_tank_vol = fuel_volume
        method = "由燃油重量除以密度反推 (ρ=800 kg/m³)"
    else:
        method = "用户指定 fuselage.fuel_tank_volume"
    metrics.append(ExtendedMetric(
        metric_id="fuel_tank_volume",
        category="volume",
        label="油箱容积",
        value=fuel_tank_vol or 0.0,
        unit="m³",
        confidence="medium" if fuel_tank_vol and fuel_tank_vol > 0 else "low",
        method=method,
        status=_status(fuel_tank_vol or 0.0, 0.02, 30.0) if fuel_tank_vol else "unusual",
        typical_range="0.02 ~ 30 m³",
        message="油箱容积估算" if fuel_tank_vol else "缺少燃油重量与油箱尺寸",
    ))

    return metrics


# ---------------------------------------------------------------------------
# Loading metrics — weight ratios and thrust-to-weight
# ---------------------------------------------------------------------------

def _build_loading_metrics(
    mtow: float,
    empty_weight: float,
    fuel_weight: float,
    payload: float,
    thrust_n: float,
    user_supplied_mtow: bool,
) -> list[ExtendedMetric]:
    metrics: list[ExtendedMetric] = []

    if mtow <= 0:
        metrics.append(ExtendedMetric(
            metric_id="mtow_loading",
            category="loading",
            label="最大起飞重量",
            value=0.0,
            unit="kg",
            confidence="low",
            method="缺少 MTOW 与载荷,无法计算",
            status="unusual",
            typical_range="—",
            message="补充 mission.mtow 或 mission.payload 后可计算",
        ))
        return metrics

    payload_frac = payload / mtow
    empty_frac = empty_weight / mtow
    fuel_frac = fuel_weight / mtow

    confidence: Confidence = "high" if user_supplied_mtow else "medium"

    metrics.append(ExtendedMetric(
        metric_id="payload_fraction",
        category="loading",
        label="载荷重量比",
        value=payload_frac,
        unit="",
        confidence=confidence,
        method="W_payload / MTOW",
        status=_status(payload_frac, 0.10, 0.30),
        typical_range="0.10 ~ 0.30 (UAV 经验值, Raymer Ch.6)",
        message="载荷占 MTOW 比例,反映任务承载效率",
    ))
    metrics.append(ExtendedMetric(
        metric_id="empty_weight_fraction",
        category="loading",
        label="空机重量比",
        value=empty_frac,
        unit="",
        confidence=confidence,
        method="W_empty / MTOW",
        status=_status(empty_frac, 0.40, 0.65),
        typical_range="0.40 ~ 0.65",
        message="空机占 MTOW 比例,衡量结构与系统重量水平",
    ))
    metrics.append(ExtendedMetric(
        metric_id="fuel_fraction",
        category="loading",
        label="燃油重量比",
        value=fuel_frac,
        unit="",
        confidence=confidence,
        method="W_fuel / MTOW",
        status=_status(fuel_frac, 0.10, 0.45),
        typical_range="0.10 ~ 0.45",
        message="燃油占 MTOW 比例,影响航程与续航",
    ))

    if thrust_n > 0:
        weight_n = mtow * 9.81
        tw = thrust_n / weight_n
        metrics.append(ExtendedMetric(
            metric_id="thrust_to_weight",
            category="loading",
            label="推重比",
            value=tw,
            unit="",
            confidence="medium",
            method="T / (MTOW · g)",
            status=_status(tw, 0.15, 1.20),
            typical_range="0.15 (低速UAV) ~ 1.2 (战斗机)",
            message="推力与起飞重量之比,决定爬升与机动性",
        ))
    else:
        metrics.append(ExtendedMetric(
            metric_id="thrust_to_weight",
            category="loading",
            label="推重比",
            value=0.0,
            unit="",
            confidence="low",
            method="未提供 mission.thrust",
            status="unusual",
            typical_range="0.15 ~ 1.2",
            message="补充 mission.thrust (单位 N) 后可计算",
        ))

    return metrics


# ---------------------------------------------------------------------------
# Stealth metrics
# ---------------------------------------------------------------------------

def _projected_areas(
    fuselage_length: float,
    fuselage_diameter: float,
    wing_span: float,
    wing_area: float,
) -> tuple[float, float, float]:
    frontal = math.pi * (fuselage_diameter / 2.0) ** 2 + wing_span * 0.05
    side = fuselage_length * fuselage_diameter
    top = fuselage_length * fuselage_diameter * 0.6 + wing_area
    return frontal, side, top


def _estimate_rcs(
    frontal_area: float,
    material: str,
    shaping: str,
) -> float:
    base = max(frontal_area, 0.01)
    mat_factor = RCS_MATERIAL_FACTOR.get(material, 1.0)
    shape_factor = RCS_SHAPING_FACTOR.get(shaping, 1.0)
    return base * mat_factor * shape_factor


def _stealth_score(rcs: float) -> tuple[float, Status, str]:
    """Map RCS to a 0-100 low-observability score (higher = stealthier)."""
    if rcs <= 0.001:
        return 95.0, "reasonable", "极低可探测性 (准 LO 级)"
    if rcs <= 0.01:
        return 85.0, "reasonable", "高隐身水平"
    if rcs <= 0.1:
        return 65.0, "reasonable", "中等隐身"
    if rcs <= 1.0:
        return 40.0, "warning", "低隐身,常规涂装/外形"
    if rcs <= 10.0:
        return 20.0, "warning", "RCS 较高,无隐身设计"
    return 5.0, "unusual", "RCS 极高"


def _build_stealth_metrics(
    spec: AircraftSpec,
    fuselage_length: float,
    fuselage_diameter: float,
    wing_span: float,
    wing_area: float,
) -> list[ExtendedMetric]:
    stealth_block = getattr(spec, "stealth", None)
    material = _text(getattr(stealth_block, "material_class", None), "metal") if stealth_block else "metal"
    shaping = _text(getattr(stealth_block, "shaping_level", None), "none") if stealth_block else "none"
    target_rcs = _num(getattr(stealth_block, "frontal_rcs_target", None)) if stealth_block else None

    frontal, side, top = _projected_areas(fuselage_length, fuselage_diameter, wing_span, wing_area)
    rcs_est = _estimate_rcs(frontal, material, shaping)
    score, score_status, score_msg = _stealth_score(rcs_est)

    metrics: list[ExtendedMetric] = []
    metrics.append(ExtendedMetric(
        metric_id="frontal_projection_area",
        category="stealth",
        label="正向投影面积",
        value=frontal,
        unit="m²",
        confidence="medium",
        method="A_front = π·(D/2)² + 0.05·span (机身正面+机翼前缘等效)",
        status=_status(frontal, 0.05, 20.0),
        typical_range="0.05 ~ 20 m²",
        message="正向 RCS 主要由该面积及外形决定",
    ))
    metrics.append(ExtendedMetric(
        metric_id="side_projection_area",
        category="stealth",
        label="侧向投影面积",
        value=side,
        unit="m²",
        confidence="medium",
        method="A_side ≈ L_fuselage · D",
        status=_status(side, 0.5, 80.0),
        typical_range="0.5 ~ 80 m²",
        message="侧向投影,与侧向 RCS 相关",
    ))
    metrics.append(ExtendedMetric(
        metric_id="top_projection_area",
        category="stealth",
        label="俯视投影面积",
        value=top,
        unit="m²",
        confidence="medium",
        method="A_top ≈ 0.6·L·D + S_wing",
        status=_status(top, 1.0, 200.0),
        typical_range="1.0 ~ 200 m²",
        message="俯视投影,影响来自上方雷达的可探测性",
    ))

    rcs_method = (
        f"A_front × material({material})={RCS_MATERIAL_FACTOR.get(material, 1.0)} "
        f"× shaping({shaping})={RCS_SHAPING_FACTOR.get(shaping, 1.0)}"
    )
    metrics.append(ExtendedMetric(
        metric_id="rcs_estimate",
        category="stealth",
        label="正向 RCS 估算",
        value=rcs_est,
        unit="m²",
        confidence="low",
        method=rcs_method,
        status=_status(rcs_est, 0.001, 1.0) if rcs_est > 0 else "unusual",
        typical_range="0.001 (LO) ~ 10 (常规)",
        message="概念级 RCS 估算,仅用于方案对比,非工程级数据",
    ))

    if target_rcs is not None and target_rcs > 0:
        gap = rcs_est - target_rcs
        gap_status: Status = "reasonable" if gap <= 0 else ("warning" if gap <= target_rcs else "unusual")
        metrics.append(ExtendedMetric(
            metric_id="rcs_target_gap",
            category="stealth",
            label="RCS 目标差距",
            value=gap,
            unit="m²",
            confidence="low",
            method="rcs_estimate - frontal_rcs_target",
            status=gap_status,
            typical_range="≤ 0 表示满足目标",
            message="估算 RCS 已满足目标" if gap <= 0 else f"估算 RCS 高出目标 {gap:.3f} m²",
        ))

    metrics.append(ExtendedMetric(
        metric_id="low_observability_score",
        category="stealth",
        label="低可探测性评分",
        value=score,
        unit="/100",
        confidence="low",
        method="基于 RCS 估算的分段映射",
        status=score_status,
        typical_range="0 ~ 100 (越高越隐身)",
        message=score_msg,
    ))

    return metrics


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_extended_metrics(spec: AircraftSpec) -> ExtendedMetricsReport:
    report = ExtendedMetricsReport()

    fuselage_length = _num(spec.fuselage.length, 0.0) or 0.0
    fuselage_diameter = _num(getattr(spec.fuselage, "max_diameter", None), 0.75) or 0.0
    wing_span = _num(spec.wing.span, 0.0) or 0.0
    root_chord = _num(spec.wing.root_chord, 0.0) or 0.0
    tip_chord = _num(spec.wing.tip_chord, 0.0) or 0.0

    wing_area = _wing_area(root_chord, tip_chord, wing_span)
    fuselage_volume = _fuselage_volume(fuselage_length, fuselage_diameter)

    payload = _num(getattr(spec.mission, "payload", None), 0.0) or 0.0

    user_mtow = _num(getattr(spec.mission, "mtow", None))
    if user_mtow and user_mtow > 0:
        mtow = user_mtow
        user_supplied_mtow = True
    elif payload > 0:
        mtow = payload / PAYLOAD_FRACTION_DEFAULT
        user_supplied_mtow = False
    else:
        mtow = 0.0
        user_supplied_mtow = False

    user_empty = _num(getattr(spec.mission, "empty_weight", None))
    empty_weight = user_empty if user_empty and user_empty > 0 else EMPTY_FRACTION_DEFAULT * mtow

    user_fuel = _num(getattr(spec.mission, "fuel_weight", None))
    if user_fuel and user_fuel > 0:
        fuel_weight = user_fuel
    else:
        fuel_weight = max(mtow - empty_weight - payload, 0.0)

    fuel_volume = _fuel_volume_from_weight(fuel_weight)

    payload_bay_length = _num(getattr(spec.fuselage, "payload_bay_length", None))
    payload_bay_diameter = _num(getattr(spec.fuselage, "payload_bay_diameter", None))
    payload_bay_volume = _payload_bay_volume(payload_bay_length, payload_bay_diameter)

    thrust_n = _num(getattr(spec.mission, "thrust", None), 0.0) or 0.0

    report.metrics.extend(_build_volume_metrics(spec, fuselage_volume, payload_bay_volume, fuel_volume))
    report.metrics.extend(_build_loading_metrics(
        mtow, empty_weight, fuel_weight, payload, thrust_n, user_supplied_mtow,
    ))
    report.metrics.extend(_build_stealth_metrics(
        spec, fuselage_length, fuselage_diameter, wing_span, wing_area,
    ))

    return report
