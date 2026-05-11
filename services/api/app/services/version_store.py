import json
from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import dump_aircraft_spec


class VersionStore:
    def __init__(self, root: Path = Path("storage")) -> None:
        self.root = root

    def next_version_no(self, design_id: str) -> int:
        versions_root = self.root / "designs" / design_id / "versions"
        if not versions_root.exists():
            return 1
        existing = [int(path.name) for path in versions_root.iterdir() if path.is_dir() and path.name.isdigit()]
        return max(existing, default=0) + 1

    def version_dir(self, design_id: str, version_no: int) -> Path:
        return self.root / "designs" / design_id / "versions" / str(version_no)

    def write_spec(self, design_id: str, version_no: int, spec: AircraftSpec) -> Path:
        path = self.version_dir(design_id, version_no) / "aircraft_spec.yaml"
        dump_aircraft_spec(spec, path)
        return path

    def read_version(self, design_id: str, version_no: int) -> dict[str, object]:
        root = self.version_dir(design_id, version_no)
        validation_path = root / "validation_report.json"
        files = sorted(path.name for path in root.iterdir() if path.is_file())
        validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
        return {
            "design_id": design_id,
            "version_no": version_no,
            "files": files,
            "validation_report": validation,
        }
