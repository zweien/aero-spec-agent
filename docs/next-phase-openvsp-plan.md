# Next Phase: OpenVSP + DesignMetrics + Compare Export

> 完整开发计划，可直接交给 coding agent 执行。
> 基线 HEAD: 5fa4959

## 当前状态

Fake CAD 后端下的完整智能设计闭环已经通过端到端 QA。

已完成：
- Chat 生成 v1
- 修改生成 v2
- Deep Design 快速探索 2 variants
- Deep Design 标准探索 3 variants
- VersionPanel 管理 v1-v7
- Compare View 5 项方案对比
- DesignMetrics 后端服务
- validation_report.design_metrics
- Compare View 读取后端 design_metrics
- no-tool-call fallback
- MiniMax-M2.5 兼容机制
- CADLoadingOverlay
- workflow_stage / artifact_generated
- Agent Run 透明过程
- docs/deep-design-compare-view-e2e-qa.md
- 523 backend tests pass
- 前端 build pass

## 本轮目标

从 fake backend 验证，推进到真实 OpenVSP 工程链路验证，增强设计指标可信度表达。

1. 完成 OpenVSP 环境自检
2. 验证 OpenVSP 单方案生成
3. 验证 OpenVSP 修改生成
4. 验证 OpenVSP Deep Design quick 2 variants
5. 验证 OpenVSP 失败场景
6. 前端显示 DesignMetrics 指标来源与可信度
7. 新增 DesignMetricsCard
8. 新增 Compare View Markdown 对比报告导出
9. 保持 Fake backend 全流程无回归

## 任务 1：OpenVSP 环境自检脚本

新增 `scripts/check_openvsp_env.py`

检查内容：
1. OpenVSP 可执行文件是否存在
2. OpenVSP 命令是否可调用
3. CAD_BACKEND=openvsp 是否能初始化
4. 输出目录是否可写
5. 能否生成最小 test aircraft
6. 能否保存 .vsp3
7. 能否导出 .glb
8. 能否导出 .step（如支持）
9. 失败时输出明确原因

新增文档 `docs/openvsp-env-check.md`：环境变量、运行方法、常见失败原因、回退 fake 方法。

## 任务 2：OpenVSP 单方案生成 QA

测试环境：`CAD_BACKEND=openvsp CHAT_GENERATION_MODE=async NO_TOOL_CALL_FALLBACK=true`

Prompt: `设计一架翼展12米、双发、上单翼、常规尾翼的固定翼长航时无人机`

验证：Agent Run 正常、workflow_stage 实时显示、vsp3/glb/step 生成、validation_report.design_metrics 存在且无 NaN、VersionPanel v1、CAD Viewer 加载 glb、Compare View 可加入。

截图：`openvsp-v1-agent-run.png`、`openvsp-v1-cad-viewer.png`、`openvsp-v1-version-panel.png`
文档：`docs/openvsp-single-generation-qa.md`

失败分类记录：初始化失败 / 几何生成失败 / vsp3 保存失败 / glb 导出失败 / step 导出失败 / validation_report 缺失 / CAD Viewer 加载失败 / VersionPanel 未更新。

## 任务 3：OpenVSP 修改生成 QA

前置：已有 OpenVSP v1。Prompt: `把翼展改为15米，并优化为长航时布局`

验证：modify_design 触发、生成 v2、不覆盖 v1、VersionPanel v1/v2、CAD Viewer v2、artifacts 正常、design_metrics 更新、Compare View v1/v2 指标差异。

截图：`openvsp-v2-modify.png`、`openvsp-v1-v2-compare.png`
文档：`docs/openvsp-modify-generation-qa.md`

## 任务 4：OpenVSP Deep Design quick 2 variants QA

前置：已有 v1/v2。操作：基于 v2 Deep Design、长航时优化、快速探索 2 variants。

验证：2 variants 进入 running、无并发冲突、独立版本/artifacts/report、VersionPanel v3/v4、RecommendedVariantCard、Compare View v1-v4。

截图：`openvsp-deep-design-quick.png`、`openvsp-compare-v1-v4.png`
文档：`docs/openvsp-deep-design-qa.md`

验收：至少 1 variant 成功。全部失败需定位 OpenVSP 并发/参数/导出/路径问题。

## 任务 5：OpenVSP 失败场景 QA

失败注入 `OPENVSP_FAIL_STAGE=exporting_glb` 或非法参数触发。

