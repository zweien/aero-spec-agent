# OpenVSP 气动布局全面扩展设计

**日期**: 2026-05-24
**范围**: 固定翼 UAV 全系列气动布局建模
**基线**: master `71cc832`

## 目标

将当前仅支持 conventional 布局的 OpenVSP 几何建模扩展为覆盖固定翼 UAV 全系列布局，使设计人员能在概念设计阶段探索 V 尾、双尾撑、飞翼、翼身融合等多种气动构型。

## 实施路径

**路径 A：布局类型驱动，分批交付**，每批包含完整的后端→Schema→UI→测试链路。

## 1. Schema 与数据模型

### 1.1 字段扩展

**`aircraft.layout`** — 从 `Literal["conventional"]` 扩展为：
```python
Literal["conventional", "twin_boom", "flying_wing", "blended_wing_body"]
```

**`tail.type`** — 新增 3 种尾翼构型：
```
现有: "conventional", "t_tail"
新增: "v_tail", "inverted_v", "cruciform"
```

**`engine.count`** — 从 `(1, 2)` 扩展到 `(1, 2, 3, 4)`

**`engine.position`** — 新增：
- `"wing_tip"` — 翼尖安装
- `"over_wing"` — 上置
- `"pusher"` — 推进式（双尾撑布局专用）

### 1.2 新增字段

| 字段 | 类型 | 默认值 | 条件 |
|------|------|--------|------|
| `wing.sections` | IntegerScalar | 1 | 始终，1-3 |
| `wing.inner_sweep` | TextScalar → float | 0.0 | sections ≥ 2 |
| `wing.inner_dihedral` | TextScalar → float | 0.0 | sections ≥ 2 |
| `boom.length` | TextScalar → float | — | layout = twin_boom |
| `boom.span` | TextScalar → float | — | layout = twin_boom |
| `body.width` | TextScalar → float | — | layout = blended_wing_body |
| `body.height` | TextScalar → float | — | layout = blended_wing_body |

### 1.3 新增示例文件

- `packages/aircraft-schema/examples/v_tail_single_uav.yaml`
- `packages/aircraft-schema/examples/twin_boom_pusher_uav.yaml`
- `packages/aircraft-schema/examples/flying_wing_uav.yaml`
- `packages/aircraft-schema/examples/bwb_uav.yaml`

## 2. 几何构建器架构

### 2.1 布局分发层

`backend.py` 中新增 `LAYOUT_BUILDERS` 分发：

```python
LAYOUT_BUILDERS = {
    "conventional": _build_conventional,
    "twin_boom":    _build_twin_boom,
    "flying_wing":  _build_flying_wing,
    "blended_wing_body": _build_bwb,
}

builder = LAYOUT_BUILDERS.get(layout, _build_conventional)
build_results = builder(adapter, spec)
```

每个 builder 函数返回 `list[GeometryBuildResult]`。

### 2.2 布局部件清单

| Builder | 几何体 |
|---------|--------|
| `_build_conventional` | fuselage + main_wing + tail(按类型) + engines（现有逻辑不变） |
| `_build_twin_boom` | fuselage + main_wing + 2×boom + tail(按类型) + pusher_engine |
| `_build_flying_wing` | main_wing（加宽根弦，可选多段）— 无机身、无尾翼 |
| `_build_bwb` | flat_body + center_wing + 2×outer_wing — 无独立尾翼 |

### 2.3 新增/修改文件

| 文件 | 改动 |
|------|------|
| `create_tail.py` | 新增 `_create_v_tail`、`_create_inverted_v`、`_create_cruciform`，复用 `_create_tail_surface` |
| `create_engine.py` | engine_count 支持 3/4；新增 `pusher`/`wing_tip`/`over_wing` 位置 |
| `create_wing.py` | 多段翼支持：sections≥2 时创建多个 WING 几何体 |
| **新建** `create_boom.py` | 双尾撑：FUSELAGE 类型，细长几何体 |
| **新建** `create_body.py` | BWB 扁平机身：FUSELAGE + 非圆形截面 |
| `backend.py` | `LAYOUT_BUILDERS` 分发 + 4 个 builder 函数 |

