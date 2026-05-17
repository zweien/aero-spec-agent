from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.services.version_store import VersionStore


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class VersionStatus:
    """Centralized read/write for version_status.json files."""

    def __init__(self, store: VersionStore) -> None:
        self._store = store

    def _path(self, design_id: str, version_no: int) -> Path:
        return self._store.version_dir(design_id, version_no) / "version_status.json"

    def write(
        self,
        design_id: str,
        version_no: int,
        *,
        status: str,
        job_id: str | None = None,
        current_step: str = "",
        error_message: str | None = None,
        files: dict[str, str] | None = None,
        duration_ms: float | None = None,
    ) -> None:
        existing = self.read_raw(design_id, version_no) or {}
        data: dict[str, Any] = {
            "status": status,
            "version_no": version_no,
            "design_id": design_id,
            "job_id": job_id,
            "updated_at": _utcnow_iso(),
        }
        if current_step:
            data["current_step"] = current_step
        if error_message:
            data["error_message"] = error_message
        if files:
            data["files"] = {k: str(v) for k, v in files.items()}
        if duration_ms is not None:
            data["duration_ms"] = duration_ms
        created_at = existing.get("created_at")
        if created_at:
            data["created_at"] = created_at
        self._path(design_id, version_no).write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    def write_pending(self, design_id: str, version_no: int) -> None:
        now = _utcnow_iso()
        data: dict[str, Any] = {
            "status": "pending",
            "version_no": version_no,
            "design_id": design_id,
            "job_id": None,
            "created_at": now,
            "updated_at": now,
        }
        self._path(design_id, version_no).write_text(
            json.dumps(data, ensure_ascii=False),
            encoding="utf-8",
        )

    def read(self, design_id: str, version_no: int) -> str:
        raw = self.read_raw(design_id, version_no)
        if raw is None:
            return "succeeded"
        return raw.get("status", "succeeded")

    def read_raw(self, design_id: str, version_no: int) -> dict[str, Any] | None:
        path = self._path(design_id, version_no)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
