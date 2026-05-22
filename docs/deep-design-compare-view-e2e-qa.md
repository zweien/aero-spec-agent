# Deep Design + Compare View E2E QA

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

| 环境变量 | 值 | 说明 |
|----------|-----|------|
| `CAD_BACKEND` | `fake` | 模拟 CAD 后端 |
| `CHAT_GENERATION_MODE` | `async` | SSE 异步模式 |
| `FAKE_CAD_STEP_DELAY_MS` | `300` | 每个 CAD 步骤延迟 |
| LLM 模型 | MiniMax-M2.5 | 192.168.2.220:3000/v1 |

## 测试 1：基础设计 v1 生成回归

**Prompt:** `设计一架翼展12米、双发、上单翼、常规尾翼的固定翼长航时无人机`

**截图:** `docs/qa-screenshots/regression-v1.png`

| 验证项 | 状态 |
|--------|------|
| 模型调用 generate_design tool | PASS |
| generation_started 出现 | PASS |
| CAD 子阶段实时显示 | PASS |
| CADLoadingOverlay 正常 | PASS |
| VersionPanel 显示 v1 | PASS |
| 3 个 artifact 文件 (vsp3/step/glb) | PASS |
| 参数面板显示 15 个参数 | PASS |
| CAD 预览 "12M / 2发" | PASS |
| 设计检查/性能估算/气动分析完成 | PASS |
| 运行时间 ~2.4s | PASS |

## 测试 2：修改生成 v2 回归

**前置条件:** 已有 v1

**Prompt:** `把翼展改为15米，并优化为长航时布局`

**截图:** `docs/qa-screenshots/regression-v2-modify.png`

| 验证项 | 状态 |
|--------|------|
| 模型调用 modify_design tool | PASS |
| 修改详情表格显示 (12m→15m) | PASS |
| 翼型变更 NACA4412→NACA4418 | PASS |
| 后掠角变更 3°→5° | PASS |
| 生成 v2 | PASS |
| VersionPanel 显示 v1/v2 | PASS |
| v2 不覆盖 v1 | PASS |
| CAD Viewer 显示 15M | PASS |
| 参数面板更新 (翼展=15m) | PASS |
| 运行时间 ~2.5s | PASS |

## 测试 3：Deep Design 快速探索 (2 variants)

**前置条件:** 已有 v1/v2

**操作:**
1. 点击 v2 消息中的"深度设计探索"
2. 填写描述："基于当前设计探索长航时优化方案"
3. 勾选"长航时优化"
4. 选择"快速探索 (2)"
5. 点击"开始探索"

**截图:** `docs/qa-screenshots/deep-design-quick-2variants.png`

| 验证项 | 状态 |
|--------|------|
| 深度设计对话框正确显示 | PASS |
| 描述/策略/深度选项可交互 | PASS |
| 探索启动后表单禁用 | PASS |
| "运行中..."按钮状态 | PASS |
| 实时进度日志显示 | PASS |
| 2 个变体全部 succeeded | PASS |
| v3 (compact): 翼展 13.0m, 航程 ~3715km, L/D 17.7 | PASS |
| v4 (standard): 翼展 15.0m, 航程 ~4025.5km, L/D 19.2 | PASS |
| AI 推荐标记正确显示 | PASS |
| 每个变体有"查看模型/设为当前方案/加入对比" | PASS |
| 设计探索报告表格 (变体/状态/耗时) | PASS |
| "导出 .md"按钮可用 | PASS |
| "下一步建议"区域显示 | PASS |
| VersionPanel 新增 v3/v4 按钮 | PASS |

## 测试 4：Deep Design 标准探索 (3 variants)

**前置条件:** 已有 v1-v4

**操作:** 选择"标准探索 (3)"，其余同上

**截图:** `docs/qa-screenshots/deep-design-standard-3variants.png`

| 验证项 | 状态 |
|--------|------|
| 3 个变体全部 succeeded | PASS |
| v5 (compact): 翼展 13.0m, 航程 ~3715km, L/D 17.7 | PASS |
| v6 (standard): 翼展 15.0m, 航程 ~4025.5km, L/D 19.2 | PASS |
| v7 (extended): 翼展 17.0m, 航程 ~4300.3km, L/D 20.5 | PASS |
| 探索报告显示 "共探索 3 个变体，其中 3 个成功" | PASS |
| VersionPanel 显示 v1-v7 共 7 个版本 | PASS |
| 每个版本都有"加入对比"按钮 | PASS |
| 总运行时间 ~7.3s (3 variants 并行) | PASS |

## 测试 5：多变体 Compare View 闭环验证 (5 项)

