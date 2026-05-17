import json
import os
from pathlib import Path

import yaml
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import ValidationError

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.schemas.job import job_to_response
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_patch import apply_patch
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend


router = APIRouter(prefix="/api", tags=["designs"])
runner = JobRunner(store=VersionStore())


def _job_response(job) -> dict[str, object]:
    return job_to_response(job)


@router.post("/designs/{design_id}/generate", status_code=202)
async def generate_design(
    design_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    raw_body = await request.body()
    try:
        data = yaml.safe_load(raw_body.decode("utf-8"))
        spec = AircraftSpec.model_validate(data)
        job = runner.enqueue_generate(design_id=design_id, spec=spec)
        background_tasks.add_task(runner.run_queued_job, job.id, spec)
    except (UnicodeDecodeError, yaml.YAMLError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail="invalid aircraft spec") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _job_response(job)


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return _job_response(job)


@router.get("/jobs/{job_id}/diagnostics")
def get_job_diagnostics(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    version_status = runner.store.version_status.read_raw(job.design_id, job.version_no)

    generation_log = None
    log_path = runner.store.version_dir(job.design_id, job.version_no) / "generation_log.json"
    if log_path.exists():
        try:
            generation_log = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            generation_log = None

    return {
        "job": _job_response(job),
        "version_status": version_status,
        "generation_log": generation_log,
    }


@router.get("/designs/{design_id}/versions")
def list_versions(design_id: str):
    try:
        return runner.store.list_versions(design_id=design_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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


def _sync_chat_spec(design_id: str, spec: AircraftSpec) -> None:
    state_path = Path("storage/conversations") / design_id / "state.json"
    if not state_path.exists():
        return
    data = json.loads(state_path.read_text(encoding="utf-8"))
    data["current_spec"] = spec.model_dump(mode="json")
    state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.patch("/designs/{design_id}/spec")
async def patch_spec(
    design_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
):
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    changes = body.get("changes", [])
    if not changes:
        raise HTTPException(status_code=400, detail="changes array is required and must not be empty")

    versions = runner.store.list_versions(design_id=design_id)
    if not versions:
        raise HTTPException(status_code=404, detail="no versions found for this design")

    latest_no = max(v["version_no"] for v in versions)
    version_data = runner.store.read_version(design_id=design_id, version_no=latest_no)
    spec_echo = version_data.get("validation_report", {}).get("spec_echo")
    if not spec_echo:
        raise HTTPException(status_code=400, detail="no spec found in latest version")

    try:
        spec = AircraftSpec.model_validate(spec_echo)
        patched = apply_patch(spec, changes)
    except (KeyError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    job = runner.enqueue_generate(design_id=design_id, spec=patched)
    background_tasks.add_task(runner.run_queued_job, job.id, patched)
    _sync_chat_spec(design_id, patched)
    response.status_code = 202
    return _job_response(job)


@router.get("/settings")
def get_settings():
    return {
        "cad_backend": os.getenv("CAD_BACKEND", "fake"),
        "run_vspaero_analysis": os.getenv("RUN_VSPAERO_ANALYSIS", "").lower() in ("1", "true", "yes"),
    }


@router.put("/settings")
async def update_settings(request: Request):
    raw = await request.body()
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc

    if "cad_backend" in body:
        val = body["cad_backend"]
        if val not in ("fake", "openvsp"):
            raise HTTPException(status_code=400, detail="cad_backend must be 'fake' or 'openvsp'")
        os.environ["CAD_BACKEND"] = val
        runner.backend = get_cad_backend(val)

    if "run_vspaero_analysis" in body:
        enabled = bool(body["run_vspaero_analysis"])
        os.environ["RUN_VSPAERO_ANALYSIS"] = "true" if enabled else ""

    return {
        "cad_backend": os.getenv("CAD_BACKEND", "fake"),
        "run_vspaero_analysis": os.getenv("RUN_VSPAERO_ANALYSIS", "").lower() in ("1", "true", "yes"),
    }
