"""Tests for variant trust/confidence calculation."""

from services.workers.cad_worker.openvsp_generator.variant_trust import compute_variant_trust


def test_fake_cad_always_low():
    trust = compute_variant_trust(
        backend_name="fake",
        metrics_source="backend_design_metrics",
        defaulted_parameter_count=0,
        has_real_geometry=False,
        has_aero_analysis=False,
    )
    assert trust.confidence_level == "low"
    assert trust.generated_by == "fake_cad"
    assert trust.has_real_geometry is False
    assert any("Fake CAD" in r for r in trust.confidence_reasons)


def test_client_heuristic_always_low():
    trust = compute_variant_trust(
        backend_name="openvsp",
        metrics_source="client_heuristic",
        defaulted_parameter_count=0,
        has_real_geometry=True,
        has_aero_analysis=True,
    )
    assert trust.confidence_level == "low"
    assert any("客户端" in r for r in trust.confidence_reasons)


def test_many_defaults_forces_low():
    trust = compute_variant_trust(
        backend_name="openvsp",
        metrics_source="performance_estimate",
        defaulted_parameter_count=6,
        has_real_geometry=True,
        has_aero_analysis=False,
    )
    assert trust.confidence_level == "low"
    assert any("默认补全" in r for r in trust.confidence_reasons)


def test_openvsp_no_aero_medium():
    trust = compute_variant_trust(
        backend_name="openvsp",
        metrics_source="performance_estimate",
        defaulted_parameter_count=1,
        has_real_geometry=True,
        has_aero_analysis=False,
    )
    assert trust.confidence_level == "medium"
    assert trust.has_real_geometry is True


def test_openvsp_full_high():
    trust = compute_variant_trust(
        backend_name="openvsp",
        metrics_source="backend_design_metrics",
        defaulted_parameter_count=1,
        has_real_geometry=True,
        has_aero_analysis=True,
    )
    assert trust.confidence_level == "high"
    assert any("真实几何" in r for r in trust.confidence_reasons)


def test_openvsp_too_many_defaults_not_high():
    trust = compute_variant_trust(
        backend_name="openvsp",
        metrics_source="backend_design_metrics",
        defaulted_parameter_count=4,
        has_real_geometry=True,
        has_aero_analysis=True,
    )
    assert trust.confidence_level != "high"


def test_to_dict_roundtrip():
    trust = compute_variant_trust(
        backend_name="fake",
        metrics_source="client_heuristic",
        defaulted_parameter_count=3,
    )
    d = trust.to_dict()
    assert d["backend"] == "fake"
    assert d["confidence_level"] == "low"
    assert "generated_by" in d
    assert "has_aero_analysis" in d


def test_generate_aircraft_includes_variant_trust(tmp_path):
    """Integration: generate_aircraft writes variant_trust to validation_report."""
    from services.api.app.services.spec_io import load_aircraft_spec
    from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend
    from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft
    from pathlib import Path

    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    result = generate_aircraft(spec, tmp_path, backend=FakeCadBackend())
    assert "variant_trust" in result.validation_report
    vt = result.validation_report["variant_trust"]
    assert vt["confidence_level"] == "low"
    assert vt["generated_by"] == "fake_cad"
