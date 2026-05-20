# Async Agent Run Browser QA

**日期：** 2026-05-20  
**目标：** 验证普通 Chat 生成在 `CHAT_GENERATION_MODE=async` 下通过 job SSE 实时展示 CAD 子阶段。

## 环境

```bash
CAD_BACKEND=fake
FAKE_CAD_STEP_DELAY_MS=300
CHAT_GENERATION_MODE=async
```

浏览器验证使用本地 Chrome CDP。`gstack browse` 在当前容器内受 Chromium sandbox 限制无法启动，因此本轮使用 `google-chrome --headless=new --no-sandbox --remote-debugging-port=9223` 采集截图。为保证 Chat 输出稳定，QA 时使用本地 OpenAI-compatible fake server 返回固定 `generate_design` tool call。

## Sync Path 限制

`CHAT_GENERATION_MODE=sync` 保留为默认 fallback。该路径会在 `/api/chat` 请求内同步执行 CAD 生成，legacy sync generate 期间会阻塞 event loop，浏览器无法通过 `/api/jobs/{id}/stream` 实时看到 CAD 子阶段，只能在生成结束后看到回放或完成态。

## Async Path 结果

`CHAT_GENERATION_MODE=async` 下，普通 Chat 的 `generate_design` 会先创建 job 并立即返回 `generation_started`，前端马上订阅 `/api/jobs/{id}/stream`。后端在后台执行 `JobRunner.run_job_generation`，SSE 能实时推送：

- `workflow_stage`: 生成飞机参数、校验设计参数、机身、机翼、尾翼、发动机、保存模型、STEP 导出、GLB 导出、preview ready
- `artifact_generated`: `vsp3`、`step`、`glb`
- terminal event: `generation_completed` 或 `generation_failed`

截图证据：

- 初始 Agent Run header：`docs/qa-screenshots/async-agent-run-initial.png`
- CADLoadingOverlay 运行中：`docs/qa-screenshots/async-agent-run-overlay-running.png`
- CAD 子阶段实时推进：`docs/qa-screenshots/async-agent-run-cad-stage.png`
- artifact badges：`docs/qa-screenshots/async-agent-run-artifacts.png`
- 完成后 AgentRunActions：`docs/qa-screenshots/async-agent-run-actions.png`

完成态验证：

- `preview_ready` 后 CAD overlay 已从 DOM 移除。
- `AgentRunActions` 显示 `查看模型`、`深度设计探索`、`导出报告`、`查看运行细节`。
- 当前 headless Chrome 不支持 WebGL，CAD 预览降级为参数化 3D/2D 视图，但不会打断 Agent Run UI。

## Failure Scenario

失败场景使用：

```bash
CAD_BACKEND=fake
FAKE_CAD_STEP_DELAY_MS=300
FAKE_CAD_FAIL_STAGE=glb_exported
CHAT_GENERATION_MODE=async
```

验证结果：

- `glb_exported` 阶段触发 fake CAD failure。
- JobRunner 将当前阶段记录为 failed，并发布失败 `workflow_stage` 与 terminal failure event。
- 前端显示失败 timeline stage、`WorkflowErrorCard`、`查看日志`、`重试`。

截图证据：

- 失败前 GLB 导出阶段：`docs/qa-screenshots/async-agent-run-failure-before-error.png`
- 失败 UI：`docs/qa-screenshots/async-agent-run-failure.png`
