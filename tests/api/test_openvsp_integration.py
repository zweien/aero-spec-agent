import os
from pathlib import Path

import pytest

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import OpenVspBackend
from services.workers.cad_worker.openvsp_generator.errors import OpenVspUnavailableError
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_OPENVSP_TESTS") != "1"
    or os.getenv("CAD_BACKEND", "").strip().lower() != "openvsp",
    reason="OpenVSP integration tests require RUN_OPENVSP_TESTS=1 and CAD_BACKEND=openvsp",
)


def test_openvsp_backend_generates_real_vsp3_and_validation_report(tmp_path: Path):
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    try:
        result = generate_aircraft(spec, tmp_path, backend=OpenVspBackend())
    except OpenVspUnavailableError as exc:
        pytest.fail(str(exc))

    vsp3 = result.files["vsp3"]
    assert vsp3.exists()
    assert vsp3.stat().st_size > 0
    assert result.validation_report["backend"]["actual"] in {"openvsp", "OpenVspBackend"}
    assert result.validation_report["vsp3.exists"]["status"] == "pass"
    assert result.validation_report["wing.span"]["status"] == "pass"
    assert result.validation_report["engine.count"]["status"] == "pass"
