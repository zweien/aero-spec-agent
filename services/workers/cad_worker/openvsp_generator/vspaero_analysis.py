from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Literal

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


@dataclass(frozen=True)
class AeroPoint:
    alpha: float
    cl: float
    cd: float
    cm: float
    mach: float
    beta: float

    def to_dict(self) -> dict[str, float]:
        return {
            "alpha": self.alpha,
            "cl": self.cl,
            "cd": self.cd,
            "cm": self.cm,
            "mach": self.mach,
            "beta": self.beta,
        }


@dataclass
class VspaeroReport:
    status: Literal["success", "skipped", "failed"]
    method: str
    alpha_sweep: list[AeroPoint] = field(default_factory=list)
    cruise_point: AeroPoint | None = None
    optimal_ld: float = 0.0
    optimal_cl: float = 0.0
    optimal_alpha: float = 0.0
    cl_alpha: float | None = None
    cd0_estimate: float | None = None
    span_load: list[dict[str, float]] = field(default_factory=list)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "status": self.status,
            "method": self.method,
            "optimal_ld": self.optimal_ld,
            "optimal_cl": self.optimal_cl,
            "optimal_alpha": self.optimal_alpha,
            "alpha_sweep": [p.to_dict() for p in self.alpha_sweep],
            "span_load": self.span_load,
        }
        if self.cruise_point is not None:
            d["cruise_point"] = self.cruise_point.to_dict()
        if self.cl_alpha is not None:
            d["cl_alpha"] = self.cl_alpha
        if self.cd0_estimate is not None:
            d["cd0_estimate"] = self.cd0_estimate
        if self.error_message is not None:
            d["error_message"] = self.error_message
        return d


LAYOUT_ANALYSIS_NAMES: dict[str, list[str]] = {
    "conventional": [],
    "twin_boom": [],
    "flying_wing": [],
    "blended_wing_body": [],
    "canard": ["canard"],
    "three_surface": ["canard"],
    "tandem_wing": ["rear_wing"],
    "joined_wing": ["rear_wing"],
    "biplane": ["lower_wing"],
    "box_wing": ["box_lower_wing"],
    "multi_fuselage": [],
}


def build_analysis_geoms(
    spec: AircraftSpec,
    build_results: list[GeometryBuildResult],
) -> list[str]:
    """Return geom IDs to include in VSPAERO analysis based on layout."""
    layout = spec.aircraft.layout.lower()
    extra_names = LAYOUT_ANALYSIS_NAMES.get(layout, [])
    components = {r.name: r.geom_id for r in build_results}
    geom_ids: list[str] = []
    if "main_wing" in components:
        geom_ids.append(components["main_wing"])
    for name in extra_names:
        if name in components:
            geom_ids.append(components[name])
    return geom_ids


def _cruise_mach(spec: AircraftSpec) -> float:
    speed_val = getattr(spec.mission, "cruise_speed", None)
    if speed_val is None:
        return 0.0
    speed = float(speed_val.value)
    unit = getattr(speed_val, "unit", None) or ""
    if isinstance(unit, str):
        unit_str = unit
    else:
        unit_str = getattr(unit, "value", str(unit))
    if unit_str == "m/s":
        pass
    else:
        speed /= 3.6
    mach = speed / 340.3
    return min(mach, 0.6)


def _compute_optimal_ld(sweep: list[AeroPoint]) -> tuple[float, float, float]:
    best_ld = 0.0
    best_cl = 0.0
    best_alpha = 0.0
    for pt in sweep:
        if pt.cd > 1e-8:
            ld = pt.cl / pt.cd
            if ld > best_ld:
                best_ld = ld
                best_cl = pt.cl
                best_alpha = pt.alpha
    return best_ld, best_cl, best_alpha


def _fit_cl_alpha(sweep: list[AeroPoint]) -> float | None:
    low = [(p.alpha, p.cl) for p in sweep if -2.0 <= p.alpha <= 6.0 and p.cl > -0.1]
    if len(low) < 3:
        return None
    n = len(low)
    sum_x = sum(a for a, _ in low)
    sum_y = sum(c for _, c in low)
    sum_xy = sum(a * c for a, c in low)
    sum_x2 = sum(a * a for a, _ in low)
    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-12:
        return None
    slope = (n * sum_xy - sum_x * sum_y) / denom
    return slope if slope > 0 else None


