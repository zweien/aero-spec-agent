# Workflow Transparency QA

**Feature:** Workflow Event Stream + TaskRuntimeCard
**Date:** 2026-05-19

---

## Normal Chat Workflow

| Step | Expected | Pass |
|------|----------|------|
| User submits design request | Button shows "生成中" with spinner | |
| Within 300ms | "AI 思考中..." indicator appears in assistant bubble | |
| LLM tokens arrive | "AI 思考中..." replaced with streaming markdown | |
| Tool call detected | ToolCard appears with spinner | |
| ToolCard running | WorkflowTimeline shows with animated stages | |
| writing_spec stage | Shows "编写设计规格" with running indicator | |
| geometry_building stage | Shows "构建几何模型" with running indicator | |
| mesh_export stage | Shows "导出三维模型" with running indicator | |
| report_generating stage | Shows "生成分析报告" with running indicator | |
| Generation complete | ToolCard shows ✓ with version badge | |
| Model loads | CadViewer updates with 3D preview | |

## Deep Design Workflow

| Step | Expected | Pass |
|------|----------|------|
| Deep Design starts | Existing timeline works unchanged | |
| Variant generation | Variant cards show status | |
| Recommendation | AI recommendation card appears | |

## SSE Fallback (Polling)

| Scenario | Expected | Pass |
|----------|----------|------|
| `/api/jobs/{id}/stream` returns 404 | Falls back to polling | |
| SSE connection drops mid-stream | Falls back to polling | |
| Polling also fails | Error message shown | |

## Failure Cases

| Scenario | Expected | Pass |
|----------|----------|------|
| OpenVSP generation fails | ToolCard shows ✗ with diagnostics | |
| Stage shows "failed" step | WorkflowTimeline highlights failed step in red | |
| LLM timeout | Error message in chat | |

## No Runtime Jargon

| Should NOT appear | OK |
|-------------------|-----|
| "node", "checkpoint", "thread_id" | |
| "subgraph", "LangGraph" | |
| Any English runtime terminology | |

---

## Browser E2E Test Commands

```bash
# Start backend
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port 8900

# Start frontend
cd apps/web && npm run dev

# Test case: send "设计一架翼展10米、单发、上单翼的长航时无人机"
# Observe: AI thinking → ToolCard with animated WorkflowTimeline → model appears
```
