import json
import re
import threading
from pathlib import Path

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.spec_io import dump_aircraft_spec

_DESIGN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class VersionStore:
    def __init__(self, root: Path = Path("storage")) -> None:
        self.root = root
        self._lock = threading.Lock()
        from services.api.app.services.version_status import VersionStatus
        self.version_status = VersionStatus(self)

    def _validate_design_id(self, design_id: str) -> str:
        if not _DESIGN_ID_PATTERN.fullmatch(design_id):
            raise ValueError("design_id must match ^[A-Za-z0-9_-]+$")
        return design_id

    def create_version_dir(self, design_id: str) -> tuple[int, Path]:
        design_id = self._validate_design_id(design_id)
        versions_root = self.root / "designs" / design_id / "versions"
        with self._lock:
            versions_root.mkdir(parents=True, exist_ok=True)
            existing = [
                int(p.name) for p in versions_root.iterdir() if p.is_dir() and p.name.isdigit()
            ]
            version_no = max(existing, default=0) + 1
            path = versions_root / str(version_no)
            path.mkdir(exist_ok=False)
        self.version_status.write_pending(design_id, version_no)
        return version_no, path

    def version_dir(self, design_id: str, version_no: int) -> Path:
        design_id = self._validate_design_id(design_id)
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

    def list_versions(self, design_id: str) -> list[dict[str, object]]:
        design_id = self._validate_design_id(design_id)
        versions_root = self.root / "designs" / design_id / "versions"
        if not versions_root.exists():
            return []
        versions = []
        for path in sorted(versions_root.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 0):
            if not (path.is_dir() and path.name.isdigit()):
                continue
            status_path = path / "version_status.json"
            if status_path.exists():
                data = json.loads(status_path.read_text(encoding="utf-8"))
                if data.get("status") != "succeeded":
                    continue
            versions.append({"version_no": int(path.name)})
        return versions

    def version_file(self, design_id: str, version_no: int, filename: str) -> Path:
        if Path(filename).name != filename or filename in {"", ".", ".."}:
            raise ValueError("filename must be a file name, not a path")
        path = self.version_dir(design_id, version_no) / filename
        if not path.is_file():
            raise FileNotFoundError(filename)
        return path
