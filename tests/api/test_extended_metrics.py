"""Tests for extended_metrics: volume / loading / stealth indicators."""

from __future__ import annotations

import yaml

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.extended_metrics import run_extended_metrics


def _load_baseline_spec() -> AircraftSpec:
    spec_path = "packages/aircraft-schema/examples/twin_engine_uav.yaml"
    with open(spec_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return AircraftSpec.model_validate(data)


def test_extended_metrics_baseline_spec_runs():
    spec = _load_baseline_spec()
    report = run_extended_metrics(spec)
    grouped = report.by_category()
    assert grouped["volume"], "expected at least one volume metric"
    assert grouped["loading"], "expected at least one loading metric"
    assert grouped["stealth"], "expected at least one stealth metric"
    summary = report.summary
    assert sum(summary.values()) == len(report.metrics)


def test_volume_metrics_include_fuselage_volume():
    spec = _load_baseline_spec()
    report = run_extended_metrics(spec)
    ids = {m.metric_id for m in report.metrics}
    assert "fuselage_volume" in ids
    fuse = next(m for m in report.metrics if m.metric_id == "fuselage_volume")
    assert fuse.value > 0
    assert fuse.unit == "m³"


def test_loading_metrics_use_user_supplied_mtow():
    spec_dict = _load_baseline_spec().model_dump()
    spec_dict["mission"]["mtow"] = {
        "value": 200.0,
        "unit": "kg",
        "source": "user",
        "confidence": 1.0,
    }
    spec_dict["mission"]["thrust"] = {
        "value": 1500.0,
        "unit": "N",
        "source": "user",
        "confidence": 1.0,
    }
    spec = AircraftSpec.model_validate(spec_dict)
    report = run_extended_metrics(spec)
    payload_frac = next(m for m in report.metrics if m.metric_id == "payload_fraction")
    assert abs(payload_frac.value - 30.0 / 200.0) < 1e-6
    assert payload_frac.confidence == "high"

    tw = next(m for m in report.metrics if m.metric_id == "thrust_to_weight")
    expected_tw = 1500.0 / (200.0 * 9.81)
    assert abs(tw.value - expected_tw) < 1e-3


def test_loading_metrics_skip_when_no_payload_or_mtow():
    spec_dict = _load_baseline_spec().model_dump()
    spec_dict["mission"].pop("payload", None)
    spec_dict["mission"].pop("mtow", None)
    spec = AircraftSpec.model_validate(spec_dict)
    report = run_extended_metrics(spec)
    loading_ids = {m.metric_id for m in report.metrics if m.category == "loading"}
    assert "mtow_loading" in loading_ids
    mtow_loading = next(m for m in report.metrics if m.metric_id == "mtow_loading")
    assert mtow_loading.status == "unusual"


def test_stealth_metrics_apply_material_and_shaping():
    spec_dict = _load_baseline_spec().model_dump()
    spec_dict["stealth"] = {
        "material_class": {
            "value": "ram",
            "source": "user",
            "confidence": 1.0,
        },
        "shaping_level": {
            "value": "high",
            "source": "user",
            "confidence": 1.0,
        },
    }
    spec = AircraftSpec.model_validate(spec_dict)
    report = run_extended_metrics(spec)
    rcs = next(m for m in report.metrics if m.metric_id == "rcs_estimate")
    front = next(m for m in report.metrics if m.metric_id == "frontal_projection_area")
    assert rcs.value < front.value
    score = next(m for m in report.metrics if m.metric_id == "low_observability_score")
    assert score.value > 50


def test_stealth_target_gap_when_target_provided():
    spec_dict = _load_baseline_spec().model_dump()
    spec_dict["stealth"] = {
        "material_class": {
            "value": "metal",
            "source": "user",
            "confidence": 1.0,
        },
        "shaping_level": {
            "value": "none",
            "source": "user",
            "confidence": 1.0,
        },
        "frontal_rcs_target": {
            "value": 0.1,
            "unit": "m²",
            "source": "user",
            "confidence": 1.0,
        },
    }
    spec = AircraftSpec.model_validate(spec_dict)
    report = run_extended_metrics(spec)
    ids = {m.metric_id for m in report.metrics}
    assert "rcs_target_gap" in ids


def test_payload_bay_volume_uses_spec_dimensions():
    spec_dict = _load_baseline_spec().model_dump()
    spec_dict["fuselage"]["payload_bay_length"] = {
        "value": 1.5,
        "unit": "m",
        "source": "user",
        "confidence": 1.0,
    }
    spec_dict["fuselage"]["payload_bay_diameter"] = {
        "value": 0.4,
        "unit": "m",
        "source": "user",
        "confidence": 1.0,
    }
    spec = AircraftSpec.model_validate(spec_dict)
    report = run_extended_metrics(spec)
    bay = next(m for m in report.metrics if m.metric_id == "payload_bay_volume")
    assert bay.value > 0


def test_serialized_report_contains_categories():
    spec = _load_baseline_spec()
    report = run_extended_metrics(spec)
    payload = report.to_dict()
    cats = {m["category"] for m in payload["metrics"]}
    assert cats == {"volume", "loading", "stealth"}
    assert "summary" in payload
