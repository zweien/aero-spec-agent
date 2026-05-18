# AeroSpec Agent 真实案例测试计划

> 版本: v1.0 | 日期: 2026-05-18 | 状态: Draft

## 1. 概述

本文档定义了 AeroSpec Agent 核心设计探索流程的端到端真实案例测试计划。每个测试案例覆盖从 API 请求到 Graph 执行、SSE 事件流和 CAD 输出的完整生命周期。

### 1.1 测试目标

- 验证 DeepDesignGraph → CompareGraph → VariantSubgraph 的 graph-of-graphs 编排正确性
- 验证 SSE 实时事件流的时序与内容完整性
- 验证 OpenVSP / FakeCadBackend 产出的 CAD 文件完整性
- 验证异常输入的 graceful failure 处理

### 1.2 关键 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/deep-design` | POST | 多变体设计探索主入口 |
| `/api/chat/stream` | POST | SSE 实时流 |
| `/api/design-controller/compare` | POST | 变体对比 |
| `/api/metrics` | GET | Prometheus 指标 |

### 1.3 Graph 节点拓扑

```
DeepDesignGraph (enable_refinement=false):
  START
  → parse_requirements
  → prepare_variants
  → run_compare
    └→ CompareGraph:
        START
        → dispatch_variants
          └→ VariantSubgraph × N:
              START
              → validate_and_enqueue
              → wait_for_completion
              END
        → compare_metrics
        → synthesize_summary
        END
  → synthesize_report
  END
```

### 1.4 SSE 事件协议

| 事件类型 | 数据字段 | 触发时机 |
|----------|----------|----------|
| `generation_started` | job_id, design_id, version_no, status | job 入队后立即发出 |
| `generation_progress` | job_id, progress, current_step | geometry_building / mesh_export / report_generating |
| `generation_complete` | job_id, design_id, version_no, duration_ms | 生成成功 |
| `generation_failed` | job_id, error_message | 生成失败 |
| `message` | content, intent, job_id, status | 最终汇总消息 |

---

## 2. 测试案例

### 案例一: 长航时侦察无人机

**场景描述:** 设计一款 500km 航程、20kg 载荷的长航时侦察无人机，探索 3 个变体（compact / standard / extended）。

#### 2.1.1 输入

**请求:**

```json
POST /api/deep-design

{
  "design_id": "recon-uav-endurance",
  "description": "设计一款长航时侦察无人机，航程 500km，载荷 20kg，优先考虑续航时间",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "recon_uav_endurance",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "mission": {
      "cruise_speed": { "value": 150, "unit": "km/h", "source": "user", "confidence": 0.9 },
      "payload": { "value": 20, "unit": "kg", "source": "user", "confidence": 1.0 },
      "priority": { "value": "endurance", "source": "user", "confidence": 1.0 }
    },
    "fuselage": {
      "length": { "value": 6.0, "unit": "m", "source": "rule_default", "confidence": 0.7 },
      "max_diameter": { "value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 14.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.4, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.7, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "sweep": { "value": 3, "unit": "deg", "source": "rule_default", "confidence": 0.7 },
      "dihedral": { "value": 4, "unit": "deg", "source": "rule_default", "confidence": 0.7 },
      "airfoil": { "value": "NACA4415", "source": "system_default", "confidence": 0.6 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    },
    "engine": {
      "count": { "value": 1, "source": "user", "confidence": 1.0 },
      "position": { "value": "rear_fuselage", "source": "inferred", "confidence": 0.75 }
    }
  },
  "constraints": {
    "variant_count": 3,
    "max_iterations": 1
  }
}
```

**description 关键解析预期:**

| 正则匹配 | 提取值 | 含义 |
|----------|--------|------|
| `(\d+)\s*km` | `500` | `requirements.range_km = 500` |
| `(\d+)\s*kg` | `20` | `requirements.payload_kg = 20` |

#### 2.1.2 预期 Graph Flow

