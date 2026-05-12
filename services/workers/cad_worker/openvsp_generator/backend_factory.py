import os

from services.workers.cad_worker.openvsp_generator.backend import CadBackend, FakeCadBackend, OpenVspBackend
from services.workers.cad_worker.openvsp_generator.errors import CadGenerationError


def get_cad_backend(name: str | None = None) -> CadBackend:
    backend_name = (name if name is not None else os.getenv("CAD_BACKEND", "fake")).strip().lower()
    if backend_name in {"", "fake"}:
        return FakeCadBackend()
    if backend_name == "openvsp":
        return OpenVspBackend()
    raise CadGenerationError(f"Unknown CAD_BACKEND: {backend_name}")
