"""Tests for biplane lower wing geometry builder."""

from unittest.mock import MagicMock

from services.workers.cad_worker.openvsp_generator.create_biplane import create_lower_wing


def _make_spec(span=6.0, chord=0.8, gap=1.5, stagger=0.3, sweep=0.0, dihedral=0.0):
    spec = MagicMock()
    spec.second_wing = MagicMock()
    spec.second_wing.span = MagicMock(value=span)
    spec.second_wing.chord = MagicMock(value=chord)
    spec.second_wing.sweep = MagicMock(value=sweep) if sweep else None
    spec.second_wing.dihedral = MagicMock(value=dihedral) if dihedral else None
    spec.second_wing.gap = MagicMock(value=gap)
    spec.second_wing.stagger = MagicMock(value=stagger) if stagger else None
    spec.fuselage = MagicMock()
    spec.fuselage.length = MagicMock(value=5.0)
    spec.fuselage.max_diameter = MagicMock(value=0.75)
    return spec


def test_lower_wing_basic():
    adapter = MagicMock()
    adapter.add_geom.return_value = "lw_geom_0"
    spec = _make_spec()

    result = create_lower_wing(adapter, spec)

    assert result.name == "lower_wing"
    assert result.applied_parameters["span"] == 6.0
    assert result.applied_parameters["gap"] == 1.5
    assert result.applied_parameters["z_rel_location"] < 0


def test_lower_wing_with_stagger():
    adapter = MagicMock()
    adapter.add_geom.return_value = "lw_geom_0"
    spec = _make_spec(stagger=0.5)

    result = create_lower_wing(adapter, spec)
    assert result.applied_parameters["x_rel_location"] == 5.0 * 0.40 + 0.5