**操作:**
1. 点击 v1, v2, v5, v6, v7 的"加入对比"
2. 点击导航栏"方案对比 (5)"

**截图:** `docs/qa-screenshots/compare-view-5items.png`

| 验证项 | 状态 |
|--------|------|
| "方案对比 (5)" 按钮正确计数 | PASS |
| CompareDrawer 打开 | PASS |
| 5 个 CompareItemCard (v1/v2/v5/v6/v7) | PASS |
| 每项显示版本号 + 风险等级 | PASS |
| 指标表列头: v1/v2/v5/v6/v7 | PASS |
| 基础尺寸: 翼展 (12/15/13/15/17m) | PASS |
| 基础尺寸: 机身长度 (8m 统一) | PASS |
| 基础尺寸: 翼面积 (16.20~22.95 m²) | PASS |
| 基础尺寸: 展弦比 (8.89~12.59) | PASS |
| 性能: 估算升阻比 (14.20~16.80) | PASS |
| 性能: 估算航程 (3544~4300 km) | PASS |
| 性能: 估算续航 (19.69~23.89 h) | PASS |
| 性能: 翼载荷 (23.24~32.92 kg/m²) | PASS |
| ★ 最佳值高亮正确 (v7 最优) | PASS |
| 可信度: 风险等级均为 low | PASS |
| 可信度: 默认补全参数均为 0 | PASS |
| 可信度: 缺失指标均为 0 | PASS |
| "查看模型"按钮 (每个 5 个) | PASS |
| "设为当前"按钮 (每个 5 个) | PASS |
| "移除"按钮 (每个 5 个) | PASS |
| "清空对比"按钮 | PASS |
| v3/v4 显示"对比已满"(最多 5 个) | PASS |
| 已加入的版本按钮显示"已加入"(disabled) | PASS |
| design_metrics 数据读取正确 | PASS |

## 自动化测试

```bash
# 后端全量测试 (~523 tests)
CAD_BACKEND=fake .venv/bin/python -m pytest -q

# 前端 SSE 解析测试
cd apps/web && npx tsx --test src/components/chat/chatSse.test.ts

# 前端 FallbackToolNotice 测试
cd apps/web && npx tsx --test src/components/chat/FallbackToolNotice.test.ts

# 前端生产构建
cd apps/web && npm run build
```

### 测试结果 (2026-05-22)

| 测试套件 | 结果 |
|----------|------|
| 后端 pytest | 523 passed, 1 skipped |
| 前端 chatSse.test.ts | 2 passed |
| 前端 FallbackToolNotice.test.ts | 4 passed |
| 前端 npm run build | 成功 |

## 版本清单

| 版本 | 来源 | 翼展 | 航程 | L/D | 展弦比 | 翼载 |
|------|------|------|------|-----|--------|------|
| v1 | 初始生成 | 12 m | ~3544 km | 14.2 | 8.89 | 32.92 kg/m² |
| v2 | 修改设计 | 15 m | ~4025 km | 15.8 | 11.11 | 26.34 kg/m² |
| v3 | DD quick compact | 13 m | ~3715 km | 17.7 | 9.6 | 30.4 kg/m² |
| v4 | DD quick standard | 15 m | ~4026 km | 19.2 | 11.1 | 26.3 kg/m² |
| v5 | DD standard compact | 13 m | ~3715 km | 17.7 | 9.6 | 30.4 kg/m² |
| v6 | DD standard standard | 15 m | ~4026 km | 19.2 | 11.1 | 26.3 kg/m² |
| v7 | DD standard extended | 17 m | ~4300 km | 20.5 | 12.6 | 23.2 kg/m² |

## 截图路径

| 截图 | 说明 |
|------|------|
| `docs/qa-screenshots/regression-v1.png` | v1 基础设计生成 |
| `docs/qa-screenshots/regression-v2-modify.png` | v2 修改设计 (12m→15m) |
| `docs/qa-screenshots/deep-design-quick-2variants.png` | Deep Design 快速探索 2 variants |
| `docs/qa-screenshots/deep-design-standard-3variants.png` | Deep Design 标准探索 3 variants |
| `docs/qa-screenshots/compare-view-5items.png` | Compare View 5 项对比 |

## 已知限制

1. **Fake CAD 后端**: 所有几何参数确定性生成，实际 OpenVSP 生成的变体差异会更大。
2. **Deep Design 变体命名**: quick/standard 模式的 compact/standard 变体可能产生相似参数，这是 fake backend 的特性。
3. **Compare View 上限**: 最多支持 5 个方案同时对比，超出部分显示"对比已满"。
