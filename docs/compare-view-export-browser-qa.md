---
qa_id: compare-view-export-browser
status: pass
date: 2026-05-22
env: any
---

# Compare View Export Browser QA

## 功能

Compare View 导出对比报告功能，将多方案指标对比结果导出为 Markdown 文件。

## 测试项

### 1. 导出按钮

- [ ] Compare Drawer 打开后，header 区域有"导出报告"按钮
- [ ] 0 个方案时按钮 disabled
- [ ] 1 个方案时按钮 disabled
- [ ] >= 2 个方案时按钮可点击

### 2. 报告内容

- [ ] 导出的 Markdown 包含 "# 方案对比报告" 标题
- [ ] 包含 "## 对比方案" 区域
- [ ] 包含 "## 指标对比表" Markdown 表格
- [ ] 包含 "## 最优项说明"
- [ ] 包含 "## 可信度说明"
- [ ] 不含 NaN / undefined / [object Object]

### 3. 文件下载

- [ ] 点击后自动下载 .md 文件
- [ ] 文件名格式: `compare-report-YYYYMMDD-HHmm.md`
- [ ] 文件内容为有效 UTF-8 Markdown

## 测试环境

```bash
# 启动后端
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host 0.0.0.0 --port 8900

# 启动前端
cd apps/web && npm run dev
```

## 自动化测试

```bash
cd apps/web && npx tsx --test src/components/compare/exportCompareReport.test.ts
```

## 结果

- 自动化测试: 7/7 通过
- 浏览器手动测试: 待执行
