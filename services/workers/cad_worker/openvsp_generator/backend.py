from pathlib import Path
from typing import Protocol

from services.api.app.schemas.aircraft_spec import AircraftSpec


class CadBackend(Protocol):
    def generate(self, spec: AircraftSpec, output_dir: Path) -> dict[str, Path]:
        """Generate CAD artifacts and return file type to path mapping."""


class FakeCadBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> dict[str, Path]:
        output_dir.mkdir(parents=True, exist_ok=True)
        files = {
            "vsp3": output_dir / "aircraft.vsp3",
            "step": output_dir / "aircraft.step",
            "glb": output_dir / "aircraft.glb",
        }
        files["vsp3"].write_text(f"fake vsp3 for {spec.aircraft.name}\n", encoding="utf-8")
        files["step"].write_text("ISO-10303-21;\nEND-ISO-10303-21;\n", encoding="utf-8")
        files["glb"].write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return files


class OpenVspBackend:
    def generate(self, spec: AircraftSpec, output_dir: Path) -> dict[str, Path]:
        try:
            import openvsp as vsp
        except ImportError as exc:
            raise RuntimeError("OpenVSP Python package is not installed") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        vsp.ClearVSPModel()
        fuselage_id = vsp.AddGeom("FUSELAGE")
        wing_id = vsp.AddGeom("WING")
        if not fuselage_id or not wing_id:
            raise RuntimeError("OpenVSP failed to create base geometry")

        vsp.Update()
        vsp3 = output_dir / "aircraft.vsp3"
        step = output_dir / "aircraft.step"
        glb = output_dir / "aircraft.glb"
        vsp.WriteVSPFile(str(vsp3))
        step.write_text("STEP export requires OpenVSP export configuration\n", encoding="utf-8")
        glb.write_bytes(b"glTF\x02\x00\x00\x00\x14\x00\x00\x00")
        return {"vsp3": vsp3, "step": step, "glb": glb}
