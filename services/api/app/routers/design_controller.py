from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from services.api.app.graph.mode import get_graph_mode
from services.api.app.services.design_controller import DesignControllerService
from services.api.app.services.version_store import VersionStore

router = APIRouter(prefix="/api/design-controller", tags=["design-controller"])

_controller_service = DesignControllerService()


class VariantSpec(BaseModel):
    label: str = ""
    changes: list[dict] = Field(default_factory=list)


class CompareRequest(BaseModel):
    design_id: str = Field(min_length=1, pattern=r"^[A-Za-z0-9_-]+$")
    base_spec: dict
    variants: list[VariantSpec] = Field(min_length=1)


def _get_runner():
    from services.api.app.routers.designs import _get_job_runner
    return _get_job_runner()


def _get_store() -> VersionStore:
    from services.api.app.routers.designs import _get_version_store
    return _get_version_store()


@router.post("/compare")
async def compare_variants(req: CompareRequest, background_tasks: BackgroundTasks):
    """Dispatch multiple variant specs as parallel generation jobs."""
    runner = _get_runner()
    store = _get_store()
    mode = get_graph_mode()

    if mode in ("partial", "shadow"):
        return await _compare_with_graph(req, runner, background_tasks)

    # legacy path
    controller = _controller_service.compare_variants(
        design_id=req.design_id,
        base_spec=req.base_spec,
        variants=[v.model_dump() for v in req.variants],
        job_runner=runner,
        version_store=store,
    )

    for variant in controller.variants:
        from services.api.app.schemas.aircraft_spec import AircraftSpec
        patched = _patch_spec(req.base_spec, variant["changes"])
        spec = AircraftSpec.model_validate(patched)
        background_tasks.add_task(runner.run_queued_job, variant["job_id"], spec)

    from dataclasses import asdict
    return asdict(controller)


async def _compare_with_graph(req: CompareRequest, runner, background_tasks: BackgroundTasks):
    """Use CompareGraph for variant dispatch, fall back to legacy on error."""
    import logging
    import uuid
    from dataclasses import asdict
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)

    try:
        from services.api.app.graph.compare_graph import build_compare_graph
        from services.api.app.schemas.aircraft_spec import AircraftSpec

        graph = build_compare_graph(job_runner=runner)
        result = graph.invoke({
            "design_id": req.design_id,
            "base_spec": req.base_spec,
            "variants": [v.model_dump() for v in req.variants],
        })

        if result.get("status") == "failed":
            raise RuntimeError(result.get("error_message", "CompareGraph failed"))

        # Run all dispatched jobs in background
        variant_jobs = result.get("variant_jobs", [])
        for vj in variant_jobs:
            job = runner.get(vj["job_id"])
            if job and job.status == "queued":
                patched = _patch_spec(req.base_spec, vj.get("changes", []))
                spec = AircraftSpec.model_validate(patched)
                background_tasks.add_task(runner.run_queued_job, vj["job_id"], spec)

        # Return response matching existing API contract (ControllerJob shape)
        now = datetime.now(timezone.utc).isoformat()
        controller_response = {
            "id": uuid.uuid4().hex[:12],
            "design_id": req.design_id,
            "status": "running",
            "variants": variant_jobs,
            "results": [],
            "created_at": now,
            "updated_at": now,
        }

        # Persist for later GET
        _controller_service._save_from_dict(controller_response)
        return controller_response

    except Exception:
        logger.exception("CompareGraph failed, falling back to legacy controller")
        store = _get_store()
        controller = _controller_service.compare_variants(
            design_id=req.design_id,
            base_spec=req.base_spec,
            variants=[v.model_dump() for v in req.variants],
            job_runner=runner,
            version_store=store,
        )
        for variant in controller.variants:
            from services.api.app.schemas.aircraft_spec import AircraftSpec
            patched = _patch_spec(req.base_spec, variant["changes"])
            spec = AircraftSpec.model_validate(patched)
            background_tasks.add_task(runner.run_queued_job, variant["job_id"], spec)
        return asdict(controller)


@router.get("/{controller_job_id}")
async def get_controller_job(controller_job_id: str):
    """Get controller job status using graph-native aggregation.

    For jobs created via CompareGraph, re-runs the aggregation graph.
    For legacy jobs, uses DesignControllerService.aggregate().
    """
    from dataclasses import asdict

    runner = _get_runner()
    controller = _controller_service.get(controller_job_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="controller job not found")

    mode = get_graph_mode()

    # Use graph-native aggregation for CompareGraph-created jobs
    if mode in ("partial", "shadow") and _is_compare_graph_job(controller):
        result = await _aggregate_with_graph(controller, runner)
        return result

    # Legacy aggregation
    aggregated = _controller_service.aggregate(controller_job_id, runner)
    if aggregated is None:
        raise HTTPException(status_code=404, detail="controller job not found")
    return asdict(aggregated)


def _is_compare_graph_job(controller) -> bool:
    """Check if a ControllerJob was created via CompareGraph."""
    # CompareGraph jobs have variant_jobs with job_id/version_no/changes
    variants = controller.variants if hasattr(controller, "variants") else []
    if not variants:
        return False
    # CompareGraph jobs are saved via _save_from_dict (have dict-like variant structure)
    return all("job_id" in v and "changes" in v for v in variants)


async def _aggregate_with_graph(controller, runner) -> dict:
    """Run CompareGraph aggregation subgraph for variant result collection."""
    import json
    from dataclasses import asdict

    try:
        from services.api.app.graph.compare_graph import build_compare_graph

        # Build a lightweight aggregation-only graph
        graph = build_compare_graph(
            job_runner=runner,
            timeout_seconds=2,
        )

        # Invoke just the aggregation portion by providing pre-dispatched state
        result = graph.invoke({
            "design_id": controller.design_id,
            "base_spec": {},
            "variants": [],
            "variant_jobs": [v if isinstance(v, dict) else v for v in controller.variants],
            "status": "running",
        })

        # Merge results back into controller
        controller_dict = asdict(controller)
        controller_dict["results"] = result.get("results", [])
        controller_dict["status"] = result.get("status", controller_dict["status"])

        if result.get("summary"):
            controller_dict["summary"] = result["summary"]

        # Persist updated state
        _controller_service._save_from_dict(controller_dict)
        return controller_dict

    except Exception:
        # Fallback to legacy aggregation
        import logging
        logging.getLogger(__name__).exception(
            "graph-native aggregation failed, falling back to legacy"
        )
        aggregated = _controller_service.aggregate(controller.id, runner)
        return asdict(aggregated) if aggregated else asdict(controller)


def _patch_spec(base: dict, changes: list[dict]) -> dict:
    """Deep-copy base spec and apply changes."""
    import json
    patched = json.loads(json.dumps(base))
    for change in changes:
        _set_nested(patched, change["path"], change["value"])
    return patched


def _set_nested(obj: dict, path: str, value) -> None:
    keys = path.split(".")
    current = obj
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value
