"""Tests for DesignMetrics computation."""

import math

import pytest

from services.api.app.services.design_metrics import compute_design_metrics


def _spec(
    span=12.0,
    root_chord=1.5,
    tip_chord=0.75,
    fuse_length=8.0,
    mtow=None,
    engines=None,
) -> dict:
    """Build a minimal spec dict for testing."""
    s: dict = {
        "wing": {
            "span": {"value": span, "unit": "m"},
            "root_chord": {"value": root_chord, "unit": "m"},
            "tip_chord": {"value": tip_chord, "unit": "m"},
        },
        "fuselage": {"length": {"value": fuse_length, "unit": "m"}},
    }
    if mtow is not None:
        s["performance"] = {"mtow": {"value": mtow, "unit": "kg"}}
    if engines is not None:
        s["engines"] = engines
    return s


class TestComputeDesignMetrics:
    def test_full_spec(self):
        m = compute_design_metrics(_spec(span=12, root_chord=1.5, tip_chord=0.75))
        assert m["wingspan_m"] == 12.0
        assert m["fuselage_length_m"] == 8.0
        # wing_area = 12 * (1.5 + 0.75) / 2 = 13.5
        assert abs(m["wing_area_m2"] - 13.5) < 0.01
        # AR = 12^2 / 13.5 = 10.67
        assert abs(m["aspect_ratio"] - 10.67) < 0.01
        # L/D = 8 + 10.67 * 0.7 = 15.47
        assert abs(m["estimated_lift_to_drag"] - 15.47) < 0.1
        assert m["risk_level"] == "low"
        assert m["confidence"] == "heuristic"

    def test_missing_chord_returns_none_area(self):
        m = compute_design_metrics(_spec(root_chord=None, tip_chord=None))
        assert m["wing_area_m2"] is None
        assert m["aspect_ratio"] is None
        assert m["estimated_lift_to_drag"] is None
        assert m["risk_level"] == "unknown"

    def test_defaulted_fields_medium_risk(self):
        fields = [{"field": f"field_{j}"} for j in range(5)]
        m = compute_design_metrics(_spec(), defaulted_fields=fields)
        assert m["risk_level"] == "medium"
        assert any("默认补全" in w for w in m["warnings"])

    def test_low_aspect_ratio_warning(self):
        # span=4, root_chord=2, tip_chord=1 → area=6, AR=2.67
        m = compute_design_metrics(_spec(span=4, root_chord=2, tip_chord=1))
        assert m["aspect_ratio"] is not None and m["aspect_ratio"] < 5
        assert m["risk_level"] == "medium"
        assert any("展弦比较低" in w for w in m["warnings"])

    def test_confidence_partial(self):
        m = compute_design_metrics({
            "wing": {"span": {"value": 10}},
            "fuselage": {"length": {"value": 5}},
        })
        assert m["confidence"] == "partial"

    def test_confidence_low(self):
        m = compute_design_metrics({"wing": {}, "fuselage": {}})
        assert m["confidence"] == "low"

    def test_no_nan_in_output(self):
        m = compute_design_metrics({"wing": {"span": {"value": 0}}, "fuselage": {}})
        for k, v in m.items():
            if isinstance(v, float):
                assert not math.isnan(v), f"{k} is NaN"

    def test_wing_loading(self):
        m = compute_design_metrics(_spec(span=10, root_chord=1, tip_chord=0.5, mtow=500))
        # area = 10 * (1 + 0.5) / 2 = 7.5
        # loading = 500 / 7.5 = 66.7
        assert m["wing_loading_kg_m2"] is not None
        assert abs(m["wing_loading_kg_m2"] - 66.7) < 0.5

    def test_thrust_to_weight(self):
        eng = [{"thrust": {"value": 500, "unit": "N"}}, {"thrust": {"value": 500, "unit": "N"}}]
        m = compute_design_metrics(_spec(span=10, root_chord=1, tip_chord=0.5, mtow=100, engines=eng))
        assert m["thrust_to_weight"] is not None
        # 1000 / (100 * 9.81) ≈ 1.02
        assert abs(m["thrust_to_weight"] - 1.02) < 0.05

    def test_range_endurance_null(self):
        m = compute_design_metrics(_spec())
        assert m["estimated_range_km"] is None
        assert m["estimated_endurance_h"] is None

    def test_plain_number_spec(self):
        """Spec fields can be plain numbers instead of {value: N} dicts."""
        m = compute_design_metrics({
            "wing": {"span": 12, "root_chord": 1.5, "tip_chord": 0.75},
            "fuselage": {"length": 8},
        })
        assert m["wingspan_m"] == 12.0
        assert abs(m["wing_area_m2"] - 13.5) < 0.01
