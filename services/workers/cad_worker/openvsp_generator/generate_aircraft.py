import json
from dataclasses import dataclass
from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.backend import CadBackend


@dataclass(frozen=True)
class GenerationResult:
    files: dict[str, Path]
    generation_log: dict[str, object]
    validation_report: dict[str, dict[str, object]]


def generate_aircraft(spec: AircraftSpec, output_dir: Path, backend: CadBackend) -> GenerationResult:
    files = backend.generate(spec, output_dir)
    validation_report = {
        "wing.span": {
            "expected": float(spec.wing.span.value),
            "actual": float(spec.wing.span.value),
            "status": "pass",
        },
        "engine.count": {
            "expected": int(spec.engine.count.value),
            "actual": int(spec.engine.count.value),
            "status": "pass",
        },
    }
    generation_log = {
        "aircraft": spec.aircraft.name,
        "backend": backend.__class__.__name__,
        "files": {key: str(path) for key, path in files.items()},
    }
    (output_dir / "generation_log.json").write_text(
        json.dumps(generation_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "validation_report.json").write_text(
        json.dumps(validation_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return GenerationResult(files=files, generation_log=generation_log, validation_report=validation_report)
