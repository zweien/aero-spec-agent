from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

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

    controller = _controller_service.compare_variants(
        design_id=req.design_id,
        base_spec=req.base_spec,
        variants=[v.model_dump() for v in req.variants],
        job_runner=runner,
        version_store=store,
    )

    # Run all variant jobs in background
    for variant in controller.variants:
        from services.api.app.schemas.aircraft_spec import AircraftSpec
        patched = _patch_spec(req.base_spec, variant["changes"])
        spec = AircraftSpec.model_validate(patched)
        background_tasks.add_task(runner.run_queued_job, variant["job_id"], spec)

    from dataclasses import asdict
    return asdict(controller)


@router.get("/{controller_job_id}")
async def get_controller_job(controller_job_id: str):
    """Get controller job status, aggregating variant results."""
    runner = _get_runner()
    result = _controller_service.aggregate(controller_job_id, runner)
    if result is None:
        raise HTTPException(status_code=404, detail="controller job not found")
    from dataclasses import asdict
    return asdict(result)


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
