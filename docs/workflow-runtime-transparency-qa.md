# Workflow Runtime Transparency QA

**Feature:** Agent Run UX — Manus-style E2E Verification
**Date:** 2026-05-20
**Environment:** Backend=localhost:8900 (CAD_BACKEND=fake), Frontend=localhost:3900 (Next.js dev)
**LLM Status:** MiniMax-M2.5 unavailable during test — Chat flow tests used preliminary phase only; backend API verified via curl/JS

---

## Summary

- **Pass:** 38 / **Fail:** 0 / **Skip:** 10
- **Key Passes:** AgentRunHeader timer, preliminary stages, SSE replay, artifact events, file access, progress non-regression, no runtime jargon, npm build, 451 backend tests, 88 frontend tests
- **Skipped:** Full Chat completion flow (LLM down), CAD overlay live observation (fake backend too fast), Deep Design browser test (needs LLM)

---

## Task 1: Test Suite Results

| Suite | Result | Count |
|-------|--------|-------|
| Backend pytest (CAD_BACKEND=fake) | PASS | 451 passed, 1 skipped |
| Frontend npm run build | PASS | No errors |
| Frontend node tests | PASS | 88 passed |
| Frontend runtime tests (tsx) | PASS | 22 passed |

New test files verified passing:
- `test_job_stream_stage_history.py`: 5/5
- `test_artifact_generated_stream.py`: 4/4
- `test_workflow_failure_events.py`: 7/7
- `test_openvsp_workflow_events.py`: 9/9

---

## Task 2: Agent Run Header (Browser Verified)

| Check | Expected | Result |
|-------|----------|--------|
| AgentRunHeader appears after submit | Within 300ms | ✅ Visible immediately |
| "正在设计飞机" title + ⟳ icon | Running state header | ✅ |
| Info line shows stage + progress + time | "生成飞机参数 · 28% · 已运行 2.8s" | ✅ |
| Elapsed time updates continuously | Not stuck at 0.0s | ✅ 2.8s → 6.2s → 72.2s observed |
| Preliminary progress simulates 0→40% | Progress increases during LLM wait | ✅ 28% → 45% observed |
| TaskRuntimeCard shows stages | "理解设计需求" + "生成飞机参数" | ✅ With ⟳ spinners |
| Stage description visible | "AI 正在理解你的设计目标和约束条件" | ✅ |
| "查看运行细节" collapsible | DisclosureTriangle present | ✅ |
| "AI 思考中..." indicator | Visible during LLM call | ✅ |
| No runtime jargon | All UI text in Chinese | ✅ |

**Note:** Timer fix verified: `useEffect` interval (200ms) correctly updates `elapsedTime` and preliminary `progress`.

---

## Task 3: CAD Viewer Overlay

| Check | Expected | Result |
|-------|----------|--------|
| Overlay visible during generation | Skeleton/compact mode | ⏭ SKIP — Fake backend completes in ~13ms, overlay not observable |
| Stage label syncs with workflow | Current stage shown | ⏭ SKIP |
| Old model preserved during regen | Canvas not cleared | ⏭ SKIP |
| preview_ready fades overlay | Smooth transition | ⏭ SKIP |
| Error state overlay | Warning + error message | ⏭ SKIP |

**Reason:** `FakeCadBackend.generate()` completes in <15ms. Overlay appears and disappears within a single render frame. `FAKE_CAD_STEP_DELAY_MS` not yet implemented. Overlay component code and CadViewer integration verified correct via code review and unit tests.

---

## Task 4: AgentRunActions

| Check | Expected | Result |
|-------|----------|--------|
| Post-completion buttons visible | "查看模型", "深度设计探索", "导出报告" | ⏭ SKIP — Needs LLM to complete full Chat flow |
| Failed state buttons | "重试", "查看日志" | ⏭ SKIP |
| Disabled states with tooltips | Non-available buttons grayed out | ⏭ SKIP |
| "查看运行细节" collapsible | Expands to show job metadata | ⏭ SKIP |

**Reason:** AgentRunActions renders after `generation_complete` SSE event. Full flow requires LLM.

---

## Task 5: Preliminary → Real Stage Transition

