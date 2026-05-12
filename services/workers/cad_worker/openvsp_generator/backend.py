from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from services.api.app.schemas.aircraft_spec import AircraftSpec


@dataclass(frozen=True)
class CadArtifacts:
    vsp3: Path
    step: Path
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
    def generate(self, spec: AircraftSpec, output_dir: Path) -> CadArtifacts:
        output_dir.mkdir(parents=True, exist_ok=True)
        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        glb = output_dir / "aircraft.glb"
        vsp3.write_text(f"placeholder OpenVSP vsp3 for {spec.aircraft.name}\n", encoding="utf-8")
        step.write_text("STEP export requires OpenVSP adapter implementation\n", encoding="utf-8")
        glb.write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return CadArtifacts(vsp3=vsp3, step=step, glb=glb, metadata={"backend": "openvsp"})
