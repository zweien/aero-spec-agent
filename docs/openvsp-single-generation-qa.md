---
qa_id: openvsp-single-generation
status: skip
date: 2026-05-22
env: fake
---

# OpenVSP 单方案生成 QA

## 状态

**SKIP** — OpenVSP 未安装（`docs/openvsp-env-check.md` 记录了环境检查失败原因）。本测试在 OpenVSP 环境可用时执行。

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
| `NO_TOOL_CALL_FALLBACK` | `true` | 启用 fallback |

## 测试步骤

### Prompt

```
设计一架翼展12米、双发、上单翼、常规尾翼的固定翼长航时无人机
```

### 验证清单

| 验证项 | 状态 |
|--------|------|
| 模型调用 generate_design tool | PENDING |
| generation_started 事件出现 | PENDING |
| workflow_stage 实时显示（fuselage_created → preview_ready） | PENDING |
| CADLoadingOverlay 正常 | PENDING |
| .vsp3 文件生成且非空 | PENDING |
| .glb 文件生成且可被 Three.js 加载 | PENDING |
| .step 文件生成（如 OpenVSP 版本支持） | PENDING |
| .obj 文件生成 | PENDING |
| validation_report.design_metrics 存在且无 NaN | PENDING |
| validation_report.backend = "openvsp" | PENDING |
| VersionPanel 显示 v1 | PENDING |
| CAD Viewer 加载 glb 模型正常 | PENDING |
| 参数面板显示完整参数 | PENDING |
| design_metrics 指标值合理（翼展 ≈ 12m） | PENDING |
| 设计检查/性能估算/气动分析完成 | PENDING |

### 截图（待补充）

| 截图 | 说明 |
|------|------|
| `docs/qa-screenshots/openvsp-v1-agent-run.png` | Agent Run 完整页面 |
| `docs/qa-screenshots/openvsp-v1-cad-viewer.png` | CAD Viewer 加载 glb |
| `docs/qa-screenshots/openvsp-v1-version-panel.png` | VersionPanel v1 |

## 失败分类

| 失败类型 | 表现 | 排查方向 |
|----------|------|----------|
| 初始化失败 | `OpenVspUnavailableError` / `import vsp` 报错 | 检查 OpenVSP 安装、`OPENVSP_EXE` 路径 |
| 几何生成失败 | `create_fuselage` / `create_wing` 抛异常 | 检查 spec 参数是否在合理范围 |
| vsp3 保存失败 | `WriteVSPFile` 报错 / 文件为空 | 检查输出目录权限、磁盘空间 |
| glb 导出失败 | `obj_to_glb` 报错 / glb 文件损坏 | 检查 OBJ 文件完整性、`obj_to_glb.py` 依赖 |
| step 导出失败 | `ExportFile` 报错 | 部分版本 OpenVSP 不支持 STEP 导出 |
| validation_report 缺失 | `generation_log.json` 中无 backend 字段 | 检查 `generate_aircraft()` 返回值 |
| CAD Viewer 加载失败 | Three.js 控制台报错 | 检查 glb 文件完整性、`GLTFLoader` |
| VersionPanel 未更新 | v1 按钮未出现 | 检查 `/api/designs/{id}/versions` 返回值 |
| design_metrics 含 NaN | 前端显示 NaN | 检查 `compute_design_metrics()` 对空值的处理 |

## 相关文件

| 文件 | 说明 |
|------|------|
| `services/workers/cad_worker/openvsp_generator/backend.py` | `OpenVspBackend.generate()` |
| `services/workers/cad_worker/openvsp_generator/generate_aircraft.py` | 生成编排 |
| `services/api/app/services/design_metrics.py` | `compute_design_metrics()` |
| `tests/api/test_openvsp_backend_unit.py` | OpenVSP 后端单元测试 |
| `tests/api/test_openvsp_integration.py` | OpenVSP 集成测试（需 `RUN_OPENVSP_TESTS=1`） |

## 自动化测试

```bash
# OpenVSP 后端单元测试（使用 FakeOpenVspModule mock，无需真实 OpenVSP）
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_backend_unit.py -q

# OpenVSP 集成测试（需安装 OpenVSP）
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 \
  .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q
```
