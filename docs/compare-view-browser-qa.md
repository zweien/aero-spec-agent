# Compare View 浏览器 QA

## 测试环境

```bash
# Terminal 1 — Backend
set -a && . .env && set +a
CAD_BACKEND=fake CHAT_GENERATION_MODE=async FAKE_CAD_STEP_DELAY_MS=300 \
  .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"

# Terminal 2 — Frontend
cd apps/web && npm run dev
```

浏览器访问 http://localhost:3900

## 测试流程

### 1. 生成基础设计

输入："设计一架翼展12米、双发、上单翼的固定翼无人机"

等待生成完成 → 出现 v1

### 2. 加入 v1 到对比

在底部 VersionPanel 中，v1 pill 旁边点击"加入对比"

检查：
- 按钮变为"已加入"（绿色边框）
- 顶部出现"方案对比 (1)"按钮

### 3. 修改并生成 v2

输入："把翼展改为15米，并优化为长航时布局"

等待 v2 生成完成

### 4. 加入 v2 到对比

在 VersionPanel 中点击 v2 旁边的"加入对比"

检查：
- 顶部变为"方案对比 (2)"

### 5. Deep Design 生成方案

切换到"深度设计"标签
选择"快速探索 (2)"
点击"开始探索"

等待 v3/v4 生成完成

### 6. 加入 Deep Design 方案到对比

在 VariantSummaryCard 中点击"加入对比"
在 RecommendedVariantCard 中点击"加入对比"

检查：
- 顶部变为"方案对比 (4)"

### 7. 打开 CompareDrawer

点击顶部"方案对比 (4)"按钮

检查：
- 右侧抽屉打开
- 显示 4 个方案卡片
- 如果有默认补全 >= 3 项的方案，显示可信度提示

### 8. 检查 CompareTable

检查：
- 指标表格正常显示
- 基础尺寸组：翼展、机身长度、翼面积、展弦比
- 性能估算组：升阻比、航程、续航、翼载荷
- 可信度与风险组：风险等级、默认补全参数、缺失指标
- 缺失值显示"暂无"
- 最佳值有绿色 ★ 标记
- 默认补全数量显示正常

### 9. 操作按钮

- [ ] "查看模型" → CAD Viewer 加载对应版本
- [ ] "设为当前" → 版本切换，参数面板更新
- [ ] "移除" → 方案从对比中移除
- [ ] "清空对比" → 所有方案清除

### 10. 关闭与不影响

- 关闭 CompareDrawer → 不影响 ChatPanel / CADViewer / DeepDesignPanel
- 重新打开 → 保留之前的对比列表

## 截图清单

| 截图 | 说明 |
|------|------|
| docs/qa-screenshots/compare-view-drawer.png | CompareDrawer 打开状态 |
| docs/qa-screenshots/compare-view-table.png | 指标对比表格 |
| docs/qa-screenshots/compare-view-defaulted-fields.png | 默认补全提示 |
| docs/qa-screenshots/compare-view-version-add.png | VersionPanel 加入对比按钮 |
| docs/qa-screenshots/compare-view-variant-add.png | VariantSummaryCard 加入对比按钮 |

## 验收标准

- [x] CompareDrawer 可打开/关闭
- [x] VersionPanel 版本可加入对比
- [x] Deep Design variants 可加入对比
- [x] RecommendedVariantCard 可加入对比
- [x] CompareTable 显示 2–5 个方案
- [x] 指标缺失显示"暂无"
- [x] 最佳值高亮正常
- [x] defaulted_fields_count 显示正常
- [x] defaulted_fields 多的方案有可信度提示
- [x] 查看模型可用
- [x] 设为当前方案可用
- [x] 移除/清空对比可用
- [x] ChatPanel / CADViewer / DeepDesignPanel 无回归
- [x] 新增测试通过
- [x] npm run build 通过
