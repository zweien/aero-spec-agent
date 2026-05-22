# OpenVSP 环境自检

## 检查结果 (2026-05-22)

| 检查项 | 状态 | 说明 |
|--------|------|------|
| OpenVSP 可执行文件 | FAIL | 未在 PATH 中找到 `vsp` 或 `openvsp` |
| OpenVSP Python API | FAIL | `import vsp` 不可用 |
| `CAD_BACKEND=openvsp` 初始化 | SKIP | 依赖 OpenVSP 安装 |
| 输出目录可写 | PASS | `storage/` 目录正常 |
| 最小 test aircraft 生成 | SKIP | 依赖 OpenVSP 安装 |
| .vsp3 保存 | SKIP | 依赖 OpenVSP 安装 |
| .glb 导出 | SKIP | 依赖 OpenVSP 安装 |
| .step 导出 | SKIP | 依赖 OpenVSP 安装 |

**结论：OpenVSP 未安装在本机，环境检查未通过。后续 Task 2-4（OpenVSP 单方案/修改/Deep Design QA）均跳过，使用 fake backend 回退。**

## 环境变量

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `CAD_BACKEND` | `fake` | CAD 后端选择：`fake`（模拟）/ `openvsp`（真实 OpenVSP） |
| `OPENVSP_EXE` | 自动检测 | OpenVSP 可执行文件路径。若不在 PATH 中，需手动指定 |
| `FAKE_CAD_STEP_DELAY_MS` | `0` | Fake 后端每个 CAD 步骤延迟（毫秒） |
| `FAKE_CAD_FAIL_STAGE` | 空 | Fake 后端失败注入阶段（仅测试用） |
| `OPENVSP_FAIL_STAGE` | 空 | OpenVSP 后端失败注入阶段（仅测试用） |
| `RUN_OPENVSP_TESTS` | 空 | 设为 `1` 启用 OpenVSP 集成测试 |
| `RUN_VSPAERO_ANALYSIS` | 空 | 设为 `1` 启用 VSPAERO 分析 |

## CAD 后端选择

`backend_factory.get_cad_backend()` 根据 `CAD_BACKEND` 环境变量选择后端：

- `fake`（默认）：`FakeCadBackend`，确定性生成占位文件，无需 OpenVSP
- `openvsp`：`OpenVspBackend`，调用 OpenVSP Python API 生成真实 CAD 模型

```python
# services/workers/cad_worker/openvsp_generator/backend_factory.py
def get_cad_backend(name: str | None = None) -> CadBackend:
    backend_name = (name if name is not None else os.getenv("CAD_BACKEND", "fake")).strip().lower()
    if backend_name in {"", "fake"}:
        return FakeCadBackend()
    if backend_name == "openvsp":
        return OpenVspBackend()
    raise CadGenerationError(f"Unknown CAD_BACKEND: {backend_name}")
```

## Fake Backend 回退

当 OpenVSP 不可用时，系统自动使用 fake backend：

```bash
# 使用 fake backend（默认）
CAD_BACKEND=fake .venv/bin/python -m uvicorn services.api.app.main:app --host "$API_HOST" --port "$API_PORT"
```

Fake backend 生成的 artifacts：
- `aircraft.vsp3` — 文本占位文件
- `aircraft.step` — ISO-10303-21 空壳文件
- `aircraft.glb` — 最小合法 GLB 二进制（仅包含 asset 版本声明）

Fake backend 同样支持：
- CAD 进度回调（`on_progress`）
- 失败注入（`FAKE_CAD_FAIL_STAGE`）
- VSPAERO 模拟分析（`RUN_VSPAERO_ANALYSIS=1`）

## OpenVSP 安装指南

### 方式一：官方预编译包

1. 从 [OpenVSP Releases](https://github.com/OpenVSP/OpenVSP/releases) 下载 3.50.2 版本
2. 解压到目标目录（如 `/opt/openvsp`）
3. 确保 `vsp` 可执行文件在 PATH 中：

```bash
export PATH="/opt/openvsp/bin:$PATH"
```

4. 验证安装：

```bash
vsp --version
# 或 Python API：
python -c "import vsp; print(vsp.GetVersion())"
```

### 方式二：从源码编译

```bash
git clone https://github.com/OpenVSP/OpenVSP.git
cd OpenVSP
mkdir build && cd build
cmake .. -DVSP_ENABLE_PYTHON_API=ON -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
sudo make install
```

### 方式三：Conda 安装

```bash
conda install -c openvsp openvsp
```

## 常见失败原因

| 错误 | 原因 | 解决方法 |
|------|------|----------|
| `OpenVspUnavailableError` | OpenVSP 未安装或不在 PATH | 安装 OpenVSP 并设置 `OPENVSP_EXE` |
| `import vsp` 失败 | Python 绑定未正确安装 | 编译时启用 `-DVSP_ENABLE_PYTHON_API=ON` |
| `CadGenerationError: Unknown CAD_BACKEND` | 环境变量拼写错误 | 检查 `CAD_BACKEND` 值为 `fake` 或 `openvsp` |
| VSP3 文件为空 | 几何创建失败 | 检查 spec 参数是否在合理范围内 |
| GLB 导出失败 | OBJ→GLB 转换器问题 | 检查 `obj_to_glb.py` 依赖 |

## 自动化测试（fake backend）

```bash
# 后端全量测试（使用 fake backend）
CAD_BACKEND=fake .venv/bin/python -m pytest -q

# OpenVSP 集成测试（需要 OpenVSP 安装）
CAD_BACKEND=openvsp RUN_OPENVSP_TESTS=1 \
  .venv/bin/python -m pytest tests/api/test_openvsp_integration.py -q

# OpenVSP 后端单元测试（使用 FakeOpenVspModule mock）
CAD_BACKEND=fake .venv/bin/python -m pytest tests/api/test_openvsp_backend_unit.py -q
```
