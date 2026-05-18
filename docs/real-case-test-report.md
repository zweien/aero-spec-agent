# AeroSpec Agent 真实案例测试报告

> 版本: v1.0 | 日期: 2026-05-19 | HEAD: ae79107+
> 后端: FakeCadBackend | 测试框架: pytest

---

## 执行环境

| 项目 | 值 |
|------|-----|
| CAD_BACKEND | fake |
| 测试文件 | tests/api/test_real_cases.py |
| Graph 模式 | DeepDesignGraph (enable_refinement=false) |
| 后端框架 | FastAPI + TestClient |

---

## 案例一：长航时侦察无人机

### 输入

- **design_id:** `recon-uav-endurance`
- **description:** 设计一款长航时侦察无人机，航程 500km，载荷 20kg，优先考虑续航时间
- **base_spec:** `packages/aircraft-schema/examples/twin_engine_uav.yaml`
- **constraints:** `{"variant_count": 3, "max_iterations": 1}`

### 执行结果

| 测试 | 状态 | 说明 |
|------|------|------|
| 3 variants complete | PASS | `comparison.total_variants == 3`，status=completed |
| Requirements parsed | PASS | description 中 500km 被解析，出现在 report 中 |
| Stream has graph_nodes | PASS | SSE 包含 parse_requirements, run_compare, synthesize_report 事件 |

### Graph Flow 验证

| 节点 | 状态 | 说明 |
|------|------|------|
| parse_requirements | completed | 提取 range_km=500, payload_kg=20, variant_count=3 |
| prepare_variants | completed | 生成 3 变体: compact(span-2), standard, extended(span+2) |
| run_compare | completed | CompareGraph 调度 3 个 VariantSubgraph |
| synthesize_report | completed | 生成 markdown 报告，包含变体对比表 |

### Report 验证

- 报告包含 `| 变体 |` markdown 表头
- compact / standard / extended 标签均出现
- 需求描述中包含 `500km`

### SSE 事件序列（/api/deep-design/stream）

```
event: message       → Deep design exploration started
event: graph_node    → parse_requirements: started → completed
event: graph_node    → prepare_variants: started → completed
event: graph_node    → run_compare: started → completed
  (内部: generation_started / generation_progress / generation_complete × 3)
event: graph_node    → synthesize_report: started → completed
event: message       → final report + status=completed
```

---

## 案例二：小型物流无人机

### 输入

- **design_id:** `logistics-uav`
- **description:** 设计一架小型物流无人机，载荷 5kg，航程 50km
- **base_spec:** `packages/aircraft-schema/examples/twin_engine_uav.yaml`
- **constraints:** `{"variant_count": 1}`

### 执行结果

| 测试 | 状态 | 说明 |
|------|------|------|
| Single variant completes | PASS | `comparison.total_variants == 1`，status=completed |
| Report has description | PASS | `50km` 出现在 report 中 |
| Metrics updated | PASS | deep_design_runs 递增，total_variants 递增 |

### Metrics 变化

执行后 `/api/metrics` 返回值：

```
deep_design_runs_total: +1
variants_total: +1
variant_success_rate: updated
```

---

## 综合结论

| 维度 | 状态 | 备注 |
|------|------|------|
| Graph 执行正确性 | PASS | DeepDesign → Compare → VariantSubgraph 三级嵌套正常 |
| 多变体 (N=3) | PASS | 3 个变体全部完成 |
| 单变体 (N=1) | PASS | 最小变体数正常工作 |
| SSE 流式事件 | PASS | graph_node / generation_* / message 事件齐全 |
| Metrics 计数器 | PASS | deep_design_runs / variants_total 正确递增 |
| Requirements 解析 | PASS | km/kg 正则提取正确 |
| Report 内容 | PASS | markdown 表格 + 描述 + 推荐 |
| FakeCadBackend 输出 | PASS | 每个变体生成 version 目录及 artifacts |

**下一步：** 在 OpenVSP 环境下执行真实 CAD 生成案例。