验证：workflow_stage failed、failed stage 显示、TaskRuntimeCard failed、WorkflowErrorCard、AgentRunDetails 错误、旧模型保留、不出现损坏版本、后端不崩溃。

新增测试：`tests/api/test_openvsp_failure_events.py`
文档：`docs/openvsp-failure-qa.md`

## 任务 6：DesignMetrics 指标来源与可信度

修改文件：
- `apps/web/src/components/compare/types.ts`
- `apps/web/src/components/compare/metricExtractors.ts`
- `apps/web/src/components/compare/CompareMetricCell.tsx`
- `apps/web/src/components/compare/CompareTable.tsx`

新增类型：
```typescript
type CompareMetricSource =
  | "backend_design_metrics"
  | "performance_estimate"
  | "client_heuristic"
  | "missing";
```

CompareMetrics 增加：`metric_sources`、`confidence`、`warnings`

显示规则：后端估算 / 性能估算 / 临时估算 / 暂无。confidence=low 显示浅黄色。warnings 显示 icon。

CompareDrawer 顶部增加说明："当前指标为概念设计阶段估算，用于方案初筛，不代表高保真气动或结构分析结果。"

新增测试：`metricSources.test.ts`、`CompareMetricCell.test.tsx`

## 任务 7：DesignMetricsCard

新增：`apps/web/src/components/metrics/DesignMetricsCard.tsx`

显示位置：AgentRunDetails completed 状态或 VersionPanel 选中版本详情区。

显示内容：翼展、机身长度、翼面积、展弦比、升阻比、航程、续航、翼载荷、推重比、风险等级、置信度、warnings。文案："概念设计估算，仅用于初步方案筛选。"

新增测试：`DesignMetricsCard.test.tsx`

## 任务 8：Compare View Markdown 对比报告导出

新增：`apps/web/src/components/compare/exportCompareReport.ts`

CompareDrawer header 新增"导出对比报告"按钮。文件名 `compare-report-YYYYMMDD-HHmm.md`。

报告结构：# 方案对比报告 → ## 对比方案 → ## 指标对比表(Markdown table) → ## 最优项说明 → ## 可信度说明

新增测试：`exportCompareReport.test.ts`

验收：≥2 方案可导出、0/1 方案按钮 disabled、Markdown 包含指标表和可信度说明、无 NaN/undefined。

## 任务 9：文档更新

新增/更新：
- `docs/openvsp-env-check.md`
- `docs/openvsp-single-generation-qa.md`
- `docs/openvsp-modify-generation-qa.md`
- `docs/openvsp-deep-design-qa.md`
- `docs/openvsp-failure-qa.md`
- `docs/design-metrics-mvp-qa.md`
- `docs/compare-view-export-report.md`

README 新增 "OpenVSP real backend verification" 小节。

## 任务 10：测试命令

```bash
# 后端 fake 全量
CAD_BACKEND=fake .venv/bin/python -m pytest tests/ -q

# OpenVSP 可用时
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 \
  .venv/bin/python -m pytest tests/api/test_openvsp_workflow_events.py -q

# OpenVSP 失败测试
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 \
  .venv/bin/python -m pytest tests/api/test_openvsp_failure_events.py -q

# 前端
cd apps/web && npm run build
npx tsx --test src/components/compare/
npx tsx --test src/components/metrics/
npx tsx --test src/components/chat/
```

## 本轮不做

高保真 CFD、VSPAERO 自动分析闭环、结构分析、多用户权限、数据库大重构、新 Agent 架构、Word/PPT 导出、复杂 3D 同屏对比、大规模优化算法、多模型调度系统。

## 验收标准

1. `scripts/check_openvsp_env.py` 完成
2. `docs/openvsp-env-check.md` 完成
3. OpenVSP 单方案 v1 QA 完成，或明确记录不可用原因
4. OpenVSP 修改生成 v2 QA 完成，或明确记录不可用原因
5. OpenVSP Deep Design quick 2 variants QA 完成，或明确记录不可用原因
6. OpenVSP 失败场景 QA 完成
7. validation_report.design_metrics 在 OpenVSP 后端下正常
8. Compare View 可读取 OpenVSP 生成版本的 design_metrics
9. CompareMetricCell 可显示指标来源或可信度提示
10. DesignMetricsCard 完成
11. Compare View Markdown 对比报告导出完成
12. 不出现 NaN / undefined / [object Object]
13. Fake backend 全量测试仍通过
14. OpenVSP 相关测试在环境可用时通过
15. 前端 build 通过
16. 新增前端测试通过
17. 文档与截图完整
