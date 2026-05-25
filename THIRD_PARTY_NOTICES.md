# Third-Party Notices

AeroSpec Agent 自身代码使用 **MIT License**。本项目依赖的第三方库和工具遵循各自的许可证，不因本项目的主许可证而改变。

## Optional External Dependency: OpenVSP

[OpenVSP](http://openvsp.org/) (Open Vehicle Sketch Pad) 是由 NASA 开发的参数化飞机设计工具，使用 **NASA Open Source Agreement Version 1.3 (NOSA-1.3)** 许可证。

- NOSA-1.3 不是 MIT 许可证，也不等同于公共领域 (public domain)
- 完整许可证文本见: <https://github.com/OpenVSP/OpenVSP/blob/master/LICENSE>
- AeroSpec Agent **不分发 OpenVSP 源码或二进制文件**
- 用户启用 `CAD_BACKEND=openvsp` 时，需自行安装 OpenVSP 并遵守 NOSA-1.3 条款
- 默认模式下 AeroSpec Agent 使用 `FakeCadBackend`，不依赖 OpenVSP

## Dependency License Summary

以下为自动扫描结果（扫描日期: 2026-05-25）。

### Python Dependencies (pip)

| 许可证 | 数量 | 代表性包 |
|--------|------|----------|
| MIT | ~40 | PyYAML, FastAPI, Pydantic, uvicorn, LangGraph, langchain-core, langchain-openai, trimesh, ruff, numpy (partial) |
| Apache-2.0 | ~8 | openai, requests, tenacity, distro, snakio |
| BSD-2-Clause / BSD-3-Clause | ~12 | httpx, click, starlette, pytest, uvloop, python-dotenv |
| PSF-2.0 / Python Software Foundation | ~3 | matplotlib, defusedxml, typing_extensions |
| MPL-2.0 | ~3 | certifi, orjson (dual), tqdm (dual) |
| LGPL-3.0-or-later | 1 | **CairoSVG** (传递依赖，经由 trimesh/matplotlib 引入) |
| Other permissive (0BSD, CC0-1.0, Zlib) | ~3 | numpy (multi-license), packaging |

**关于 CairoSVG (LGPL-3.0-or-later):**
- CairoSVG 是传递依赖，AeroSpec Agent 不直接调用其 API
- LGPL 允许以库的形式动态链接而不触发 copyleft 传染
- 若未来以静态链接或嵌入方式分发，需遵守 LGPL 条款（提供目标文件、允许用户替换该库）

### NPM Dependencies (Node.js / Frontend)

| 许可证 | 数量 | 代表性包 |
|--------|------|----------|
| MIT | 133 | React, Next.js, Three.js, @types/*, three-related |
| Apache-2.0 | 13 | @ai-sdk/*, @opentelemetry/api, @swc/*, @dimforge/rapier3d-compat |
| ISC | 3 | 简单工具库 |
| BSD-3-Clause | 1 | busboy |
| 0BSD | 1 | 简单工具库 |
| CC-BY-4.0 | 1 | caniuse-lite (浏览器兼容性数据) |
| AFL-2.1 OR BSD-3-Clause | 1 | json-schema |

## No GPL / AGPL / Non-Commercial Dependencies

扫描结果中未发现以下类型的许可证：
- GNU General Public License (GPL)
- GNU Affero General Public License (AGPL)
- 非商业 (Non-Commercial / CC-NC) 许可证
- 共享源码 (Shared Source) 限制性许可证

唯一涉及的 copyleft 许可证为 CairoSVG 的 **LGPL-3.0-or-later**，详见上文说明。

## Distribution Notice

### Source Code Distribution (当前)

源码发布（GitHub repository、git clone）不包含任何第三方库的源码。用户通过 `pip install` 和 `npm install` 自行下载依赖，各依赖遵循各自许可证。

### Docker / Installer / Offline Package

若未来通过以下任一方式分发：
- **Docker 镜像**（包含 pip/npm 安装后的依赖）
- **安装包**（包含预编译的依赖）
- **离线包**（包含所有依赖的 wheel / tarball）

需要注意：

1. **OpenVSP**: 若镜像中包含 OpenVSP，必须包含 NOSA-1.3 许可证全文，并说明如何获取 OpenVSP 源码（如提供 GitHub 仓库链接）
2. **CairoSVG (LGPL)**: 需确保 CairoSVG 以可替换方式提供（标准 pip install 即满足），并在分发中附带 LGPL-3.0 许可证文本
3. **所有依赖**: 建议在镜像中附带 `pip-licenses` 和 `license-checker` 的输出报告，或使用 `LICENSES/` 目录存放所有第三方许可证文本
4. **推荐工具**: `pip-licenses --format=html --output-file=LICENSES/python.html`，`npx license-checker --out LICENSES/npm.txt`

## Endorsement Disclaimer

AeroSpec Agent 是独立开发的社区项目。以下组织或项目未对本项目进行背书、赞助或认证：

- NASA / OpenVSP 团队
- Vercel / Next.js 团队
- OpenAI
- LangChain / LangGraph 团队
- Meta / React 团队
- Three.js 团队

各上游项目的名称和标识归其各自所有者所有。

## How to Regenerate This Report

```bash
# Python dependencies
.venv/bin/pip install pip-licenses -q
.venv/bin/pip-licenses --format=plain --from=mixed

# NPM dependencies
cd apps/web
npx license-checker --summary
npx license-checker --csv
```