| 序号 | Graph | 节点 | 说明 |
|------|-------|------|------|
| 1 | DeepDesignGraph | `parse_requirements` | 解析 description，提取 range_km=500, payload_kg=20, variant_count=3 |
| 2 | DeepDesignGraph | `prepare_variants` | 基于 DEFAULT_STRATEGIES 生成 3 个变体: compact(span-2), standard(原样), extended(span+2) |
| 3 | DeepDesignGraph | `run_compare` | 调用 CompareGraph |
| 3a | CompareGraph | `dispatch_variants` | 遍历 3 个变体，逐个调用 VariantSubgraph |
| 3a-i | VariantSubgraph | `validate_and_enqueue` | 验证 AircraftSpec，入队生成 job |
| 3a-ii | VariantSubgraph | `wait_for_completion` | 等待 job 完成，超时 120s |
| 3b | CompareGraph | `compare_metrics` | 汇总 3 个变体的成功/失败计数 |
| 3c | CompareGraph | `synthesize_summary` | 生成文本对比摘要 |
| 4 | DeepDesignGraph | `synthesize_report` | 生成最终设计探索报告 |

**3 个变体 spec 差异:**

| 变体 | label | wing.span | 与 base 差异 |
|------|-------|-----------|-------------|
| compact | compact | 12.0 m | -2.0 m |
| standard | standard | 14.0 m | 无修改 |
| extended | extended | 16.0 m | +2.0 m |

#### 2.1.3 预期 SSE 事件序列

每个变体依次触发以下事件流（共 3 组）:

```
event: generation_started
data: {"job_id":"<job_id_1>","design_id":"recon-uav-endurance","version_no":1,"status":"queued"}

event: generation_progress
data: {"job_id":"<job_id_1>","status":"running","progress":25,"current_step":"geometry_building"}

event: generation_progress
data: {"job_id":"<job_id_1>","status":"running","progress":60,"current_step":"mesh_export"}

event: generation_progress
data: {"job_id":"<job_id_1>","status":"running","progress":90,"current_step":"report_generating"}

event: generation_complete
data: {"job_id":"<job_id_1>","design_id":"recon-uav-endurance","version_no":1,"duration_ms":<N>}

--- 变体 2 / 变体 3 类似，version_no 递增 ---

event: message
data: {"content":"已提交生成任务，正在后台生成 CAD 模型。","intent":"generate_design","job_id":"","status":"completed"}
```

#### 2.1.4 预期 CAD 输出

每个变体在 `storage/designs/recon-uav-endurance/versions/{N}/` 下生成:

| 文件 | 格式 | 说明 |
|------|------|------|
| `aircraft_spec.yaml` | YAML | 该变体的完整 spec |
| `aircraft.vsp3` | OpenVSP | 原生模型文件 |
| `aircraft.step` | STEP | 通用 CAD 交换格式 |
| `aircraft.glb` | glTF Binary | 前端 3D 预览用 |
| `generation_log.json` | JSON | 生成过程日志 |
| `validation_report.json` | JSON | 模型验证报告 |

3 个变体共 18 个文件。

#### 2.1.5 验收标准

- [ ] HTTP 200 响应，`status == "completed"`
- [ ] `report` 字段非空，包含 3 个变体的对比表格
- [ ] `comparison.total_variants == 3`，`comparison.succeeded == 3`
- [ ] 3 个 version 目录均已创建且各包含 6 个文件
- [ ] compact 变体的 `wing.span.value == 12.0`，extended 变体的 `wing.span.value == 16.0`
- [ ] 所有 `.glb` 文件可被 Three.js `GLTFLoader` 正常加载
- [ ] SSE 事件序列完整，无 `generation_failed` 事件
- [ ] `/api/metrics` 中 `deep_design_total` 计数器增加 1

---

### 案例二: 小型物流无人机

**场景描述:** 设计一款 50km 短航程、100kg 大载荷的小型物流无人机，探索 2 个变体。

