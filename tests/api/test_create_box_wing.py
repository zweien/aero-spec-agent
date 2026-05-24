"""Tests for box wing geometry builder."""

from unittest.mock import MagicMock

from services.workers.cad_worker.openvsp_generator.create_box_wing import (
    create_box_lower_wing, create_endplates,
)


def _make_spec(gap=2.0, endplate_chord=0.3, wing_span=8.0, root_chord=1.0):
    spec = MagicMock()
    spec.box_wing_config = MagicMock()
    spec.box_wing_config.gap = MagicMock(value=gap)
    spec.box_wing_config.endplate_chord = MagicMock(value=endplate_chord) if endplate_chord else None
    spec.wing = MagicMock()
    spec.wing.span = MagicMock(value=wing_span)
    spec.wing.root_chord = MagicMock(value=root_chord)
    spec.fuselage = MagicMock()
    spec.fuselage.length = MagicMock(value=5.0)
    spec.fuselage.max_diameter = MagicMock(value=0.75)
    return spec


def test_box_lower_wing():
    adapter = MagicMock()
    adapter.add_geom.return_value = "blw_geom"
    spec = _make_spec()

    result = create_box_lower_wing(adapter, spec)

    assert result.name == "box_lower_wing"
    assert result.applied_parameters["span"] == 8.0
    assert result.applied_parameters["z_rel_location"] < 0


def test_endplates_creates_two():
    adapter = MagicMock()
    adapter.add_geom.return_value = "ep_geom"
    spec = _make_spec()

    results = create_endplates(adapter, spec)

    assert len(results) == 2
    assert results[0].name == "left_endplate"
    assert results[1].name == "right_endplate"


def test_endplates_vertical_rotation():
    adapter = MagicMock()
    adapter.add_geom.return_value = "ep_geom"
    spec = _make_spec()

    results = create_endplates(adapter, spec)

    for r in results:
        assert r.applied_parameters["x_rel_rotation"] == 90.0
