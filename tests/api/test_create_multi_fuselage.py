"""Tests for multi-fuselage geometry builder."""

from unittest.mock import MagicMock

from services.workers.cad_worker.openvsp_generator.create_multi_fuselage import create_multi_fuselage


def _make_spec(spacing=4.0, fuselage_length=5.0, fuselage_diameter=0.75):
    spec = MagicMock()
    spec.multi_fuselage = MagicMock()
    spec.multi_fuselage.spacing = MagicMock(value=spacing)
    spec.fuselage = MagicMock()
    spec.fuselage.length = MagicMock(value=fuselage_length)
    spec.fuselage.max_diameter = MagicMock(value=fuselage_diameter)
    return spec


def test_creates_two_fuselages():
    adapter = MagicMock()
    adapter.add_geom.return_value = "mf_geom"
    spec = _make_spec()

    results = create_multi_fuselage(adapter, spec)

    assert len(results) == 2
    assert results[0].name == "left_fuselage"
    assert results[1].name == "right_fuselage"


def test_symmetric_y_offsets():
    adapter = MagicMock()
    adapter.add_geom.return_value = "mf_geom"
    spec = _make_spec(spacing=6.0)

    results = create_multi_fuselage(adapter, spec)

    left_y = results[0].applied_parameters["y_offset"]
    right_y = results[1].applied_parameters["y_offset"]
    assert left_y == -3.0
    assert right_y == 3.0