#### 2.2.1 输入

**请求:**

```json
POST /api/deep-design

{
  "design_id": "logistics-uav-heavy",
  "description": "设计小型物流无人机，航程 50km，载荷 100kg，短距起降",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "logistics_uav_heavy",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "mission": {
      "cruise_speed": { "value": 100, "unit": "km/h", "source": "user", "confidence": 0.85 },
      "payload": { "value": 100, "unit": "kg", "source": "user", "confidence": 1.0 },
      "priority": { "value": "payload", "source": "user", "confidence": 0.9 }
    },
    "fuselage": {
      "length": { "value": 5.0, "unit": "m", "source": "rule_default", "confidence": 0.7 },
      "max_diameter": { "value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 10.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.8, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.9, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "sweep": { "value": 2, "unit": "deg", "source": "rule_default", "confidence": 0.7 },
      "dihedral": { "value": 5, "unit": "deg", "source": "rule_default", "confidence": 0.7 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    },
    "engine": {
      "count": { "value": 2, "source": "user", "confidence": 1.0 },
      "position": { "value": "under_wing", "source": "inferred", "confidence": 0.75 }
    }
  },
  "constraints": {
    "variant_count": 2,
    "max_iterations": 1
  }
}
```

**description 关键解析预期:**

| 正则匹配 | 提取值 | 含义 |
|----------|--------|------|
| `(\d+)\s*km` | `50` | `requirements.range_km = 50` |
| `(\d+)\s*kg` | `100` | `requirements.payload_kg = 100` |

#### 2.2.2 预期 Graph Flow

| 序号 | Graph | 节点 | 说明 |
|------|-------|------|------|
| 1 | DeepDesignGraph | `parse_requirements` | 解析 description，提取 range_km=50, payload_kg=100, variant_count=2 |
| 2 | DeepDesignGraph | `prepare_variants` | 基于 DEFAULT_STRATEGIES 前 2 个: compact(span-2), standard(原样) |
| 3 | DeepDesignGraph | `run_compare` | 调用 CompareGraph |
| 3a | CompareGraph | `dispatch_variants` | 遍历 2 个变体 |
| 3a-i | VariantSubgraph (compact) | `validate_and_enqueue` → `wait_for_completion` | span=8.0m |
| 3a-ii | VariantSubgraph (standard) | `validate_and_enqueue` → `wait_for_completion` | span=10.0m |
| 3b | CompareGraph | `compare_metrics` | 汇总 2 个变体 |
| 3c | CompareGraph | `synthesize_summary` | 生成对比摘要 |
| 4 | DeepDesignGraph | `synthesize_report` | 最终报告 |

**2 个变体 spec 差异:**

| 变体 | label | wing.span |
|------|-------|-----------|
| compact | compact | 8.0 m |
| standard | standard | 10.0 m |

#### 2.2.3 预期 SSE 事件序列

```
event: generation_started       → variant 1 (compact)
event: generation_progress      → geometry_building
event: generation_progress      → mesh_export
event: generation_progress      → report_generating
event: generation_complete      → variant 1 完成

event: generation_started       → variant 2 (standard)
event: generation_progress      → geometry_building
event: generation_progress      → mesh_export
event: generation_progress      → report_generating
event: generation_complete      → variant 2 完成

event: message                  → 最终汇总
```

#### 2.2.4 预期 CAD 输出

2 个变体，各 6 个文件，共 12 个文件。位于 `storage/designs/logistics-uav-heavy/versions/{1,2}/`。

#### 2.2.5 验收标准

- [ ] HTTP 200，`status == "completed"`
- [ ] `comparison.total_variants == 2`，`comparison.succeeded == 2`
- [ ] compact 变体 `wing.span.value == 8.0`
- [ ] 2 个 version 目录均已创建，各含 6 个文件
- [ ] 机身 `max_diameter == 1.2` 体现在 compact 和 standard 两个变体的 spec 中
- [ ] `engine.count.value == 2` 在所有变体中保持不变
- [ ] SSE 事件序列完整，每个变体 4 个 progress + 1 个 complete

