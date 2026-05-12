import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.backend import CadArtifacts, CadBackend
from services.workers.cad_worker.openvsp_generator.verify_model import verification_entry


@dataclass(frozen=True)
class GenerationResult:
    files: dict[str, Path]
    generation_log: dict[str, object]
    validation_report: dict[str, Any]


def _artifact_files(artifacts: CadArtifacts) -> dict[str, Path]:
    files = {"vsp3": artifacts.vsp3}
    if artifacts.step is not None:
        files["step"] = artifacts.step
    if artifacts.glb is not None:
        files["glb"] = artifacts.glb
    return files


def generate_aircraft(spec: AircraftSpec, output_dir: Path, backend: CadBackend) -> GenerationResult:
    artifacts = backend.generate(spec, output_dir)
    artifact_files = _artifact_files(artifacts)
    backend_name = str(artifacts.metadata.get("backend", backend.__class__.__name__))
    generation_log_path = output_dir / "generation_log.json"
    validation_report_path = output_dir / "validation_report.json"
    applied_parameters = artifacts.metadata.get("applied_parameters", {})
    if not isinstance(applied_parameters, dict):
        applied_parameters = {}
    backend_validation = artifacts.metadata.get("validation", {})
    if not isinstance(backend_validation, dict):
        backend_validation = {}
    wing_span_actual = applied_parameters.get("wing.span", float(spec.wing.span.value))
    engine_count_actual = applied_parameters.get("engine.count", int(spec.engine.count.value))
    validation_report = {
        "backend": verification_entry(backend_name, backend_name),
        "backend_name": backend_name,
        "vsp3": {
            "path": str(artifacts.vsp3),
            "exists": artifacts.vsp3.exists(),
        },
        "spec_echo": spec.model_dump(mode="json"),
    }
    for key, value in backend_validation.items():
        if key == "vsp3" and isinstance(value, dict):
            validation_report["vsp3"].update(value)
        else:
            validation_report[key] = value
    validation_report["vsp3.exists"] = verification_entry(True, artifacts.vsp3.exists())
    validation_report["wing.span"] = verification_entry(
        float(spec.wing.span.value),
        wing_span_actual,
    )
    validation_report["engine.count"] = verification_entry(
        int(spec.engine.count.value),
        engine_count_actual,
    )
    generation_log = {
        "aircraft": spec.aircraft.name,
        "backend": backend_name,
        "backend_metadata": artifacts.metadata,
        "components": artifacts.metadata.get("components", {}),
        "applied_parameters": applied_parameters,
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
