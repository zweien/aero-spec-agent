# Workflow Runtime Transparency QA

**Feature:** AI Workflow Runtime Transparency v2
**Date:** 2026-05-20

---

## Normal Chat Workflow

| Step | Expected | Pass |
|------|----------|------|
| User submits design request | "生成中" button with spinner | |
| Within 300ms | UnifiedWorkflowTimeline appears with "理解设计需求" running | |
| LLM tokens arrive | "理解设计需求" completed, "生成飞机参数" running, text streams | |
| generation_started event | ToolCard appears, timeline transitions to real stages | |
| generating_spec stage | "生成飞机参数" shows as running | |
| validating_parameters stage | "校验设计参数" shows as running | |
| CAD sub-stages (OpenVSP) | "生成机身" → "生成机翼" → "生成尾翼" → "生成发动机" progress | |
| glb_exported stage | "导出 3D 模型" progress | |
| preview_ready stage | "三维预览准备就绪", CADLoadingOverlay fades out | |
| Generation complete | UnifiedWorkflowTimeline all ● completed, version badge | |
| Model loads | CadViewer updates with 3D preview (smooth fade-in) | |

## CAD Loading Overlay

| Step | Expected | Pass |
|------|----------|------|
| Generation starts | Overlay appears with skeleton animation | |
| Stage updates | Current stage label updates in overlay | |
| Progress bar | Mini progress bar updates in real-time | |
| preview_ready | Overlay fades out smoothly (0.5s transition) | |
| No flash | Viewer does not flash between loading and loaded states | |

## Progress Bar in ToolCard

| Step | Expected | Pass |
|------|----------|------|
| Generation running | Progress bar visible with percentage | |
| Progress updates | Bar width animates smoothly | |
| 100% | Bar full, then ToolCard shows completed state | |

## Deep Design Workflow

| Step | Expected | Pass |
|------|----------|------|
| Deep Design starts | GraphTimeline shows graph nodes | |
| Variant generation | Variant status updates in cards | |
| CAD sub-stages | workflow_stage events appear in event log | |
| Recommendation | AI recommendation card appears | |
| GraphTimeline + UnifiedTimeline | Both coexist without conflict | |

## Failure Cases

| Scenario | Expected | Pass |
|----------|----------|------|
| OpenVSP generation fails | WorkflowErrorCard with failed stage + suggestions | |
| "重试" button | Triggers regeneration | |
| "查看详情" button | Toggles DiagnosticsPanel | |
| SSE connection drops | Falls back to polling | |
| Stage shows "failed" | UnifiedWorkflowTimeline highlights failed step in red | |

## No Runtime Jargon

| Should NOT appear | OK |
|-------------------|-----|
| "node", "checkpoint", "thread_id" | |
| "subgraph", "LangGraph" | |
| "workflow_stage" (raw) | |
| Any English runtime terminology | |

## Elapsed Time

| Scenario | Expected | Pass |
|----------|----------|------|
| Generation running | "已运行：Xs" shows at timeline bottom | |
| Each completed stage | Duration shown next to stage (e.g. "123ms") | |
| Generation complete | Total elapsed time accurate | |

---

## Browser E2E Test Commands

```bash
# Start backend
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port 8900

# Start frontend
cd apps/web && npm run dev

# Test case: send "设计一架翼展10米、单发、上单翼、常规尾翼的固定翼长航时无人机"
# Observe: timeline → spec → CAD loading → preview → complete
```

## OpenVSP Real Backend Test

```bash
CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port 8900

# Test with same prompt — expect to see individual CAD sub-stages:
# 生成机身 → 生成机翼 → 生成尾翼 → 生成发动机 → 保存模型 → 导出 3D 模型 → 三维预览准备就绪
```
