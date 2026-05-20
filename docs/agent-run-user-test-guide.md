# Agent Run 用户测试指南

## 推荐启动方式

### 1. 启动后端

```bash
set -a && . .env && set +a
CAD_BACKEND=fake CHAT_GENERATION_MODE=async FAKE_CAD_STEP_DELAY_MS=300 \
  .venv/bin/python -m uvicorn services.api.app.main:app \
  --host "$API_HOST" --port "$API_PORT"
```

- `CAD_BACKEND=fake`：模拟后端，无需安装 OpenVSP
- `CHAT_GENERATION_MODE=async`：推荐模式，支持实时 Agent Run 阶段
- `FAKE_CAD_STEP_DELAY_MS=300`：每个 CAD 子阶段延迟 300ms（方便观察），设为 `0` 则全速

### 2. 启动前端

```bash
cd apps/web
npm run dev
```

浏览器访问 http://localhost:3900

## 推荐测试 Prompt

| Prompt | 重点验证 |
|--------|----------|
| 设计一架翼展12米、双发、上单翼的固定翼无人机 | 基础流程 |
| 设计一架小型长航时无人机 | 参数默认补全 |
| 设计一架翼展8米、单发、下单翼、V尾的无人机 | 非标准配置 |
| 设计一架高空长航时 surveillance UAV | 英文混合 |

## 预期看到的阶段

点击发送后，对话面板中应依次显示：

1. **AgentRunHeader**：正在设计飞机
2. **生成飞机参数**（~10%）— AI 生成 spec
3. **校验设计参数**（~20%）— 参数校验
4. **正在生成机身**（~62%）— CAD 阶段开始
5. **正在生成机翼**（~68%）
6. **正在生成尾翼**（~72%）
7. **正在生成发动机**（~76%）
8. **正在保存模型**（~82%）
9. **正在导出 STEP 文件**（~86%）
10. **正在导出 3D 模型**（~92%）
11. **三维预览准备就绪**（~96%）

CAD 预览区同步显示 CADLoadingOverlay 进度条。

## 预期看到的文件

生成完成后，AgentRunDetails 展开后可见：

| 文件 | 说明 |
|------|------|
| vsp3 | OpenVSP 原始模型 |
| step | STEP 工程格式 |
| glb | 3D 预览模型 |

## 操作按钮

生成完成后出现 4 个按钮：

| 按钮 | 作用 |
|------|------|
| 查看模型 | 加载 3D 模型到 CAD Viewer |
| 深度设计探索 | 切换到 Deep Design，探索多个方案 |
| 导出报告 | 打开 validation_report.json |
| 查看运行细节 | 展开 Job ID、阶段时间线、工件列表 |

## 默认补全提示

如果 LLM 未提供全部参数，系统会自动补全并在 AgentRunDetails 中显示蓝色提示框："系统已补全 N 个必要参数"。

展开后可看到每个补全参数的名称、默认值和原因。

## 常见问题

### 页面加载但 API 请求失败（端口不对）

删除 `.next` 缓存后重启前端：
```bash
rm -rf apps/web/.next
cd apps/web && npm run dev
```

### 生成卡住不动

- 检查后端日志是否有异常
- 检查 `OPENAI_API_KEY` 是否有效
- 尝试 `FAKE_CAD_STEP_DELAY_MS=0` 减少等待时间

### "spec 校验失败" 错误

系统会自动补全缺失的必填参数（如机身长度）。如果仍然失败，查看后端日志中的完整错误信息。

### 如何判断系统是否卡住

- AgentRunHeader 的计时器持续更新 → 正在运行
- 计时器停在某个值超过 30s → 可能卡住，检查后端日志
- 点击"查看运行细节"查看当前阶段

### 如何查看日志

- 成功时：点击"导出报告"查看 validation_report.json
- 失败时：点击"查看日志"打开诊断页面
- 后端日志：查看终端中的 uvicorn 输出
