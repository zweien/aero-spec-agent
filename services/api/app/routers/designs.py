import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator

import yaml
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import ValidationError

from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.schemas.job import job_to_response
from services.api.app.services.job_events import (
    TERMINAL_TYPES,
    JobEventType,
    get_job_event_bus,
)
from services.api.app.services.job_runner import JobRunner
from services.api.app.services.spec_patch import apply_patch
from services.api.app.services.version_store import VersionStore
from services.workers.cad_worker.openvsp_generator.backend_factory import get_cad_backend


router = APIRouter(prefix="/api", tags=["designs"])
runner = JobRunner(store=VersionStore())


def _get_job_runner() -> JobRunner:
    return runner


def _get_version_store() -> VersionStore:
    return runner.store


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


_SSE_EVENT_MAP = {
    JobEventType.STARTED: "generation_started",
    JobEventType.PROGRESS: "generation_progress",
    JobEventType.COMPLETED: "generation_complete",
    JobEventType.FAILED: "generation_failed",
    JobEventType.WORKFLOW_STAGE: "workflow_stage",
    JobEventType.ARTIFACT_GENERATED: "artifact_generated",
}


def _sse_line(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_job_events(job_id: str) -> AsyncIterator[str]:
    bus = get_job_event_bus()
    q = bus.async_queue()
    try:
        deadline = asyncio.get_event_loop().time() + 120
        while asyncio.get_event_loop().time() < deadline:
            try:
                event = await asyncio.wait_for(q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                continue

            if event.job_id != job_id:
                continue

            sse_type = _SSE_EVENT_MAP.get(event.type, event.type.value)
            payload = {
                "job_id": event.job_id,
                "design_id": event.design_id,
                "version_no": event.version_no,
                "status": (
                    "succeeded"
                    if event.type == JobEventType.COMPLETED
                    else "failed" if event.type == JobEventType.FAILED else "running"
                ),
                "progress": event.progress,
                "current_step": event.current_step,
                "timestamp": event.timestamp,
            }
            if event.error_message:
                payload["error_message"] = event.error_message
            if event.duration_ms is not None:
                payload["duration_ms"] = event.duration_ms
            if event.files:
                payload["files"] = event.files
            if event.stage:
                payload["stage"] = event.stage
            if event.label:
                payload["label"] = event.label
            if event.metadata:
                payload["metadata"] = event.metadata

            yield _sse_line(sse_type, payload)

            if event.type in TERMINAL_TYPES:
                return
    finally:
        bus.release_async_queue(q)


@router.get("/jobs/{job_id}/stream")
async def stream_job(job_id: str):
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    if job.status in ("succeeded", "failed"):
        evt_type = "generation_complete" if job.status == "succeeded" else "generation_failed"
        data = _job_response(job)
        data["status"] = job.status

        # Replay recorded workflow_stage events so late-connecting clients
        # don't miss the progress that happened before they subscribed.
        def _replay():
            for entry in getattr(job, "stage_history", []):
                if entry.get("event_type") == "artifact_generated":
                    payload = {
                        "job_id": job.id,
                        "design_id": job.design_id,
                        "version_no": job.version_no,
                        "status": "running",
                        "artifact": entry.get("artifact", ""),
                        "label": entry.get("label", ""),
                        "path": entry.get("path", ""),
                        "metadata": {
                            "artifact_key": entry.get("artifact", ""),
                            "artifact_path": entry.get("path", ""),
                        },
                        "timestamp": "",
                    }
                    yield _sse_line("artifact_generated", payload)
                else:
                    payload = {
                        "job_id": job.id,
                        "design_id": job.design_id,
                        "version_no": job.version_no,
                        "status": "running",
                        "stage": entry.get("stage", ""),
                        "label": entry.get("label", ""),
                        "progress": entry.get("progress", 0),
                        "timestamp": "",
                    }
                    yield _sse_line("workflow_stage", payload)
            yield _sse_line(evt_type, data)

        return StreamingResponse(
            _replay(),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        _stream_job_events(job_id),
        media_type="text/event-stream",
    )


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

    validation_report = None
    report_path = runner.store.version_dir(job.design_id, job.version_no) / "validation_report.json"
    if report_path.exists():
        try:
            validation_report = json.loads(report_path.read_text(encoding="utf-8"))
        except Exception:
            validation_report = None

    vdir = runner.store.version_dir(job.design_id, job.version_no)
    expected_files = ["aircraft_spec.yaml", "aircraft.vsp3", "aircraft.step", "aircraft.glb",
                      "validation_report.json", "generation_log.json"]
    files_exist = {name: (vdir / name).is_file() for name in expected_files}

    return {
        "job": _job_response(job),
        "version_status": version_status,
        "generation_log": generation_log,
        "validation_report": validation_report,
        "files_exist": files_exist,
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