def _fit_cd0(sweep: list[AeroPoint]) -> float | None:
    positive = [(p.cl, p.cd) for p in sweep if p.cl > 0.01 and p.cd > 0]
    if len(positive) < 3:
        return None
    # Linear regression: CD = CD0 + k * CL^2
    # Treat x = CL^2, y = CD, fit y = a + b*x
    n = len(positive)
    xs = [cl * cl for cl, _ in positive]
    ys = [cd for _, cd in positive]
    sx = sum(xs)
    sy = sum(ys)
    sxy = sum(x * y for x, y in zip(xs, ys))
    sx2 = sum(x * x for x in xs)
    denom = n * sx2 - sx * sx
    if abs(denom) < 1e-12:
        return None
    cd0 = (sy * sx2 - sx * sxy) / denom
    cd0 = max(cd0, 0.0)
    return round(cd0, 6)


def run_vspaero_analysis(
    adapter: OpenVspAdapter,
    spec: AircraftSpec,
    wing_geom_id: str,
    *,
    alpha_range: tuple[float, float] = (-4.0, 12.0),
    alpha_step: float = 1.0,
    mach: float | None = None,
    output_dir: "Path | None" = None,
) -> VspaeroReport:
    import os
    from pathlib import Path

    adapter.set_vspaero_ref_wing(wing_geom_id)

    # VSPAERO requires a .vsp3 file on disk to determine output paths for
    # .vspgeom, .history, .polar etc.  Use output_dir (which already has
    # aircraft.vsp3 written by the backend) or fall back to a temp dir.
    if output_dir is not None:
        work_dir = str(output_dir)
        vsp_prefix = "aircraft"
    else:
        import tempfile
        work_dir = tempfile.mkdtemp(prefix="vspaero_")
        adapter.write_vsp_file(os.path.join(work_dir, "model.vsp3"))
        vsp_prefix = "model"

    orig_dir = os.getcwd()
    os.chdir(work_dir)
    try:
        # Step 1: generate geometry mesh.
        # Use Set_0 and only add the wing to avoid mesh issues with complex bodies.
        wing_set_id = adapter.create_set("Set_0")
        adapter.add_to_set(wing_set_id, wing_geom_id)

        geom_analysis = "VSPAEROComputeGeometry"
        adapter.set_analysis_input_defaults(geom_analysis)
        adapter.set_int_analysis_input(geom_analysis, "GeomSet", [wing_set_id])
        adapter.set_int_analysis_input(geom_analysis, "ThinGeomSet", [0])
        adapter.set_int_analysis_input(geom_analysis, "Symmetry", [1])
        adapter.exec_analysis(geom_analysis)

        if not os.path.exists(f"{vsp_prefix}.vspgeom"):
            return VspaeroReport(status="failed", method="VSPAERO_panel", error_message="vspgeom generation failed")

        # Step 2: run aero sweep
        sweep_analysis = "VSPAEROSweep"
        adapter.set_analysis_input_defaults(sweep_analysis)
        adapter.set_int_analysis_input(sweep_analysis, "GeomSet", [wing_set_id])
        adapter.set_int_analysis_input(sweep_analysis, "ThinGeomSet", [0])
        adapter.set_int_analysis_input(sweep_analysis, "Symmetry", [1])

        num_alphas = int(round((alpha_range[1] - alpha_range[0]) / alpha_step)) + 1
        adapter.set_double_analysis_input(sweep_analysis, "AlphaStart", [alpha_range[0]])
        adapter.set_double_analysis_input(sweep_analysis, "AlphaEnd", [alpha_range[1]])
        adapter.set_int_analysis_input(sweep_analysis, "AlphaNpts", [num_alphas])

        mach_val = mach if mach is not None else _cruise_mach(spec)
        adapter.set_double_analysis_input(sweep_analysis, "MachStart", [mach_val])
        adapter.set_double_analysis_input(sweep_analysis, "MachEnd", [mach_val])
        adapter.set_int_analysis_input(sweep_analysis, "MachNpts", [1])

        adapter.set_double_analysis_input(sweep_analysis, "BetaStart", [0.0])
        adapter.set_double_analysis_input(sweep_analysis, "BetaEnd", [0.0])
        adapter.set_int_analysis_input(sweep_analysis, "BetaNpts", [1])

        adapter.set_int_analysis_input(sweep_analysis, "WakeNumIter", [3])
        adapter.set_int_analysis_input(sweep_analysis, "NCPU", [1])

        adapter.exec_analysis(sweep_analysis)

        # Results are stored under "VSPAERO_Polar", not the exec return value
        polar_id = adapter.find_latest_results_id("VSPAERO_Polar")
        if not polar_id:
            # Fallback: try VSPAERO_History if Polar is not available
            polar_id = adapter.find_latest_results_id("VSPAERO_History")
        if not polar_id:
            import logging
            vsp = adapter._module.vsp
            all_names = list(vsp.GetAllResultsNames())
            logging.getLogger(__name__).warning("VSPAERO_Polar not found. Available: %s", all_names)
            return VspaeroReport(status="failed", method="VSPAERO_panel", error_message="no polar results")

        cl_arr = adapter.get_double_results(polar_id, "CLtot")
        cd_arr = adapter.get_double_results(polar_id, "CDtot")
        cm_arr = adapter.get_double_results(polar_id, "CMytot")
    finally:
        os.chdir(orig_dir)
        if output_dir is None:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)

    alphas = []
    a = alpha_range[0]
    while a <= alpha_range[1] + 1e-6:
        alphas.append(round(a, 2))
        a += alpha_step

    sweep: list[AeroPoint] = []
    count = min(len(alphas), len(cl_arr), len(cd_arr), len(cm_arr))
    for i in range(count):
        sweep.append(AeroPoint(
            alpha=alphas[i] if i < len(alphas) else 0.0,
            cl=cl_arr[i], cd=cd_arr[i], cm=cm_arr[i],
            mach=mach_val, beta=0.0,
        ))

    if not sweep:
        return VspaeroReport(status="failed", method="VSPAERO_panel", error_message="no results")

    optimal_ld, optimal_cl, optimal_alpha = _compute_optimal_ld(sweep)
    cl_alpha = _fit_cl_alpha(sweep)
    cd0_estimate = _fit_cd0(sweep)

    cruise_point: AeroPoint | None = None
    cruise_cl = 0.5
    closest = min(sweep, key=lambda p: abs(p.cl - cruise_cl))
    cruise_point = closest

    return VspaeroReport(
        status="success",
        method="VSPAERO_panel",
        alpha_sweep=sweep,
        cruise_point=cruise_point,
        optimal_ld=round(optimal_ld, 3),
        optimal_cl=round(optimal_cl, 4),
        optimal_alpha=round(optimal_alpha, 2),
        cl_alpha=round(cl_alpha, 4) if cl_alpha is not None else None,
        cd0_estimate=cd0_estimate,
    )


