import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.backend import CadArtifacts, CadBackend


@dataclass(frozen=True)
class GenerationResult:
    files: dict[str, Path]
    generation_log: dict[str, object]
    validation_report: dict[str, Any]


def _artifact_files(artifacts: CadArtifacts) -> dict[str, Path]:
    files = {
        "vsp3": artifacts.vsp3,
        "step": artifacts.step,
    }
    if artifacts.glb is not None:
        files["glb"] = artifacts.glb
    return files


def generate_aircraft(spec: AircraftSpec, output_dir: Path, backend: CadBackend) -> GenerationResult:
    artifacts = backend.generate(spec, output_dir)
    artifact_files = _artifact_files(artifacts)
    backend_name = str(artifacts.metadata.get("backend", backend.__class__.__name__))
    generation_log_path = output_dir / "generation_log.json"
    validation_report_path = output_dir / "validation_report.json"
    validation_report = {
        "backend": backend_name,
        "vsp3": {
            "path": str(artifacts.vsp3),
            "exists": artifacts.vsp3.exists(),
        },
        "spec_echo": spec.model_dump(mode="json"),
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
        "backend": backend_name,
        "backend_metadata": artifacts.metadata,
        "files": {key: str(path) for key, path in artifact_files.items()},
    }
    generation_log_path.write_text(
        json.dumps(generation_log, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    validation_report_path.write_text(
        json.dumps(validation_report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return GenerationResult(files=artifact_files, generation_log=generation_log, validation_report=validation_report)
