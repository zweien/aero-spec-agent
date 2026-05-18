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
    """Use CompareGraph (with VariantSubgraph) for variant dispatch and completion."""
    import logging
    import uuid
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)

    try:
        from services.api.app.graph.compare_graph import build_compare_graph

        graph = build_compare_graph(job_runner=runner)
        result = graph.invoke({
            "design_id": req.design_id,
            "base_spec": req.base_spec,
            "variants": [v.model_dump() for v in req.variants],
        })

        if result.get("status") == "failed":
            raise RuntimeError(result.get("error_message", "CompareGraph failed"))

        # CompareGraph now completes all variants via VariantSubgraph
        now = datetime.now(timezone.utc).isoformat()
        graph_status = result.get("status", "completed")
        variant_results = result.get("results", [])

        controller_response = {
            "id": uuid.uuid4().hex[:12],
            "design_id": req.design_id,
            "status": graph_status,
            "variants": variant_results,
            "results": variant_results,
            "created_at": now,
            "updated_at": now,
        }

        if result.get("summary"):
            controller_response["summary"] = result["summary"]

        # Persist for later GET (exclude extra fields not in ControllerJob)
        persist_data = {
            k: v for k, v in controller_response.items()
            if k in ("id", "design_id", "status", "variants", "results", "created_at", "updated_at")
        }
        _controller_service._save_from_dict(persist_data)
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
        from dataclasses import asdict
        return asdict(controller)


@router.get("/{controller_job_id}")
async def get_controller_job(controller_job_id: str):
    """Get controller job status."""
    from dataclasses import asdict

    runner = _get_runner()
    controller = _controller_service.get(controller_job_id)
    if controller is None:
        raise HTTPException(status_code=404, detail="controller job not found")

    # If results are already populated (from graph-completed CompareGraph), return as-is
    if hasattr(controller, "results") and controller.results:
        return asdict(controller)

    # Legacy aggregation for incomplete jobs
    aggregated = _controller_service.aggregate(controller_job_id, runner)
    if aggregated is None:
        raise HTTPException(status_code=404, detail="controller job not found")
    return asdict(aggregated)


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
