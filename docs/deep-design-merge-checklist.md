# Deep Design 合并前检查清单

## Frontend

- [ ] `cd apps/web && npm run build` 通过
- [ ] `cd apps/web && npx tsx --test src/components/graph/` 全绿
- [ ] 深度设计标签渲染正常
- [ ] 探索深度选择器（快速/标准/深度）
- [ ] 优化策略复选框
- [ ] 高级选项折叠
- [ ] Base Spec JSON 自动加载
- [ ] 无规格提示正确显示

## Backend

- [ ] `CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q` 全绿
- [ ] SSE 端点 `/api/deep-design/stream` 正常响应
- [ ] VariantSubgraph 同步执行不 deadlock
- [ ] 所有 variant 独立运行，互不影响
- [ ] 无孤立 event listener 或 hanging subscription

## UX — 核心闭环

- [ ] Chat → 生成设计 → Deep Design → 开始探索 → 完成
- [ ] 推荐方案卡片显示（AI 推荐 badge、结构化理由）
- [ ] "设为当前方案" → 切换到参数编辑 → CAD 更新
- [ ] "查看模型" → CAD Viewer 加载对应版本
- [ ] Report Markdown 渲染正确
- [ ] 导出 .md 文件下载正常
- [ ] 下一步建议显示

## UX — 运行时

- [ ] GraphTimeline 中文标签显示
- [ ] 运行中阶段有 pulse 动画
- [ ] 运行细节默认折叠
- [ ] localStorage 记忆运行细节展开状态
- [ ] 取消操作正常

## UX — Variant 卡片

- [ ] VariantThumbnail 显示状态覆盖（✓/✕/⟳）
- [ ] 状态标签中文化（已完成/失败/生成中）
- [ ] 气动参数显示（翼展、航程、L/D、展弦比、翼载）
- [ ] "查看模型" 和 "设为当前方案" 按钮可用

## Performance

- [ ] SSE 流延迟 < 500ms（从后端事件到前端更新）
- [ ] 2 variant 快速探索总耗时 < 30s（fake backend）
- [ ] 大报告 Markdown 渲染不卡顿
- [ ] 右侧面板滚动流畅
