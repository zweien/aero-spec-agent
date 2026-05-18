"""DesignController v1 — multi-variant generation and comparison."""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.api.app.services.version_store import VersionStore

logger = logging.getLogger(__name__)


@dataclass
class ControllerJob:
    id: str
    design_id: str
    status: str  # running | completed | failed
    variants: list[dict[str, Any]]
    results: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        self.updated_at = now


class DesignControllerService:
    """Orchestrate multi-variant design generation and comparison."""

    def __init__(self, storage_root: str | Path | None = None) -> None:
        if storage_root is None:
            storage_root = os.environ.get("STORAGE_ROOT", "storage")
        self._root = Path(storage_root) / "controller_jobs"
        self._root.mkdir(parents=True, exist_ok=True)

    def compare_variants(
        self,
        design_id: str,
        base_spec: dict[str, Any],
        variants: list[dict[str, Any]],
        job_runner: Any,
        version_store: VersionStore,
    ) -> ControllerJob:
        """Dispatch multiple variant specs as parallel generation jobs.

        Each variant is a normal version under the same design_id.
        Returns a ControllerJob tracking all variant jobs.
        """
        from services.api.app.schemas.aircraft_spec import AircraftSpec

        variant_entries = []
        for var in variants:
            # Patch the base spec with variant changes
            patched = json.loads(json.dumps(base_spec))  # deep copy
            for change in var.get("changes", []):
                _set_nested(patched, change["path"], change["value"])

            spec = AircraftSpec.model_validate(patched)
            job = job_runner.enqueue_generate(design_id=design_id, spec=spec)
            variant_entries.append({
                "label": var.get("label", f"variant_{len(variant_entries) + 1}"),
                "job_id": job.id,
                "version_no": job.version_no,
                "changes": var.get("changes", []),
                "status": "queued",
            })

        controller = ControllerJob(
            id=uuid.uuid4().hex[:12],
            design_id=design_id,
            status="running",
            variants=variant_entries,
        )
        self._save(controller)
        return controller

    def get(self, controller_job_id: str) -> ControllerJob | None:
        """Load a ControllerJob from disk."""
        path = self._root / f"{controller_job_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ControllerJob(**data)

    def aggregate(self, controller_job_id: str, job_runner: Any) -> ControllerJob | None:
        """Check variant job statuses and aggregate results."""
        controller = self.get(controller_job_id)
        if controller is None:
            return None

        all_terminal = True
        for variant in controller.variants:
            if variant["status"] in ("succeeded", "failed"):
                continue
            job = job_runner.get(variant["job_id"])
            if job is None:
                variant["status"] = "failed"
                continue
            variant["status"] = job.status
            if job.status not in ("succeeded", "failed"):
                all_terminal = False
            if job.status == "succeeded":
                controller.results.append({
                    "label": variant["label"],
                    "version_no": job.version_no,
                    "status": "succeeded",
                    "files": job.files,
                })
            else:
                controller.results.append({
                    "label": variant["label"],
                    "version_no": job.version_no,
                    "status": "failed",
                    "error_message": job.error_message,
                })

        if all_terminal:
            controller.status = "completed"

        controller.updated_at = datetime.now(timezone.utc).isoformat()
        self._save(controller)
        return controller

    def _save(self, job: ControllerJob) -> None:
        from dataclasses import asdict
        path = self._root / f"{job.id}.json"
        path.write_text(
            json.dumps(asdict(job), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _save_from_dict(self, data: dict[str, Any]) -> None:
        """Persist a controller job dict directly (used by CompareGraph path)."""
        path = self._root / f"{data.get('id', 'unknown')}.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _set_nested(obj: dict, path: str, value: Any) -> None:
    keys = path.split(".")
    current = obj
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