---

### 案例三: 翼展参数对比

**场景描述:** 固定布局不变，仅通过 compare API 直接对比翼展参数变化对模型的影响。使用 `-2m / 标准 / +2m` 三组参数。

#### 2.3.1 输入

**请求:**

```json
POST /api/design-controller/compare

{
  "design_id": "span-compare-study",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "span_compare",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "mission": {
      "cruise_speed": { "value": 120, "unit": "km/h", "source": "user", "confidence": 1.0 },
      "payload": { "value": 30, "unit": "kg", "source": "user", "confidence": 1.0 }
    },
    "fuselage": {
      "length": { "value": 7.0, "unit": "m", "source": "rule_default", "confidence": 0.7 },
      "max_diameter": { "value": 0.75, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 12.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "sweep": { "value": 5, "unit": "deg", "source": "rule_default", "confidence": 0.7 },
      "dihedral": { "value": 3, "unit": "deg", "source": "rule_default", "confidence": 0.7 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    },
    "engine": {
      "count": { "value": 2, "source": "user", "confidence": 1.0 },
      "position": { "value": "under_wing", "source": "inferred", "confidence": 0.75 }
    }
  },
  "variants": [
    {
      "label": "short_span",
      "changes": [
        { "path": "wing.span.value", "value": 10.0 }
      ]
    },
    {
      "label": "standard_span",
      "changes": []
    },
    {
      "label": "long_span",
      "changes": [
        { "path": "wing.span.value", "value": 14.0 }
      ]
    }
  ]
}
```

#### 2.3.2 预期 Graph Flow

本案例使用 `/api/design-controller/compare`（graph mode 下），直接触发 CompareGraph，不经过 DeepDesignGraph:

| 序号 | Graph | 节点 | 说明 |
|------|-------|------|------|
| 1 | CompareGraph | `dispatch_variants` | 遍历 3 个显式定义的变体 |
| 1a | VariantSubgraph (short_span) | `validate_and_enqueue` → `wait_for_completion` | span=10.0m |
| 1b | VariantSubgraph (standard_span) | `validate_and_enqueue` → `wait_for_completion` | span=12.0m（base 原样） |
| 1c | VariantSubgraph (long_span) | `validate_and_enqueue` → `wait_for_completion` | span=14.0m |
| 2 | CompareGraph | `compare_metrics` | 汇总 3 个变体结果 |
| 3 | CompareGraph | `synthesize_summary` | 生成对比摘要文本 |

#### 2.3.3 预期 SSE 事件序列

通过 `/api/chat/stream` 端点观察时（若配合流式使用）:

```
event: generation_started       → short_span (job_id_1)
event: generation_progress      → geometry_building
event: generation_progress      → mesh_export
event: generation_progress      → report_generating
event: generation_complete      → job_id_1

event: generation_started       → standard_span (job_id_2)
event: generation_progress      → ...
event: generation_complete      → job_id_2

event: generation_started       → long_span (job_id_3)
event: generation_progress      → ...
event: generation_complete      → job_id_3
```

#### 2.3.4 预期 CAD 输出

3 个变体，位于 `storage/designs/span-compare-study/versions/{1,2,3}/`:

| 变体 | version_no | wing.span | 预期展弦比变化 |
|------|-----------|-----------|---------------|
| short_span | 1 | 10.0 m | 较低展弦比 |
| standard_span | 2 | 12.0 m | 标准 |
| long_span | 3 | 14.0 m | 较大展弦比 |

每个目录 6 个文件（aircraft_spec.yaml, .vsp3, .step, .glb, generation_log.json, validation_report.json）。

#### 2.3.5 验收标准

