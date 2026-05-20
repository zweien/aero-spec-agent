"""Centralized workflow event publishing helpers.

Provides convenience functions that wrap the raw JobEventBus publish API
so that callers don't need to construct JobEvent objects by hand for the
most common event patterns.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from services.api.app.services.job_events import JobEvent, JobEventBus, JobEventType

# Human-readable labels for generated artifacts
ARTIFACT_LABELS: dict[str, str] = {
    "vsp3": "OpenVSP 模型",
    "step": "STEP 工程文件",
    "glb": "三维预览模型",
    "obj": "OBJ 模型",
    "generation_log": "生成日志",
    "validation_report": "验证报告",
}

# Stage labels for CAD generation progress (moved from job_runner.py)
CAD_STAGE_LABELS: dict[str, str] = {
    "fuselage_created": "正在生成机身",
    "wing_created": "正在生成机翼",
    "tail_created": "正在生成尾翼",
    "engine_created": "正在生成发动机",
    "vsp_model_saved": "正在保存模型",
    "step_exported": "正在导出 STEP 文件",
    "glb_exported": "正在导出 3D 模型",
    "preview_ready": "三维预览准备就绪",
}


def publish_workflow_stage(
    bus: JobEventBus,
    job_id: str,
    design_id: str,
    version_no: int,
    stage: str,
    label: str,
    *,
    progress: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Publish a WORKFLOW_STAGE event, optionally with a backward-compatible PROGRESS event.

    Parameters
    ----------
    bus:
        The event bus to publish on.
    job_id, design_id, version_no:
        Identifiers for the job / design / version.
    stage:
        Machine-readable stage identifier (e.g. "generating_spec").
    label:
        Human-readable stage label (e.g. "生成飞机参数").
    progress:
        Optional progress percentage (0-100). When provided, a second
        PROGRESS event is also emitted for backward compatibility.
    metadata:
        Optional extra metadata dict attached to the WORKFLOW_STAGE event.
    """
    meta = metadata or {}

    bus.publish(JobEvent(
        type=JobEventType.WORKFLOW_STAGE,
        job_id=job_id,
        design_id=design_id,
        version_no=version_no,
        stage=stage,
        label=label,
        progress=progress if progress is not None else 0,
        metadata=meta,
    ))

    if progress is not None:
        bus.publish(JobEvent(
            type=JobEventType.PROGRESS,
            job_id=job_id,
            design_id=design_id,
            version_no=version_no,
            progress=progress,
            current_step=stage,
        ))


def publish_artifact_generated(
    bus: JobEventBus,
    job_id: str,
    design_id: str,
    version_no: int,
    artifact_key: str,
    artifact_path: str | Path,
) -> None:
    """Publish an ARTIFACT_GENERATED event.

    Parameters
    ----------
    bus:
        The event bus to publish on.
    job_id, design_id, version_no:
        Identifiers for the job / design / version.
    artifact_key:
        Short key identifying the artifact type (e.g. "glb", "step", "vsp3").
    artifact_path:
        Filesystem path to the generated artifact.
    """
    bus.publish(JobEvent(
        type=JobEventType.ARTIFACT_GENERATED,
        job_id=job_id,
        design_id=design_id,
        version_no=version_no,
        metadata={
            "artifact_key": artifact_key,
            "artifact_path": str(artifact_path),
        },
    ))
