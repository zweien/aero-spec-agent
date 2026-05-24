"""Tests for canard geometry builder."""

from unittest.mock import MagicMock

from services.workers.cad_worker.openvsp_generator.create_canard import create_canard


def _make_spec(canard_span=2.5, canard_chord=0.5, sweep=5.0, x_ratio=0.15,
               fuselage_length=5.0):
    spec = MagicMock()
    spec.canard = MagicMock()
    spec.canard.span = MagicMock(value=canard_span)
    spec.canard.chord = MagicMock(value=canard_chord)
    spec.canard.sweep = MagicMock(value=sweep) if sweep else None
    spec.canard.x_position_ratio = MagicMock(value=x_ratio) if x_ratio else None
    spec.fuselage = MagicMock()
    spec.fuselage.length = MagicMock(value=fuselage_length)
    return spec


def test_create_canard_basic():
    adapter = MagicMock()
    adapter.add_geom.return_value = "canard_geom_0"
    spec = _make_spec()

    result = create_canard(adapter, spec)

    assert result.name == "canard"
    assert result.geom_id == "canard_geom_0"
    assert result.applied_parameters["span"] == 2.5
    assert result.applied_parameters["chord"] == 0.5
    assert result.applied_parameters["x_rel_location"] == 5.0 * 0.15


def test_create_canard_custom_sweep():
    adapter = MagicMock()
    adapter.add_geom.return_value = "canard_geom_0"
    spec = _make_spec(sweep=10.0)

    result = create_canard(adapter, spec)

    assert result.applied_parameters["sweep"] == 10.0


def test_create_canard_custom_x_position():
    adapter = MagicMock()
    adapter.add_geom.return_value = "canard_geom_0"
    spec = _make_spec(x_ratio=0.20)

    result = create_canard(adapter, spec)

    assert result.applied_parameters["x_rel_location"] == 5.0 * 0.20


def test_create_canard_default_when_none():
    adapter = MagicMock()
    adapter.add_geom.return_value = "canard_geom_0"
    spec = _make_spec(sweep=None, x_ratio=None)

    result = create_canard(adapter, spec)

    assert result.applied_parameters["sweep"] == 5.0
    assert result.applied_parameters["x_rel_location"] == 5.0 * 0.15
