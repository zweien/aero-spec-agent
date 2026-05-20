# Compare View MVP 设计文档

## 目标

Deep Design 生成多个方案后，用户需要一个直观的"设计决策视图"来比较指标、风险和模型差异。

## 入口

在以下位置增加"加入对比"按钮：

1. **VersionPanel** — 每个版本的 pill 旁
2. **VariantSummaryCard** — Deep Design 的每个变体
3. **RecommendedVariantCard** — 推荐方案

## MVP 组件

### CompareDrawer

- 从右侧或底部抽屉弹出
- 支持 2–5 个方案同时比较
- 关闭按钮清空对比列表

### CompareTable

- 横向对比表格：每列一个方案
- 行按指标分组（翼面、重量、性能、风险）
- 最佳值高亮（绿色加粗）
- 风险项高亮（红色）

### CompareMetricCell

- 单个指标值 + 单位
- 支持最佳/最差标记
- 缺失指标显示"暂无"

### CompareItemCard（可选）

- 每个方案的缩略卡片
- 缩略图 + 名称 + 来源标签
- "移除" 和 "设为当前方案" 按钮

## 指标

| 指标 | 来源 | 最佳值规则 |
|------|------|-----------|
| 翼展 (m) | spec.wing.span | 按任务需求 |
| 机身长度 (m) | spec.fuselage.length | — |
| 翼面积 (m²) | performance_estimate | — |
| 展弦比 | performance_estimate | 长航时越大越好 |
| 估算升阻比 | performance_estimate | 越大越好 |
| 估算航程 (km) | performance_estimate | 越大越好 |
| 估算续航 (h) | performance_estimate | 越大越好 |
| 翼载荷 (kg/m²) | performance_estimate | 过高标风险 |
| 风险等级 | design_rules | low 最优 |

## 数据来源

- `aircraft_spec.yaml` → 基础参数
- `validation_report.json` → design_rules + performance_estimate
- `defaulted_fields` → 参数来源可信度
- future `design_metrics.json` → 更丰富的指标

## 操作

| 操作 | 说明 |
|------|------|
| 查看模型 | 在 CAD Viewer 中加载该方案的 GLB |
| 设为当前方案 | loadVersion 替换主视图 |
| 移除对比 | 从 CompareDrawer 中移除 |
| 导出对比报告 | 生成 Markdown 对比表格 |

## 不做范围（MVP 阶段）

- 不做复杂图表（雷达图、折线图）
- 不做 3D 同屏联动对比
- 不做高保真 CFD 对比
- 不做多用户协作
- 不做参数修改 + 重新对比循环

## 数据模型（前端）

```typescript
type CompareItem = {
  designId: string;
  versionNo: number;
  name?: string;
  source: "version" | "deep-design-variant";
  spec: Record<string, unknown>;
  metrics?: DesignMetrics;
  artifacts?: string[];
};

type DesignMetrics = {
  wingspan_m?: number;
  range_km?: number;
  endurance_h?: number;
  lift_to_drag?: number;
  aspect_ratio?: number;
  wing_loading?: number;
  risk_level?: "low" | "medium" | "high";
};
```

## 实现优先级

1. CompareDrawer + CompareTable 基础框架
2. 从 VariantSummaryCard / VersionPanel 加入对比
3. 指标数据填充（从 validation_report 提取）
4. 最佳值高亮
5. 设为当前方案
