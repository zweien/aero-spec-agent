"""API endpoints for historical-aircraft comparison."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException, Query

from services.api.app.routers.designs import _get_version_store
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.historical_compare import (
    build_comparison_payload,
    load_database,
)


router = APIRouter(prefix="/api", tags=["historical"])


@router.get("/historical-aircraft")
def list_historical_aircraft():
    """Return the curated reference database (read-only)."""
    db = load_database()
    return {"aircraft": db, "count": len(db)}


def _latest_version_no(store, design_id: str) -> int | None:
    versions = store.list_versions(design_id)
    if not versions:
        return None
    return max(int(v["version_no"]) for v in versions)


@router.get("/designs/{design_id}/historical-compare")
def compare_design_to_history(
    design_id: str,
    version_no: int | None = Query(default=None, ge=1),
    top_k: int = Query(default=5, ge=1, le=20),
):
    store = _get_version_store()
    if version_no is None:
        version_no = _latest_version_no(store, design_id)
        if version_no is None:
            raise HTTPException(status_code=404, detail="design has no versions")

    spec_path = store.version_dir(design_id, version_no) / "aircraft_spec.yaml"
    if not spec_path.exists():
        raise HTTPException(status_code=404, detail="aircraft_spec.yaml not found for version")
    try:
        with open(spec_path, encoding="utf-8") as f:
            spec_data = yaml.safe_load(f)
        spec = AircraftSpec.model_validate(spec_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"failed to parse stored spec: {exc}") from exc

    payload = build_comparison_payload(spec, top_k=top_k)
    payload["design_id"] = design_id
    payload["version_no"] = version_no
    return payload


@router.post("/historical-compare")
async def compare_inline_spec(
    payload: dict,
    top_k: int = Query(default=5, ge=1, le=20),
):
    """Compare an inline spec without persisting it.

    Body: { "spec": <aircraft spec dict or YAML string> }
    """
    raw = payload.get("spec") if isinstance(payload, dict) else None
    if raw is None:
        raise HTTPException(status_code=400, detail="missing 'spec' in body")
    if isinstance(raw, str):
        try:
            data = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise HTTPException(status_code=400, detail="invalid YAML in spec") from exc
    else:
        data = raw
    try:
        spec = AircraftSpec.model_validate(data)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid spec: {exc}") from exc
    return build_comparison_payload(spec, top_k=top_k)