### 2.4 尾翼构型实现细节

| 尾翼类型 | 实现方式 |
|----------|----------|
| conventional | 现有逻辑不变 |
| t_tail | 现有逻辑不变，暴露给 Chat Tool |
| **v_tail** | 2 个 WING，分别旋转 +45° 和 -45°，span = 常规垂尾 * 1.2 |
| **inverted_v** | 同 v_tail，旋转角度反向（-45°/+45° 向下倾斜） |
| **cruciform** | 水平尾翼 + 垂直尾翼，水平尾翼位于垂尾中部高度（z = v_tail_span * 0.5） |

### 2.5 多段翼实现

- `sections=1`：现有逻辑不变
- `sections=2`：inner_wing + outer_wing，inner 用 spec sweep/dihedral，outer 用 inner_sweep/inner_dihedral
- `sections=3`：再加一个最外翼段
- 每段是独立 WING 几何体，通过 X/Y 相对位置拼接
- 不使用 OpenVSP 多截面 API（概念设计阶段不需要连续翼型过渡）

### 2.6 发动机扩展

**3 发：** 1 台中轴 + 2 台对称（under_wing）
**4 发：** 4 台对称 POD
**新位置映射：**
- `wing_tip`：Y = wingspan/2
- `over_wing`：Z = wing_z + offset
- `pusher`：X = wing_x + offset，位于机翼后方

### 2.7 飞翼布局特殊处理

- 无 FUSELAGE 几何体，spec 中 `fuselage.length` 保留作为参考长度
- 根弦加大到等效机身宽度
- `tail.type` 强制忽略
- 发动机可选 1-2 台 POD，位于机翼上方或后缘

### 2.8 BWB 布局特殊处理

- `create_body.py`：FUSELAGE 类型，width ≫ height（如 width=3m, height=0.6m）
- 扩展 `set_fuselage_diameter` 为支持 width/height 独立设置
- center_wing 与机身平滑过渡（相同 sweep）
- 外翼段更大 sweep/dihedral（典型 35-45°）

## 3. 前端 UI 适配

### 3.1 ParameterPanel 新增控件

| 参数 | 控件类型 | 条件显示 |
|------|----------|----------|
| `aircraft.layout` | 下拉选择 | 始终 |
| `tail.type` | 下拉选择（新增选项） | layout ≠ flying_wing 且 layout ≠ BWB |
| `wing.sections` | 数字输入（1-3） | 始终 |
| `wing.inner_sweep` | 滑块 | sections ≥ 2 |
| `wing.inner_dihedral` | 滑块 | sections ≥ 2 |
| `engine.count` | 数字输入（1-4） | 始终 |
| `boom.length` | 滑块 | layout = twin_boom |
| `boom.span` | 滑块 | layout = twin_boom |
| `body.width` | 滑块 | layout = BWB |
| `body.height` | 滑块 | layout = BWB |

### 3.2 Chat Tool 字段暴露

`chat_tools.py` 的 `SUPPORTED_FIELD_VALUES` 更新：
```python
"aircraft.layout": ["conventional", "twin_boom", "flying_wing", "blended_wing_body"],
"tail.type": ["conventional", "t_tail", "v_tail", "inverted_v", "cruciform"],
"engine.count": [1, 2, 3, 4],
"engine.position": ["nose", "tail", "rear_fuselage", "under_wing", "wing_tip", "over_wing", "pusher"],
```

### 3.3 CadViewer

GLB 加载逻辑无需改动。part selection 需更新名称映射（新增 boom、outer_wing 等）。

## 4. VSPAERO 分析扩展

### 4.1 布局感知分析

| 布局 | 分析对象 |
|------|----------|
| conventional | main_wing（现有） |
| twin_boom | main_wing + booms |
| flying_wing | main_wing（全翼面） |
| BWB | center_wing + outer_wings |

### 4.2 实现方式

