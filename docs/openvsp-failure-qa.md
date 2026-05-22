---
qa_id: openvsp-failure
status: pass
date: 2026-05-22
env: fake
---

# OpenVSP 失败注入 QA

## 测试环境

```bash
# 使用 fake backend 验证失败注入机制（OpenVSP 后端使用相同的机制）
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_failure_events.py -q
```

## 失败注入机制

`OPENVSP_FAIL_STAGE` 环境变量控制在 OpenVSP 后端的哪个阶段注入 `RuntimeError`。该机制与 `FakeCadBackend` 的 `FAKE_CAD_FAIL_STAGE` 平行设计。

### 实现位置

`services/workers/cad_worker/openvsp_generator/backend.py` — `OpenVspBackend.generate()`

```python
# 每个关键阶段后检查
fail_stage = os.getenv("OPENVSP_FAIL_STAGE", "").strip()
# ...
if fail_stage == "creating_fuselage":
    raise RuntimeError(f"OpenVSP failure injection at stage: creating_fuselage")
```

### 支持的阶段

| 阶段 | 环境变量值 | 说明 |
|------|-----------|------|
| 机身创建后 | `creating_fuselage` | `create_fuselage()` 完成后失败 |
| 机翼创建后 | `creating_wing` | `create_main_wing()` 完成后失败 |
| 尾翼创建后 | `creating_tail` | `create_tail()` 完成后失败 |
| 发动机创建后 | `creating_engine` | `create_engine_nacelles()` 完成后失败 |
| vsp3 保存后 | `saving_vsp3` | `WriteVSPFile()` 完成后失败 |
| step 导出后 | `exporting_step` | `ExportFile(EXPORT_STEP)` 完成后失败 |
| glb 导出后 | `exporting_glb` | OBJ→GLB 转换完成后失败 |

### FakeCadBackend 对应阶段

| 阶段 | 环境变量值 |
|------|-----------|
| `fuselage_created` | 机身进度 |
| `wing_created` | 机翼进度 |
| `tail_created` | 尾翼进度 |
| `engine_created` | 发动机进度 |
| `vsp_model_saved` | 模型保存进度 |
| `step_exported` | step 导出进度 |
| `glb_exported` | glb 导出进度 |
| `preview_ready` | 预览就绪进度 |

## 测试结果 (2026-05-22)

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_failure_events.py -v
```

| 测试用例 | 状态 | 说明 |
|----------|------|------|
| `test_openvsp_fail_stage_marks_failed_workflow_stage` | PASS | `OPENVSP_FAIL_STAGE=glb_exported` 导致 job.status == "failed"，错误信息包含阶段名 |
| `test_openvsp_fail_stage_preserves_previous_version` | PASS | 失败的 v2 不影响已存在的 v1 artifacts |
| `test_openvsp_fail_stage_stream_events` | PASS | SSE 流中 `workflow_stage(failed)` 出现在 `generation_failed` 之前 |
| `test_openvsp_no_corrupted_version_on_failure` | PASS | 失败时不产生损坏的不完整版本 |
| `test_openvsp_fail_stage_no_env_var` | PASS | 不设置 `OPENVSP_FAIL_STAGE` 时生成正常成功 |

**5 passed**

## 验证要点

### 1. Job 状态正确标记

失败注入后，`JobRunner` 将 job 状态设为 `"failed"`，`error_message` 包含失败阶段名。

### 2. 旧版本保留

`VersionStore` 的自增版本号机制确保失败的版本不会覆盖已有的成功版本。

### 3. SSE 事件顺序

SSE 流中事件顺序为：
1. `workflow_stage` (各阶段 progress)
2. `workflow_stage` (failed 阶段)
3. `generation_failed`

前端可据此正确展示失败状态。

### 4. 无损坏版本

失败可能创建了版本目录，但不完整的 artifacts 不会被当作有效版本展示。

## 相关文件

| 文件 | 说明 |
|------|------|
| `services/workers/cad_worker/openvsp_generator/backend.py` | `OpenVspBackend` / `FakeCadBackend` 失败注入实现 |
| `tests/api/test_openvsp_failure_events.py` | 5 条失败注入测试 |
| `tests/api/test_fake_cad_failure_stage.py` | Fake backend 失败注入测试 |
| `tests/api/test_workflow_failure_events.py` | 工作流失败事件测试 |
| `services/api/app/services/job_runner.py` | JobRunner 错误处理 |

## 自动化测试

```bash
# OpenVSP 失败注入测试
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_failure_events.py -v

# Fake CAD 失败注入测试
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_fake_cad_failure_stage.py -v

# 工作流失败事件测试
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_workflow_failure_events.py -v
```
