import os
import time
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
        # Emit CAD progress events for testing visibility
        step_delay = float(os.getenv("FAKE_CAD_STEP_DELAY_MS", "0")) / 1000.0
        fail_stage = os.getenv("FAKE_CAD_FAIL_STAGE", "").strip()
        if on_progress:
            for stage, progress in [
                ("fuselage_created", 62),
                ("wing_created", 68),
                ("tail_created", 72),
                ("engine_created", 76),
                ("vsp_model_saved", 82),
                ("step_exported", 86),
                ("glb_exported", 92),
                ("preview_ready", 96),
            ]:
                if step_delay > 0:
                    time.sleep(step_delay)
                on_progress(stage, progress)
                if fail_stage == stage:
                    raise RuntimeError(f"Fake CAD failure at stage: {stage}")
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
        fail_stage = os.getenv("OPENVSP_FAIL_STAGE", "").strip()
        adapter = OpenVspAdapter(module=self._vsp_module)
        adapter.clear_model()

        layout = str(spec.aircraft.layout).lower()

        build_results: list[GeometryBuildResult] = []

        # Fuselage (not for flying_wing; BWB uses flat_body; multi_fuselage uses paired fuselages)
        if layout == "multi_fuselage" and spec.multi_fuselage is not None:
            from services.workers.cad_worker.openvsp_generator.create_multi_fuselage import create_multi_fuselage
            build_results.extend(create_multi_fuselage(adapter, spec))
        elif layout == "blended_wing_body" and spec.body is not None:
            from services.workers.cad_worker.openvsp_generator.create_body import create_flat_body
            build_results.append(create_flat_body(adapter, spec))
        elif layout != "flying_wing":
            build_results.append(create_fuselage(adapter, spec))
        if on_progress: on_progress("fuselage_created", 62)
        if fail_stage == "creating_fuselage":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_fuselage")

        # Wing creation (all layouts)
        wing_result = create_main_wing(adapter, spec)
        if isinstance(wing_result, list):
            build_results.extend(wing_result)
        else:
            build_results.append(wing_result)
        if on_progress: on_progress("wing_created", 68)
        if fail_stage == "creating_wing":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_wing")

        # Booms (twin_boom layout only)
        if layout == "twin_boom" and spec.boom is not None:
            from services.workers.cad_worker.openvsp_generator.create_boom import create_booms
            build_results.extend(create_booms(adapter, spec))
        if on_progress: on_progress("booms_created", 70)
        if fail_stage == "creating_booms":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_booms")

        # Canard (canard / three_surface layouts)
        if layout in ("canard", "three_surface") and spec.canard is not None:
            from services.workers.cad_worker.openvsp_generator.create_canard import create_canard
            build_results.append(create_canard(adapter, spec))

        # Rear wing (tandem_wing / joined_wing layouts)
        if layout in ("tandem_wing", "joined_wing") and spec.rear_wing is not None:
            from services.workers.cad_worker.openvsp_generator.create_tandem_wing import create_rear_wing
            build_results.append(create_rear_wing(adapter, spec))

        # Second/lower wing (biplane layout)
        if layout == "biplane" and spec.second_wing is not None:
            from services.workers.cad_worker.openvsp_generator.create_biplane import create_lower_wing
            build_results.append(create_lower_wing(adapter, spec))

        # Box wing lower wing + endplates (box_wing layout)
        if layout == "box_wing" and spec.box_wing_config is not None:
            from services.workers.cad_worker.openvsp_generator.create_box_wing import (
                create_box_lower_wing, create_endplates,
            )
            build_results.append(create_box_lower_wing(adapter, spec))
            build_results.extend(create_endplates(adapter, spec))

        # Tail (not for flying_wing, BWB, tandem_wing, joined_wing)
        if layout not in ("flying_wing", "blended_wing_body", "tandem_wing", "joined_wing"):
            build_results.extend(create_tail(adapter, spec))
        if on_progress: on_progress("tail_created", 72)
        if fail_stage == "creating_tail":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_tail")

        # Engines
        build_results.extend(create_engine_nacelles(adapter, spec))
        if on_progress: on_progress("engine_created", 76)
        if fail_stage == "creating_engine":
            raise RuntimeError(f"OpenVSP failure injection at stage: creating_engine")

        adapter.update()

        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        obj = output_dir / "aircraft.obj"
        glb = output_dir / "aircraft.glb"
        adapter.write_vsp_file(vsp3)
        if on_progress: on_progress("vsp_model_saved", 82)
        if fail_stage == "saving_vsp3":
            raise RuntimeError(f"OpenVSP failure injection at stage: saving_vsp3")

        vspaero_data: dict[str, Any] = {}
        if _vspaero_enabled():
            from services.workers.cad_worker.openvsp_generator.vspaero_analysis import (
                build_analysis_geoms,
                LAYOUT_ANALYSIS_NAMES,
                run_vspaero_analysis,
            )
            geom_ids = build_analysis_geoms(spec, build_results)
            if geom_ids:
                try:
                    report = run_vspaero_analysis(
                        adapter, spec, geom_ids, output_dir=output_dir,
                    )
                    layout = spec.aircraft.layout.lower()
                    all_names = ["main_wing"] + LAYOUT_ANALYSIS_NAMES.get(layout, [])
                    component_map = _components(build_results)
                    report.components_analyzed = [
                        n for n in all_names if n in component_map
                    ]
                    vspaero_data = report.to_dict()
                except Exception as exc:
                    vspaero_data = {"status": "failed", "error_message": str(exc)}
        try:
            adapter.export_file(step, "EXPORT_STEP")
        except Exception as exc:
            adapter.errors.append(f"STEP export failed: {exc}")
        if on_progress: on_progress("step_exported", 86)
        if fail_stage == "exporting_step":
            raise RuntimeError(f"OpenVSP failure injection at stage: exporting_step")
        adapter.export_file(obj, "EXPORT_OBJ")
        self._obj_to_glb(obj, glb)
        if on_progress: on_progress("glb_exported", 92)
        if fail_stage == "exporting_glb":
            raise RuntimeError(f"OpenVSP failure injection at stage: exporting_glb")

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

    _ALL_WING_NAMES = {
        "main_wing", "inner_wing", "outer_wing", "outer_wing_2", "mid_wing",
    }
    _ALL_ENGINE_NAMES = {
        "center_engine", "left_engine", "right_engine",
        "left_inner_engine", "left_outer_engine",
        "right_inner_engine", "right_outer_engine",
        "front_engine", "rear_engine",
    }
    _ALL_BOOM_NAMES = {"left_boom", "right_boom"}
    _BODY_NAMES = {"flat_body"}
    _CANARD_NAMES = {"canard"}
    _REAR_WING_NAMES = {"rear_wing", "joined_rear_wing"}
    _SECOND_WING_NAMES = {"lower_wing"}
    _MULTI_FUSELAGE_NAMES = {"left_fuselage", "right_fuselage"}
    _BOX_WING_NAMES = {"box_lower_wing"}
    _ENDPLATE_NAMES = {"left_endplate", "right_endplate"}

    for result in build_results:
        if result.name == "fuselage":
            _copy_parameters(applied, "fuselage", result, ["length", "max_diameter"])
        elif result.name in _ALL_WING_NAMES:
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
        elif result.name in _ALL_ENGINE_NAMES:
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
        elif result.name in _ALL_BOOM_NAMES:
            _copy_parameters(
                applied,
                result.name,
                result,
                list(result.applied_parameters),
            )
        elif result.name in _BODY_NAMES:
            _copy_parameters(
                applied,
                result.name,
                result,
                list(result.applied_parameters),
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
