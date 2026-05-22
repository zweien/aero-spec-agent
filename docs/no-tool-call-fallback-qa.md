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

## MiniMax-M2.5 预设验证

### 测试结果 (2026-05-22)

| 验证项 | 状态 |
|--------|------|
| Settings 中显示 MiniMax-M2.5 预设按钮 | PASS |
| 点击预设自动填入 modelName=MiniMax-M2.5 | PASS |
| 点击预设自动填入 baseUrl=http://192.168.2.220:3000/v1 | PASS |
| Test Connection 返回"连接成功" | PASS |
| 不破坏 DeepSeek / OpenAI / 自定义预设 | PASS |
| localStorage profile 保存正常 | PASS |

**重要发现：** MiniMax-M2.5 (192.168.2.220:3000) 通过 VLLM 代理**支持 function calling**，因此 fallback 路径不会被触发。Fallback 是为真正不支持 tool calling 的模型准备的兼容路径。

## 测试 1：生成 v1

**Prompt:** `设计一架翼展12米、双发、上单翼、常规尾翼的固定翼长航时无人机`

**截图:** `docs/qa-screenshots/minimax-agent-run-v1.png`

| 验证项 | 状态 |
|--------|------|
| 模型调用 generate_design tool | PASS |
| generation_started 出现 | PASS |
| CAD 子阶段实时显示 | PASS |
| CADLoadingOverlay 正常 | PASS |
| VersionPanel 显示 v1 | PASS |
| 4 个 artifact 文件 (vsp3/step/glb/obj) | PASS |
| 参数面板显示 14 个参数 | PASS |
| 运行时间 ~27s | PASS |
| CAD 预览加载 GLB 模型 | PASS |
| 设计检查/性能估算/气动分析完成 | PASS |

## 测试 2：修改生成 v2

**前置条件:** 已有 v1

**Prompt:** `把翼展改为15米，并优化为长航时布局`

**截图:** `docs/qa-screenshots/minimax-fallback-modify-v2.png`

| 验证项 | 状态 |
|--------|------|
| 模型调用 modify_design tool | PASS |
| 修改详情表格显示 (12m→15m 等) | PASS |
| 生成 v2 | PASS |
| VersionPanel 显示 v1/v2 | PASS |
| v2 不覆盖 v1 | PASS |
| CAD Viewer 加载 v2 (15 M) | PASS |
| 参数面板更新 (翼展=15m) | PASS |

## 测试 3：概念问答负例

**说明:** MiniMax-M2.5 通过 VLLM 代理支持 function calling，负例由后端单元测试覆盖。

**单元测试覆盖：** `tests/api/test_tool_fallback.py` 中 12 条负例 parametrize

| 测试 prompt | 预期 | 单元测试 |
|-------------|------|----------|
| 什么是展弦比？ | 不触发 fallback | PASS |
| 固定翼无人机有哪些布局？ | 不触发 fallback | PASS |
| 请解释一下 OpenVSP | 不触发 fallback | PASS |
| 不要生成，只给我讲讲设计思路 | 不触发 fallback | PASS |
| 导出报告 | 不触发 fallback | PASS |

## 测试 4：Compare View E2E

**截图:** `docs/qa-screenshots/minimax-compare-v1-v2.png`

| 验证项 | 状态 |
|--------|------|
| v1 加入对比 | PASS |
| v2 加入对比 | PASS |
| CompareDrawer 打开 | PASS |
| 标题"方案对比 (2)" | PASS |
| v1/v2 CompareItemCard 显示 | PASS |
| 指标表 (翼展/翼面积/展弦比/升阻比/航程/续航/翼载荷) | PASS |
| design_metrics 读取正确 | PASS |
| ★ 最佳值高亮 | PASS |
| 风险等级 low | PASS |
| "查看模型"按钮可用 | PASS |
| "设为当前"按钮可用 | PASS |
| "移除"按钮可用 | PASS |
| "清空对比"按钮可用 | PASS |

## 测试 5：Deep Design 回归

| 状态 | 说明 |
|------|------|
| SKIP | 不在本轮核心范围内，基础功能不受 fallback 影响 |

## 自动化测试

```bash
# Fallback 意图检测 + args 构造 (~45 tests)
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_tool_fallback.py -q

# Fallback 集成测试 (~5 tests)
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_chat_service_no_tool_fallback.py -q

# Design metrics 测试
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_design_metrics.py -q

# 前端测试
cd apps/web && npx tsx --test src/components/chat/chatSse.test.ts
cd apps/web && npx tsx --test src/components/chat/FallbackToolNotice.test.ts

# 生产构建
cd apps/web && npm run build
```

## 已知限制

1. **MiniMax-M2.5 实际支持 function calling**: 通过 VLLM 代理 (192.168.2.220:3000)，MiniMax-M2.5 能正确返回 tool_calls，fallback 路径不会被触发。
2. **Fallback 适用于**: 真正不支持 function calling 的模型（如部分本地 VLLM 部署）。Fallback 逻辑由单元/集成测试独立验证。
3. **Fallback 精度**: 基于规则引擎，不调用 LLM。对边缘 case 可能误判，可通过 `NO_TOOL_CALL_FALLBACK=false` 关闭。

## 截图路径

| 截图 | 说明 |
|------|------|
| `docs/qa-screenshots/minimax-agent-run-v1.png` | MiniMax-M2.5 生成 v1 完整页面 |
| `docs/qa-screenshots/minimax-version-v1.png` | VersionPanel v1 |
| `docs/qa-screenshots/minimax-fallback-modify-v2.png` | 修改设计生成 v2 |
| `docs/qa-screenshots/minimax-compare-v1-v2.png` | Compare View v1/v2 |
