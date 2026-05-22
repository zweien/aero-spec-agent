# Compare View Markdown 对比报告导出 QA

## 概述

`exportCompareReport.ts` 从 Compare View 的方案数据生成 Markdown 格式的对比报告。用户点击 CompareDrawer 中的"导出对比报告"按钮，浏览器下载 `.md` 文件。

## 实现位置

| 文件 | 说明 |
|------|------|
| `apps/web/src/components/compare/exportCompareReport.ts` | 报告生成逻辑 |
| `apps/web/src/components/compare/exportCompareReport.test.ts` | 8 条测试 |
| `apps/web/src/components/compare/CompareDrawer.tsx` | "导出对比报告"按钮 |

## 报告结构

生成的 Markdown 文档包含以下章节：

```
# 方案对比报告

## 对比方案
- **v1** (版本 1)
- **v2** (版本 2)

## 指标对比表
| 指标 | v1 | v2 |
| --- | --- | --- |
| 翼展 | 12 m | 15 m |
| 机身长度 | 8 m | 8 m |
| ... | ... | ... |

## 最优项说明
指标表中 ★ 标记的数值为该指标在所有方案中的最优值。
- 翼展、翼面积、展弦比、升阻比、航程、续航：越大越优
- 翼载荷：越小越优
- 风险等级：low > medium > high

## 可信度说明
**当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。**

- **v1**: 后端估算 5 项，性能估算 2 项，暂无 1 项
- **v2**: 后端估算 7 项

### 注意事项
- 3 项核心指标缺失
- 整体置信度较低，建议谨慎参考
```

## 指标表内容

| 指标 | 单位 | 说明 |
|------|------|------|
| 翼展 | m | wingspan_m |
| 机身长度 | m | fuselage_length_m |
| 翼面积 | m² | wing_area_m2 |
| 展弦比 | - | aspect_ratio |
| 估算升阻比 | - | estimated_lift_to_drag |
| 估算航程 | km | estimated_range_km |
| 估算续航 | h | estimated_endurance_h |
| 翼载荷 | kg/m² | wing_loading_kg_m2 |
| 风险等级 | - | risk_level |

## 导出逻辑

```typescript
export function exportCompareReport(items: CompareItem[]): string
```

- 参数：`CompareItem[]`（至少 2 项）
- 返回值：Markdown 字符串。少于 2 项时返回空字符串。
- 文件名格式：`compare-report-YYYYMMDD-HHmm.md`

## CompareDrawer 按钮

CompareDrawer header 区域包含"导出对比报告"按钮：

- 方案数 >= 2：按钮可用，点击触发下载
- 方案数 < 2：按钮 disabled（灰色，`cursor: not-allowed`）

```typescript
<button onClick={handleExport} disabled={!hasMinItems}>
  导出对比报告
</button>
```

## 缺失值处理

| 场景 | 处理 |
|------|------|
| 值为 `null` / `undefined` | 显示 `-` |
| 整数值 | 不带小数 |
| 浮点数值 | 保留 2 位小数 |
| 报告中 NaN / undefined | 不出现（已测试） |

## 可信度章节

报告为每个方案生成来源统计：

```typescript
// 从 metric_sources 中统计各来源数量
const sourceCounts: Record<string, number> = {};
for (const src of Object.values(sources)) {
  const label = SOURCE_LABELS[src];
  sourceCounts[label] = (sourceCounts[label] || 0) + 1;
}
```

输出格式：`- **v1**: 后端估算 5 项，性能估算 2 项`

## 测试结果 (2026-05-22)

```bash
cd apps/web && npx tsx --test src/components/compare/exportCompareReport.test.ts
```

| 测试用例 | 状态 | 说明 |
|----------|------|------|
| `returns empty string for fewer than 2 items` | PASS | 空数组或 1 项返回空字符串 |
| `generates report for 2+ items` | PASS | 2 项以上生成完整报告，包含所有章节标题 |
| `includes metric values in the table` | PASS | 指标值（12/15 等）出现在表格中 |
| `does not contain NaN or undefined` | PASS | 无数据方案不产生 NaN/undefined/[object Object] |
| `uses - for missing values` | PASS | 翼展行包含 `-`（缺失值占位符） |
| `getExportFilename returns expected format` | PASS | 文件名以 `compare-report-` 开头，`.md` 结尾 |
| `includes source breakdown in confidence section` | PASS | 可信度章节包含来源统计（"后端估算"） |
| `handles items with warnings` | PASS | 有警告时报告正常完成 |

**8 passed**

## 验收标准

| 验收项 | 状态 |
|--------|------|
| >= 2 方案可导出 | PASS |
| 0/1 方案按钮 disabled | PASS |
| Markdown 包含指标对比表 | PASS |
| Markdown 包含可信度说明 | PASS |
| 不出现 NaN / undefined / [object Object] | PASS |
| 缺失值显示为 `-` | PASS |
| 文件名格式正确 | PASS |

## 相关文件

| 文件 | 说明 |
|------|------|
| `apps/web/src/components/compare/exportCompareReport.ts` | 报告生成 |
| `apps/web/src/components/compare/exportCompareReport.test.ts` | 8 条测试 |
| `apps/web/src/components/compare/CompareDrawer.tsx` | "导出对比报告"按钮 |
| `apps/web/src/components/compare/metricExtractors.ts` | `extractCompareMetrics()` / `SOURCE_LABELS` |
| `apps/web/src/components/compare/types.ts` | `CompareItem` / `CompareMetrics` 类型 |

## 自动化测试

```bash
# 导出报告测试
cd apps/web && npx tsx --test src/components/compare/exportCompareReport.test.ts

# 指标来源测试
cd apps/web && npx tsx --test src/components/compare/metricSources.test.ts

# 前端生产构建
cd apps/web && npm run build
```
