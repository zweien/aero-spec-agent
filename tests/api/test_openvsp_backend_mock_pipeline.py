"""OpenVSP backend mock pipeline tests.

Tests the OpenVspBackend pipeline using FakeOpenVspModule,
covering normal flow, failure injection, STEP degradation, and GLB failure.
"""

import os
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft
from tests.api.test_openvsp_backend_unit import FakeOpenVspModule, fake_obj_to_glb
from tests.api.test_openvsp_geometry_builders import valid_spec_data


def _spec():
    return load_aircraft_spec(valid_spec_data())


class StepFailingVspModule(FakeOpenVspModule):
    """FakeVspModule that raises on STEP export."""

    def ExportFile(self, path: str, set_id: int, export_type: int) -> None:
        if export_type == self.EXPORT_STEP:
            raise RuntimeError("STEP export not supported in this build")
        super().ExportFile(path, set_id, export_type)


class GlbFailingConverter:
    """obj_to_glb that always fails."""

    def __call__(self, _obj_path: Path, glb_path: Path) -> None:
        raise RuntimeError("GLB conversion failed: trimesh error")


def test_mock_pipeline_normal_flow_all_artifacts(tmp_path: Path):
    """Normal flow generates vsp3, step, obj, glb."""
    fake_vsp = FakeOpenVspModule()
    artifacts = OpenVspBackend(
        obj_to_glb=fake_obj_to_glb,
        vsp_module=fake_vsp,
    ).generate(_spec(), tmp_path)

    assert artifacts.vsp3.exists()
    assert artifacts.step is not None and artifacts.step.exists()
    assert artifacts.extra_files["obj"].exists()
    assert artifacts.glb is not None and artifacts.glb.exists()
    assert artifacts.glb.read_bytes()[:4] == b"glTF"


def test_mock_pipeline_stage_order(tmp_path: Path):
    """Progress callbacks arrive in expected order."""
    fake_vsp = FakeOpenVspModule()
    stages: list[str] = []

    def on_progress(stage: str, pct: int) -> None:
        stages.append(stage)

    OpenVspBackend(
        obj_to_glb=fake_obj_to_glb,
        vsp_module=fake_vsp,
    ).generate(_spec(), tmp_path, on_progress=on_progress)

    assert stages[0] == "fuselage_created"
    assert stages[1] == "wing_created"
    assert stages.index("vsp_model_saved") < stages.index("glb_exported")


def test_mock_pipeline_step_failure_degradation(tmp_path: Path):
    """STEP export failure does not block GLB generation."""
    fake_vsp = StepFailingVspModule()
    artifacts = OpenVspBackend(
        obj_to_glb=fake_obj_to_glb,
        vsp_module=fake_vsp,
    ).generate(_spec(), tmp_path)

    # STEP should not exist (export failed), but GLB should still be generated
    assert not artifacts.step.exists() or artifacts.step.stat().st_size == 0
    assert artifacts.glb is not None and artifacts.glb.exists()
    assert artifacts.glb.read_bytes()[:4] == b"glTF"


def test_mock_pipeline_glb_conversion_failure(tmp_path: Path):
    """GLB conversion failure propagates as exception."""
    fake_vsp = FakeOpenVspModule()
    with pytest.raises(RuntimeError, match="GLB conversion failed"):
        OpenVspBackend(
            obj_to_glb=GlbFailingConverter(),
            vsp_module=fake_vsp,
        ).generate(_spec(), tmp_path)


@pytest.mark.parametrize("fail_stage", [
    "creating_fuselage",
    "creating_wing",
    "creating_tail",
    "creating_engine",
    "saving_vsp3",
    "exporting_step",
    "exporting_glb",
])
def test_mock_pipeline_fail_stage_injection(tmp_path: Path, fail_stage: str, monkeypatch):
    """OPENVSP_FAIL_STAGE raises RuntimeError at the specified stage."""
    monkeypatch.setenv("OPENVSP_FAIL_STAGE", fail_stage)
    fake_vsp = FakeOpenVspModule()
    with pytest.raises(RuntimeError, match=f"OpenVSP failure injection at stage: {fail_stage}"):
        OpenVspBackend(
            obj_to_glb=fake_obj_to_glb,
            vsp_module=fake_vsp,
        ).generate(_spec(), tmp_path)


def test_mock_pipeline_generate_aircraft_integration(tmp_path: Path):
    """Full generate_aircraft pipeline with FakeOpenVspModule produces valid output."""
    fake_vsp = FakeOpenVspModule()
    result = generate_aircraft(
        spec=_spec(),
        output_dir=tmp_path,
        backend=OpenVspBackend(obj_to_glb=fake_obj_to_glb, vsp_module=fake_vsp),
    )

    assert set(result.files) == {"vsp3", "step", "obj", "glb"}
    assert result.validation_report["backend"]["actual"] == "openvsp"
    assert result.validation_report["vsp3.exists"]["status"] == "pass"
    assert result.validation_report["glb.exists"]["status"] == "pass"
    assert result.generation_log["applied_parameters"]["wing.span"] == 12.0
