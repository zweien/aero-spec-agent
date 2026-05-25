import math

import pytest

from services.api.app.schemas.aircraft_spec import (
    Aircraft,
    AircraftSpec,
    Engine,
    Fuselage,
    IntegerScalar,
    Mission,
    NumericScalar,
    TextScalar,
    Tail,
    Wing,
)
from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
    AeroPoint,
    VspaeroReport,
    _compute_optimal_ld,
    _fit_cd0,
    _fit_cl_alpha,
    build_analysis_geoms,
    fake_vspaero_results,
)
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult


def _make_spec(**overrides) -> AircraftSpec:
    defaults = {
        "schema_version": "0.1",
        "aircraft": Aircraft(name="test_uav", type="fixed_wing_uav", layout="conventional"),
        "mission": Mission(
            cruise_speed=NumericScalar(value=150, unit="km/h", source="rule_default", confidence=0.7),
            payload=NumericScalar(value=30, unit="kg", source="rule_default", confidence=0.7),
            priority=TextScalar(value="endurance", source="rule_default", confidence=0.7),
        ),
        "fuselage": Fuselage(
            length=NumericScalar(value=4.5, unit="m", source="rule_default", confidence=0.7),
            max_diameter=NumericScalar(value=0.5, unit="m", source="rule_default", confidence=0.7),
        ),
        "wing": Wing(
            position=TextScalar(value="high", source="user", confidence=1.0),
            span=NumericScalar(value=10, unit="m", source="user", confidence=1.0),
            root_chord=NumericScalar(value=1.2, unit="m", source="inferred", confidence=0.75),
            tip_chord=NumericScalar(value=0.6, unit="m", source="inferred", confidence=0.75),
        ),
        "tail": Tail(type=TextScalar(value="conventional", source="user", confidence=1.0)),
        "engine": Engine(
            count=IntegerScalar(value=2, source="user", confidence=1.0),
            position=TextScalar(value="under_wing", source="inferred", confidence=0.8),
        ),
    }
    defaults.update(overrides)
    return AircraftSpec(**defaults)


class TestAeroPoint:
    def test_to_dict(self):
        pt = AeroPoint(alpha=2.0, cl=0.5, cd=0.02, cm=-0.05, mach=0.0, beta=0.0)
        d = pt.to_dict()
        assert d["alpha"] == 2.0
        assert d["cl"] == 0.5
        assert len(d) == 6


class TestVspaeroReport:
    def test_to_dict_structure(self):
        sweep = [AeroPoint(alpha=0, cl=0.1, cd=0.025, cm=0.0, mach=0.0, beta=0.0)]
        report = VspaeroReport(
            status="success",
            method="VSPAERO_panel",
            alpha_sweep=sweep,
            optimal_ld=20.0,
            optimal_cl=0.5,
            optimal_alpha=3.0,
            cl_alpha=5.2,
            cd0_estimate=0.025,
        )
        d = report.to_dict()
        assert d["status"] == "success"
        assert d["method"] == "VSPAERO_panel"
        assert len(d["alpha_sweep"]) == 1
        assert d["optimal_ld"] == 20.0
        assert d["cl_alpha"] == 5.2
        assert d["cd0_estimate"] == 0.025
        assert "error_message" not in d

    def test_to_dict_with_error(self):
        report = VspaeroReport(
            status="failed",
            method="VSPAERO_panel",
            error_message="timeout",
        )
        d = report.to_dict()
        assert d["status"] == "failed"
        assert d["error_message"] == "timeout"


class TestOptimalLd:
    def test_finds_best_cl_cd(self):
        sweep = [
            AeroPoint(alpha=0, cl=0.0, cd=0.025, cm=0.0, mach=0.0, beta=0.0),
            AeroPoint(alpha=2, cl=0.4, cd=0.02, cm=-0.01, mach=0.0, beta=0.0),
            AeroPoint(alpha=4, cl=0.8, cd=0.03, cm=-0.02, mach=0.0, beta=0.0),
        ]
        ld, cl, alpha = _compute_optimal_ld(sweep)
        assert ld == pytest.approx(0.8 / 0.03)
        assert cl == pytest.approx(0.8)
        assert alpha == pytest.approx(4.0)

    def test_zero_cd_handled(self):
        sweep = [AeroPoint(alpha=0, cl=0.1, cd=0.0, cm=0.0, mach=0.0, beta=0.0)]
        ld, cl, alpha = _compute_optimal_ld(sweep)
        assert ld == 0.0


class TestClAlphaFit:
    def test_linear_region(self):
        sweep = [
            AeroPoint(alpha=a, cl=0.1 * a, cd=0.02, cm=0.0, mach=0.0, beta=0.0)
            for a in range(-2, 7)
        ]
        result = _fit_cl_alpha(sweep)
        assert result is not None
        assert result == pytest.approx(0.1, abs=0.01)

    def test_insufficient_data(self):
        sweep = [AeroPoint(alpha=10, cl=1.0, cd=0.05, cm=0.0, mach=0.0, beta=0.0)]
        assert _fit_cl_alpha(sweep) is None


class TestCd0Fit:
    def test_parabolic_drag(self):
        cd0_true = 0.025
        k = 0.05
        sweep = [
            AeroPoint(
                alpha=a,
                cl=0.1 * a,
                cd=cd0_true + k * (0.1 * a) ** 2,
                cm=0.0,
                mach=0.0,
                beta=0.0,
            )
            for a in range(1, 8)
        ]
        result = _fit_cd0(sweep)
        assert result is not None
        assert result == pytest.approx(cd0_true, abs=0.005)

    def test_insufficient_data(self):
        sweep = [AeroPoint(alpha=0, cl=0.0, cd=0.02, cm=0.0, mach=0.0, beta=0.0)]
        assert _fit_cd0(sweep) is None


