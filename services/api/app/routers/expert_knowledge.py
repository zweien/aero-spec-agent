"""API endpoints for expert-knowledge lookup."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from services.api.app.routers.designs import _get_version_store
from services.api.app.schemas.aircraft_spec import AircraftSpec
from services.api.app.services.expert_knowledge import (
    KnowledgeEntry,
    list_aircraft_categories,
    list_topics,
    load_books,
    load_entries,
    lookup,
    render_citation,
)
from services.workers.cad_worker.openvsp_generator.extended_metrics import run_extended_metrics
from services.workers.cad_worker.openvsp_generator.performance_estimate import run_performance_estimate

# Canonical mapping from expert-knowledge metric names to computed metric IDs.
METRIC_ALIASES: dict[str, str] = {
    "aspect_ratio": "aspect_ratio_perf",
    "taper_ratio": "taper_ratio_perf",
    "wing_loading_kg_m2": "wing_loading_mtow",
    "ld_cruise": "ld_cruise",
    "cl_max_clean": "cl_max",
    "cd0_clean": "cd0",
    "oswald_efficiency": "oswald",
    "endurance_h": "endurance_est",
    "range_km": "range_est",
    "thrust_to_weight": "thrust_to_weight",
    "payload_fraction": "payload_fraction",
    "empty_weight_fraction": "empty_weight_fraction",
    "fuel_fraction": "fuel_fraction",
    "payload_volume_ratio": "payload_volume_ratio",
    "rcs_estimate": "rcs_estimate",
    "htail_volume": "htail_volume",
    "vtail_volume": "vtail_volume",
}


class InlineSpecRequest(BaseModel):
    spec: str | dict


router = APIRouter(prefix="/api/expert-knowledge", tags=["expert-knowledge"])


def _entry_to_payload(entry: KnowledgeEntry) -> dict:
    payload = entry.to_dict()
    payload["citations"] = render_citation(entry)
    return payload


@router.get("/books")
def get_books():
    return {"books": load_books()}


@router.get("/topics")
def get_topics():
    return {"topics": list_topics(), "categories": list_aircraft_categories()}


@router.get("/lookup")
def get_lookup(
    topic: str | None = Query(default=None),
    aircraft_category: str | None = Query(default=None),
    metric: str | None = Query(default=None),
):
    matches = lookup(topic=topic, aircraft_category=aircraft_category, metric=metric)
    return {
        "count": len(matches),
        "entries": [_entry_to_payload(e) for e in matches],
    }


@router.get("/entries")
def get_all_entries():
    entries = load_entries()
    return {
        "count": len(entries),
        "entries": [_entry_to_payload(e) for e in entries],
    }


def _value_status(value: float, entry: KnowledgeEntry) -> str:
    if entry.range is None:
        return "info"
    lo, hi = entry.range
    if lo <= value <= hi:
        return "pass"
    if entry.warn_range:
        wlo, whi = entry.warn_range
        if wlo <= value <= whi:
            return "warn"
    return "fail"


def _build_metric_map(spec: AircraftSpec) -> dict[str, float]:
    """Pre-compute all metric values once, returning {metric_id: value}."""
    perf = run_performance_estimate(spec).to_dict()
    ext = run_extended_metrics(spec).to_dict()
    metric_map: dict[str, float] = {}
    for e in perf.get("estimates", []):
        if e.get("estimate_id"):
            metric_map[e["estimate_id"]] = float(e.get("value", 0.0))
    for m in ext.get("metrics", []):
        if m.get("metric_id"):
            metric_map[m["metric_id"]] = float(m.get("value", 0.0))
    return metric_map


def _advise(spec: AircraftSpec, aircraft_category: str | None) -> dict:
    metric_map = _build_metric_map(spec)
    advisory: list[dict] = []
    for entry in load_entries():
        if aircraft_category and aircraft_category not in entry.applies_to:
            continue
        if not entry.metric or entry.range is None:
            continue
        key = METRIC_ALIASES.get(entry.metric, entry.metric)
        value = metric_map.get(key)
        if value is None:
            continue
        status = _value_status(value, entry)
        advisory.append({
            "entry_id": entry.id,
            "topic": entry.topic,
            "metric": entry.metric,
            "value": round(value, 4),
            "unit": entry.unit,
            "expected_range": list(entry.range),
            "warn_range": list(entry.warn_range) if entry.warn_range else None,
            "status": status,
            "summary_zh": entry.summary_zh,
            "summary_en": entry.summary_en,
            "citations": render_citation(entry),
        })
    summary = {"pass": 0, "warn": 0, "fail": 0, "info": 0}
    for item in advisory:
        summary[item["status"]] = summary.get(item["status"], 0) + 1
    return {"advisory": advisory, "summary": summary}


@router.get("/designs/{design_id}/advisory")
def get_advisory_for_design(
    design_id: str,
    version_no: int | None = Query(default=None, ge=1),
    aircraft_category: str | None = Query(default=None),
):
    store = _get_version_store()
    if version_no is None:
        versions = store.list_versions(design_id)
        if not versions:
            raise HTTPException(status_code=404, detail="design has no versions")
        version_no = max(int(v["version_no"]) for v in versions)
    spec_path = store.version_dir(design_id, version_no) / "aircraft_spec.yaml"
    if not spec_path.exists():
        raise HTTPException(status_code=404, detail="aircraft_spec.yaml not found")
    with open(spec_path, encoding="utf-8") as f:
        spec = AircraftSpec.model_validate(yaml.safe_load(f))
    payload = _advise(spec, aircraft_category)
    payload["design_id"] = design_id
    payload["version_no"] = version_no
    payload["aircraft_category"] = aircraft_category
    return payload


@router.post("/advisory")
async def post_inline_advisory(
    body: InlineSpecRequest,
    aircraft_category: str | None = Query(default=None),
):
    raw = body.spec
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
    return _advise(spec, aircraft_category)
