from copy import deepcopy
from typing import Any

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.design_rules import (
    DesignRuleReport,
    DesignRuleResult,
    load_rules_config,
    run_design_rules,
)


def _spec_data() -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "aircraft": {
            "name": "test_uav",
            "type": "fixed_wing_uav",
            "layout": "conventional",
        },
        "mission": {
            "cruise_speed": {"value": 120, "unit": "km/h", "source": "user", "confidence": 1.0},
            "payload": {"value": 30, "unit": "kg", "source": "user", "confidence": 1.0},
            "priority": {"value": "endurance", "source": "user", "confidence": 0.9},
        },
        "fuselage": {
            "length": {"value": 7.0, "unit": "m", "source": "rule_default", "confidence": 0.8},
            "max_diameter": {"value": 0.75, "unit": "m", "source": "rule_default", "confidence": 0.8},
        },
        "wing": {
            "position": {"value": "high", "source": "user", "confidence": 1.0},
            "span": {"value": 12.0, "unit": "m", "source": "user", "confidence": 1.0},
            "root_chord": {"value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.8},
            "tip_chord": {"value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.8},
            "sweep": {"value": 5.0, "unit": "deg", "source": "rule_default", "confidence": 0.8},
            "dihedral": {"value": 3.0, "unit": "deg", "source": "rule_default", "confidence": 0.8},
        },
        "tail": {"type": {"value": "conventional", "source": "user", "confidence": 1.0}},
        "engine": {
            "count": {"value": 2, "source": "user", "confidence": 1.0},
            "position": {"value": "under_wing", "source": "inferred", "confidence": 0.75},
        },
    }


def _make_spec(**overrides: Any):
    data = _spec_data()
    for path, value in overrides.items():
        keys = path.split(".")
        obj = data
        for k in keys[:-1]:
            obj = obj[k]
        obj[keys[-1]] = value
    return load_aircraft_spec(data)


def _find_rule(report: DesignRuleReport, rule_id: str) -> DesignRuleResult:
    for r in report.rules:
        if r.rule_id == rule_id:
            return r
    raise AssertionError(f"Rule {rule_id!r} not found in report")


# -- config loading --


def test_load_config_returns_defaults():
    config = load_rules_config("fixed_wing_uav")
    assert "wing_span_range" in config
    assert config["wing_span_range"]["pass"] == [3.0, 30.0]


def test_load_config_fallback_when_missing(tmp_path, monkeypatch):
    import services.workers.cad_worker.openvsp_generator.design_rules as mod

    monkeypatch.setattr(mod, "_CONFIG_PATH", tmp_path / "nonexistent.yaml")
    config = load_rules_config()
    assert "wing_span_range" in config


# -- all pass for standard spec --


def test_all_rules_pass_for_standard_spec():
    spec = _make_spec()
    report = run_design_rules(spec)
    for r in report.rules:
        assert r.status in ("pass", "skip"), f"{r.rule_id}: {r.status} — {r.message}"


# -- wing_span_range --


def test_wing_span_too_large_fails():
    spec = _make_spec(**{"wing.span": {"value": 45.0, "unit": "m", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "wing_span_range")
    assert r.status == "fail"


def test_wing_span_boundary_warn():
    spec = _make_spec(**{"wing.span": {"value": 2.5, "unit": "m", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "wing_span_range")
    assert r.status == "warn"


def test_wing_span_at_upper_warn_boundary():
    spec = _make_spec(**{"wing.span": {"value": 35.0, "unit": "m", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "wing_span_range")
    assert r.status == "warn"


# -- fuselage_length_range --


def test_fuselage_too_short_fails():
    spec = _make_spec(**{"fuselage.length": {"value": 0.5, "unit": "m", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "fuselage_length_range")
    assert r.status == "fail"


def test_fuselage_warn_boundary():
    spec = _make_spec(**{"fuselage.length": {"value": 1.5, "unit": "m", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "fuselage_length_range")
    assert r.status == "warn"


# -- span_length_ratio --


def test_span_length_ratio_too_high():
    spec = _make_spec(
        **{
            "wing.span": {"value": 25.0, "unit": "m", "source": "user", "confidence": 1.0},
            "fuselage.length": {"value": 7.0, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "span_length_ratio")
    assert r.status == "fail"


def test_span_length_ratio_warn():
    spec = _make_spec(
        **{
            "wing.span": {"value": 20.0, "unit": "m", "source": "user", "confidence": 1.0},
            "fuselage.length": {"value": 7.0, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "span_length_ratio")
    assert r.status == "warn"


# -- aspect_ratio --


def test_aspect_ratio_too_low():
    spec = _make_spec(
        **{
            "wing.span": {"value": 5.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.root_chord": {"value": 2.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.tip_chord": {"value": 2.0, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "aspect_ratio")
    assert r.status == "fail"


def test_aspect_ratio_warn_high():
    # AR = span / mean_chord = 12 / 0.7 ≈ 17.1, in warn zone (15-20)
    spec = _make_spec(
        **{
            "wing.span": {"value": 12.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.root_chord": {"value": 0.8, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.tip_chord": {"value": 0.6, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "aspect_ratio")
    assert r.status == "warn"


# -- taper_ratio --


def test_taper_ratio_zero_root_chord():
    spec = _make_spec(
        **{
            "wing.root_chord": {"value": 0.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.tip_chord": {"value": 0.5, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "taper_ratio")
    assert r.status == "fail"
    assert "根弦长" in r.message


def test_taper_ratio_out_of_range():
    spec = _make_spec(
        **{
            "wing.root_chord": {"value": 1.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.tip_chord": {"value": 1.5, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "taper_ratio")
    assert r.status == "fail"


# -- engine_count --


def test_engine_count_invalid():
    data = _spec_data()
    data["engine"]["count"] = {"value": 3, "source": "user", "confidence": 1.0}
    data["engine"].pop("position", None)
    spec = load_aircraft_spec(data)
    r = _find_rule(run_design_rules(spec), "engine_count")
    assert r.status == "fail"


# -- engine_position --


def test_engine_position_mismatch():
    spec = _make_spec(
        **{
            "engine.count": {"value": 2, "source": "user", "confidence": 1.0},
            "engine.position": {"value": "nose", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "engine_position")
    assert r.status == "fail"


def test_engine_position_skip_when_absent():
    data = _spec_data()
    data["engine"].pop("position", None)
    spec = load_aircraft_spec(data)
    r = _find_rule(run_design_rules(spec), "engine_position")
    assert r.status == "skip"


# -- wing_position --


def test_wing_position_invalid():
    spec = _make_spec(**{"wing.position": {"value": "parasol", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "wing_position")
    assert r.status == "fail"


# -- tail_type --


def test_tail_type_unsupported():
    spec = _make_spec(**{"tail.type": {"value": "v_tail", "source": "user", "confidence": 1.0}})
    r = _find_rule(run_design_rules(spec), "tail_type")
    assert r.status == "fail"


# -- wing_loading --


def test_wing_loading_skip_without_payload():
    data = _spec_data()
    data["mission"] = {}
    spec = load_aircraft_spec(data)
    r = _find_rule(run_design_rules(spec), "wing_loading")
    assert r.status == "skip"


def test_wing_loading_pass():
    spec = _make_spec()
    r = _find_rule(run_design_rules(spec), "wing_loading")
    assert r.status == "pass"


def test_wing_loading_warn():
    # payload=80, wing_area=5*(1.0+0.5)/2=3.75, loading=21.3 → pass actually
    # Need higher: payload=300, wing_area=3.75, loading=80 → warn (50-100)
    spec = _make_spec(
        **{
            "mission.payload": {"value": 300, "unit": "kg", "source": "user", "confidence": 1.0},
            "wing.span": {"value": 5.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.root_chord": {"value": 1.0, "unit": "m", "source": "user", "confidence": 1.0},
            "wing.tip_chord": {"value": 0.5, "unit": "m", "source": "user", "confidence": 1.0},
        },
    )
    r = _find_rule(run_design_rules(spec), "wing_loading")
    assert r.status == "warn"


# -- report format --


def test_report_to_dict_structure():
    spec = _make_spec()
    report = run_design_rules(spec)
    d = report.to_dict()
    assert "rules" in d
    assert "summary" in d
    assert len(d["rules"]) == 10
    for rule_dict in d["rules"]:
        assert "rule_id" in rule_dict
        assert "label" in rule_dict
        assert "status" in rule_dict
        assert "value" in rule_dict
        assert "expected" in rule_dict
        assert "message" in rule_dict


def test_report_summary_counts():
    spec = _make_spec()
    report = run_design_rules(spec)
    summary = report.summary
    total = sum(summary.values())
    assert total == 10
    assert "pass" in summary
    assert "fail" in summary


# -- integration with generate_aircraft --


def test_design_rules_in_validation_report():
    from pathlib import Path

    from services.workers.cad_worker.openvsp_generator.backend import CadArtifacts, FakeCadBackend
    from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft

    spec = _make_spec()
    backend = FakeCadBackend()
    output_dir = Path("/tmp/test_design_rules_output")
    output_dir.mkdir(exist_ok=True)

    result = generate_aircraft(spec, output_dir, backend)
    assert "design_rules" in result.validation_report
    rules = result.validation_report["design_rules"]["rules"]
    assert len(rules) == 10
    summary = result.validation_report["design_rules"]["summary"]
    assert summary["pass"] + summary["skip"] == 10
