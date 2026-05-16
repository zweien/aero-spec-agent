import importlib
from pathlib import Path
from typing import Any

import pytest

from services.workers.cad_worker.openvsp_generator.errors import (
    CadGenerationError,
    OpenVspUnavailableError,
)
from services.workers.cad_worker.openvsp_generator.openvsp_adapter import OpenVspAdapter


class FakeOpenVspModule:
    SET_ALL = 0
    EXPORT_STEP = 10
    EXPORT_OBJ = 11

    def __init__(
        self,
        *,
        geom_id: str | None = "geom-1",
        parm_id: str | None = "parm-1",
    ) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.geom_id = geom_id
        self.parm_id = parm_id

    def ClearVSPModel(self) -> None:
        self.calls.append(("ClearVSPModel",))

    def AddGeom(self, kind: str, parent_id: str) -> str | None:
        self.calls.append(("AddGeom", kind, parent_id))
        return self.geom_id

    def FindParm(self, geom_id: str, parm_name: str, group_name: str) -> str | None:
        self.calls.append(("FindParm", geom_id, parm_name, group_name))
        return self.parm_id

    def SetParmVal(self, parm_id: str, value: float | int | str) -> None:
        self.calls.append(("SetParmVal", parm_id, value))

    def WriteVSPFile(self, path: str) -> None:
        self.calls.append(("WriteVSPFile", path))

    def ExportFile(self, path: str, set_id: int, export_type: int) -> None:
        self.calls.append(("ExportFile", path, set_id, export_type))
        Path(path).write_text(f"export {export_type}\n", encoding="utf-8")


class FakeVspError:
    def __init__(self, message: str) -> None:
        self.message = message

    def GetErrorString(self) -> str:
        return self.message


class FakeErrorManager:
    def __init__(self, errors: list[str] | None = None) -> None:
        self.errors = [FakeVspError(error) for error in (errors or [])]

    def GetNumTotalErrors(self) -> int:
        return len(self.errors)

    def PopLastError(self) -> FakeVspError:
        return self.errors.pop()

    def push(self, message: str) -> None:
        self.errors.append(FakeVspError(message))


def _attach_error_manager(fake_vsp: FakeOpenVspModule, manager: FakeErrorManager) -> None:
    fake_vsp.ErrorMgrSingleton = type(
        "ErrorMgrSingleton",
        (),
        {"getInstance": staticmethod(lambda: manager)},
    )


def test_adapter_delegates_openvsp_calls_in_order(tmp_path: Path):
    fake_vsp = FakeOpenVspModule()
    adapter = OpenVspAdapter(module=fake_vsp)
    output_path = tmp_path / "aircraft.vsp3"

    adapter.clear_model()
    geom_id = adapter.add_geom("FUSELAGE")
    adapter.set_param(geom_id, "Length", "Design", 12.5)
    adapter.write_vsp_file(output_path)

    assert geom_id == "geom-1"
    assert fake_vsp.calls == [
        ("ClearVSPModel",),
        ("AddGeom", "FUSELAGE", ""),
        ("FindParm", "geom-1", "Length", "Design"),
        ("SetParmVal", "parm-1", 12.5),
        ("WriteVSPFile", str(output_path)),
    ]


def test_set_param_uses_find_parm_result_for_set_parm_val():
    fake_vsp = FakeOpenVspModule(parm_id="resolved-parm")
    adapter = OpenVspAdapter(module=fake_vsp)

    adapter.set_param("geom-2", "Span", "XForm", 42)

    assert ("SetParmVal", "resolved-parm", 42) in fake_vsp.calls
    assert ("SetParmVal", "geom-2", "Span", "XForm", 42) not in fake_vsp.calls


def test_export_file_uses_openvsp_export_constant_and_all_set(tmp_path: Path):
    fake_vsp = FakeOpenVspModule()
    adapter = OpenVspAdapter(module=fake_vsp)
    output_path = tmp_path / "aircraft.step"

    adapter.export_file(output_path, "EXPORT_STEP")

    assert output_path.read_text(encoding="utf-8") == "export 10\n"
    assert ("ExportFile", str(output_path), 0, 10) in fake_vsp.calls


@pytest.mark.parametrize("empty_geom_id", ["", None])
def test_add_geom_raises_when_openvsp_returns_empty_id(empty_geom_id: str | None):
    fake_vsp = FakeOpenVspModule(geom_id=empty_geom_id)
    adapter = OpenVspAdapter(module=fake_vsp)

    with pytest.raises(CadGenerationError, match="WING"):
        adapter.add_geom("WING")


@pytest.mark.parametrize("empty_parm_id", ["", None])
def test_set_param_raises_when_openvsp_returns_empty_parm_id(empty_parm_id: str | None):
    fake_vsp = FakeOpenVspModule(parm_id=empty_parm_id)
    adapter = OpenVspAdapter(module=fake_vsp)

    with pytest.raises(CadGenerationError, match="Span"):
        adapter.set_param("geom-3", "Span", "XForm", 18.0)


def test_adapter_raises_clear_error_when_openvsp_module_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    real_import_module = importlib.import_module

    def fake_import_module(name: str, package: str | None = None):
        if name == "openvsp":
            raise ModuleNotFoundError("No module named 'openvsp'")
        return real_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import_module)
    adapter = OpenVspAdapter()

    with pytest.raises(OpenVspUnavailableError, match="OpenVSP Python bindings"):
        adapter.clear_model()


def test_check_errors_records_openvsp_error_stack():
    fake_vsp = FakeOpenVspModule()
    manager = FakeErrorManager(["bad span"])
    _attach_error_manager(fake_vsp, manager)
    adapter = OpenVspAdapter(module=fake_vsp)

    errors = adapter.check_errors("manual")

    assert errors == [{"context": "manual", "message": "bad span"}]
    assert adapter.errors == errors


def test_add_geom_checks_openvsp_error_stack_after_call():
    class ErroringAddGeomModule(FakeOpenVspModule):
        def __init__(self, manager: FakeErrorManager) -> None:
            super().__init__()
            self.manager = manager

        def AddGeom(self, kind: str, parent_id: str) -> str | None:
            geom_id = super().AddGeom(kind, parent_id)
            self.manager.push("AddGeom warning")
            return geom_id

    manager = FakeErrorManager()
    fake_vsp = ErroringAddGeomModule(manager)
    _attach_error_manager(fake_vsp, manager)
    adapter = OpenVspAdapter(module=fake_vsp)

    adapter.add_geom("WING")

    assert adapter.errors == [
        {"context": "AddGeom(WING)", "message": "AddGeom warning"}
    ]


def test_error_policy_warn_does_not_raise(monkeypatch):
    monkeypatch.setenv("OPENVSP_ERROR_POLICY", "warn")
    fake_vsp = FakeOpenVspModule()
    manager = FakeErrorManager(["soft warn"])
    _attach_error_manager(fake_vsp, manager)
    adapter = OpenVspAdapter(module=fake_vsp)

    errors = adapter.check_errors("warn-test")
    assert len(errors) == 1


def test_error_policy_fail_raises_cad_generation_error(monkeypatch):
    monkeypatch.setenv("OPENVSP_ERROR_POLICY", "fail")
    fake_vsp = FakeOpenVspModule()
    manager = FakeErrorManager(["fatal error"])
    _attach_error_manager(fake_vsp, manager)
    adapter = OpenVspAdapter(module=fake_vsp)

    with pytest.raises(CadGenerationError, match="fatal error"):
        adapter.check_errors("fail-test")
