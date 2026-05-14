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
