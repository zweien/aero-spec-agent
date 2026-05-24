"""Tests for joined wing rear wing geometry builder."""

from unittest.mock import MagicMock

from services.workers.cad_worker.openvsp_generator.create_joined_wing import create_rear_wing as create_joined_rear_wing


def _make_spec(rear_span=8.0, rear_chord=0.8, sweep=-15.0, x_ratio=0.70):
    spec = MagicMock()
    spec.rear_wing = MagicMock()
    spec.rear_wing.span = MagicMock(value=rear_span)
    spec.rear_wing.chord = MagicMock(value=rear_chord)
    spec.rear_wing.sweep = MagicMock(value=sweep) if sweep else None
    spec.rear_wing.x_position_ratio = MagicMock(value=x_ratio) if x_ratio else None
    spec.fuselage = MagicMock()
    spec.fuselage.length = MagicMock(value=5.0)
    return spec


def test_joined_rear_wing_negative_sweep():
    adapter = MagicMock()
    adapter.add_geom.return_value = "jrw_geom"
    spec = _make_spec()

    result = create_joined_rear_wing(adapter, spec)

    assert result.name == "joined_rear_wing"
    assert result.applied_parameters["sweep"] == -15.0


def test_joined_rear_wing_default_sweep():
    adapter = MagicMock()
    adapter.add_geom.return_value = "jrw_geom"
    spec = _make_spec(sweep=None)

    result = create_joined_rear_wing(adapter, spec)
    assert result.applied_parameters["sweep"] == -15.0
