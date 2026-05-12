from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.workers.cad_worker.openvsp_generator.create_engine import (
    create_engine_nacelles,
)
from services.workers.cad_worker.openvsp_generator.create_fuselage import create_fuselage
from services.workers.cad_worker.openvsp_generator.create_tail import create_tail
from services.workers.cad_worker.openvsp_generator.create_wing import create_main_wing
from services.workers.cad_worker.openvsp_generator.geometry import GeometryBuildResult
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter
from services.workers.cad_worker.openvsp_generator.verify_model import (
    verification_entry,
    verify_vsp3_file,
)


@dataclass(frozen=True)
class CadArtifacts:
    vsp3: Path
    step: Path | None = None
    glb: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class CadBackend(Protocol):
    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        """Generate CAD artifacts."""


class FakeCadBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        glb = output_dir / "aircraft.glb"
        vsp3.write_text(f"fake vsp3 for {spec.aircraft.name}\n", encoding="utf-8")
        step.write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        glb.write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return CadArtifacts(vsp3=vsp3, step=step, glb=glb, metadata={"backend": "fake"})


class OpenVspBackend:
    def __init__(self, vsp_module: object | None = None) -> None:
        self._vsp_module = vsp_module

    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        adapter = OpenVspAdapter(module=self._vsp_module)
        adapter.clear_model()

        build_results: list[GeometryBuildResult] = [
            create_fuselage(adapter, spec),
            create_main_wing(adapter, spec),
            *create_tail(adapter, spec),
            *create_engine_nacelles(adapter, spec),
        ]

        adapter.update()
        vsp3 = output_dir / "aircraft.vsp3"
        adapter.write_vsp_file(vsp3)

        applied_parameters = _stable_applied_parameters(build_results)
        validation = {
            "vsp3": verify_vsp3_file(vsp3),
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
            step=None,
            glb=None,
            metadata={
                "backend": "openvsp",
                "components": _components(build_results),
                "applied_parameters": applied_parameters,
                "validation": validation,
            },
        )


def _components(build_results: list[GeometryBuildResult]) -> dict[str, str]:
    return {result.name: result.geom_id for result in build_results}


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
        elif result.name in {"left_engine", "right_engine"}:
            if "engine.count" in result.applied_parameters:
                applied["engine.count"] = result.applied_parameters["engine.count"]
            _copy_parameters(
                applied,
                result.name,
                result,
                [
                    "x_rel_location",
                    "y_rel_location",
                    "z_rel_location",
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
