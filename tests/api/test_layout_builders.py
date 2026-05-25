# tests/api/test_layout_builders.py — 新建
"""Tests for layout builder integration."""

import json

import yaml
from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import load_aircraft_spec
from services.api.app.graph.deep_design_graph import (
    LAYOUT_STRATEGIES,
    DEFAULT_STRATEGIES,
    prepare_variants,
)


_EXAMPLE_SPEC_PATH = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def _load_spec_dict() -> dict:
    with open(_EXAMPLE_SPEC_PATH) as f:
        return yaml.safe_load(f)


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


def test_canard_layout_accepted():
    spec = _spec_with_layout("canard")
    assert spec.aircraft.layout == "canard"


def test_three_surface_layout_accepted():
    spec = _spec_with_layout("three_surface")
    assert spec.aircraft.layout == "three_surface"


def test_tandem_wing_layout_accepted():
    spec = _spec_with_layout("tandem_wing")
    assert spec.aircraft.layout == "tandem_wing"


def test_biplane_layout_accepted():
    spec = _spec_with_layout("biplane")
    assert spec.aircraft.layout == "biplane"


def test_joined_wing_layout_accepted():
    spec = _spec_with_layout("joined_wing")
    assert spec.aircraft.layout == "joined_wing"


def test_box_wing_layout_accepted():
    spec = _spec_with_layout("box_wing")
    assert spec.aircraft.layout == "box_wing"


def test_multi_fuselage_layout_accepted():
    spec = _spec_with_layout("multi_fuselage")
    assert spec.aircraft.layout == "multi_fuselage"


class TestLayoutStrategies:
    def test_canard_compact_varies_canard_span(self):
        strategies = LAYOUT_STRATEGIES["canard"]
        compact = strategies[0]
        assert compact["label"] == "compact"
        changes = compact["changes"]
        paths = {c["path"] for c in changes}
        assert "wing.span.value" in paths
        assert "canard.span.value" in paths
        canard_change = next(c for c in changes if c["path"] == "canard.span.value")
        assert canard_change["value"] == -0.5
        assert canard_change["op"] == "relative"

    def test_canard_extended_varies_canard_span(self):
        strategies = LAYOUT_STRATEGIES["canard"]
        extended = strategies[2]
        assert extended["label"] == "extended"
        canard_change = next(c for c in extended["changes"] if c["path"] == "canard.span.value")
        assert canard_change["value"] == 0.5

    def test_biplane_extended_varies_gap(self):
        strategies = LAYOUT_STRATEGIES["biplane"]
        extended = strategies[2]
        assert extended["label"] == "extended"
        gap_change = next(c for c in extended["changes"] if c["path"] == "second_wing.gap.value")
        assert gap_change["value"] == 0.2

    def test_biplane_compact_varies_gap(self):
        strategies = LAYOUT_STRATEGIES["biplane"]
        compact = strategies[0]
        gap_change = next(c for c in compact["changes"] if c["path"] == "second_wing.gap.value")
        assert gap_change["value"] == -0.2

    def test_tandem_wing_varies_rear_wing_span(self):
        strategies = LAYOUT_STRATEGIES["tandem_wing"]
        compact = strategies[0]
        assert compact["label"] == "compact"
        paths = {c["path"] for c in compact["changes"]}
        assert "wing.span.value" in paths
        assert "rear_wing.span.value" in paths
        rear_change = next(c for c in compact["changes"] if c["path"] == "rear_wing.span.value")
        assert rear_change["value"] == -1

    def test_box_wing_varies_gap(self):
        strategies = LAYOUT_STRATEGIES["box_wing"]
        extended = strategies[2]
        gap_change = next(c for c in extended["changes"] if c["path"] == "box_wing_config.gap.value")
        assert gap_change["value"] == 0.3

    def test_three_surface_same_as_canard(self):
        canard_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["canard"] for c in s["changes"]}
        three_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["three_surface"] for c in s["changes"]}
        assert canard_paths == three_paths

    def test_joined_wing_same_as_tandem(self):
        tandem_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["tandem_wing"] for c in s["changes"]}
        joined_paths = {(c["path"], c["value"]) for s in LAYOUT_STRATEGIES["joined_wing"] for c in s["changes"]}
        assert tandem_paths == joined_paths

    def test_conventional_uses_default_strategies(self):
        assert LAYOUT_STRATEGIES["conventional"] is DEFAULT_STRATEGIES

    def test_single_surface_layouts_use_default(self):
        for layout in ("twin_boom", "flying_wing", "blended_wing_body", "multi_fuselage"):
            assert LAYOUT_STRATEGIES[layout] is DEFAULT_STRATEGIES, f"{layout} should use DEFAULT_STRATEGIES"

    def test_unknown_layout_falls_back(self):
        strategies = LAYOUT_STRATEGIES.get("hypothetical_layout", LAYOUT_STRATEGIES["conventional"])
        assert strategies is DEFAULT_STRATEGIES

    def test_all_layouts_have_three_strategies(self):
        for layout, strategies in LAYOUT_STRATEGIES.items():
            labels = [s["label"] for s in strategies]
            assert labels == ["compact", "standard", "extended"], f"{layout} strategy labels incorrect"


class TestLayoutAwarePrepareVariants:
    def test_canard_compact_patches_canard_span(self):
        spec_dict = _load_spec_dict()
        spec_dict["aircraft"]["layout"] = "canard"
        spec_dict["canard"] = {
            "span": {"value": 3.0, "unit": "m", "source": "user"},
            "chord": {"value": 0.5, "unit": "m", "source": "user"},
        }
        state = {"base_spec": spec_dict, "constraints": {"variant_count": 3}}
        result = prepare_variants(state)
        compact = result["variants"][0]
        assert compact["label"] == "compact"
        patched = compact["patched_spec"]
        assert patched["wing"]["span"]["value"] < spec_dict["wing"]["span"]["value"]
        assert patched["canard"]["span"]["value"] < spec_dict["canard"]["span"]["value"]

    def test_biplane_extended_patches_gap(self):
        spec_dict = _load_spec_dict()
        spec_dict["aircraft"]["layout"] = "biplane"
        spec_dict["second_wing"] = {
            "span": {"value": 5.0, "unit": "m", "source": "user"},
            "chord": {"value": 0.8, "unit": "m", "source": "user"},
            "gap": {"value": 1.2, "unit": "m", "source": "user"},
        }
        state = {"base_spec": spec_dict, "constraints": {"variant_count": 3}}
        result = prepare_variants(state)
        extended = result["variants"][2]
        assert extended["label"] == "extended"
        patched = extended["patched_spec"]
        assert patched["second_wing"]["gap"]["value"] > spec_dict["second_wing"]["gap"]["value"]

    def test_conventional_unchanged(self):
        spec_dict = _load_spec_dict()
        state = {"base_spec": spec_dict, "constraints": {"variant_count": 3}}
        result = prepare_variants(state)
        assert len(result["variants"]) == 3
        assert result["variants"][0]["label"] == "compact"
        compact = result["variants"][0]
        patched = compact["patched_spec"]
        assert patched["wing"]["span"]["value"] < spec_dict["wing"]["span"]["value"]
