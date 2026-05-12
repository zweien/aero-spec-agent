from pathlib import Path
from typing import Any

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import CadArtifacts, OpenVspBackend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft
from tests.api.test_openvsp_geometry_builders import valid_spec_data


class FakeOpenVspModule:
    _ALLOWED_PARAMETERS = {
        "FUSELAGE": {
            ("Length", "Design"),
            ("Diameter", "Design"),
        },
        "WING": {
            ("TotalSpan", "WingGeom"),
            ("Root_Chord", "XSec_1"),
            ("Tip_Chord", "XSec_1"),
            ("Sweep", "XSec_1"),
            ("Dihedral", "XSec_1"),
            ("X_Rel_Location", "XForm"),
            ("X_Rel_Rotation", "XForm"),
            ("Z_Rel_Location", "XForm"),
        },
        "POD": {
            ("X_Rel_Location", "XForm"),
            ("Y_Rel_Location", "XForm"),
            ("Z_Rel_Location", "XForm"),
            ("Length", "Design"),
            ("FineRatio", "Design"),
        },
    }

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.geom_kinds: dict[str, str] = {}
        self.next_index = 1

    def ClearVSPModel(self) -> None:
        self.calls.append(("ClearVSPModel",))

    def AddGeom(self, kind: str, parent_id: str) -> str:
        geom_id = f"geom-{self.next_index}"
        self.next_index += 1
        self.geom_kinds[geom_id] = kind
        self.calls.append(("AddGeom", kind, parent_id, geom_id))
        return geom_id

    def FindParm(self, geom_id: str, parm_name: str, group_name: str) -> str:
        self.calls.append(("FindParm", geom_id, parm_name, group_name))
        kind = self.geom_kinds[geom_id]
        if (parm_name, group_name) not in self._ALLOWED_PARAMETERS[kind]:
            return ""
        return f"parm:{geom_id}:{parm_name}:{group_name}"

    def SetParmVal(self, parm_id: str, value: float | int | str) -> None:
        self.calls.append(("SetParmVal", parm_id, value))

    def Update(self) -> None:
        self.calls.append(("Update",))

    def WriteVSPFile(self, path: str) -> None:
        self.calls.append(("WriteVSPFile", path))
        Path(path).write_text("fake openvsp model\n", encoding="utf-8")


def _spec():
    return load_aircraft_spec(valid_spec_data())


def test_openvsp_backend_orchestrates_builders_and_returns_vsp3_only(tmp_path: Path):
    fake_vsp = FakeOpenVspModule()

    artifacts = OpenVspBackend(vsp_module=fake_vsp).generate(_spec(), tmp_path)

    assert artifacts.vsp3.exists()
    assert artifacts.vsp3.stat().st_size > 0
    assert artifacts.step is None
    assert artifacts.glb is None
    assert artifacts.metadata["backend"] == "openvsp"
    assert artifacts.metadata["components"] == {
        "fuselage": "geom-1",
        "main_wing": "geom-2",
        "horizontal_tail": "geom-3",
        "vertical_tail": "geom-4",
        "left_engine": "geom-5",
        "right_engine": "geom-6",
    }
    assert artifacts.metadata["applied_parameters"]["wing.span"] == 12.0
    assert artifacts.metadata["applied_parameters"]["wing.root_chord"] == 1.2
    assert artifacts.metadata["applied_parameters"]["fuselage.length"] == 7.0
    assert artifacts.metadata["applied_parameters"]["engine.count"] == 2
    assert artifacts.metadata["applied_parameters"]["left_engine.diameter"] == 0.375
    assert artifacts.metadata["applied_parameters"]["left_engine.fineness_ratio"] == pytest.approx(
        3.2
    )
    assert artifacts.metadata["validation"]["vsp3"]["status"] == "pass"


def test_openvsp_backend_updates_model_before_writing_vsp3(tmp_path: Path):
    fake_vsp = FakeOpenVspModule()

    OpenVspBackend(vsp_module=fake_vsp).generate(_spec(), tmp_path)

    call_names = [call[0] for call in fake_vsp.calls]
    assert call_names.index("Update") < call_names.index("WriteVSPFile")


def test_generate_aircraft_uses_openvsp_metadata_for_files_validation_and_log(
    tmp_path: Path,
):
    fake_vsp = FakeOpenVspModule()

    result = generate_aircraft(
        spec=_spec(),
        output_dir=tmp_path,
        backend=OpenVspBackend(vsp_module=fake_vsp),
    )

    assert set(result.files) == {"vsp3"}
    assert result.validation_report["backend"] == {
        "expected": "openvsp",
        "actual": "openvsp",
        "status": "pass",
    }
    assert result.validation_report["backend_name"] == "openvsp"
    assert result.validation_report["wing.span"]["actual"] == 12.0
    assert result.validation_report["engine.count"]["actual"] == 2
    assert result.generation_log["components"]["fuselage"] == "geom-1"
    assert result.generation_log["applied_parameters"]["wing.span"] == 12.0


def test_generate_aircraft_prefers_applied_parameters_over_backend_validation(
    tmp_path: Path,
):
    class StaleValidationBackend:
        def generate(self, _spec, output_dir: Path) -> CadArtifacts:
            output_dir.mkdir(parents=True, exist_ok=True)
            vsp3 = output_dir / "aircraft.vsp3"
            vsp3.write_text("fake openvsp model\n", encoding="utf-8")
            return CadArtifacts(
                vsp3=vsp3,
                metadata={
                    "backend": "openvsp",
                    "applied_parameters": {
                        "wing.span": 12.0,
                        "engine.count": 2,
                    },
                    "validation": {
                        "wing.span": {
                            "expected": 12.0,
                            "actual": 99.0,
                            "status": "fail",
                        },
                        "engine.count": {
                            "expected": 2,
                            "actual": 99,
                            "status": "fail",
                        },
                    },
                },
            )

    result = generate_aircraft(
        spec=_spec(),
        output_dir=tmp_path,
        backend=StaleValidationBackend(),
    )

    assert result.validation_report["wing.span"] == {
        "expected": 12.0,
        "actual": 12.0,
        "status": "pass",
    }
    assert result.validation_report["engine.count"] == {
        "expected": 2,
        "actual": 2,
        "status": "pass",
    }
