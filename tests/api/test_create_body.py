"""Tests for BWB flat body geometry creation."""

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.create_body import create_flat_body
from tests.api.test_openvsp_geometry_builders import make_adapter


def _bwb_spec_data() -> dict:
    return {
        "schema_version": "0.1",
        "aircraft": {
            "name": "bwb_uav",
            "type": "fixed_wing_uav",
            "layout": "blended_wing_body",
        },
        "mission": {},
        "fuselage": {
            "length": {
                "value": 5.0,
                "unit": "m",
                "source": "user",
                "confidence": 0.9,
            },
            "max_diameter": {
                "value": 0.75,
                "unit": "m",
                "source": "inferred",
                "confidence": 0.6,
            },
        },
        "wing": {
            "position": {"value": "mid", "source": "rule_default", "confidence": 0.5},
            "span": {"value": 8.0, "unit": "m", "source": "user", "confidence": 0.9},
            "root_chord": {"value": 3.0, "unit": "m", "source": "user", "confidence": 0.9},
            "tip_chord": {"value": 1.0, "unit": "m", "source": "inferred", "confidence": 0.7},
            "sweep": {"value": 30.0, "unit": "deg", "source": "user", "confidence": 0.9},
            "dihedral": {"value": 3.0, "unit": "deg", "source": "rule_default", "confidence": 0.5},
        },
        "tail": {"type": {"value": "conventional", "source": "rule_default", "confidence": 0.5}},
        "engine": {"count": {"value": 2, "source": "user", "confidence": 0.9}},
        "body": {
            "width": {"value": 3.0, "unit": "m", "source": "user", "confidence": 0.9},
            "height": {"value": 0.6, "unit": "m", "source": "inferred", "confidence": 0.7},
        },
    }


def _bwb_spec():
    return load_aircraft_spec(_bwb_spec_data())


def test_creates_flat_body():
    adapter, fake_vsp = make_adapter()

    result = create_flat_body(adapter, _bwb_spec())

    assert result.name == "flat_body"
    assert result.applied_parameters["width"] == 3.0
    assert result.applied_parameters["height"] == 0.6


def test_flat_body_length():
    adapter, fake_vsp = make_adapter()

    result = create_flat_body(adapter, _bwb_spec())

    assert result.applied_parameters["length"] == 5.0


def test_flat_body_uses_add_geom_fuselage():
    adapter, fake_vsp = make_adapter()

    create_flat_body(adapter, _bwb_spec())

    assert ("AddGeom", "FUSELAGE", "", "geom-1") in fake_vsp.calls


def test_flat_body_sets_length_parameter():
    adapter, fake_vsp = make_adapter()

    create_flat_body(adapter, _bwb_spec())

    assert fake_vsp.value_for("geom-1", "Length", "Design") == 5.0


def test_flat_body_calls_set_fuselage_cross_section():
    adapter, fake_vsp = make_adapter()

    create_flat_body(adapter, _bwb_spec())

    width_height_calls = [
        call for call in fake_vsp.calls
        if call[0] == "SetXSecWidthHeight"
    ]
    assert len(width_height_calls) == 3  # num_xsecs=5, start=1, end=4 => 3 calls
    for call in width_height_calls:
        assert call[2] == 3.0  # width (index 2: after xsec_id)
        assert call[3] == 0.6  # height (index 3)


def test_flat_body_cross_section_uses_independent_width_and_height():
    """Unlike set_fuselage_diameter, width and height should differ."""
    adapter, fake_vsp = make_adapter()

    create_flat_body(adapter, _bwb_spec())

    for call in fake_vsp.calls:
        if call[0] == "SetXSecWidthHeight":
            assert call[2] != call[3], "BWB flat body should have width != height"
