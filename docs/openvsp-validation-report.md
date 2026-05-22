---
qa_id: openvsp-pipeline-validation
status: pass
date: 2026-05-22
env: openvsp
---

# OpenVSP Pipeline Validation Report

## 结果

**全部通过** — 单发和双发常规布局 UAV 均成功生成完整 artifact。

## 验证环境

- OpenVSP: 3.50.2 Python API
- CAD Backend: openvsp
- Python: 3.12

## 单发常规布局 UAV

| Artifact | 状态 | 大小 |
|----------|------|------|
| aircraft.vsp3 | PASS | 248.6 KB |
| aircraft.step | PASS | 597.5 KB |
| aircraft.obj | PASS | 139.2 KB |
| aircraft.glb | PASS | 63.7 KB |
| generation_log.json | PASS | valid JSON |
| validation_report.json | PASS | design_metrics=yes |

## 双发常规布局 UAV

| Artifact | 状态 | 大小 |
|----------|------|------|
| aircraft.vsp3 | PASS | 256.5 KB |
| aircraft.step | PASS | 606.5 KB |
| aircraft.obj | PASS | 150.0 KB |
| aircraft.glb | PASS | 68.7 KB |
| generation_log.json | PASS | valid JSON |
| validation_report.json | PASS | design_metrics=yes |

## 验证方法

```bash
python scripts/validate_openvsp_pipeline.py
```

## 结论

OpenVSP 3.50.2 Python API 完整可用，单发/双发常规布局无人机可正常生成所有 artifact。v0.1.0 可支持真实 OpenVSP 生成。
