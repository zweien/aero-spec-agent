import logging
from dataclasses import dataclass, field
from uuid import uuid4

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend import CadBackend, FakeCadBackend
from services.workers.cad_worker.openvsp_generator.generate_aircraft import generate_aircraft

logger = logging.getLogger(__name__)


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


class JobRunner:
    def __init__(self, store: VersionStore, backend: CadBackend | None = None) -> None:
        self.store = store
        self.backend = backend or FakeCadBackend()
        self.jobs: dict[str, JobRecord] = {}

    def generate(self, design_id: str, spec: AircraftSpec) -> JobRecord:
        job_id = str(uuid4())
        version_no, output_dir = self.store.create_version_dir(design_id)
        job = JobRecord(
            id=job_id,
            design_id=design_id,
            version_no=version_no,
            status="running",
            progress=10,
            current_step="writing_spec",
        )
        self.jobs[job_id] = job
        try:
            self.store.write_spec(design_id, version_no, spec)
            job.current_step = "generating_cad"
            job.progress = 50
            result = generate_aircraft(spec=spec, output_dir=output_dir, backend=self.backend)
            job.status = "ready"
            job.progress = 100
            job.current_step = "ready"
            job.files = {key: str(path) for key, path in result.files.items()}
        except Exception as exc:
            logger.exception("Generation job failed for design_id=%s version_no=%s", design_id, version_no)
            job.status = "failed"
            job.current_step = "failed"
            job.error_message = str(exc)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        return self.jobs.get(job_id)
