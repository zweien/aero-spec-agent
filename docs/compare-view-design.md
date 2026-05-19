# Compare View Design Document

> **DESIGN ONLY — NOT IMPLEMENTED**
>
> This document describes the planned "Compare View" feature. No code has been written for this feature yet.

---

## 1. Why

用户在完成 Deep Design 探索后，通常会生成多个设计变体（variants）。目前用户只能逐一查看变体详情，无法直观地对比不同变体之间的关键参数差异。Compare View 提供并排对比能力，帮助用户做出更明智的变体选择。

## 2. Entry Points

### 2.1 Variant Card Button

- 每个 Variant 卡片上增加"加入对比"（Add to Compare）按钮
- 当前该按钮为占位符（placeholder），实现时激活
- 点击后变体被添加到对比队列，按钮状态变为"已加入"（Added）
- 当对比队列中已有 2 个变体时，自动跳转到 Compare View

### 2.2 VersionPanel Multi-Select

- VersionPanel 中的变体列表支持多选模式
- 用户勾选 2 个变体后，出现"对比"（Compare）操作按钮
- 点击后进入 Compare View

## 3. Comparison Table Columns

| Column                  | Key           | Description                                  |
|-------------------------|---------------|----------------------------------------------|
| 翼展 (Span)             | `span`        | 翼展长度，单位 m                             |
| 航程 (Range)            | `range`       | 设计航程，单位 km                            |
| 升阻比 (L/D Ratio)      | `ld_ratio`    | 升阻比，无量纲                               |
| 展弦比 (Aspect Ratio)   | `aspect_ratio`| 展弦比，无量纲                               |
| 翼载 (Wing Loading)     | `wing_loading`| 翼载，单位 kg/m²                             |
| 设计检查 (Design Checks) | `checks`      | 设计规则通过/警告/失败数量 (pass/warn/fail)  |

## 4. Best Value Highlighting

对比表中自动高亮最优值：

- **升阻比 (L/D):** 最高值 → 绿色高亮
- **航程 (Range):** 最长航程 → 绿色高亮
- **翼载 (Wing Loading):** 最低翼载 → 绿色高亮
- **设计检查:** 通过数最多 → 绿色高亮

其他列（翼展、展弦比）不自动高亮，因为"最优"取决于具体任务需求。

## 5. CAD Thumbnail Comparison

- 在对比表上方展示两个变体的 CAD 缩略图并排排列
- 缩略图选项：
  - **Plan view SVG** — 俯视图轮廓，轻量且一致性好（MVP 优先方案）
  - **3D thumbnail** — Three.js 渲染的缩略图，视觉更丰富但实现复杂度更高
- 缩略图下方显示变体编号和探索策略标签

## 6. Relationship with Deep Design

- **时序关系：** Compare View 在 Deep Design 探索完成后才可使用
- **数据来源：** 对比数据直接来自 Deep Design 生成的变体数据（variant metrics + design checks）
- **导航关系：** Compare View 不替代 Deep Design 结果页，而是作为结果页的延伸视图
- **返回路径：** Compare View 提供明确的"返回 Deep Design 结果"按钮

## 7. Relationship with VersionPanel

- **视图切换：** 进入 Compare View 时，临时替代 VersionPanel 的版本详情视图
- **数据共享：** Compare View 和 VersionPanel 共享同一份变体数据，无需重复请求
- **状态同步：** 在 Compare View 中选择"设为当前变体"后，VersionPanel 的状态同步更新
- **退出 Compare View：** 关闭对比视图后，VersionPanel 恢复正常的版本详情展示

## 8. MVP Scope

MVP 仅包含以下内容：

- [x] 2-variant comparison table（两变体对比表）
- [x] Best value highlighting（最优值绿色高亮）
- [x] Basic layout: thumbnails on top, table below（缩略图在上，对比表在下）
- [x] "Set as current variant" action per variant（每个变体可设为当前）
- [x] Back navigation to Deep Design results（返回 Deep Design 结果页）

## 9. Out of Scope for MVP

以下功能不在 MVP 范围内，可作为后续迭代考虑：

- 3+ variant comparison（三变体及以上对比）
- Radar charts / spider charts（雷达图对比）
- Auto-generated comparison report（自动生成对比报告）
- Diff view highlighting parameter differences（差异高亮视图）
- Export comparison table as CSV/PDF（导出对比表）
- Persistent comparison sessions across page reloads（跨页面刷新的持久对比会话）

---

*Last updated: 2026-05-19*
