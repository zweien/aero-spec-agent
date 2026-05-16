"""Aircraft performance estimation (Layer 2: aerodynamic, Layer 3: weight & mission)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from services.api.app.schemas.aircraft_spec import AircraftSpec

Status = Literal["reasonable", "warning", "unusual"]
Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class EstimateResult:
    estimate_id: str
    label: str
    value: float
    unit: str
    confidence: Confidence
    method: str
    status: Status
    typical_range: str
    message: str


@dataclass
class PerformanceEstimateReport:
    estimates: list[EstimateResult] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {"reasonable": 0, "warning": 0, "unusual": 0}
        for e in self.estimates:
            counts[e.status] = counts.get(e.status, 0) + 1
        return counts

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimates": [
                {
                    "estimate_id": e.estimate_id,
                    "label": e.label,
                    "value": round(e.value, 6),
                    "unit": e.unit,
                    "confidence": e.confidence,
                    "method": e.method,
                    "status": e.status,
                    "typical_range": e.typical_range,
                    "message": e.message,
                }
                for e in self.estimates
            ],
            "summary": self.summary,
        }


def _num(spec_val: Any, fallback: float) -> float:
    v = getattr(spec_val, "value", spec_val)
    n = float(v) if v is not None else float("nan")
    return n if (n == n and n != 0) else fallback  # nan guard


def _text(spec_val: Any, fallback: str) -> str:
    v = getattr(spec_val, "value", None)
    return str(v).strip().lower() if v else fallback


def _status(value: float, lo: float, hi: float) -> Status:
    if lo <= value <= hi:
        return "reasonable"
    if lo * 0.7 <= value <= hi * 1.3:
        return "warning"
    return "unusual"


# ---------------------------------------------------------------------------
# Layer 2 – aerodynamic estimates (high confidence, direct from spec)
# ---------------------------------------------------------------------------

def _wing_area(root_chord: float, tip_chord: float, span: float) -> float:
    return span * (root_chord + tip_chord) / 2


def _mac(root_chord: float, tip_chord: float) -> float:
    t = tip_chord / root_chord if root_chord else 0
    return (2 / 3) * root_chord * (1 + t + t * t) / (1 + t) if (1 + t) else 0


def _aspect_ratio(span: float, area: float) -> float:
    return span * span / area if area else 0


def _taper_ratio(root_chord: float, tip_chord: float) -> float:
    return tip_chord / root_chord if root_chord else 0


def _cl_max(airfoil: str) -> tuple[float, Confidence]:
    if airfoil and "naca" in airfoil:
        return 1.4, "high"
    return 1.4, "medium"


def _cd0(position: str) -> float:
    if position == "high":
        return 0.020
    if position == "low":
        return 0.025
    return 0.030


def _oswald(position: str) -> float:
    if position == "high":
        return 0.85
    if position == "low":
        return 0.80
    return 0.78


# ---------------------------------------------------------------------------
# Layer 3 – weight estimates (medium confidence, empirical formulas)
# ---------------------------------------------------------------------------

SFC_KG_WS = 8.5e-5  # ~0.5 lb/(hp·hr) in kg/(W·s)
PAYLOAD_FRACTION = 0.15
EMPTY_FRACTION = 0.55
CRUISE_SPEED_DEFAULT = 100 / 3.6  # 100 km/h → m/s


def _mtow(payload: float | None) -> tuple[float, Confidence, Status]:
    if payload is None or payload <= 0:
        return 0, "low", "unusual"
    mtow = payload / PAYLOAD_FRACTION
    conf: Confidence = "medium"
    st = _status(mtow, 50, 500)
    return mtow, conf, st


def _empty_weight(mtow: float) -> float:
    return EMPTY_FRACTION * mtow


def _fuel_weight(mtow: float, empty: float, payload: float) -> tuple[float, Status]:
    fuel = mtow - empty - payload
    if fuel <= 0:
        return 0, "unusual"
    return fuel, "reasonable"


# ---------------------------------------------------------------------------
# Layer 3 – mission performance (low/medium confidence, chain estimates)
# ---------------------------------------------------------------------------

def _ld_cruise(cl_cruise: float, cd0: float, ar: float, e: float) -> float:
    cd_ind = cl_cruise * cl_cruise / (3.14159265 * ar * e) if (ar * e) else 0
    cd = cd0 + cd_ind
    return cl_cruise / cd if cd else 0


def _range_est(v: float, sfc: float, ld: float, wi: float, wf: float) -> float:
    if wf <= 0 or wi <= wf:
        return 0
    return (v / sfc) * ld * _ln_ratio(wi, wf)


def _endurance_est(sfc: float, ld: float, wi: float, wf: float) -> float:
    if wf <= 0 or wi <= wf:
        return 0
    return (1 / sfc) * ld * _ln_ratio(wi, wf)


def _ln_ratio(wi: float, wf: float) -> float:
    import math
    r = wi / wf
    return math.log(r) if r > 1 else 0


def _wing_loading(mtow: float, area: float) -> float:
    return mtow / area if area else 0


def _htail_volume(
    tail_span: float, tail_chord: float, tail_arm: float,
    wing_area: float, mac: float,
) -> float:
    sh = tail_span * tail_chord
    return sh * tail_arm / (wing_area * mac) if (wing_area * mac) else 0


def _vtail_volume(
    tail_span: float, tail_chord: float, tail_arm: float,
    wing_area: float, wing_span: float,
) -> float:
    sv = tail_span * tail_chord
    return sv * tail_arm / (wing_area * wing_span) if (wing_area * wing_span) else 0


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_performance_estimate(spec: AircraftSpec) -> PerformanceEstimateReport:
    report = PerformanceEstimateReport()

    # -- extract spec values --
    fuselage_length = _num(spec.fuselage.length, 7)
    fuselage_diameter = _num(spec.fuselage.max_diameter, 0.75)
    wing_span = _num(spec.wing.span, 12)
    root_chord = _num(spec.wing.root_chord, 1.2)
    tip_chord = _num(spec.wing.tip_chord, 0.6)
    engine_count = max(0, round(_num(spec.engine.count, 0)))
    position = _text(spec.wing.position, "mid")

    # mission fields (may be absent)
    payload_raw = getattr(spec, "mission", None)
    payload_val = None
    if payload_raw:
        payload_val = _num(getattr(payload_raw, "payload", None), 0)
        if payload_val == 0:
            payload_val = None
    cruise_speed_raw = getattr(spec, "mission", None)
    cruise_speed = CRUISE_SPEED_DEFAULT
    if cruise_speed_raw:
        cs = _num(getattr(cruise_speed_raw, "cruise_speed", None), 0)
        if cs > 0:
            cruise_speed = cs / 3.6  # km/h → m/s

    airfoil_raw = getattr(spec.wing, "airfoil", None)
    airfoil = _text(airfoil_raw, "") if airfoil_raw else ""

    # ---- Layer 2: Aerodynamic ----
    area = _wing_area(root_chord, tip_chord, wing_span)
    mac_val = _mac(root_chord, tip_chord)
    ar = _aspect_ratio(wing_span, area)
    tr = _taper_ratio(root_chord, tip_chord)
    cl_max, cl_conf = _cl_max(airfoil)
    cd0 = _cd0(position)
    oswald_e = _oswald(position)

    report.estimates.append(EstimateResult(
        estimate_id="wing_area", label="机翼面积", value=area, unit="m²",
        confidence="high", method="S = span × (cr + ct) / 2",
        status=_status(area, 3, 50), typical_range="3.0 ~ 50.0 m²",
        message="基于机翼几何参数直接计算",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="mac", label="平均气动弦长", value=mac_val, unit="m",
        confidence="high", method="MAC = (2/3)·cr·(1+t+t²)/(1+t)",
        status=_status(mac_val, 0.3, 3.0), typical_range="0.3 ~ 3.0 m",
        message="标准梯形翼 MAC 公式",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="aspect_ratio_perf", label="展弦比", value=ar, unit="",
        confidence="high", method="AR = span² / S",
        status=_status(ar, 6, 20), typical_range="6 ~ 20",
        message="基于机翼面积和展长",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="taper_ratio_perf", label="梢根比", value=tr, unit="",
        confidence="high", method="t = ct / cr",
        status=_status(tr, 0.3, 1.0), typical_range="0.3 ~ 1.0",
        message="翼尖弦长与翼根弦长之比",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="cl_max", label="最大升力系数", value=cl_max, unit="",
        confidence=cl_conf, method="NACA 4位翼型典型值",
        status=_status(cl_max, 1.0, 2.0), typical_range="1.0 ~ 2.0",
        message="基于翼型类型经验值" + (" (已知翼型)" if airfoil else " (未指定翼型, 使用默认值)"),
    ))
    report.estimates.append(EstimateResult(
        estimate_id="cd0", label="零升阻力系数", value=cd0, unit="",
        confidence="medium", method="经验值: 上单翼0.020, 下单翼0.025, 中单翼0.030",
        status=_status(cd0, 0.015, 0.045), typical_range="0.015 ~ 0.045",
        message=f"基于机翼位置({position})的经验估计",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="oswald", label="奥斯沃尔德效率", value=oswald_e, unit="",
        confidence="medium", method="经验值: 上单翼直翼0.85, 其他0.78~0.80",
        status=_status(oswald_e, 0.7, 0.9), typical_range="0.7 ~ 0.9",
        message=f"基于机翼位置({position})的经验估计",
    ))

    # ---- Layer 3: Weight estimates ----
    mtow_val, mtow_conf, mtow_status = _mtow(payload_val)
    empty_val = _empty_weight(mtow_val)
    fuel_val, fuel_status = _fuel_weight(mtow_val, empty_val, payload_val or 0)

    report.estimates.append(EstimateResult(
        estimate_id="mtow", label="最大起飞重量", value=mtow_val, unit="kg",
        confidence=mtow_conf,
        method="MTOW = payload / 0.15 (UAV载荷比10-20%)",
        status=mtow_status, typical_range="50 ~ 500 kg",
        message="基于载荷比经验值估算" if payload_val else "缺少载荷数据, 无法估算",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="empty_weight", label="空机重量", value=empty_val, unit="kg",
        confidence="medium" if payload_val else "low",
        method="We = 0.55 × MTOW (小型固定翼UAV经验值)",
        status="reasonable" if mtow_val > 0 else "unusual",
        typical_range="—",
        message="基于小型固定翼UAV统计比例" if mtow_val > 0 else "缺少MTOW数据",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="fuel_weight", label="燃油重量", value=fuel_val, unit="kg",
        confidence="medium" if fuel_val > 0 else "low",
        method="Wf = MTOW - We - payload",
        status=fuel_status, typical_range="> 0 kg",
        message="由重量平衡计算" if fuel_val > 0 else "燃油重量为负, 参数不合理",
    ))

    # ---- Layer 3: Mission performance ----
    cl_cruise = 0.6 * cl_max  # 巡航升力系数约为 CLmax 的 60%
    ld = _ld_cruise(cl_cruise, cd0, ar, oswald_e)

    report.estimates.append(EstimateResult(
        estimate_id="ld_cruise", label="巡航升阻比", value=ld, unit="",
        confidence="medium",
        method="CL_cruise / (CD0 + CL²/(π·AR·e))",
        status=_status(ld, 8, 18), typical_range="8 ~ 18",
        message=f"基于气动参数链式估算",
    ))

    wi = mtow_val
    wf = empty_val + (payload_val or 0)
    range_km = _range_est(cruise_speed, SFC_KG_WS, ld, wi, wf) / 1000
    endurance_h = _endurance_est(SFC_KG_WS, ld, wi, wf) / 3600

    report.estimates.append(EstimateResult(
        estimate_id="range_est", label="航程", value=range_km, unit="km",
        confidence="low" if range_km <= 0 else "medium",
        method="Breguet: R = (V/SFC)·(L/D)·ln(Wi/Wf)",
        status=_status(range_km, 100, 3000) if range_km > 0 else "unusual",
        typical_range="100 ~ 3000 km",
        message="Breguet航程公式链式估算" if range_km > 0 else "缺少重量数据, 无法估算航程",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="endurance_est", label="续航时间", value=endurance_h, unit="h",
        confidence="low" if endurance_h <= 0 else "medium",
        method="E = (1/SFC)·(L/D)·ln(Wi/Wf)",
        status=_status(endurance_h, 2, 30) if endurance_h > 0 else "unusual",
        typical_range="2 ~ 30 h",
        message="续航公式链式估算" if endurance_h > 0 else "缺少重量数据, 无法估算续航",
    ))

    wl = _wing_loading(mtow_val, area)
    report.estimates.append(EstimateResult(
        estimate_id="wing_loading_mtow", label="翼载荷(MTOW)", value=wl, unit="kg/m²",
        confidence="medium" if mtow_val > 0 else "low",
        method="MTOW / S",
        status=_status(wl, 20, 120) if wl > 0 else "unusual",
        typical_range="20 ~ 120 kg/m²",
        message="基于机翼面积和MTOW" if wl > 0 else "缺少MTOW数据",
    ))

    # Tail volumes — reuse geometry proportions from threePreviewModel.ts
    htail_span = wing_span * 0.28
    htail_chord = root_chord * 0.45
    vtail_span = wing_span * 0.16
    vtail_chord = root_chord * 0.55
    tail_arm = fuselage_length * 0.90 - fuselage_length * 0.40  # lever arm

    vh = _htail_volume(htail_span, htail_chord, tail_arm, area, mac_val)
    vv = _vtail_volume(vtail_span, vtail_chord, tail_arm, area, wing_span)

    report.estimates.append(EstimateResult(
        estimate_id="htail_volume", label="水平尾容量", value=vh, unit="",
        confidence="medium",
        method="Vh = Sh·lh / (S·MAC), 比例来自参数化模型",
        status=_status(vh, 0.3, 0.8), typical_range="0.3 ~ 0.8",
        message="基于参数化模型尾翼比例估算",
    ))
    report.estimates.append(EstimateResult(
        estimate_id="vtail_volume", label="垂直尾容量", value=vv, unit="",
        confidence="medium",
        method="Vv = Sv·lv / (S·span), 比例来自参数化模型",
        status=_status(vv, 0.02, 0.08), typical_range="0.02 ~ 0.08",
        message="基于参数化模型尾翼比例估算",
    ))

    return report
