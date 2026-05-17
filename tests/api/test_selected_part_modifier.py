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


@pytest.mark.parametrize(
    ("part_ref", "operation", "value"),
    [
        ("part:fuselage", "decrease_length", 7),
        ("part:fuselage", "decrease_diameter", 0.75),
        ("part:main_wing", "decrease_span", 12),
        ("part:main_wing", "decrease_root_chord", 1.2),
        ("part:main_wing", "decrease_tip_chord", 0.6),
    ],
)
def test_apply_selected_part_patch_rejects_non_positive_size_fields(
    part_ref: str,
    operation: str,
    value: float,
):
    spec = load_aircraft_spec(EXAMPLE)

    with pytest.raises(SelectedPartPatchError, match="必须大于 0"):
        apply_selected_part_patch(
            spec,
            selected_refs=[part_ref],
            part_ref=part_ref,
            operation=operation,
            value=value,
        )


def test_apply_selected_part_patch_rejects_invalid_operation_for_part():
    spec = load_aircraft_spec(EXAMPLE)

    with pytest.raises(SelectedPartPatchError, match="不支持操作"):
        apply_selected_part_patch(
            spec,
            selected_refs=["part:fuselage"],
            part_ref="part:fuselage",
            operation="move_outboard",
            value=1,
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