- [ ] HTTP 200，响应 `status == "completed"`
- [ ] `results` 数组长度 == 3，所有变体 `status == "succeeded"`
- [ ] `summary` 字段非空，包含 "共 3 个变体：3 个成功"
- [ ] short_span 变体 `wing.span.value == 10.0`，long_span `wing.span.value == 14.0`
- [ ] 3 个 .glb 文件尺寸存在明显差异（长翼展模型更大）
- [ ] 除 `wing.span` 外，其余参数在 3 个变体中完全一致
- [ ] 所有 `thread_id` 格式为 `span-compare-study_variant_{0,1,2}`

---

### 案例四: 发动机布局修改

**场景描述:** 修改发动机数量和纵向位置，对比不同发动机布局对模型的影响。

#### 2.4.1 输入

**请求:**

```json
POST /api/design-controller/compare

{
  "design_id": "engine-layout-study",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "engine_layout_compare",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "mission": {
      "cruise_speed": { "value": 120, "unit": "km/h", "source": "user", "confidence": 1.0 },
      "payload": { "value": 30, "unit": "kg", "source": "user", "confidence": 1.0 }
    },
    "fuselage": {
      "length": { "value": 7.0, "unit": "m", "source": "rule_default", "confidence": 0.7 },
      "max_diameter": { "value": 0.75, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 12.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.75 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    },
    "engine": {
      "count": { "value": 2, "source": "user", "confidence": 1.0 },
      "position": { "value": "under_wing", "source": "inferred", "confidence": 0.75 },
      "x_offset": { "value": 1.5, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    }
  },
  "variants": [
    {
      "label": "single_rear",
      "changes": [
        { "path": "engine.count.value", "value": 1 },
        { "path": "engine.position.value", "value": "rear_fuselage" },
        { "path": "engine.x_offset", "value": { "value": -1.0, "unit": "m", "source": "user", "confidence": 0.9 } }
      ]
    },
    {
      "label": "dual_forward",
      "changes": [
        { "path": "engine.x_offset", "value": { "value": 2.5, "unit": "m", "source": "user", "confidence": 0.9 } }
      ]
    }
  ]
}
```

#### 2.4.2 预期 Graph Flow

| 序号 | Graph | 节点 | 说明 |
|------|-------|------|------|
| 1 | CompareGraph | `dispatch_variants` | 遍历 2 个变体 |
| 1a | VariantSubgraph (single_rear) | `validate_and_enqueue` | 验证 engine.count=1 + rear_fuselage + x_offset=-1.0 的 spec |
| 1a | VariantSubgraph (single_rear) | `wait_for_completion` | 等待生成完成 |
| 1b | VariantSubgraph (dual_forward) | `validate_and_enqueue` | 验证 engine.count=2 + x_offset=2.5 的 spec |
| 1b | VariantSubgraph (dual_forward) | `wait_for_completion` | 等待生成完成 |
| 2 | CompareGraph | `compare_metrics` | 汇总 2 个变体 |
| 3 | CompareGraph | `synthesize_summary` | 对比摘要 |

**变体 spec 差异:**

| 字段 | single_rear | dual_forward | base |
|------|-------------|-------------|------|
| engine.count | 1 | 2 (不变) | 2 |
| engine.position | rear_fuselage | under_wing (不变) | under_wing |
| engine.x_offset | -1.0 m | 2.5 m | 1.5 m |

#### 2.4.3 预期 SSE 事件序列

```
event: generation_started       → single_rear
event: generation_progress      → geometry_building
event: generation_progress      → mesh_export
event: generation_progress      → report_generating
event: generation_complete      → single_rear 完成

event: generation_started       → dual_forward
event: generation_progress      → geometry_building
event: generation_progress      → mesh_export
event: generation_progress      → report_generating
event: generation_complete      → dual_forward 完成
```

#### 2.4.4 预期 CAD 输出

2 个变体，位于 `storage/designs/engine-layout-study/versions/{1,2}/`:

| 变体 | 预期模型特征 |
|------|-------------|
| single_rear | 单发尾置，机身尾部可见发动机短舱 |
| dual_forward | 双发翼下前置，发动机位置较 base 更靠前 |

