# Deep Design Beta Test Plan

> **Disclaimer:** Deep Design 生成的设计结果仅用于概念探索，不可作为工程设计依据。

## 1. Test Goal

在面向更广泛用户发布之前，验证 Deep Design 功能的用户体验流程是否完整、可用、易懂。

## 2. Test Object

AeroSpec Agent Deep Design 功能，覆盖完整流程：

Chat → Initial Design → Deep Design → Variant Selection

## 3. Recommended Users

- 人数：3-5 人
- 背景：优先选择具有飞行器设计背景或对航空器设计有兴趣的测试者
- 无需编程经验，但需熟悉浏览器基本操作

## 4. Recommended Backend

**CAD_BACKEND=fake**

- 无需安装 OpenVSP，环境稳定
- 生成速度快，适合快速迭代测试
- 如需测试 OpenVSP 后端，请单独安排并在反馈表中标明

## 5. Test Flow

| Phase                | Duration | Description                                              |
|----------------------|----------|----------------------------------------------------------|
| Session Setup        | 15 min   | 环境确认、账号登录、功能简介                              |
| Free Exploration     | 30 min   | 测试者自由使用 Deep Design 功能，不限制输入内容           |
| Structured Test Cases| 30 min   | 按下方测试用例逐项执行                                   |
| Feedback Collection  | 15 min   | 填写反馈表（见 `docs/user-feedback-template.md`）         |

Total: approximately 90 minutes

## 6. Test Cases

### TC-1: Long-Endurance UAV (长航时无人机)

- **Input:** "设计一架翼展10米、单发、上单翼的长航时无人机"
- **Exploration Depth:** 快速探索 (Quick)
- **Expected:** 生成初始设计 → Deep Design 生成变体 → 推荐变体 → 可设置当前变体
- **Notes:** 验证基本流程完整性

### TC-2: Small Logistics UAV (小型物流无人机)

- **Input:** "设计一架翼展6米、双发、下单翼的物流无人机"
- **Exploration Depth:** 标准探索 (Standard) + 勾选"载荷优化"策略
- **Expected:** 变体之间应有载荷相关的差异
- **Notes:** 验证设计策略对探索结果的影响

### TC-3: Exploration Depth Comparison (翼展对比)

- **Input:** 同一需求（如"设计一架翼展8米、单发、上单翼的侦察无人机"）
- **Exploration Depth:** 分别使用快速探索和深度探索
- **Expected:** 深度探索生成的变体数量和参数范围应更广
- **Notes:** 对比两次探索的结果差异，评估探索深度是否有实际意义

### TC-4: STOL Exploration (短距起降探索)

- **Input:** "设计一架短距起降无人机"
- **Exploration Depth:** 自选
- **Strategy:** 勾选"短距起降"策略
- **Expected:** 变体中应体现短距起降相关的设计特征（如高升力装置、较大翼面积等）
- **Notes:** 验证策略标签对设计方向的引导

### TC-5: Abnormal Input (异常输入)

以下子场景逐项测试：

- **TC-5a 空描述：** 输入空内容或仅空格，提交生成
- **TC-5b 极端参数：** "设计一架翼展1米的运输机"
- **TC-5c 无初始设计直接探索：** 在未生成初始设计的情况下尝试启动 Deep Design
- **Expected:** 系统应给出合理的错误提示或降级处理，不应崩溃
- **Notes:** 记录系统的错误处理表现

## 7. Not Recommended

以下内容不在本次 Beta 测试范围内：

- OpenVSP 真实后端测试（环境依赖复杂，单独安排）
- Compare View（对比视图，尚未实现）
- 性能基准测试（响应时间、并发能力等）
- 浏览器兼容性全面测试（建议使用 Chrome 最新版）

## 8. Feedback Method

请使用反馈模板收集测试者反馈：`docs/user-feedback-template.md`

## 9. Success Criteria

| Criteria                                                            | Target |
|---------------------------------------------------------------------|--------|
| 用户能独立完成 Chat → Deep Design → Set Current Variant 完整流程    | 80%+   |
| 用户理解 AI 推荐理由                                                | 80%+   |
| 无 P0 级别问题                                                      | 0      |
| 收集到可操作的改进建议                                               | ≥ 3 条 |

### Issue Severity Reference

问题严重程度判定请参考：`docs/issue-triage-rules.md`
