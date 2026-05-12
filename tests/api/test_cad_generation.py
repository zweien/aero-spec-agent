import json
from pathlib import Path

from services.api.app.services.spec_io import load_aircraft_spec
from services.workers.cad_worker.openvsp_generator.backend import FakeCadBackend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft


def test_fake_backend_writes_expected_artifacts(tmp_path: Path):
    spec = load_aircraft_spec(Path("packages/aircraft-schema/examples/twin_engine_uav.yaml"))

    result = generate_aircraft(spec=spec, output_dir=tmp_path, backend=FakeCadBackend())

    assert result.files["vsp3"].name == "aircraft.vsp3"
    assert result.files["step"].name == "aircraft.step"
    assert result.files["glb"].name == "aircraft.glb"
    assert set(result.files) == {"vsp3", "step", "glb"}
    assert result.validation_report["wing.span"]["status"] == "pass"
    assert result.validation_report["engine.count"]["actual"] == 2
    assert result.validation_report["backend"] == {
        "expected": "fake",
        "actual": "fake",
        "status": "pass",
    }
    assert result.validation_report["backend_name"] == "fake"
    assert result.validation_report["vsp3"]["exists"] is True

    validation_report = json.loads((tmp_path / "validation_report.json").read_text(encoding="utf-8"))
    assert validation_report["backend"]["actual"] == "fake"
    assert validation_report["vsp3"]["exists"] is True
