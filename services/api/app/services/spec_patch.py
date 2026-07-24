from __future__ import annotations

from typing import Any

from services.api.app.schemas.aircraft_spec import AircraftSpec


def apply_patch(spec: AircraftSpec, changes: list[dict[str, Any]]) -> AircraftSpec:
    data = spec.model_dump(mode="json")
    for change in changes:
        path = change["path"]
        value = change["value"]
        _set_nested(data, path, value)
    return AircraftSpec.model_validate(data)


def pre_fill_none_scalars(data: dict[str, Any], paths: list[str]) -> None:
    """Replace None scalar fields (only those being patched) with empty dicts.

    Paths like "wing.sweep.value" → check if "wing.sweep" is None, replace
    with {}. Used before patching so a None scalar (e.g. a layout-specific
    section the LLM left null) becomes patchable. Single implementation shared
    by ChatService (modify_design) and selected_part_modifier.
    """
    for path in paths:
        keys = path.split(".")
        if len(keys) < 2:
            continue
        # Navigate to the parent of the last key (e.g. wing.sweep from wing.sweep.value)
        parent_keys = keys[:-1]
        scalar_key = parent_keys[-1]  # e.g. "sweep"
        current = data
        for key in parent_keys[:-1]:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if isinstance(current, dict) and current.get(scalar_key) is None:
                current[scalar_key] = {}


def _set_nested(data: dict[str, Any], path: str, value: Any) -> None:
    keys = path.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current:
            raise KeyError(f"nonexistent path component: {key} in {path}")
        current = current[key]
    last_key = keys[-1]
    if last_key not in current:
        raise KeyError(f"nonexistent path component: {last_key} in {path}")
    current[last_key] = value