#### 2.4.5 验收标准

- [ ] HTTP 200，`status == "completed"`
- [ ] 2 个变体均 `status == "succeeded"`
- [ ] single_rear 变体的 `aircraft_spec.yaml` 中 `engine.count.value == 1`
- [ ] single_rear 变体的 `engine.position.value == "rear_fuselage"`
- [ ] dual_forward 变体的 `engine.x_offset.value == 2.5`
- [ ] `.glb` 文件可正常加载，前端 CadViewer 可渲染 2 种不同发动机布局
- [ ] validation_report.json 中无严重几何错误
- [ ] 除 engine 相关字段外，其余参数与 base_spec 一致

---

### 案例五: 异常参数失败诊断

**场景描述:** 提交缺少必填字段的无效 base_spec，验证 graceful failure 路径。系统应在 `validate_and_enqueue` 节点检测到校验错误并优雅降级，不应出现未捕获异常或 500 错误。

#### 2.5.1 输入

**请求 A — 缺少 `fuselage` 必填字段:**

```json
POST /api/deep-design

{
  "design_id": "invalid-spec-test",
  "description": "测试异常参数",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "broken_uav",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 12.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.75 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    },
    "engine": {
      "count": { "value": 2, "source": "user", "confidence": 1.0 }
    }
  },
  "constraints": {
    "variant_count": 2
  }
}
```

**缺失字段清单:**

| 缺失字段 | AircraftSpec 约束 | 预期 Pydantic 错误 |
|----------|-------------------|-------------------|
| `fuselage` | `Fuselage` (必填) | `Field required` |
| `fuselage.length` | `NumericScalar` (必填) | `Field required` |

**请求 B — confidence 值非法（user source 但 confidence < 0.7）:**

```json
POST /api/deep-design

{
  "design_id": "invalid-confidence-test",
  "description": "测试 confidence 校验",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "bad_confidence",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "mission": {
      "payload": { "value": 30, "unit": "kg", "source": "user", "confidence": 0.3 }
    },
    "fuselage": {
      "length": { "value": 7.0, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 12.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.75 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    },
    "engine": {
      "count": { "value": 2, "source": "user", "confidence": 1.0 }
    }
  },
  "constraints": {
    "variant_count": 1
  }
}
```

**请求 C — 通过 `/api/design-controller/compare` 缺少必填字段:**

```json
POST /api/design-controller/compare

{
  "design_id": "invalid-compare-test",
  "base_spec": {
    "schema_version": "0.1",
    "aircraft": {
      "name": "no_engine",
      "type": "fixed_wing_uav",
      "layout": "conventional"
    },
    "fuselage": {
      "length": { "value": 7.0, "unit": "m", "source": "rule_default", "confidence": 0.7 }
    },
    "wing": {
      "position": { "value": "high", "source": "user", "confidence": 1.0 },
      "span": { "value": 12.0, "unit": "m", "source": "user", "confidence": 1.0 },
      "root_chord": { "value": 1.2, "unit": "m", "source": "rule_default", "confidence": 0.75 },
      "tip_chord": { "value": 0.6, "unit": "m", "source": "rule_default", "confidence": 0.75 }
    },
    "tail": {
      "type": { "value": "conventional", "source": "user", "confidence": 1.0 }
    }
  },
  "variants": [
    {
      "label": "v1",
      "changes": []
    }
  ]
}
```

**缺失字段:** `engine`（AircraftSpec 必填）

#### 2.5.2 预期 Graph Flow

**请求 A — 缺少 fuselage:**

