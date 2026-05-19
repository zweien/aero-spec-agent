# Deep Design 合并总结

## 1. 功能概述

Deep Design（深度设计）是一个 AI 驱动的飞机概念设计探索功能。用户在生成初始设计方案后，可以通过深度设计面板让 AI 自动探索多个设计变体，比较方案差异，并获得推荐方案。

## 2. 本分支新增能力

- **AI 设计探索：** 基于 LangGraph 的多变体自动生成与比较
- **推荐方案：** AI 自动分析并推荐最优方案，附推荐理由
- **可视化时间线：** 中文标签的设计流程进度追踪
- **方案卡片：** 展示气动参数（翼展、航程、升阻比、展弦比、翼载）
- **Markdown 报告：** 完整的设计探索报告，支持导出
- **工作流闭环：** Chat → 深度设计 → 推荐方案 → 设为当前方案 → 参数编辑

## 3. 用户可见变化

- 右侧面板新增"深度设计"标签（原"运行监控"标签已移除）
- 深度设计面板包含：描述输入、优化策略（4选）、探索深度（3级）、高级选项
- 运行时显示中文时间线和状态栏
- 完成后显示推荐方案卡片（含 AI 推荐 badge）和变体详情卡片
- "设为当前方案"自动切换回参数编辑面板
- 报告使用 Markdown 渲染，可导出 .md 文件

## 4. 后端 API 变化

- `POST /api/deep-design/stream` — SSE 流式端点，返回设计探索过程事件
- `VariantSubgraph` — 从异步 enqueue+wait 改为同步 `job_runner.generate()`，修复了 variant 状态卡在 "queued" 的 bug
- 无新增 REST API 端点

## 5. 前端组件变化

| 新增组件 | 说明 |
|---|---|
| `GraphTimeline.tsx` | 垂直时间线，中文阶段标签 |
| `VariantSummaryCard.tsx` | 方案卡片，显示气动参数 |
| `RecommendedVariantCard.tsx` | 推荐方案卡片，AI 推荐 badge + 发光边框 |
| `VariantThumbnail.tsx` | 飞机轮廓缩略图，状态覆盖层 |

| 修改组件 | 说明 |
|---|---|
| `DeepDesignPanel.tsx` | 完全重构：探索深度、策略复选框、Markdown 报告、运行细节折叠 |
| `useDeepDesignStream.ts` | 中文节点标签、versionNo 追踪 |
| `page.tsx` | 右侧面板两标签布局、传入 onLoadVersion/onSwitchToParameters |

## 6. 测试结果

| 测试 | 结果 |
|---|---|
| `npm run build` | PASS |
| 前端 graph 组件测试 (18) | PASS |
| 后端 pytest (411) | PASS (411 passed, 1 skipped) |
| 浏览器 QA (15 项) | PASS |
| 运行时稳定性测试 (9) | PASS |

## 7. 已知限制

- **FakeCadBackend 为主要测试后端。** OpenVSP 真实生成仍需单独验证（需要 OpenVSP 3.50.2 环境）
- **Deep Design 结果仅用于概念设计探索，不作为工程设计依据**
- **Variant 比较功能为占位状态**，"加入 Compare View" 按钮未实现
- **推荐理由解析依赖报告格式**，如果 LLM 生成的报告格式变化，推荐理由可能回退到默认文本
- **探索深度映射为固定值**（2/3/5），未来可能需要根据 spec 复杂度动态调整
- **SSE 流不支持断线重连**，刷新页面后需要重新运行
- **VariantThumbnail 为静态 SVG 占位图**，未来可替换为真实 3D 缩略图

## 8. 合并风险

- **低风险：** 后端 API 无破坏性变更，新增的 SSE 端点为独立功能
- **低风险：** 前端组件完全增量添加，ParameterPanel/CadViewer 等现有组件未修改
- **中风险：** `variant_subgraph.py` 从异步改为同步执行。已通过 411 项后端测试 + 9 项运行时稳定性测试验证，无 deadlock
- **低风险：** CSS 全局样式变更（workspace 布局从 column 改为 row），已在浏览器 QA 中验证

## 9. 回滚方式

如果合并后发现问题：

1. `git revert` 合并提交即可完整回滚
2. 深度设计功能为独立模块，回滚不影响 Chat / ParameterPanel / CadViewer 等核心功能
3. 后端 SSE 端点为独立路由，移除后不影响其他 API