`run_vspaero_analysis` 接收 `geom_ids: list[str]` 参数（替代单 `wing_id`）。通过 `SetSetFlag` 将需要分析的部件加入同一 Set，对该 Set 运行 VSPAERO。

### 4.3 新增输出

- 多部件布局输出各部件升力分布（span loading）
- 尾撑布局输出干扰阻力估算

## 5. Design Rules 扩展

`design_rules.yaml` 新增规则：

| 规则 ID | 条件 | 检查内容 | 级别 |
|---------|------|----------|------|
| boom_span_ratio | layout = twin_boom | boom.span > wingspan * 0.3 | warn |
| flying_wing_stability | layout = flying_wing | MAC 位置俯仰稳定裕度估算 | warn |
| bwb_aspect_ratio | layout = BWB | body.width / body.height > 6 | warn |
| v_tail_area | tail.type = v_tail | V 尾面积 vs 常规垂尾面积比较 | warn |
| multi_section_sweep | wing.sections ≥ 2 | 内外翼 sweep 差 > 20° | warn |

## 6. 测试策略

### 6.1 测试模板

每个新布局/构型遵循：

| 测试类型 | 内容 | 文件 |
|----------|------|------|
| Mock 单元测试 | FakeOpenVspModule 验证参数传递 | `test_create_tail_extended.py` 等 |
| Builder 集成 | 完整 builder 调用验证 | `test_layout_builders.py` |
| Schema 验证 | 新值通过 Pydantic 校验 | `test_aircraft_spec_extended.py` |
| Fake CAD E2E | FakeCadBackend 完整生成 | `test_generation_api.py` 扩展 |
| OpenVSP 集成 | 真实 vsp3/step/glb | `test_openvsp_layout_integration.py`，`@pytest.mark.openvsp` |

## 7. 分批交付计划

### 批次 1：常规布局增强

- V 尾 / 倒 V 尾 / 十字尾（`create_tail.py`）
- T 尾暴露给 Chat Tool（`chat_tools.py`）
- 多段翼 sections 1-3（`create_wing.py`）
- 3-4 发动机 + 新位置（`create_engine.py`）
- Schema 扩展（`aircraft_spec.py`）
- 设计规则（`design_rules.yaml`）
- 测试：20+ 新增
- 示例：`v_tail_single_uav.yaml`

### 批次 2：双尾撑布局

- 尾撑几何（新建 `create_boom.py`）
- 双尾撑 builder（`backend.py`）
- 推进式发动机（`create_engine.py`）
- Schema boom 字段（`aircraft_spec.py`）
- VSPAERO 多部件分析（`vspaero_analysis.py`）
- 测试：12+ 新增
- 示例：`twin_boom_pusher_uav.yaml`

### 批次 3：飞翼布局

- 飞翼 builder（`backend.py`）
- 宽根弦机翼（`create_wing.py`）
- 无尾翼设计规则（`design_rules.yaml`）
- 前端条件显示（`ParameterPanel`）
- 测试：8+ 新增
- 示例：`flying_wing_uav.yaml`

### 批次 4：翼身融合

- 扁平机身（新建 `create_body.py`）
- BWB builder（`backend.py`）
- 中央翼 + 外翼段（`create_wing.py`）
- VSPAERO 多 Set 分析（`vspaero_analysis.py`）
- 测试：12+ 新增
- 示例：`bwb_uav.yaml`

## 8. 验收标准

1. 4 种布局均可在 Fake CAD 和 OpenVSP 后端生成完整 artifact（vsp3/step/glb）
2. 5 种尾翼构型参数正确传递到 OpenVSP API
3. 多段翼（1-3 段）正确创建独立 WING 几何体
4. 1-4 台发动机正确放置
5. Schema 新字段通过 Pydantic 校验
6. Chat Tool 可生成新布局的 spec
7. VSPAERO 对各布局产生合理的气动分析结果
8. 新设计规则对不合规配置发出 warn
9. 前端 ParameterPanel 条件显示新字段
10. 后端全量测试不回归（520+）
11. 新增 52+ 测试
12. README 验证状态表和几何支持矩阵更新
