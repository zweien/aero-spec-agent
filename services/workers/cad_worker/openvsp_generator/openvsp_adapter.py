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

    def update(self) -> None:
        self._vsp.Update()
