# tests/api/test_layout_builders.py — 新建
"""Tests for layout builder integration."""

from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import load_aircraft_spec


def _spec_with_layout(layout: str):
    base = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))
    data = base.model_dump()
    data["aircraft"]["layout"] = layout
    return AircraftSpec.model_validate(data)


def test_flying_wing_layout_accepted():
    spec = _spec_with_layout("flying_wing")
    assert spec.aircraft.layout == "flying_wing"


def test_flying_wing_layout_validates():
    """Flying wing layout should validate without boom/body."""
    spec = _spec_with_layout("flying_wing")
    assert spec.boom is None
    assert spec.body is None


def test_twin_boom_layout_with_boom():
    """Twin boom layout with boom field should validate."""
    spec = _spec_with_layout("twin_boom")
    assert spec.aircraft.layout == "twin_boom"
    # boom is optional, won't be present from base spec
    assert spec.boom is None


def test_bwb_layout_accepted():
    spec = _spec_with_layout("blended_wing_body")
    assert spec.aircraft.layout == "blended_wing_body"