| 序号 | Graph | 节点 | 结果 |
|------|-------|------|------|
| 1 | DeepDesignGraph | `parse_requirements` | 正常解析 |
| 2 | DeepDesignGraph | `prepare_variants` | 使用缺少 fuselage 的 base_spec 构建变体 |
| 3 | DeepDesignGraph | `run_compare` | 调用 CompareGraph |
| 3a | CompareGraph | `dispatch_variants` | 调用 VariantSubgraph |
| 3a-i | VariantSubgraph | `validate_and_enqueue` | `AircraftSpec.model_validate()` 抛出 Pydantic ValidationError，捕获后返回 `status: "failed"` |
| 3a-ii | VariantSubgraph | `wait_for_completion` | 检测到 `status == "failed"`，直接返回 |
| 3b | CompareGraph | `compare_metrics` | 汇总为 `succeeded: 0, failed: 2` |
| 3c | CompareGraph | `synthesize_summary` | 生成包含失败信息的摘要 |
| 4 | DeepDesignGraph | `synthesize_report` | 报告标记失败状态 |

**请求 B — confidence 校验失败:**

| 序号 | 节点 | 结果 |
|------|------|------|
| ... | `validate_and_enqueue` | `model_validator` 触发: `"user supplied values must have confidence >= 0.7"`，`status: "failed"` |

**请求 C — CompareGraph 路径:**

| 序号 | 节点 | 结果 |
|------|------|------|
| 1 | `dispatch_variants` | 调用 VariantSubgraph |
| 1a | `validate_and_enqueue` | 缺少 engine 字段，Pydantic 校验失败，`status: "failed"` |

#### 2.5.3 预期 SSE 事件序列

**请求 A / B — 通过 DeepDesignGraph:**

由于 `validate_and_enqueue` 失败，不会入队生成 job，因此:

```
event: generation_failed
data: {"job_id":"","design_id":"invalid-spec-test","version_no":0,"status":"failed","error_message":"invalid spec: ... Field required ..."}

event: message
data: {"content":"生成任务提交失败，正在重试。","intent":"generate_design","job_id":"","status":"failed"}
```

**请求 C — 通过 CompareGraph:**

```
无 generation_started 事件（job 未入队）

event: generation_failed
data: {"job_id":"","design_id":"invalid-compare-test","status":"failed","error_message":"invalid spec: ... Field required ..."}
```

#### 2.5.4 预期 CAD 输出

**无 CAD 输出。** 不创建 version 目录或仅创建空目录。

#### 2.5.5 验收标准

**请求 A（缺少 fuselage）:**

- [ ] HTTP 200（非 500），`status == "completed"` 或含 `error_message`
- [ ] `report` 中包含失败说明
- [ ] `comparison.failed == 2`，`comparison.succeeded == 0`
- [ ] 不存在 `storage/designs/invalid-spec-test/versions/` 下的有效 CAD 文件
- [ ] 服务器日志无未捕获异常 traceback
- [ ] `/api/metrics` 中 `deep_design_errors_total` 增加

**请求 B（confidence 校验）:**

- [ ] HTTP 200，`error_message` 包含 `"confidence >= 0.7"` 文本
- [ ] 所有变体 `status == "failed"`
- [ ] 无 CAD 文件生成

**请求 C（CompareGraph 缺少 engine）:**

- [ ] HTTP 200，响应中 `status != "completed"`
- [ ] `results[0].status == "failed"`
- [ ] `results[0].error_message` 包含 `"Field required"` 或 `"engine"` 相关信息
- [ ] 无 CAD 文件生成

**通用验收标准:**

- [ ] 所有 3 个失败请求均返回 HTTP 200（graceful failure），不返回 HTTP 500
- [ ] 无进程崩溃或未处理异常
- [ ] 错误消息对用户可读，包含缺失字段名或校验规则描述
- [ ] 服务器日志记录了完整的 Pydantic ValidationError 详情

---

## 3. 测试执行清单

### 3.1 环境准备

| 步骤 | 命令 | 说明 |
|------|------|------|
| 启动 API (fake) | `CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port 3901` | 标准测试使用 fake backend |
| 启动 API (openvsp) | `CAD_BACKEND=openvsp .venv/bin/python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port 3901` | OpenVSP 集成测试 |
| 清理 storage | `rm -rf storage/designs/*` | 确保干净状态 |
| 启动前端 | `cd apps/web && npm run dev` | 可选，用于可视化验证 |

