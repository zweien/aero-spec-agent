from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from services.api.app.graph.deep_design_graph import build_deep_design_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["deep-design"])


class DeepDesignRequest(BaseModel):
    design_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    base_spec: dict[str, Any]
    constraints: dict[str, Any] = Field(default_factory=dict)


class DeepDesignResponse(BaseModel):
    design_id: str
    status: str
    report: str = ""
    comparison: dict[str, Any] | None = None
    error_message: str | None = None


@router.post("/deep-design", response_model=DeepDesignResponse)
async def deep_design(req: DeepDesignRequest, background_tasks: BackgroundTasks):
    """Run multi-variant design exploration.

    Phase 1: parse requirements, dispatch N variant jobs, wait, compare, report.
    """
    try:
        from services.api.app.routers.designs import _get_job_runner

        job_runner = _get_job_runner()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="job runner not available") from exc

    graph = build_deep_design_graph(job_runner=job_runner, timeout_seconds=120)

    try:
        result = graph.invoke({
            "user_description": req.description,
            "design_id": req.design_id,
            "base_spec": req.base_spec,
            "constraints": req.constraints,
        })
    except Exception as exc:
        logger.exception("deep-design graph failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return DeepDesignResponse(
        design_id=req.design_id,
        status=result.get("status", "unknown"),
        report=result.get("report", ""),
        comparison=result.get("comparison"),
        error_message=result.get("error_message"),
    )