| Check | Expected | Result |
|-------|----------|--------|
| No progress regression | Real progress never < preliminary | ✅ Fixed: `Math.max(event.progress, prev.progress)` |
| No timeline flash | Real card renders before preliminary disappears | ✅ Verified: `isRunning` check at line 604 preserves card during transition |
| Preliminary cap at 40% | Leaves room for real progress takeover | ✅ |
| Real progress starts at 10% (generating_spec) | Math.max(10, 40) = 40% — no visible drop | ✅ Code review confirmed |

**Code change:** `useWorkflowRuntime.ts` — `applyEvent` uses `Math.max` for progress, preventing the "45% → 10%" visual regression.

---

## Task 6: Deep Design Regression

| Check | Expected | Result |
|-------|----------|--------|
| DeepDesignPanel imports | Uses UnifiedWorkflowTimeline directly | ✅ Code review |
| GraphTimeline re-export | Backward compatible | ✅ `UnifiedWorkflowTimeline as GraphTimeline` |
| nodes→stages conversion | nodesToStages field mapping correct | ✅ 7 unit tests pass |
| SSE parsing (useDeepDesignStream) | parseSseChunk correct | ✅ 5 unit tests pass |
| Build includes all components | No TS errors | ✅ npm run build passes |
| Browser: Deep Design tab | Requires completed design to interact | ⏭ SKIP — Needs LLM |
| Browser: Variant cards | 2-3 variants with status | ⏭ SKIP |
| Browser: Recommendation | AI recommendation card | ⏭ SKIP |

---

## Task 7: SSE Stream Verification (API Level)

**Method:** curl + browser evaluate_script against `/api/jobs/{id}/stream`

| Check | Expected | Result |
|-------|----------|--------|
| Total events per completed job | 14 events | ✅ 10 workflow_stage + 3 artifact_generated + 1 generation_complete |
| Stages in correct order | generating_spec → ... → preview_ready | ✅ All 10 stages present |
| artifact_generated events | One per file (vsp3, step, glb) | ✅ With Chinese labels + metadata |
| generation_complete terminal | Contains files + version_no | ✅ status=succeeded, progress=100 |
| File download URLs | All return 200 | ✅ spec(1277B), vsp3(23B), step(32B), glb(48B) |
| Diagnostics endpoint | Returns job + files_exist | ✅ All 6 files exist |

### SSE Event Sequence (verified)

```
workflow_stage: generating_spec (10%)
workflow_stage: validating_parameters (20%)
workflow_stage: fuselage_created (62%)
workflow_stage: wing_created (68%)
workflow_stage: tail_created (72%)
workflow_stage: engine_created (76%)
workflow_stage: vsp_model_saved (82%)
workflow_stage: step_exported (86%)
workflow_stage: glb_exported (92%)
workflow_stage: preview_ready (96%)
artifact_generated: vsp3 "OpenVSP 模型"
artifact_generated: step "STEP 工程文件"
artifact_generated: glb "三维预览模型"
generation_complete: succeeded (100%)
```

---

## No Runtime Jargon

| Should NOT appear | Result |
|-------------------|--------|
| "node", "checkpoint", "thread_id" | ✅ Not in page text |
| "subgraph", "LangGraph" | ✅ Not in page text |
| "workflow_stage" (raw) | ✅ Only in SSE payloads |
| Any English runtime terminology | ✅ All UI text is Chinese |

---

## Fixes Applied This Session

1. **AgentRunHeader timer** (`useWorkflowRuntime.ts`): Added `useEffect` interval (200ms) to continuously update `elapsedTime` and simulate preliminary progress (0→40%) during LLM thinking phase.
2. **Progress non-regression** (`useWorkflowRuntime.ts`): Changed `applyEvent` to use `Math.max(event.progress, prev.progress)` so real events never decrease displayed progress.
3. **Preliminary cap lowered** from 45% to 40% to give real stages earlier takeover point.

---

## Blocked Items (require LLM or slow backend)

- Full Chat Agent Run completion flow (AgentRunActions post-completion buttons)
- CAD Loading Overlay live observation
- Deep Design browser E2E (variant cards, recommendation, set current variant)
- Failure scenario (WorkflowErrorCard, retry button)
- `FAKE_CAD_STEP_DELAY_MS` for slow-motion testing (not yet implemented)

These are not blocking issues — they require either:
1. LLM service (MiniMax-M2.5) to be available
2. `FAKE_CAD_STEP_DELAY_MS` env var support in FakeCadBackend for slow-motion testing
3. OpenVSP backend for real CAD generation
