# DesignMetrics 指标来源与可信度 QA

## 概述

Compare View 新增指标来源追踪（`CompareMetricSource`）、置信度分级（`MetricConfidence`）、警告提示（`warnings`）。前端 `metricExtractors.ts` 按优先级从三个层级提取指标：后端估算 > 性能估算 > 客户端临时计算。

## 类型定义

`apps/web/src/components/compare/types.ts`

```typescript
export type CompareMetricSource =
  | "backend_design_metrics"   // 后端 design_metrics
  | "performance_estimate"     // 后端 performance_estimate
  | "client_heuristic"         // 客户端临时计算
  | "missing";                 // 无数据

export type MetricConfidence = "high" | "medium" | "low";
```

`CompareMetrics` 新增字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| `metric_sources` | `Record<string, CompareMetricSource>` | 每个指标的数据来源 |
| `confidence` | `MetricConfidence` | 整体置信度 |
| `warnings` | `string[]` | 警告信息列表 |
| `defaulted_fields_count` | `number` | 系统默认补全参数数量 |
| `missing_metrics_count` | `number` | 缺失指标数量 |

## 指标来源优先级

`metricExtractors.ts` 中 `sourceFor()` 函数定义了优先级：

1. **backend_design_metrics**（后端估算） — 来自 `validationReport.design_metrics`，由 `compute_design_metrics()` 计算
2. **performance_estimate**（性能估算） — 来自 `validationReport.performance_estimate.estimates`
3. **client_heuristic**（临时估算） — 前端根据 spec 参数临时计算（梯形翼面积、Raymer 经验升阻比等）
4. **missing**（暂无） — 无任何数据来源

## 置信度计算规则

| 等级 | 条件 | 前端显示 |
|------|------|----------|
| `high` | backend 来源 >= 5 且 missing <= 1 | 正常 |
| `medium` | backend 来源 >= 3 或 missing <= 3 | 正常 |
| `low` | 其余情况 | 浅黄色背景 |

## 警告规则

| 条件 | 警告文案 |
|------|----------|
| missing_metrics_count > 0 | `"N 项核心指标缺失"` |
| defaulted_fields_count >= 3 | `"N 项参数由系统默认补全"` |
| confidence === "low" | `"整体置信度较低，建议谨慎参考"` |

## CompareMetricCell 显示规则

| 条件 | 显示 |
|------|------|
| `source === "missing"` 或 value 为 null | 斜体灰色"暂无" |
| `isBest === true` | 绿色背景 + ★ 标记 |
| `confidence === "low"` 或 `isRisk === true` | 浅黄色背景 |
| 正常 | 默认样式 |

`title` 属性显示来源标签（后端估算/性能估算/临时估算/暂无）。

## CompareDrawer 顶部说明

Drawer 顶部固定显示蓝色提示条：

> 当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。

若任一方案 defaultedFields >= 3，额外显示黄色警告条：

> 部分方案包含较多系统默认补全参数，默认补全越多说明由系统假设的内容越多。建议在进入工程分析前进一步确认参数。

## 测试结果 (2026-05-22)

### metricSources.test.ts — 8 passed

```bash
cd apps/web && npx tsx --test src/components/compare/metricSources.test.ts
```

| 测试用例 | 状态 | 说明 |
|----------|------|------|
| `marks backend_design_metrics when value comes from design_metrics` | PASS | 翼展/翼面积/展弦比标记为后端来源 |
| `marks performance_estimate when value comes from perf estimates` | PASS | 升阻比/航程标记为性能估算 |
| `marks client_heuristic when computed client-side` | PASS | 翼展/翼面积/展弦比/升阻比标记为临时估算 |
| `marks missing when no value available` | PASS | 航程/续航/翼载荷标记为缺失 |
| `sets confidence to high when most metrics from backend` | PASS | 8 项后端指标 → confidence = "high" |
| `sets confidence to low when most metrics missing` | PASS | 无指标 → confidence = "low" |
| `populates warnings for missing metrics` | PASS | 警告包含"核心指标缺失" |
| `SOURCE_LABELS has entries for all source types` | PASS | 4 种来源均有中文标签 |

### CompareMetricCell.test.tsx — 3 passed

```bash
cd apps/web && npx tsx --test src/components/compare/CompareMetricCell.test.tsx
```

| 测试用例 | 状态 | 说明 |
|----------|------|------|
| `missing source should display as 暂无` | PASS | missing 来源显示"暂无" |
| `confidence low maps to warning style` | PASS | low 置信度对应警告样式 |
| `source labels are correctly mapped` | PASS | SOURCE_LABELS 4 项中文标签正确 |

### DesignMetricsCard.test.tsx — 4 passed

```bash
cd apps/web && npx tsx --test src/components/metrics/DesignMetricsCard.test.tsx
```

| 测试用例 | 状态 | 说明 |
|----------|------|------|
| `formats integer values` | PASS | 整数值不带小数 |
| `formats decimal values` | PASS | 浮点值保留 2 位 |
| `maps risk levels to labels` | PASS | low→低, medium→中, high→高, unknown→未知 |
| `maps confidence levels to labels` | PASS | high→高, medium→中, low→低 |

## 后端 design_metrics 服务

`services/api/app/services/design_metrics.py` — `compute_design_metrics()` 从 AircraftSpec dict 计算以下指标：

| 指标 | 计算方式 |
|------|----------|
| wingspan_m | spec.wing.span |
| fuselage_length_m | spec.fuselage.length |
| wing_area_m2 | span * (root_chord + tip_chord) / 2 |
| aspect_ratio | span^2 / wing_area |
| estimated_lift_to_drag | Raymer 经验公式: clamp(8 + AR * 0.7, 8, 22) |
| wing_loading_kg_m2 | MTOW / wing_area |
| thrust_to_weight | total_thrust / (MTOW * g) |
| risk_level | 基于 missing_core / defaulted_count / AR |
| confidence | heuristic / partial / low |

## 相关文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/components/compare/types.ts` | `CompareMetricSource` / `MetricConfidence` 类型定义 |
| `apps/web/src/components/compare/metricExtractors.ts` | `extractCompareMetrics()` + `SOURCE_LABELS` |
| `apps/web/src/components/compare/CompareMetricCell.tsx` | 指标单元格组件 |
| `apps/web/src/components/compare/CompareDrawer.tsx` | Drawer 顶部说明 + 默认补全警告 |
| `apps/web/src/components/metrics/DesignMetricsCard.tsx` | 指标卡片组件 |
| `apps/web/src/components/compare/metricSources.test.ts` | 8 条指标来源测试 |
| `apps/web/src/components/compare/CompareMetricCell.test.tsx` | 3 条单元格测试 |
| `apps/web/src/components/metrics/DesignMetricsCard.test.tsx` | 4 条卡片测试 |
| `services/api/app/services/design_metrics.py` | 后端指标计算服务 |

## 自动化测试

```bash
# 前端指标来源测试
cd apps/web && npx tsx --test src/components/compare/metricSources.test.ts

# 前端单元格测试
cd apps/web && npx tsx --test src/components/compare/CompareMetricCell.test.tsx

# 前端指标卡片测试
cd apps/web && npx tsx --test src/components/metrics/DesignMetricsCard.test.tsx

# 后端 design_metrics 测试
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_design_metrics.py -q

# 前端生产构建
cd apps/web && npm run build
```
