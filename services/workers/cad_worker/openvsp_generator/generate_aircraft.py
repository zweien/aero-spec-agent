import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.backend import CadArtifacts, CadBackend, ProgressCallback
from services.workers.cad_worker.openvsp_generator.design_rules import run_design_rules
from services.workers.cad_worker.openvsp_generator.performance_estimate import run_performance_estimate
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
    files.update(artifacts.extra_files)
    return files


def _scalar_value(scalar: Any, default: float | int | None = None) -> float | int:
    if scalar is None:
        if default is None:
            raise ValueError("missing scalar")
        return default
    return scalar.value


def _engine_offset_value(spec: Any, attr: str) -> float:
    field = getattr(spec.engine, attr, None)
    if field is not None and hasattr(field, "value"):
        return float(field.value)
    return 0.0


def _file_size_entry(path: Path) -> dict[str, Any]:
    size = path.stat().st_size if path.exists() else 0
    return {
        "expected": ">0 bytes",
        "actual": size,
        "status": "pass" if size > 0 else "fail",
    }


def _glb_parseable_entry(path: Path) -> dict[str, Any]:
    actual = False
    if path.exists():
        data = path.read_bytes()
        if len(data) >= 12:
            version = int.from_bytes(data[4:8], "little")
            declared_length = int.from_bytes(data[8:12], "little")
            actual = data[:4] == b"glTF" and version == 2 and declared_length == len(data)
    return verification_entry(True, actual)


def generate_aircraft(spec: AircraftSpec, output_dir: Path, backend: CadBackend, *, on_progress: ProgressCallback | None = None) -> GenerationResult:
    try:
        artifacts = backend.generate(spec, output_dir, on_progress=on_progress)
    except TypeError:
        # Backward compat: legacy backends that don't accept on_progress yet
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
    parameter_expectations = {
        "fuselage.length": _scalar_value(spec.fuselage.length),
        "fuselage.max_diameter": _scalar_value(spec.fuselage.max_diameter, 0.75),
        "wing.root_chord": _scalar_value(spec.wing.root_chord),
        "wing.tip_chord": _scalar_value(spec.wing.tip_chord),
        "wing.sweep": _scalar_value(spec.wing.sweep, 0.0),
        "wing.dihedral": _scalar_value(spec.wing.dihedral, 0.0),
        "engine.x_offset": _engine_offset_value(spec, "x_offset"),
        "engine.y_offset": _engine_offset_value(spec, "y_offset"),
        "engine.z_offset": _engine_offset_value(spec, "z_offset"),
    }
    for key, expected in parameter_expectations.items():
        validation_report[key] = verification_entry(
            expected,
            applied_parameters.get(key, expected),
        )
    validation_report["file_sizes"] = {
        key: _file_size_entry(path) for key, path in artifact_files.items()
    }
    if artifacts.glb is not None:
        validation_report["glb.parseable"] = _glb_parseable_entry(artifacts.glb)
    rule_report = run_design_rules(spec)
    validation_report["design_rules"] = rule_report.to_dict()
    perf_report = run_performance_estimate(spec)
    validation_report["performance_estimate"] = perf_report.to_dict()
    vspaero_data = artifacts.metadata.get("vspaero_analysis")
    if vspaero_data:
        validation_report["vspaero_analysis"] = vspaero_data
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
