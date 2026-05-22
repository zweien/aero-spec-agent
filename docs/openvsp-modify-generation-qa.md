---
qa_id: openvsp-modify-generation
status: skip
date: 2026-05-22
env: fake
---

# OpenVSP 修改生成 QA

## 状态

**SKIP** — OpenVSP 未安装（`docs/openvsp-env-check.md` 记录了环境检查失败原因）。本测试在 OpenVSP 环境可用时执行。

## 前置条件

- OpenVSP 已安装且可通过环境检查
- 已有 v1（OpenVSP 单方案生成成功）

## 测试环境（待执行）

```bash
# Terminal 1 — Backend
set -a && . .env && set +a
CAD_BACKEND=openvsp CHAT_GENERATION_MODE=async \
  .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Terminal 2 — Frontend
cd apps/web && npm run dev
```

浏览器访问 http://localhost:3900

## 配置

| 环境变量 | 值 | 说明 |
|----------|-----|------|
| `CAD_BACKEND` | `openvsp` | 使用真实 OpenVSP 后端 |
| `CHAT_GENERATION_MODE` | `async` | SSE 异步模式 |

## 测试步骤

### Prompt

```
把翼展改为15米，并优化为长航时布局
```

### 验证清单

| 验证项 | 状态 |
|--------|------|
| 模型调用 modify_design tool | PENDING |
| 修改详情表格显示（翼展 12m → 15m） | PENDING |
| 生成 v2（OpenVSP 后端） | PENDING |
| VersionPanel 显示 v1/v2 两个版本 | PENDING |
| v2 不覆盖 v1 的 artifacts | PENDING |
| v2 的 .vsp3 / .glb / .step / .obj 均生成 | PENDING |
| CAD Viewer 加载 v2 glb（15M 翼展） | PENDING |
| 参数面板更新（翼展 = 15m） | PENDING |
| validation_report.design_metrics 更新 | PENDING |
| v2 design_metrics 与 v1 有合理差异 | PENDING |
| Compare View 可加入 v1/v2 对比 | PENDING |
| Compare View 指标差异正确（翼展/翼面积/展弦比等） | PENDING |

### 截图（待补充）

| 截图 | 说明 |
|------|------|
| `docs/qa-screenshots/openvsp-v2-modify.png` | 修改设计生成 v2 |
| `docs/qa-screenshots/openvsp-v1-v2-compare.png` | Compare View v1/v2 |

## 失败分类

| 失败类型 | 表现 | 排查方向 |
|----------|------|----------|
| modify_design 未触发 | Agent 返回纯文本 | 检查 LLM tool calling |
| v2 覆盖 v1 | v1 artifacts 消失 | 检查 `VersionStore` 自增版本号逻辑 |
| OpenVSP 参数越界 | 几何创建抛异常 | 检查 spec 参数范围校验 |
| glb 未更新 | CAD Viewer 仍显示 v1 | 检查版本号传递、GLB URL 缓存 |
| design_metrics 未变化 | v2 指标与 v1 完全相同 | 检查 `compute_design_metrics()` 是否读取了新 spec |

## 版本对比预期

| 指标 | v1 | v2 | 变化 |
|------|-----|-----|------|
| 翼展 | 12 m | 15 m | ↑ 25% |
| 翼面积 | ~16 m² | ~22 m² | ↑ ~37% |
| 展弦比 | ~9.0 | ~10.2 | ↑ |
| 估算升阻比 | ~14.3 | ~15.1 | ↑ |

> 注：以上为 fake backend 参考值，OpenVSP 实际值会有差异。

## 相关文件

| 文件 | 说明 |
|------|------|
| `services/workers/cad_worker/openvsp_generator/backend.py` | `OpenVspBackend.generate()` |
| `services/api/app/services/version_store.py` | 版本自增、目录隔离 |
| `services/api/app/services/design_metrics.py` | `compute_design_metrics()` |
| `apps/web/src/components/compare/metricExtractors.ts` | 前端指标提取 |

## 自动化测试

```bash
# 修改生成集成测试（fake backend）
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/ -q -k "modify"

# OpenVSP 后端单元测试
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_backend_unit.py -q
```