### 3.2 测试矩阵

| 案例 | CAD Backend | Graph Mode | 预期耗时 | 优先级 |
|------|-------------|-----------|----------|--------|
| 案例一 | fake / openvsp | partial | < 30s / < 120s | P0 |
| 案例二 | fake / openvsp | partial | < 20s / < 90s | P0 |
| 案例三 | fake / openvsp | partial | < 30s / < 120s | P1 |
| 案例四 | openvsp only | partial | < 90s | P1 |
| 案例五 | fake / openvsp | partial | < 10s | P0 |

### 3.3 自动化验证脚本（伪代码）

```bash
# 通用验证流程
DESIGN_ID="<design_id>"
RESPONSE=$(curl -s -X POST http://localhost:3901/api/deep-design \
  -H "Content-Type: application/json" \
  -d @test_case_input.json)

# 验证 HTTP 状态
HTTP_CODE=$(echo "$RESPONSE" | jq -r '.status')

# 验证 version 目录
ls storage/designs/$DESIGN_ID/versions/

# 验证 CAD 文件
for v in storage/designs/$DESIGN_ID/versions/*/; do
  test -f "$v/aircraft.vsp3" && echo "PASS: $v/aircraft.vsp3" || echo "FAIL: $v/aircraft.vsp3"
  test -f "$v/aircraft.glb" && echo "PASS: $v/aircraft.glb" || echo "FAIL: $v/aircraft.glb"
  test -f "$v/aircraft_spec.yaml" && echo "PASS: $v/aircraft_spec.yaml" || echo "FAIL: $v/aircraft_spec.yaml"
done

# 验证 spec 参数
python3 -c "
import yaml, sys
spec = yaml.safe_load(open('storage/designs/$DESIGN_ID/versions/1/aircraft_spec.yaml'))
print('wing.span:', spec['wing']['span']['value'])
print('engine.count:', spec['engine']['count']['value'])
"
```

---

## 4. 附录

### 4.1 AircraftSpec 必填字段速查

| 模块 | 必填字段 | 类型 |
|------|----------|------|
| schema_version | `"0.1"` | Literal |
| aircraft.name | string | str |
| aircraft.type | `"fixed_wing_uav"` | Literal |
| aircraft.layout | `"conventional"` | Literal |
| fuselage.length | NumericScalar | value + unit + source + confidence |
| wing.position | TextScalar | value + source + confidence |
| wing.span | NumericScalar | value + unit + source + confidence |
| wing.root_chord | NumericScalar | value + unit + source + confidence |
| wing.tip_chord | NumericScalar | value + unit + source + confidence |
| tail.type | TextScalar | value + source + confidence |
| engine.count | IntegerScalar | value + source + confidence |

### 4.2 DEFAULT_STRATEGIES 定义

```python
DEFAULT_STRATEGIES = [
    {"label": "compact",  "changes": [{"path": "wing.span.value", "value": -2, "op": "relative"}]},
    {"label": "standard", "changes": []},
    {"label": "extended", "changes": [{"path": "wing.span.value", "value": 2, "op": "relative"}]},
]
```

### 4.3 SSE 事件 payload 模板

```json
{
  "generation_started": {
    "job_id": "string",
    "design_id": "string",
    "version_no": 0,
    "status": "queued",
    "created_at": "ISO-8601"
  },
  "generation_progress": {
    "job_id": "string",
    "status": "running",
    "progress": 0,
    "current_step": "geometry_building | mesh_export | report_generating"
  },
  "generation_complete": {
    "job_id": "string",
    "design_id": "string",
    "version_no": 0,
    "status": "succeeded",
    "duration_ms": 0
  },
  "generation_failed": {
    "job_id": "string",
    "status": "failed",
    "error_message": "string"
  }
}
```
