# No-Tool-Call Fallback QA

## 测试环境

```bash
# Terminal 1 — Backend
set -a && . .env && set +a
CAD_BACKEND=fake CHAT_GENERATION_MODE=async FAKE_CAD_STEP_DELAY_MS=300 \
  .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Terminal 2 — Frontend
cd apps/web && npm run dev
```

浏览器访问 http://localhost:3900

## 配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `NO_TOOL_CALL_FALLBACK` | `true` | 启用/禁用 fallback |
| `NO_TOOL_CALL_FALLBACK_MIN_CONFIDENCE` | `0.6` | 最低置信度阈值 |

## 测试流程

### 测试 1：生成设计

Prompt: `设计一架翼展12米、双发、上单翼、常规尾翼的固定翼长航时无人机`

预期：
- [ ] 模型返回纯文本（无 tool call）
- [ ] 聊天中显示 fallback 提示："模型未调用工具，系统自动识别为「生成设计」任务"
- [ ] generation_started 出现
- [ ] CAD 子阶段正常显示
- [ ] VersionPanel 出现 v1
- [ ] validation_report 包含 design_metrics
- [ ] AgentRunDetails 显示 FallbackToolNotice

### 测试 2：修改设计

前置条件：已有 v1

Prompt: `把翼展改为15米，并优化为长航时布局`

预期：
- [ ] fallback 识别为 modify_design
- [ ] 生成 v2
- [ ] VersionPanel 出现 v2

### 测试 3：概念问答负例

Prompt: `什么是展弦比？`

预期：
- [ ] 不触发 fallback
- [ ] 不生成 job
- [ ] 不出现 CAD loading
- [ ] 只返回文本回答

### 测试 4：Compare View E2E

前置条件：v1 和 v2 已生成

流程：
1. [ ] v1 加入对比
2. [ ] v2 加入对比
3. [ ] 打开 CompareDrawer
4. [ ] 查看后端 design_metrics
5. [ ] 查看默认补全提示
6. [ ] 查看模型 / 设为当前方案

## 验收标准

- [ ] MiniMax-M2.5 无 tool_call 时，设计请求可触发 fallback
- [ ] fallback_tool_detected event 正常发出
- [ ] AgentRunDetails 显示 FallbackToolNotice
- [ ] generate_design fallback 可生成 v1
- [ ] modify_design fallback 可生成 v2
- [ ] 概念问答不误触发 fallback
- [ ] validation_report.json 包含 design_metrics
- [ ] VersionPanel 正常显示版本
- [ ] Compare View 可加入 v1/v2
- [ ] tests/api/test_tool_fallback.py 通过
- [ ] tests/api/test_chat_service_no_tool_fallback.py 通过
- [ ] 前端 fallback 相关测试通过
- [ ] npm run build 通过
- [ ] pytest 通过
