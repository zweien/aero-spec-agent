import importlib
import os
from pathlib import Path
from typing import Any

from services.workers.cad_worker.openvsp_generator.errors import (
    CadGenerationError,
    OpenVspUnavailableError,
)

_ERROR_POLICY_FAIL = os.getenv("OPENVSP_ERROR_POLICY", "warn").lower() == "fail"


class OpenVspAdapter:
    def __init__(self, module: Any | None = None) -> None:
        self._module = module
        self.errors: list[dict[str, str]] = []

    @property
    def _vsp(self) -> Any:
        if self._module is None:
            try:
                self._module = importlib.import_module("openvsp")
            except ModuleNotFoundError as exc:
                raise OpenVspUnavailableError(
                    "OpenVSP Python bindings are required. Install OpenVSP with "
                    "Python bindings before using CAD_BACKEND=openvsp."
                ) from exc
        return self._module

    def clear_model(self) -> None:
        self._vsp.ClearVSPModel()

    def add_geom(self, kind: str, parent_id: str = "") -> str:
        geom_id = self._vsp.AddGeom(kind, parent_id)
        self.check_errors(f"AddGeom({kind})")
        if not geom_id:
            raise CadGenerationError(f"OpenVSP AddGeom failed for geometry kind: {kind}")
        return geom_id

    def set_param(
        self,
        geom_id: str,
        parm_name: str,
        group_name: str,
        value: float | int | str,
    ) -> None:
        parm_id = self._vsp.FindParm(geom_id, parm_name, group_name)
        if not parm_id:
            raise CadGenerationError(
                f"OpenVSP FindParm failed for parameter: {parm_name}"
            )
        self._vsp.SetParmVal(parm_id, value)
        self.check_errors(f"SetParmVal({parm_name})")

    def write_vsp_file(self, path: Path | str) -> None:
        self._vsp.WriteVSPFile(str(path))

    def set_fuselage_diameter(self, geom_id: str, diameter: float) -> None:
        xsec_surf_id = self._vsp.GetXSecSurf(geom_id, 0)
        num_xsecs = self._vsp.GetNumXSec(xsec_surf_id)
        if num_xsecs <= 0:
            raise CadGenerationError("OpenVSP fuselage has no cross sections")
        start_index = 1 if num_xsecs > 2 else 0
        end_index = num_xsecs - 1 if num_xsecs > 2 else num_xsecs
        for xsec_index in range(start_index, end_index):
            xsec_id = self._vsp.GetXSec(xsec_surf_id, xsec_index)
            self._vsp.SetXSecWidthHeight(xsec_id, diameter, diameter)

    def export_file(
        self,
        path: Path,
        export_type_name: str,
        set_id: int | None = None,
    ) -> None:
        export_type = getattr(self._vsp, export_type_name, None)
        if export_type is None:
            raise CadGenerationError(
                f"OpenVSP export type is unavailable: {export_type_name}"
            )
        resolved_set_id = self.default_set_id() if set_id is None else set_id
        self._vsp.ExportFile(str(path), resolved_set_id, export_type)
        self.check_errors(f"ExportFile({path.name})")

    def default_set_id(self) -> int:
        return int(getattr(self._vsp, "SET_ALL", 0))

    def update(self) -> None:
        self._vsp.Update()
        self.check_errors("Update")

    def set_vspaero_ref_wing(self, wing_id: str) -> None:
        self._vsp.SetVSPAERORefWingID(wing_id)

    def set_analysis_input_defaults(self, name: str) -> None:
        self._vsp.SetAnalysisInputDefaults(name)

    def set_int_analysis_input(self, name: str, key: str, vals: list[int], index: int = 0) -> None:
        self._vsp.SetIntAnalysisInput(name, key, vals, index)

    def set_double_analysis_input(self, name: str, key: str, vals: list[float]) -> None:
        self._vsp.SetDoubleAnalysisInput(name, key, vals, 0)

    def exec_analysis(self, name: str) -> str:
        result_id = self._vsp.ExecAnalysis(name)
        self.check_errors(f"ExecAnalysis({name})")
        return result_id

    def get_double_results(self, result_id: str, name: str) -> list[float]:
        return list(self._vsp.GetDoubleResults(result_id, name))

    def find_latest_results_id(self, name: str) -> str:
        return self._vsp.FindLatestResultsID(name)

    def create_set(self, name: str) -> int:
        set_id = self._vsp.GetSetIndex(name)
        if set_id < 0:
            raise CadGenerationError(f"Could not find set: {name}")
        return set_id

    def add_to_set(self, set_id: int, geom_id: str) -> None:
        self._vsp.SetSetFlag(geom_id, set_id, True)

    def check_errors(self, context: str) -> list[dict[str, str]]:
        manager = self._error_manager()
        if manager is None:
            return []

        try:
            num_errors = int(manager.GetNumTotalErrors())
        except Exception:
            return []

        errors: list[dict[str, str]] = []
        for _ in range(num_errors):
            try:
                error = manager.PopLastError()
            except Exception:
                break
            message = _openvsp_error_message(error)
            entry = {"context": context, "message": message}
            errors.append(entry)
            self.errors.append(entry)
        if errors and _ERROR_POLICY_FAIL:
            summary = "; ".join(e["message"] for e in errors)
            raise CadGenerationError(f"OpenVSP error(s) in {context}: {summary}")
        return errors

    def _error_manager(self) -> Any | None:
        vsp = self._vsp
        singleton = getattr(vsp, "ErrorMgrSingleton", None)
        if singleton is not None and hasattr(singleton, "getInstance"):
            return singleton.getInstance()
        getter = getattr(vsp, "ErrorMgrSingleton_getInstance", None)
        if getter is not None:
            return getter()
        if hasattr(vsp, "GetNumTotalErrors") and hasattr(vsp, "PopLastError"):
            return vsp
        return None


def _openvsp_error_message(error: Any) -> str:
    getter = getattr(error, "GetErrorString", None)
    if getter is not None:
        return str(getter())
    for attr in ("m_ErrorString", "error_string", "message"):
        value = getattr(error, attr, None)
        if value:
            return str(value)
    return str(error)
