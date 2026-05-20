# Agent Run Async 主路径

## 概述

`CHAT_GENERATION_MODE=async` 是推荐的 CAD 生成模式。用户发送设计请求后，后端立即创建 Job 并返回 `job_id`，然后通过 ThreadPoolExecutor 在后台执行生成。前端订阅 SSE 流获取实时进度更新。

同步模式（sync）仅作为 fallback，它会阻塞 SSE 响应直到生成完成。

## 架构

### 后端流程

```
用户发送消息
  → ChatService._handle_generate_design()
    → JobRunner.create_job() → JobRecord
    → SSE: generation_started (job_id, status="running")
    → ThreadPoolExecutor.submit(run_job_generation)
      → JobRunner._run_generation()
        → workflow_stage events (via JobEventBus)
        → FakeCadBackend / OpenVspBackend.generate()
          → on_progress(stage, progress)
          → FAKE_CAD_FAIL_STAGE 可注入失败
        → artifact_generated events
        → SSE: generation_complete 或 generation_failed
```

关键文件：
- `services/api/app/services/chat_service.py` — async 模式判断、job 调度
- `services/api/app/services/job_runner.py` — Job 生命周期、stage_history
- `services/api/app/routers/designs.py` — SSE 流（replay + live events）
- `services/workers/cad_worker/openvsp_generator/backend.py` — CAD 后端

### 前端流程

```
ChatPanel 收到 generation_started (job_id)
  → startJobStreaming(jobId)
    → streamJobEvents() → fetch /api/jobs/{id}/stream
      → workflow_stage → updateRuntimeEvent()
        → TaskRuntimeCard 时间线更新
        → AgentRunHeader 进度更新
        → CADLoadingOverlay 阶段显示
      → artifact_generated → updateRuntimeArtifacts()
    → generation_complete
      → completeLatestTool() → onGenerationComplete()
        → loadVersion() → CAD 模型加载
        → AgentRunActions 按钮显示
```

关键文件：
- `apps/web/src/components/chat/ChatPanel.tsx` — SSE 事件分发
- `apps/web/src/components/chat/useJobEventStream.ts` — SSE 解析
- `apps/web/src/components/chat/AgentRunActions.tsx` — 操作按钮
- `apps/web/src/components/chat/AgentRunActionsModel.ts` — 按钮模型
- `apps/web/src/components/chat/AgentRunDetails.tsx` — 可折叠详情

## 操作按钮

| 状态 | 按钮 | 行为 |
|------|------|------|
| 完成 | 查看模型 | `loadVersion(designId, versionNo)` + 滚动到 CAD Viewer |
| 完成 | 深度设计探索 | 设置 designId + 切换到 Deep Design tab |
| 完成 | 导出报告 | `window.open` validation_report.json |
| 完成 | 查看运行细节 | 展开 AgentRunDetails `<details>`（Job ID、阶段、工件、错误） |
| 失败 | 查看日志 | `window.open` 诊断页面 |
| 失败 | 重试 | 重新发送用户消息触发新一轮生成 |

## 失败恢复

### 失败注入（开发/QA）

```bash
FAKE_CAD_FAIL_STAGE=glb_exported   # 在指定阶段抛出 RuntimeError
```

可用阶段：`fuselage_created`, `wing_created`, `tail_created`, `engine_created`, `vsp_model_saved`, `step_exported`, `glb_exported`, `preview_ready`

### 失败时 UI 行为

1. TaskRuntimeCard 显示 WorkflowErrorCard（失败阶段 + 错误信息 + 建议）
2. AgentRunHeader 显示 ✗ 图标和 "设计失败"
3. AgentRunDetails 展示失败阶段（✗ 图标）和错误信息
4. CAD Viewer 保留之前加载的模型（compact overlay）
5. "重试"按钮重新发送原始用户消息

### SSE 失败事件流

```
workflow_stage (stage=X, status=running, progress=P)
  → RuntimeError
  → workflow_stage (stage=X, error_message="...")
  → generation_failed (job_id, error_message)
```

`_replay_stage_history` 确保 late-connecting 客户端也能看到失败阶段。

## 启动命令

```bash
# 后端（async 模式 + fake 后端 + 可控延迟）
set -a && . .env && set +a
CAD_BACKEND=fake CHAT_GENERATION_MODE=async FAKE_CAD_STEP_DELAY_MS=300 \
  .venv/bin/python -m uvicorn services.api.app.main:app \
  --host "$API_HOST" --port "$API_PORT"

# 前端
cd apps/web
set -a && . ../../.env && set +a
npm run dev
```

## 已知限制

1. **ThreadPoolExecutor 固定 4 worker**：高并发时可能排队
2. **无 Job 持久化**：服务重启后进行中的 Job 丢失
3. **SSE 120s 超时**：极慢的 OpenVSP 生成可能超时
4. **重试 = 重新生成**：不保留失败 Job 的 spec 修改
5. **无 Job 取消**：一旦开始无法中止

## 相关测试

- `tests/api/test_async_chat_generation.py` — async 模式 SSE 事件验证
- `tests/api/test_fake_cad_failure_stage.py` — 失败注入验证
- `apps/web/src/components/chat/AgentRunActionsModel.test.ts` — 按钮模型测试
- `apps/web/src/components/runtime/WorkflowErrorCard.test.ts` — 错误卡片测试
- `apps/web/src/components/runtime/TaskRuntimeCard.test.ts` — 运行时卡片测试