def fake_vspaero_results(spec: AircraftSpec) -> dict[str, Any]:
    span = float(spec.wing.span.value)
    root_chord = float(spec.wing.root_chord.value)
    tip_chord = float(spec.wing.tip_chord.value)
    area = span * (root_chord + tip_chord) / 2.0
    ar = span * span / area if area > 0 else 10.0
    e = 0.85
    cd0 = 0.025
    cl_alpha = round(2 * math.pi * ar / (ar + 2), 3)

    sweep: list[dict[str, Any]] = []
    for i in range(17):
        alpha = round(-4.0 + i * 1.0, 1)
        cl = round(cl_alpha * math.radians(alpha), 4)
        cd = round(cd0 + cl * cl / (math.pi * ar * e) if abs(cl) > 0.001 else cd0, 5)
        cm = round(-0.01 * alpha, 4)
        sweep.append({"alpha": alpha, "cl": cl, "cd": cd, "cm": cm, "mach": 0.0, "beta": 0.0})

    best = max(sweep, key=lambda p: p["cl"] / p["cd"] if p["cd"] > 1e-6 else 0)
    optimal_ld = round(best["cl"] / best["cd"], 3)

    return {
        "status": "success",
        "method": "fake_vspaero",
        "optimal_ld": optimal_ld,
        "optimal_cl": best["cl"],
        "optimal_alpha": best["alpha"],
        "cl_alpha": cl_alpha,
        "cd0_estimate": cd0,
        "alpha_sweep": sweep,
        "span_load": [],
    }
