"""Tests for tandem wing rear wing geometry builder."""

from unittest.mock import MagicMock

from services.workers.cad_worker.openvsp_generator.create_tandem_wing import create_rear_wing


def _make_spec(rear_span=4.0, rear_chord=0.6, sweep=0.0, x_ratio=0.65, gap=0.5,
               fuselage_length=5.0):
    spec = MagicMock()
    spec.rear_wing = MagicMock()
    spec.rear_wing.span = MagicMock(value=rear_span)
    spec.rear_wing.chord = MagicMock(value=rear_chord)
    spec.rear_wing.sweep = MagicMock(value=sweep) if sweep else None
    spec.rear_wing.x_position_ratio = MagicMock(value=x_ratio) if x_ratio else None
    spec.rear_wing.gap = MagicMock(value=gap) if gap else None
    spec.fuselage = MagicMock()
    spec.fuselage.length = MagicMock(value=fuselage_length)
    spec.fuselage.max_diameter = MagicMock(value=0.75)
    return spec


def test_rear_wing_basic():
    adapter = MagicMock()
    adapter.add_geom.return_value = "rw_geom_0"
    spec = _make_spec()

    result = create_rear_wing(adapter, spec)

    assert result.name == "rear_wing"
    assert result.applied_parameters["span"] == 4.0
    assert result.applied_parameters["x_rel_location"] == 5.0 * 0.65


def test_rear_wing_default_x_ratio():
    adapter = MagicMock()
    adapter.add_geom.return_value = "rw_geom_0"
    spec = _make_spec(x_ratio=None)

    result = create_rear_wing(adapter, spec)
    assert result.applied_parameters["x_rel_location"] == 5.0 * 0.65
