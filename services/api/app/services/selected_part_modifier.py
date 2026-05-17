from __future__ import annotations

from typing import Any

from services.api.app.schemas.aircraft_spec import AircraftSpec


class SelectedPartPatchError(ValueError):
    pass


PART_SET_OPERATIONS: dict[str, dict[str, tuple[str, str, str | None]]] = {
    "part:fuselage": {
        "set_length": ("fuselage", "length", "m"),
        "set_diameter": ("fuselage", "max_diameter", "m"),
    },
    "part:main_wing": {
        "set_span": ("wing", "span", "m"),
        "set_root_chord": ("wing", "root_chord", "m"),
        "set_tip_chord": ("wing", "tip_chord", "m"),
        "set_sweep": ("wing", "sweep", "deg"),
        "set_dihedral": ("wing", "dihedral", "deg"),
    },
    "part:tail": {
        "set_tail_type": ("tail", "type", None),
    },
}

PART_DELTA_OPERATIONS: dict[str, dict[str, tuple[str, str, str | None, float]]] = {
    "part:fuselage": {
        "increase_length": ("fuselage", "length", "m", 1.0),
        "decrease_length": ("fuselage", "length", "m", -1.0),
        "increase_diameter": ("fuselage", "max_diameter", "m", 1.0),
        "decrease_diameter": ("fuselage", "max_diameter", "m", -1.0),
    },
    "part:main_wing": {
        "increase_span": ("wing", "span", "m", 1.0),
        "decrease_span": ("wing", "span", "m", -1.0),
        "increase_root_chord": ("wing", "root_chord", "m", 1.0),
        "decrease_root_chord": ("wing", "root_chord", "m", -1.0),
        "increase_tip_chord": ("wing", "tip_chord", "m", 1.0),
        "decrease_tip_chord": ("wing", "tip_chord", "m", -1.0),
        "increase_sweep": ("wing", "sweep", "deg", 1.0),
        "decrease_sweep": ("wing", "sweep", "deg", -1.0),
        "increase_dihedral": ("wing", "dihedral", "deg", 1.0),
        "decrease_dihedral": ("wing", "dihedral", "deg", -1.0),
    },
}

ENGINE_MOVE_MAP: dict[str, tuple[str, float]] = {
    "move_outboard": ("y_offset", 1.0),
    "move_inboard": ("y_offset", -1.0),
    "move_forward": ("x_offset", 1.0),
    "move_backward": ("x_offset", -1.0),
    "move_up": ("z_offset", 1.0),
    "move_down": ("z_offset", -1.0),
}

POSITIVE_SCALAR_FIELDS = {
    ("fuselage", "length"),
    ("fuselage", "max_diameter"),
    ("wing", "span"),
    ("wing", "root_chord"),
    ("wing", "tip_chord"),
}


def apply_selected_part_patch(
    spec: AircraftSpec,
    selected_refs: list[str],
    part_ref: str,
    operation: str,
    value: Any,
) -> AircraftSpec:
    if not part_ref or not operation or value is None:
        raise SelectedPartPatchError("缺少必要参数: part_ref, operation, value")

    if selected_refs and part_ref not in selected_refs:
        raise SelectedPartPatchError(
            f"当前选中对象为 {selected_refs}，"
            f"但工具请求修改 {part_ref}，为避免误操作已拒绝。"
        )

    data = spec.model_dump(mode="json")

    if operation in ENGINE_MOVE_MAP:
        _apply_engine_move(data, part_ref, operation, value)
    elif part_ref in PART_SET_OPERATIONS or part_ref in PART_DELTA_OPERATIONS:
        _apply_part_scalar_patch(data, part_ref, operation, value)
    else:
        raise SelectedPartPatchError(f"不支持操作的部件: {part_ref}，或未知操作: {operation}")

    try:
        return AircraftSpec.model_validate(data)
    except Exception as exc:
        raise SelectedPartPatchError(f"spec patch 失败: {exc}") from exc


def _apply_engine_move(
    data: dict[str, Any],
    part_ref: str,
    operation: str,
    value: Any,
) -> None:
    if part_ref not in ("part:left_engine", "part:right_engine"):
        raise SelectedPartPatchError(f"部件 {part_ref} 不支持操作 {operation}，该操作仅适用于发动机部件")

    offset_field, sign = ENGINE_MOVE_MAP[operation]
    offset_path = f"engine.{offset_field}"
    _pre_fill_none_scalars(data, [f"{offset_path}.value"])

    engine_dict = data.setdefault("engine", {})
    if offset_field not in engine_dict or engine_dict[offset_field] is None:
        engine_dict[offset_field] = {}

    offset_scalar = engine_dict.get(offset_field)
    current_val = 0.0
    if isinstance(offset_scalar, dict) and "value" in offset_scalar:
        current_val = float(offset_scalar["value"])

    engine_dict[offset_field]["value"] = current_val + sign * float(value)
    engine_dict[offset_field]["source"] = "user"
    engine_dict[offset_field]["confidence"] = 1.0
    engine_dict[offset_field]["unit"] = "m"


def _apply_part_scalar_patch(
    data: dict[str, Any],
    part_ref: str,
    operation: str,
    value: Any,
) -> None:
    ops = PART_SET_OPERATIONS.get(part_ref, {})
    delta_ops = PART_DELTA_OPERATIONS.get(part_ref, {})
    if operation not in ops and operation not in delta_ops:
        available_ops = sorted([*ops.keys(), *delta_ops.keys()])
        raise SelectedPartPatchError(
            f"部件 {part_ref} 不支持操作 {operation}，可用: {', '.join(available_ops)}"
        )

    is_delta_operation = operation in delta_ops
    if is_delta_operation:
        section, field_name, default_unit, sign = delta_ops[operation]
    else:
        section, field_name, default_unit = ops[operation]
        sign = 1.0

    field_path = f"{section}.{field_name}"
    _pre_fill_none_scalars(data, [f"{field_path}.value"])

    section_dict = data.setdefault(section, {})
    if field_name not in section_dict or section_dict[field_name] is None:
        section_dict[field_name] = {}
    scalar_dict = section_dict[field_name]

    if field_name == "type" and section == "tail":
        if str(value) != "conventional":
            raise SelectedPartPatchError(
                "当前 CAD 后端暂只支持 conventional 尾翼，已拒绝其他尾翼类型。"
            )
        scalar_dict["value"] = str(value)
    else:
        next_value = float(value)
        if is_delta_operation:
            next_value = float(scalar_dict.get("value", 0)) + sign * next_value
        if (section, field_name) in POSITIVE_SCALAR_FIELDS and next_value <= 0:
            raise SelectedPartPatchError(f"{field_path} 必须大于 0，拒绝写入 {next_value}")
        scalar_dict["value"] = next_value

    scalar_dict["source"] = "user"
    scalar_dict["confidence"] = 1.0
    if default_unit:
        scalar_dict["unit"] = default_unit


def _pre_fill_none_scalars(data: dict[str, Any], paths: list[str]) -> None:
    for path in paths:
        keys = path.split(".")
        if len(keys) < 2:
            continue
        parent_keys = keys[:-1]
        scalar_key = parent_keys[-1]
        current = data
        for key in parent_keys[:-1]:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, dict) and current.get(scalar_key) is None:
                current[scalar_key] = {}
