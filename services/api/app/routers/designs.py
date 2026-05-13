import yaml
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.version_store import VersionStore


router = APIRouter(prefix="/api", tags=["designs"])
runner = JobRunner(store=VersionStore())


@router.post("/designs/{design_id}/generate")
async def generate_design(design_id: str, request: Request):
    raw_body = await request.body()
    try:
        data = yaml.safe_load(raw_body.decode("utf-8"))
        spec = AircraftSpec.model_validate(data)
        job = runner.generate(design_id=design_id, spec=spec)
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="invalid aircraft spec") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return job.__dict__


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job.__dict__


@router.get("/designs/{design_id}/versions/{version_no}")
def get_version(design_id: str, version_no: int):
    try:
        return runner.store.read_version(design_id=design_id, version_no=version_no)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="version not found") from exc


@router.get("/designs/{design_id}/versions/{version_no}/files/{filename:path}")
def get_version_file(design_id: str, version_no: int, filename: str):
    try:
        path = runner.store.version_file(
            design_id=design_id,
            version_no=version_no,
            filename=filename,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc
    return FileResponse(path)
