from pathlib import Path
from typing import Any

import yaml

from services.api.app.schemas.aircraft_spec import AircraftSpec


def load_aircraft_spec(source: Path | dict[str, Any]) -> AircraftSpec:
    if isinstance(source, Path):
        data = yaml.safe_load(source.read_text(encoding="utf-8"))
    else:
        data = source
    return AircraftSpec.model_validate(data)


def dump_aircraft_spec(spec: AircraftSpec, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = spec.model_dump(mode="json", exclude_none=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
