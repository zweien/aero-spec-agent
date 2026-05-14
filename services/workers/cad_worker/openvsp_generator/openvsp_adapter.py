import importlib
from pathlib import Path
from typing import Any

from services.workers.cad_worker.openvsp_generator.errors import (
    CadGenerationError,
    OpenVspUnavailableError,
)


class OpenVspAdapter:
    def __init__(self, module: Any | None = None) -> None:
        self._module = module

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

    def write_vsp_file(self, path: Path) -> None:
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

    def default_set_id(self) -> int:
        return int(getattr(self._vsp, "SET_ALL", 0))

    def update(self) -> None:
        self._vsp.Update()
