# OpenVSP Workflow Events Validation

**Date:** 2026-05-20
**Feature:** Unified AI Workflow Runtime Layer v3

## Summary

Both `FakeCadBackend` and `OpenVspBackend` emit the same 8 CAD sub-stages via
`on_progress` callbacks, with identical stage names and progress percentages.
This ensures consistent frontend progress display regardless of which backend
is active.

## Verification Result

All 8 CAD stages are confirmed identical between the two backends by source
code inspection (`services/workers/cad_worker/openvsp_generator/backend.py`).

## Stage Sequence

Both backends emit these 8 CAD sub-stages:

| Stage                | Progress | Label              | Backend Timing                          |
|----------------------|----------|--------------------|-----------------------------------------|
| fuselage_created     | 62%      | 正在生成机身       | after `create_fuselage()`               |
| wing_created         | 68%      | 正在生成机翼       | after `create_main_wing()`              |
| tail_created         | 72%      | 正在生成尾翼       | after `create_tail()`                   |
| engine_created       | 76%      | 正在生成发动机     | after `create_engine_nacelles()`        |
| vsp_model_saved      | 82%      | 正在保存模型       | after `adapter.write_vsp_file()`        |
| step_exported        | 86%      | 正在导出 STEP 文件 | after `adapter.export_file(step)`       |
| glb_exported         | 92%      | 正在导出 3D 模型   | after `obj_to_glb` conversion           |
| preview_ready        | 96%      | 三维预览准备就绪   | before return                           |

## Full Event Sequence

The complete workflow event sequence from start to finish:

1. `generating_spec` (10%) -- 生成飞机参数
2. `validating_parameters` (20%) -- 校验设计参数
3. `fuselage_created` (62%) -- 正在生成机身
4. `wing_created` (68%) -- 正在生成机翼
5. `tail_created` (72%) -- 正在生成尾翼
6. `engine_created` (76%) -- 正在生成发动机
7. `vsp_model_saved` (82%) -- 正在保存模型
8. `step_exported` (86%) -- 正在导出 STEP 文件
9. `glb_exported` (92%) -- 正在导出 3D 模型
10. `preview_ready` (96%) -- 三维预览准备就绪
11. `completed` (100%) -- 设计完成

## Source Locations

- Backend implementations: `services/workers/cad_worker/openvsp_generator/backend.py`
  - `FakeCadBackend.generate()` -- lines 55-65 (on_progress loop)
  - `OpenVspBackend.generate()` -- lines 87-126 (inline on_progress calls)
- Stage labels: `services/api/app/services/workflow_events.py` (`CAD_STAGE_LABELS`)
- Event bus: `services/api/app/services/job_events.py`
- Tests: `tests/api/test_openvsp_workflow_events.py`

## Verification Checklist

- [x] FakeCadBackend emits all 8 CAD stages
- [x] OpenVspBackend emits all 8 CAD stages
- [x] Stage names match between backends
- [x] Progress values match between backends
- [x] All stages have Chinese labels in `CAD_STAGE_LABELS`
- [x] Progress values are monotonically increasing
- [x] `on_progress` signature present on both backends
- [ ] SSE stream includes `workflow_stage` events (integration)
- [ ] Frontend timeline shows all stages in order (integration)

## Automated Tests

Run with:

```bash
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_workflow_events.py -q
```

Test cases:
- `test_cad_stage_names_match_between_backends` -- source code inspection
- `test_all_cad_stages_have_chinese_labels` -- label completeness
- `test_cad_stage_progress_values_are_monotonically_increasing` -- ordering
- `test_cad_stages_cover_full_range` -- range coverage
- `test_openvsp_backend_on_progress_signature` -- API contract
- `test_fake_backend_emits_all_cad_stages` -- runtime callback verification
- `test_cad_stage_labels_are_non_empty_strings` -- label validity
- `test_no_duplicate_stage_names` -- uniqueness
- `test_no_duplicate_progress_values` -- uniqueness