class TestFakeVspaeroResults:
    def test_generates_valid_structure(self):
        spec = _make_spec()
        result = fake_vspaero_results(spec)
        assert result["status"] == "success"
        assert result["method"] == "fake_vspaero"
        assert len(result["alpha_sweep"]) == 17
        assert result["optimal_ld"] > 0
        assert result["cl_alpha"] > 0
        assert result["cd0_estimate"] > 0

    def test_sweep_cl_increases_with_alpha(self):
        spec = _make_spec()
        result = fake_vspaero_results(spec)
        sweep = result["alpha_sweep"]
        for i in range(1, len(sweep)):
            if sweep[i]["alpha"] > 0 and sweep[i - 1]["alpha"] > 0:
                assert sweep[i]["cl"] >= sweep[i - 1]["cl"]

    def test_respects_spec_dimensions(self):
        small = _make_spec(
            wing=Wing(
                position=TextScalar(value="high", source="user", confidence=1.0),
                span=NumericScalar(value=5, unit="m", source="user", confidence=1.0),
                root_chord=NumericScalar(value=0.6, unit="m", source="inferred", confidence=0.75),
                tip_chord=NumericScalar(value=0.3, unit="m", source="inferred", confidence=0.75),
            ),
        )
        result_small = fake_vspaero_results(small)
        big = _make_spec(
            wing=Wing(
                position=TextScalar(value="high", source="user", confidence=1.0),
                span=NumericScalar(value=20, unit="m", source="user", confidence=1.0),
                root_chord=NumericScalar(value=2.0, unit="m", source="inferred", confidence=0.75),
                tip_chord=NumericScalar(value=1.0, unit="m", source="inferred", confidence=0.75),
            ),
        )
        result_big = fake_vspaero_results(big)
        assert result_small["cl_alpha"] < result_big["cl_alpha"]


class TestRunVspaeroHandlesError:
    def test_adapter_failure(self):
        class FailAdapter:
            def set_vspaero_ref_wing(self, wing_id):
                pass

            def write_vsp_file(self, path):
                pass

            def set_analysis_input_defaults(self, name):
                pass

            def set_int_analysis_input(self, name, key, vals, index=0):
                pass

            def set_double_analysis_input(self, name, key, vals):
                pass

            def exec_analysis(self, name):
                raise RuntimeError("VSPAERO not installed")

            def default_set_id(self):
                return 0

            def find_latest_results_id(self, name):
                return ""

            def create_set(self, name):
                return 1

            def add_to_set(self, set_id, geom_id):
                pass

        from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
            run_vspaero_analysis,
        )

        spec = _make_spec()
        with pytest.raises(RuntimeError, match="VSPAERO not installed"):
            run_vspaero_analysis(FailAdapter(), spec, "wing-1")


def _mock_results(names: list[str]) -> list[GeometryBuildResult]:
    return [GeometryBuildResult(name=n, geom_id=f"id-{n}") for n in names]


class TestBuildAnalysisGeoms:
    def test_conventional_returns_main_wing_only(self):
        spec = _make_spec()
        results = _mock_results(["fuselage", "main_wing", "horizontal_tail", "vertical_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_twin_boom_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="twin_boom"))
        results = _mock_results(["fuselage", "main_wing", "horizontal_tail", "left_boom", "right_boom"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_flying_wing_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="flying_wing"))
        results = _mock_results(["main_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_blended_wing_body_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="blended_wing_body"))
        results = _mock_results(["flat_body", "main_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_canard_returns_main_wing_and_canard(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="canard"))
        results = _mock_results(["fuselage", "main_wing", "canard", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-canard"]

    def test_three_surface_returns_main_wing_and_canard(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="three_surface"))
        results = _mock_results(["fuselage", "main_wing", "canard", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-canard"]

    def test_tandem_wing_returns_main_wing_and_rear_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="tandem_wing"))
        results = _mock_results(["fuselage", "main_wing", "rear_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-rear_wing"]

    def test_joined_wing_returns_main_wing_and_rear_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="joined_wing"))
        results = _mock_results(["fuselage", "main_wing", "rear_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-rear_wing"]

    def test_biplane_returns_main_wing_and_lower_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="biplane"))
        results = _mock_results(["fuselage", "main_wing", "lower_wing", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-lower_wing"]

    def test_box_wing_returns_main_wing_and_box_lower_wing(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="box_wing"))
        results = _mock_results(["fuselage", "main_wing", "box_lower_wing", "left_endplate", "right_endplate", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing", "id-box_lower_wing"]

    def test_multi_fuselage_returns_main_wing_only(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="multi_fuselage"))
        results = _mock_results(["left_fuselage", "right_fuselage", "main_wing", "horizontal_tail"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_missing_component_skipped_gracefully(self):
        spec = _make_spec(aircraft=Aircraft(name="t", type="fixed_wing_uav", layout="canard"))
        results = _mock_results(["fuselage", "main_wing"])  # no canard
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]

    def test_unknown_layout_returns_main_wing_only(self):
        spec = _make_spec()  # conventional
        results = _mock_results(["fuselage", "main_wing"])
        geom_ids = build_analysis_geoms(spec, results)
        assert geom_ids == ["id-main_wing"]
