---
qa_id: openvsp-deep-design
status: skip
date: 2026-05-22
env: fake
---

# OpenVSP Deep Design QA

## 状态

**SKIP** — OpenVSP 未安装（`docs/openvsp-env-check.md` 记录了环境检查失败原因）。本测试在 OpenVSP 环境可用时执行。

## 前置条件

- OpenVSP 已安装且可通过环境检查
- 已有 v1（单方案生成成功）和 v2（修改生成成功）

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

### 操作

1. 点击 v2 消息中的"深度设计探索"
2. 填写描述："基于当前设计探索长航时优化方案"
3. 勾选"长航时优化"
4. 选择"快速探索 (2)"
5. 点击"开始探索"

### 验证清单

| 验证项 | 状态 |
|--------|------|
| 深度设计对话框正确显示 | PENDING |
| 描述/策略/深度选项可交互 | PENDING |
| 探索启动后表单禁用 | PENDING |
| 实时进度日志显示 | PENDING |
| 2 个变体进入 running 状态 | PENDING |
| 无并发冲突（两个 OpenVSP 实例不干扰） | PENDING |
| 每个变体有独立版本号（v3/v4） | PENDING |
| 每个变体有独立 artifacts（vsp3/glb/step/obj） | PENDING |
| 每个变体有独立 generation_log.json | PENDING |
| 每个变体有独立 validation_report.json | PENDING |
| 至少 1 个变体 succeeded | PENDING |
| 两个变体均 succeeded | PENDING |
| VersionPanel 新增 v3/v4 按钮 | PENDING |
| AI 推荐标记正确显示 | PENDING |
| 每个变体有"查看模型/设为当前方案/加入对比" | PENDING |
| 设计探索报告表格（变体/状态/耗时） | PENDING |
| Compare View 可加入 v1-v4 对比 | PENDING |
| Compare View 4 项指标差异正确 | PENDING |

### 截图（待补充）

| 截图 | 说明 |
|------|------|
| `docs/qa-screenshots/openvsp-deep-design-quick.png` | Deep Design 快速探索 2 variants |
| `docs/qa-screenshots/openvsp-compare-v1-v4.png` | Compare View v1-v4 |

## 验收标准

- 至少 1 个 variant 成功即可记录为部分通过
- 全部失败需定位问题原因，可能是：
  - OpenVSP 并发问题（多个 OpenVSP 实例同时运行）
  - 参数越界（自动生成的变体参数超出 OpenVSP 合理范围）
  - 导出冲突（多个实例写入同一路径）
  - 内存不足（OpenVSP 占用大量内存）

## 失败分类

| 失败类型 | 表现 | 排查方向 |
|----------|------|----------|
| 并发冲突 | v3/v4 互相覆盖或报错 | 检查 VersionStore 线程安全、输出目录隔离 |
| 参数越界 | OpenVSP 几何创建失败 | 检查变体参数范围 |
| 内存不足 | OOM 或进程被 kill | 监控内存使用，考虑串行执行 |
| 导出失败 | vsp3/glb 部分缺失 | 检查 OpenVSP 日志 |
| 版本号冲突 | v3/v4 版本号相同 | 检查 VersionStore 线程安全自增 |

## 相关文件

| 文件 | 说明 |
|------|------|
| `services/workers/cad_worker/openvsp_generator/backend.py` | `OpenVspBackend.generate()` |
| `services/api/app/services/job_runner.py` | `JobRunner.generate()` 并发管理 |
| `services/api/app/services/version_store.py` | 版本自增、线程安全 |
| `apps/web/src/components/compare/CompareDrawer.tsx` | Compare View 抽屉 |

## 自动化测试

```bash
# Deep Design 集成测试（fake backend）
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/ -q -k "deep_design"

# OpenVSP 并发测试（需安装 OpenVSP）
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 \
  .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q -k "concurrent"
```
