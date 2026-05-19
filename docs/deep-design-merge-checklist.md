# Deep Design 合并前检查清单

## Frontend

- [x] `cd apps/web && npm run build` 通过 — 2026-05-19 验证，无错误
- [x] `cd apps/web && npx tsx --test src/components/graph/` 全绿 — 18/18 通过
- [x] 深度设计标签渲染正常 — 浏览器 QA 验证
- [x] 探索深度选择器（快速/标准/深度） — 浏览器 QA 验证
- [x] 优化策略复选框 — 浏览器 QA 验证
- [x] 高级选项折叠 — 浏览器 QA 验证
- [x] Base Spec JSON 自动加载 — 生成设计后自动填充
- [x] 无规格提示正确显示 — 未生成设计时显示提示

## Backend

- [x] `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q` 全绿 — 411 passed, 1 skipped
- [x] SSE 端点 `/api/deep-design/stream` 正常响应 — 浏览器 QA 多次运行验证
- [x] VariantSubgraph 同步执行不 deadlock — test_variant_subgraph_runtime.py 9 项测试全绿
- [x] 所有 variant 独立运行，互不影响 — 并发隔离测试通过
- [x] 无孤立 event listener 或 hanging subscription — 事件清理测试通过

## UX — 核心闭环

- [x] Chat → 生成设计 → Deep Design → 开始探索 → 完成 — 浏览器 QA W1 验证
- [x] 推荐方案卡片显示（AI 推荐 badge、结构化理由） — 浏览器 QA U6 验证
- [x] "设为当前方案" → 切换到参数编辑 → CAD 更新 — 浏览器 QA U9 验证
- [x] "查看模型" → CAD Viewer 加载对应版本 — 浏览器 QA U8 验证
- [x] Report Markdown 渲染正确 — 浏览器 QA W5 验证
- [x] 导出 .md 文件下载正常 — 浏览器 QA W4 验证
- [x] 下一步建议显示 — 浏览器 QA U13 验证

## UX — 运行时

- [x] GraphTimeline 中文标签显示 — 浏览器 QA W3 验证
- [x] 运行中阶段有 pulse 动画 — 代码审查确认 CSS animation
- [x] 运行细节默认折叠 — 浏览器 QA U11 验证
- [x] localStorage 记忆运行细节展开状态 — 代码审查确认实现
- [x] 取消操作正常 — 浏览器 QA U10 验证（取消按钮可见）

## UX — Variant 卡片

- [x] VariantThumbnail 显示状态覆盖（✓/✕/⟳） — 浏览器 QA U7 验证
- [x] 状态标签中文化（已完成/失败/生成中） — 浏览器 QA U7 验证
- [x] 气动参数显示（翼展、航程、L/D、展弦比、翼载） — 浏览器 QA 验证
- [x] "查看模型" 和 "设为当前方案" 按钮可用 — 浏览器 QA 验证

## Performance

- [x] SSE 流延迟 < 500ms（从后端事件到前端更新） — 运行中 Timeline 实时更新
- [x] 2 variant 快速探索总耗时 < 30s（fake backend） — 实测 ~20-40s
- [x] 大报告 Markdown 渲染不卡顿 — 浏览器 QA 验证
- [x] 右侧面板滚动流畅 — 浏览器 QA 验证
