import pytest

from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend, OpenVspBackend
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend
from services.workers.cad_worker.openvsp_generator.errors import CadGenerationError


def test_backend_factory_defaults_to_fake(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CAD_BACKEND", raising=False)

    backend = get_cad_backend()

    assert isinstance(backend, FakeCadBackend)


def test_backend_factory_uses_fake_from_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CAD_BACKEND", "  FaKe  ")

    backend = get_cad_backend()

    assert isinstance(backend, FakeCadBackend)


def test_backend_factory_explicit_openvsp_without_importing_openvsp():
    backend = get_cad_backend("openvsp")

    assert isinstance(backend, OpenVspBackend)


def test_backend_factory_rejects_unknown_backend():
    with pytest.raises(CadGenerationError):
        get_cad_backend("unknown")
