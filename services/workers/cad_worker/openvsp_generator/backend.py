import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.create_engine import (
    create_engine_nacelles,
)
from services.workers.cad_worker.openvsp_generator.create_fuselage import create_fuselage
from services.workers.cad_worker.openvsp_generator.create_tail import create_tail
from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.obj_to_glb import convert_obj_to_glb
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter
from services.workers.cad_worker.openvsp_generator.verify_model import (
    verification_entry,
    verify_vsp3_file,
)

ProgressCallback = Callable[[str, int], None]


@dataclass(frozen=True)
class CadArtifacts:
    vsp3: Path
    step: Path | None = None
    glb: Path | None = None
    extra_files: dict[str, Path] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class CadBackend(Protocol):
    def generate(self, spec: AircraftSpec, output_dir: Path, *, on_progress: "ProgressCallback | None" = None) -> CadArtifacts:
        """Generate CAD artifacts."""


class FakeCadBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path, *, on_progress: ProgressCallback | None = None) -> CadArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        glb = output_dir / "aircraft.glb"
        vsp3.write_text(f"fake vsp3 for {spec.aircraft.name}\n", encoding="utf-8")
        step.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        glb.write_bytes(_minimal_glb())
        metadata: dict[str, Any] = {"backend": "fake"}
        if _vspaero_enabled():
            from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
                fake_vspaero_results,
            )
            metadata["vspaero_analysis"] = fake_vspaero_results(spec)
        return CadArtifacts(vsp3=vsp3, step=step, glb=glb, metadata=metadata)


class OpenVspBackend:
    def __init__(
        self,
        *,
        obj_to_glb: Callable[[Path, Path], None] = convert_obj_to_glb,
        vsp_module: object | None = None,
    ) -> None:
        self._obj_to_glb = obj_to_glb
        self._vsp_module = vsp_module

    def generate(self, spec: AircraftSpec, output_dir: Path, *, on_progress: ProgressCallback | None = None) -> CadArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        adapter = OpenVspAdapter(module=self._vsp_module)
        adapter.clear_model()

        build_results: list[GeometryBuildResult] = [
            create_fuselage(adapter, spec),
        ]
        if on_progress: on_progress("fuselage_created", 62)
        build_results.append(create_main_wing(adapter, spec))
        if on_progress: on_progress("wing_created", 68)
        build_results.extend(create_tail(adapter, spec))
        if on_progress: on_progress("tail_created", 72)
        build_results.extend(create_engine_nacelles(adapter, spec))
        if on_progress: on_progress("engine_created", 76)

        adapter.update()

        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        obj = output_dir / "aircraft.obj"
        glb = output_dir / "aircraft.glb"
        adapter.write_vsp_file(vsp3)
        if on_progress: on_progress("vsp_model_saved", 82)

        vspaero_data: dict[str, Any] = {}
        if _vspaero_enabled():
            from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
                run_vspaero_analysis,
            )
            components = _components(build_results)
            wing_id = components.get("main_wing", "")
            if wing_id:
                try:
                    report = run_vspaero_analysis(
                        adapter, spec, wing_id, output_dir=output_dir,
                    )
                    vspaero_data = report.to_dict()
                except Exception as exc:
                    vspaero_data = {"status": "failed", "error_message": str(exc)}
        adapter.export_file(step, "EXPORT_STEP")
        if on_progress: on_progress("step_exported", 86)
        adapter.export_file(obj, "EXPORT_OBJ")
        self._obj_to_glb(obj, glb)
        if on_progress: on_progress("glb_exported", 92)

        applied_parameters = _stable_applied_parameters(build_results)
        if on_progress: on_progress("preview_ready", 96)
        vsp3_validation = verify_vsp3_file(vsp3)
        step_validation = verify_vsp3_file(step)
        obj_validation = verify_vsp3_file(obj)
        glb_validation = verify_vsp3_file(glb)
        validation = {
            "vsp3": vsp3_validation,
            "vsp3.exists": vsp3_validation,
            "step.exists": step_validation,
            "obj.exists": obj_validation,
            "glb.exists": glb_validation,
            "openvsp.errors": _openvsp_error_validation(adapter.errors),
            "wing.span": verification_entry(
                float(spec.wing.span.value),
                applied_parameters.get("wing.span"),
            ),
            "engine.count": verification_entry(
                int(spec.engine.count.value),
                applied_parameters.get("engine.count"),
            ),
        }
        return CadArtifacts(
            vsp3=vsp3,
            step=step,
            glb=glb,
            extra_files={"obj": obj},
            metadata={
                "backend": "openvsp",
                "components": _components(build_results),
                "applied_parameters": applied_parameters,
                "validation": validation,
                "openvsp_errors": adapter.errors,
                "vspaero_analysis": vspaero_data,
            },
        )


def _components(build_results: list[GeometryBuildResult]) -> dict[str, str]:
    return {result.name: result.geom_id for result in build_results}


def _vspaero_enabled() -> bool:
    return os.getenv("RUN_VSPAERO_ANALYSIS", "").lower() in ("1", "true", "yes")


def _stable_applied_parameters(
    build_results: list[GeometryBuildResult],
) -> dict[str, object]:
    applied: dict[str, object] = {}
    for result in build_results:
        if result.name == "fuselage":
            _copy_parameters(applied, "fuselage", result, ["length", "max_diameter"])
        elif result.name == "main_wing":
            _copy_parameters(
                applied,
                "wing",
                result,
                [
                    "span",
                    "root_chord",
                    "tip_chord",
                    "sweep",
                    "dihedral",
                    "z_rel_location",
                ],
            )
        elif result.name in {"center_engine", "left_engine", "right_engine"}:
            if "engine.count" in result.applied_parameters:
                applied["engine.count"] = result.applied_parameters["engine.count"]
            for key in (
                "engine.x_offset",
                "engine.y_offset",
                "engine.z_offset",
                "base_x",
                "base_y",
                "base_z",
            ):
                if key in result.applied_parameters:
                    applied[f"engine.{key}" if key.startswith("base_") else key] = (
                        result.applied_parameters[key]
                    )
            _copy_parameters(
                applied,
                result.name,
                result,
                [
                    "x_rel_location",
                    "y_offset",
                    "z_rel_location",
                    "base_x",
                    "base_y",
                    "base_z",
                    "final_x",
                    "final_y",
                    "final_z",
                    "length",
                    "diameter",
                    "fineness_ratio",
                ],
            )
        else:
            _copy_parameters(
                applied,
                result.name,
                result,
                list(result.applied_parameters),
            )
    return applied


def _copy_parameters(
    target: dict[str, object],
    prefix: str,
    result: GeometryBuildResult,
    keys: list[str],
) -> None:
    for key in keys:
        if key in result.applied_parameters:
            target[f"{prefix}.{key}"] = result.applied_parameters[key]


def _minimal_glb() -> bytes:
    json_chunk = b'{"asset":{"version":"2.0"}}'
    padding = (4 - len(json_chunk) % 4) % 4
    json_chunk += b" " * padding
    chunk_header = len(json_chunk).to_bytes(4, "little") + b"JSON"
    total_length = 12 + len(chunk_header) + len(json_chunk)
    return b"glTF" + (2).to_bytes(4, "little") + total_length.to_bytes(4, "little") + chunk_header + json_chunk


def _openvsp_error_validation(errors: list[dict[str, str]]) -> dict[str, object]:
    return {
        "expected": [],
        "actual": errors,
        "status": "pass" if not errors else "fail",
    }
