# Compare View MVP 实现总结

## 功能概述

Compare View MVP 提供了多方案对比能力，核心交互为 CompareDrawer 右侧抽屉，内含 CompareTable 三组 11 行指标表。入口按钮 AddToCompareButton 分布在 VersionPanel、VariantSummaryCard、RecommendedVariantCard 中，用户可将多个设计方案加入对比，通过表格直观查看关键指标差异。

## 数据流

```
VersionPanel / DeepDesign
  -> handleAddToCompare
  -> fetch version data
  -> extractCompareMetrics
  -> useCompareItems state
  -> CompareDrawer renders CompareTable
```

1. 用户在 VersionPanel 或 Deep Design 中点击 AddToCompareButton
2. handleAddToCompare 触发，拉取对应版本的完整数据
3. extractCompareMetrics 从 spec / validation_report 中提取指标
4. useCompareItems hook 管理对比列表状态
5. CompareDrawer 渲染 CompareTable，展示所有已加入方案的指标

## 组件结构

| 组件 | 说明 |
|------|------|
| **CompareDrawer** | 右侧固定抽屉，z-index 1000 |
| **CompareItemCard** | 方案卡片，显示来源标签、默认补全数量、风险等级、操作按钮 |
| **CompareTable** | 指标分组表格，3 组 11 行 |
| **CompareMetricCell** | 单元格，最佳值以星号高亮 |
| **AddToCompareButton** | 复用按钮，支持"已加入"和"对比已满"两种禁用状态 |
| **useCompareItems** | Hook，提供 add / remove / clear / isIn 方法，上限 5 个方案 |
| **metricExtractors** | 从 spec / validation_report 提取指标的工具函数集 |
| **bestValue** | 最佳值高亮规则判定函数 |

## 指标提取逻辑

| 指标 | 提取来源 | Fallback |
|------|----------|----------|
| `wingspan_m` | `spec.wing.span.value` 或 `spec.wingspan` | — |
| `fuselage_length_m` | `spec.fuselage.length.value` | — |
| `wing_area_m2` | 优先 `performance_estimate` | 梯形翼估算 |
| `aspect_ratio` | 优先 `estimate` | `span² / area` |
| `estimated_lift_to_drag` | 优先 `estimate` | `clamp(8 + AR * 0.7, 8, 22)` |
| `risk_level` | 基于 `defaulted_fields_count`、`missing_metrics_count`、`aspect_ratio` | — |

**风险等级判定：**
- 低 / 中 / 高 / 未知
- 综合考虑 defaulted_fields_count、missing_metrics_count、aspect_ratio 等因素

## 最佳值高亮规则

| 类别 | 指标 | 规则 |
|------|------|------|
| 越大越好 | `lift_to_drag`, `range_km`, `endurance_h`, `aspect_ratio` | 最大值高亮 |
| 越低越好 | `defaulted_fields_count`, `missing_metrics_count` | 最小值高亮 |
| 不高亮 | `wingspan`, `fuselage_length`, `wing_area`, `wing_loading` | — |
| 排序 | `risk_level` | `low < medium < high < unknown` |

## 默认补全可信度提示

- CompareDrawer 顶部黄色提示条，提醒用户部分字段为默认补全
- CompareItemCard 中显示具体补全数量
- 补全项 >= 3 时显示"默认补全较多"警告
- 补全项 >= 5 时以黄色风险标签突出显示

## 已知限制

1. 指标多为前端概念估算，非工程精度
2. 航程（range_km）/ 续航（endurance_h）可能缺失
3. 尚未接入后端 DesignMetrics 服务
4. 尚未接入 VSPAERO 分析
5. 暂不支持对比报告导出
6. 暂不支持 3D 同屏对比
7. 最多支持 5 个方案同时对比

## 后续计划

- **DesignMetrics 后端服务**：将指标计算迁移至后端统一处理
- **对比报告导出**：支持将对比结果导出为 PDF / Markdown
- **雷达图**：可视化多维指标对比
- **3D 同屏对比**：并排显示多个方案的 CAD 模型
