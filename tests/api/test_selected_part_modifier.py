from pathlib import Path

import pytest

from services.api.app.services.selected_part_modifier import (
    SelectedPartPatchError,
    apply_selected_part_patch,
)
from services.api.app.services.spec_io import load_aircraft_spec


EXAMPLE = Path("packages/aircraft-schema/examples/twin_engine_uav.yaml")


def test_apply_selected_part_patch_moves_selected_engine_outboard():
    spec = load_aircraft_spec(EXAMPLE)

    patched = apply_selected_part_patch(
        spec,
        selected_refs=["part:right_engine"],
        part_ref="part:right_engine",
        operation="move_outboard",
        value=0.5,
    )

    assert patched.engine.y_offset is not None
    assert patched.engine.y_offset.value == 0.5
    assert patched.engine.y_offset.source == "user"


def test_apply_selected_part_patch_increases_fuselage_length():
    spec = load_aircraft_spec(EXAMPLE)

    patched = apply_selected_part_patch(
        spec,
        selected_refs=["part:fuselage"],
        part_ref="part:fuselage",
        operation="increase_length",
        value=2,
    )

    assert patched.fuselage.length.value == 9.0


def test_apply_selected_part_patch_decreases_wing_span():
    spec = load_aircraft_spec(EXAMPLE)

    patched = apply_selected_part_patch(
        spec,
        selected_refs=["part:main_wing"],
        part_ref="part:main_wing",
        operation="decrease_span",
        value=1,
    )

    assert patched.wing.span.value == 11.0


def test_apply_selected_part_patch_rejects_non_positive_dimension():
    spec = load_aircraft_spec(EXAMPLE)

    with pytest.raises(SelectedPartPatchError, match="必须大于 0"):
        apply_selected_part_patch(
            spec,
            selected_refs=["part:main_wing"],
            part_ref="part:main_wing",
            operation="decrease_span",
            value=12,
        )


def test_apply_selected_part_patch_rejects_unselected_part():
    spec = load_aircraft_spec(EXAMPLE)

    with pytest.raises(SelectedPartPatchError, match="当前选中对象"):
        apply_selected_part_patch(
            spec,
            selected_refs=["part:right_engine"],
            part_ref="part:left_engine",
            operation="move_outboard",
            value=0.5,
        )
