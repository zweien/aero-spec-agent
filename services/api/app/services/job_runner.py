import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_events import JobEvent, JobEventType, get_job_event_bus
from services.api.app.services.workflow_events import (
    ARTIFACT_LABELS,
    CAD_STAGE_LABELS,
    publish_artifact_generated,
    publish_workflow_stage,
)
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import CadBackend
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft

logger = logging.getLogger(__name__)

def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class JobRecord:
    id: str
    design_id: str
    version_no: int
    status: str
    progress: int
    current_step: str
    error_message: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""
    duration_ms: float | None = None
    version_status: str = "pending"
    stage_history: list[dict] = field(default_factory=list)


class JobRunner:
    def __init__(self, store: VersionStore, backend: CadBackend | None = None) -> None:
        self.store = store
        self.backend = backend if backend is not None else get_cad_backend()
        self.jobs: dict[str, JobRecord] = {}
        self._lock = threading.RLock()

    def create_job(self, design_id: str) -> JobRecord:
        job_id = str(uuid4())
        now = _utcnow()
        version_no, _ = self.store.create_version_dir(design_id)
        job = JobRecord(
            id=job_id,
            design_id=design_id,
            version_no=version_no,
            status="running",
            progress=10,
            current_step="writing_spec",
            created_at=now,
            updated_at=now,
            version_status="pending",
        )
        self._remember(job)
        return job

    def run_job_generation(self, job: JobRecord, spec: AircraftSpec) -> None:
        output_dir = self.store.version_dir(job.design_id, job.version_no)
        self._run_generation(job, spec, output_dir=output_dir, success_status="succeeded")

    def generate(self, design_id: str, spec: AircraftSpec) -> JobRecord:
        job = self.create_job(design_id)
        self.run_job_generation(job, spec)
        return job

    def enqueue_generate(self, design_id: str, spec: AircraftSpec) -> JobRecord:
        job_id = str(uuid4())
        now = _utcnow()
        version_no, _ = self.store.create_version_dir(design_id)
        job = JobRecord(
            id=job_id,
            design_id=design_id,
            version_no=version_no,
            status="queued",
            progress=0,
            current_step="queued",
            created_at=now,
            updated_at=now,
            duration_ms=None,
            version_status="pending",
        )
        self._remember(job)
        self._save_job(job)
        return job

    def run_queued_job(self, job_id: str, spec: AircraftSpec) -> JobRecord:
        job = self.get(job_id)
        if job is None:
            raise ValueError(f"job not found: {job_id}")
        output_dir = self.store.version_dir(job.design_id, job.version_no)
        self._run_generation(job, spec, output_dir=output_dir, success_status="succeeded")
        return job

    def _run_generation(
        self,
        job: JobRecord,
        spec: AircraftSpec,
        *,
        output_dir,
        success_status: str,
    ) -> None:
        bus = get_job_event_bus()
        job.status = "running"
        job.progress = 10
        job.current_step = "writing_spec"
        job.updated_at = _utcnow()
        self._save_job(job)
        bus.publish(JobEvent(
            type=JobEventType.STARTED,
            job_id=job.id,
            design_id=job.design_id,
            version_no=job.version_no,
            progress=job.progress,
            current_step=job.current_step,
        ))

        stage_history: list[dict] = []
        job.stage_history = stage_history

        def _record_stage(stage: str, label: str, progress: int) -> None:
            entry = {"stage": stage, "label": label, "progress": progress, "status": "running"}
            stage_history.append(entry)
            publish_workflow_stage(bus, job.id, job.design_id, job.version_no,
                                  stage, label, progress=progress)

        try:
            self.store.write_spec(job.design_id, job.version_no, spec)

            # Emit workflow_stage + backward-compatible PROGRESS events
            for ws_stage, ws_label, ws_progress in [
                ("generating_spec", "生成飞机参数", 10),
                ("validating_parameters", "校验设计参数", 20),
            ]:
                _record_stage(ws_stage, ws_label, ws_progress)
                job.current_step = ws_stage
                job.progress = ws_progress
                job.updated_at = _utcnow()
                self._save_job(job)

            def _cad_progress(stage: str, progress: int) -> None:
                label = CAD_STAGE_LABELS.get(stage, stage)
                _record_stage(stage, label, progress)
                job.current_step = stage
                job.progress = progress
                job.updated_at = _utcnow()
                self._save_job(job)

            result = generate_aircraft(spec=spec, output_dir=output_dir, backend=self.backend, on_progress=_cad_progress)

            # Store stage history before marking complete
            job.stage_history = stage_history

            job.status = success_status
            job.progress = 100
            job.current_step = success_status
            job.files = {key: str(path) for key, path in result.files.items()}
            for artifact_key, artifact_path in result.files.items():
                label = ARTIFACT_LABELS.get(artifact_key, artifact_key)
                publish_artifact_generated(
                    bus, job.id, job.design_id, job.version_no,
                    artifact_key, str(artifact_path),
                )
                stage_history.append({
                    "event_type": "artifact_generated",
                    "artifact": artifact_key,
                    "label": label,
                    "path": str(artifact_path),
                })
            job.version_status = "succeeded"
            job.updated_at = _utcnow()
            if job.created_at:
                from datetime import datetime as _dt, timezone as _tz
                created = _dt.fromisoformat(job.created_at)
                elapsed = (_dt.now(_tz.utc) - created).total_seconds()
                job.duration_ms = round(elapsed * 1000, 1)
            self.store.version_status.write(
                job.design_id, job.version_no,
                status="succeeded",
                job_id=job.id,
                current_step="succeeded",
                files=job.files,
                duration_ms=job.duration_ms,
            )
            bus.publish(JobEvent(
                type=JobEventType.COMPLETED,
                job_id=job.id,
                design_id=job.design_id,
                version_no=job.version_no,
                progress=100,
                current_step="succeeded",
                files=job.files,
                duration_ms=job.duration_ms,
            ))
        except Exception as exc:
            # Store partial stage history even on failure
            failed_stage = job.current_step or "failed"
            failed_label = CAD_STAGE_LABELS.get(failed_stage, failed_stage)
            stage_history.append({
                "stage": failed_stage,
                "label": failed_label,
                "progress": job.progress,
                "status": "failed",
                "error_message": str(exc),
            })
            bus.publish(JobEvent(
                type=JobEventType.WORKFLOW_STAGE,
                job_id=job.id,
                design_id=job.design_id,
                version_no=job.version_no,
                stage=failed_stage,
                label=failed_label,
                progress=job.progress,
                current_step=failed_stage,
                error_message=str(exc),
            ))
            job.stage_history = stage_history

            logger.exception(
                "Generation job failed for design_id=%s version_no=%s",
                job.design_id,
                job.version_no,
            )
            job.status = "failed"
            job.current_step = "failed"
            job.error_message = str(exc)
            job.version_status = "failed"
            job.updated_at = _utcnow()
            if job.created_at:
                from datetime import datetime as _dt, timezone as _tz
                created = _dt.fromisoformat(job.created_at)
                elapsed = (_dt.now(_tz.utc) - created).total_seconds()
                job.duration_ms = round(elapsed * 1000, 1)
            self.store.version_status.write(
                job.design_id, job.version_no,
                status="failed",
                job_id=job.id,
                current_step="failed",
                error_message=job.error_message,
                duration_ms=job.duration_ms,
            )
            bus.publish(JobEvent(
                type=JobEventType.FAILED,
                job_id=job.id,
                design_id=job.design_id,
                version_no=job.version_no,
                progress=job.progress,
                current_step="failed",
                error_message=job.error_message,
                duration_ms=job.duration_ms,
            ))
        finally:
            self._save_job(job)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            if job_id in self.jobs:
                return self.jobs[job_id]
            path = self._job_path(job_id)
            if not path.exists():
                return None
            data = json.loads(path.read_text(encoding="utf-8"))
            job = JobRecord(**data)
            self.jobs[job_id] = job
            return job

    def _remember(self, job: JobRecord) -> None:
        with self._lock:
            self.jobs[job.id] = job

    def _jobs_root(self):
        return self.store.root / "jobs"

    def _job_path(self, job_id: str):
        return self._jobs_root() / f"{job_id}.json"

    def _save_job(self, job: JobRecord) -> None:
        with self._lock:
            self.jobs[job.id] = job
            self._jobs_root().mkdir(parents=True, exist_ok=True)
            self._job_path(job.id).write_text(
                json.dumps(asdict(job), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
