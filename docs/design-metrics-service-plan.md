# Design Metrics 后端服务设计计划

## 目标

将 Compare View 中的前端临时指标估算迁移到后端统一的 DesignMetrics 指标服务，提供一致的、可追溯的、带可信度标注的指标计算能力。

## 后端模块

**文件路径：** `services/api/app/services/design_metrics.py`

### 职责

1. 接收设计版本数据（spec、validation_report、generation artifacts）
2. 执行指标计算，标注每项指标的数据来源和可信度
3. 输出 `design_metrics.json`，写入 `storage/designs/{id}/versions/{N}/`

## 输出

### 文件

- `design_metrics.json` — 独立指标文件
- `validation_report.json` 中新增 `design_metrics` 字段（双重写入）

### 写入位置

```
storage/designs/{design_id}/versions/{N}/
  ├── aircraft_spec.yaml
  ├── aircraft.vsp3
  ├── ...
  ├── validation_report.json    ← 新增 design_metrics 字段
  └── design_metrics.json       ← 新增独立文件
```

## 指标列表

| 指标名 | 单位 | 说明 |
|--------|------|------|
| `wingspan_m` | m | 翼展 |
| `fuselage_length_m` | m | 机身长度 |
| `wing_area_m2` | m² | 机翼面积 |
| `aspect_ratio` | — | 展弦比 |
| `estimated_lift_to_drag` | — | 估算升阻比 |
| `estimated_range_km` | km | 估算航程 |
| `estimated_endurance_h` | h | 估算续航时间 |
| `wing_loading_kg_m2` | kg/m² | 翼载荷 |
| `thrust_to_weight` | — | 推重比 |
| `risk_level` | — | 风险等级 (low / medium / high / unknown) |
| `warnings` | string[] | 警告列表 |
| `confidence` | enum | 总体可信度 |

## 数据来源

指标值可能来自以下数据源，按优先级排序：

| 来源 | 标签 | 说明 |
|------|------|------|
| **spec_echo** | `user_input` / `inferred` / `rule_default` | 用户直接输入或推理引擎输出的规格参数 |
| **performance_estimate** | `heuristic` | 现有基于经验公式的估算 |
| **vspaero_analysis** | `vspaero` | VSPAERO 气动分析结果（如果可用） |

## 可信度标注

每项指标附带一个 `source` 字段标识其可信度级别：

| 标签 | 含义 |
|------|------|
| `user_input` | 用户直接输入，最高可信度 |
| `inferred` | 推理引擎推断 |
| `heuristic` | 经验公式估算 |
| `vspaero` | VSPAERO 气动分析 |
| `rule_default` | 规则默认值，最低可信度 |

## 前端变更

`metricExtractors` 逻辑调整为：

1. **优先读取** `design_metrics` 字段（来自后端）
2. **Fallback** 保持现有前端临时估算逻辑，确保向后兼容

```typescript
// 伪代码
function extractMetric(versionData, metricName) {
  if (versionData.design_metrics?.[metricName] != null) {
    return versionData.design_metrics[metricName];
  }
  // fallback to existing frontend logic
  return frontendEstimate(versionData, metricName);
}
```

## 不做范围

以下内容不在本次计划范围内：

- 高保真 CFD 计算
- 结构分析
- 真实任务剖面优化
- 多用户协作
