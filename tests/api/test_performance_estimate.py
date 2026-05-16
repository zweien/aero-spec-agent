"""Tests for performance_estimate module."""

import pytest

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.performance_estimate import (
    run_performance_estimate,
)


def _s(value, unit=None, source="user", confidence=0.9):
    """Build a scalar dict with required source/confidence fields."""
    d = {"value": value, "source": source, "confidence": confidence}
    if unit is not None:
        d["unit"] = unit
    return d


def _make_spec(**overrides: object) -> AircraftSpec:
    defaults = {
        "schema_version": "0.1",
        "aircraft": {"name": "test", "type": "fixed_wing_uav", "layout": "conventional"},
        "fuselage": {"length": _s(7, "m"), "max_diameter": _s(0.75, "m")},
        "wing": {
            "span": _s(12, "m"),
            "root_chord": _s(1.2, "m"),
            "tip_chord": _s(0.6, "m"),
            "position": _s("mid"),
        },
        "tail": {"type": _s("conventional")},
        "engine": {"count": _s(2)},
    }
    for key, val in overrides.items():
        if isinstance(val, dict):
            defaults[key] = {**defaults.get(key, {}), **val}
        else:
            defaults[key] = val
    return AircraftSpec(**defaults)


class TestLayer2Aerodynamic:
    def test_wing_area(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "wing_area")
        # 12 * (1.2 + 0.6) / 2 = 10.8
        assert e.value == pytest.approx(10.8, abs=0.01)
        assert e.confidence == "high"
        assert e.status == "reasonable"

    def test_mac(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "mac")
        # t=0.5, MAC = (2/3)*1.2*(1+0.5+0.25)/(1+0.5) = 0.8*1.75/1.5 ≈ 0.933
        assert e.value == pytest.approx(0.933, abs=0.01)
        assert e.unit == "m"

    def test_aspect_ratio(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "aspect_ratio_perf")
        # 12² / 10.8 ≈ 13.33
        assert e.value == pytest.approx(13.33, abs=0.1)

    def test_taper_ratio(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "taper_ratio_perf")
        # 0.6 / 1.2 = 0.5
        assert e.value == pytest.approx(0.5, abs=0.01)

    def test_cl_max_default(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "cl_max")
        assert e.value == pytest.approx(1.4, abs=0.01)
        assert e.confidence == "medium"

    def test_cd0_mid(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "cd0")
        assert e.value == pytest.approx(0.030, abs=0.001)

    def test_cd0_high_wing(self):
        report = run_performance_estimate(_make_spec(wing={"position": _s("high")}))
        e = _find(report, "cd0")
        assert e.value == pytest.approx(0.020, abs=0.001)

    def test_oswald_high_wing(self):
        report = run_performance_estimate(_make_spec(wing={"position": _s("high")}))
        e = _find(report, "oswald")
        assert e.value == pytest.approx(0.85, abs=0.01)

    def test_unusual_taper_ratio(self):
        report = run_performance_estimate(_make_spec(wing={"tip_chord": _s(0.05, "m")}))
        e = _find(report, "taper_ratio_perf")
        # 0.05/1.2 ≈ 0.042 — way outside 0.3-1.0
        assert e.status == "unusual"


class TestLayer3Weight:
    def test_mtow_unusual_without_payload(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "mtow")
        assert e.status == "unusual"
        assert e.value == 0

    def test_mtow_with_payload(self):
        spec = _make_spec(mission={"payload": _s(30, "kg"), "cruise_speed": _s(120, "km/h")})
        report = run_performance_estimate(spec)
        e = _find(report, "mtow")
        # 30 / 0.15 = 200
        assert e.value == pytest.approx(200, abs=1)
        assert e.status == "reasonable"

    def test_fuel_weight_chain(self):
        spec = _make_spec(mission={"payload": _s(30, "kg")})
        report = run_performance_estimate(spec)
        fuel = _find(report, "fuel_weight")
        # MTOW=200, empty=110, fuel=200-110-30=60
        assert fuel.value == pytest.approx(60, abs=1)
        assert fuel.status == "reasonable"


class TestLayer3Mission:
    def test_ld_cruise(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "ld_cruise")
        assert e.value > 0
        assert 8 <= e.value <= 18 or e.status != "reasonable"

    def test_range_without_payload(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "range_est")
        assert e.status == "unusual"

    def test_range_with_payload(self):
        spec = _make_spec(mission={"payload": _s(30, "kg"), "cruise_speed": _s(120, "km/h")})
        report = run_performance_estimate(spec)
        e = _find(report, "range_est")
        assert e.value > 0

    def test_wing_loading(self):
        spec = _make_spec(mission={"payload": _s(30, "kg")})
        report = run_performance_estimate(spec)
        e = _find(report, "wing_loading_mtow")
        # 200 / 10.8 ≈ 18.5 — slightly below 20
        assert e.value == pytest.approx(18.52, abs=1)

    def test_htail_volume(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "htail_volume")
        assert 0.3 <= e.value <= 0.8 or e.status in ("warning", "unusual")

    def test_vtail_volume(self):
        report = run_performance_estimate(_make_spec())
        e = _find(report, "vtail_volume")
        assert 0.02 <= e.value <= 0.08 or e.status in ("warning", "unusual")


class TestReport:
    def test_to_dict_structure(self):
        report = run_performance_estimate(_make_spec())
        d = report.to_dict()
        assert "estimates" in d
        assert "summary" in d
        assert len(d["estimates"]) == 16
        first = d["estimates"][0]
        for key in ("estimate_id", "label", "value", "unit", "confidence", "method", "status", "typical_range", "message"):
            assert key in first

    def test_summary_counts(self):
        report = run_performance_estimate(_make_spec())
        s = report.summary
        total = s["reasonable"] + s["warning"] + s["unusual"]
        assert total == 16


def _find(report, estimate_id: str):
    for e in report.estimates:
        if e.estimate_id == estimate_id:
            return e
    pytest.fail(f"estimate {estimate_id} not found")
