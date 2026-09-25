# 开发与验证

[中文](development.md) | [English](development.en.md) · [文档目录](index.md)

环境要求见 [pyproject.toml](../pyproject.toml)，仓库规则见 [AGENTS.md](../AGENTS.md)。Python 3.12+，统一使用项目根目录的 Conda 前缀 `.conda`；前端无构建依赖，JS 测试需可运行 `node --test` 的 Node.js。

## 安装与启动

首次安装：在 **Anaconda Prompt / Miniconda Prompt** 中进入 Qprint 根目录，执行：

```text
conda init powershell
conda env create -p .\.conda -f environment.yml
```

`environment.yml` 会安装 Python 3.12+、项目和开发依赖。以后在 Qprint 根目录打开 PowerShell 或 Agent，直接运行：

```powershell
.\.conda\python.exe -m qprint serve --workspace examples/demo --port 8765
```

也可运行 `.\start.ps1`。打开 <http://127.0.0.1:8765>；默认仅监听本机。脚本使用项目内 `.conda`，缺少环境时会提示首次安装命令。

Agent 不执行 `conda activate`，也不需要 Conda 位于 PATH 或加载 PowerShell profile。若 Conda 可用，等价写法为 `conda run -p .\.conda python -m qprint agent state`。命令和路径均相对 Qprint 根目录；迁移安装位置时重新创建 `.conda`，不复制旧环境。

复现已记录依赖版本：

```powershell
.\.conda\python.exe -m pip install -r requirements-lock.txt
.\.conda\python.exe -m pip install -e . --no-deps
```

## CLI

新增 `toolchain list|install|remove [目录项ID] [--home PATH]`，安装可用 `--archive ZIP`；`verify`/`serve` 支持 `--toolchain-home` 和显式 `--allow-system-toolchains`。`start.ps1` 对应 `-ToolchainHome`、`-AllowVerification`、`-AllowSystemToolchains`。没有 demo 的发行包默认使用 `examples/verification`。完整安装与 `scripts/build-release.ps1 [-Full]` 契约见[工具链管理](toolchains.md)。

| 命令 | 参数与行为 |
| --- | --- |
| `serve` | `--workspace PATH`、`--port 8765`；要求工作区存在，绑定 127.0.0.1 |
| `check` | `--workspace PATH`；输出 JSON 诊断，有 error 退出 1，否则 0 |
| `verify` | `--workspace PATH`；可选 `--node`、`--language`、`--timeout`；显式运行工具链，全部通过才退出 0 |
| `import-code URL` | 必填 `--language`、`--dest`；可选 `--ref`、`--workspace` |
| `import-paper ID` | 必填 `--dest`、`--name`；可选 `--workspace` |

统一前缀为 `.\.conda\python.exe -m qprint`。默认工作区相对当前目录为 `examples/demo`。导入同步输出 JSON 或失败信息；`serve` 是持续运行进程。入口安装后也提供 `qprint` 命令，但仓库示例统一使用模块调用。

## 自动验证

`serve --allow-verification` 为可信工作区启用后台验证 API。编译器可通过仓库内 manager 显式安装，配置和结果边界见[形式化验证](formal-verification.md)。`test_verification.py` 覆盖适配器、执行器和 API，真实工具链缺失时明确跳过。

```powershell
.\.conda\python.exe -m pytest -q
node --test tests/graph_view.test.mjs
node --check qprint/static/app.js
node --check qprint/static/graph.js
.\.conda\python.exe -m qprint check --workspace examples/demo
```

| 文件 | 主要覆盖 |
| --- | --- |
| `test_blueprint.py` | 节点、元数据、链接、歧义与诊断 |
| `test_tex_formal.py` | 标签、渲染回退、三语言定位 |
| `test_workspace_api.py` | 保存、冲突、API、路径与本地请求保护 |
| `test_importers.py` | 下载格式、限额、归档和发布失败 |
| `test_graph_index.py` | 项目归属、引用提取与聚合 |
| `graph_view.test.mjs` | 前端范围、投影与两级下钻状态 |

Windows 临时目录受限时可以给 pytest 指定工作区内**测试专用**目录：

```powershell
New-Item -ItemType Directory .qprint -Force
.\.conda\python.exe -m pytest -q --basetemp .qprint/test-local
```

pytest 会清理 `--basetemp`，不得指向用户资料。变更解析/业务行为时运行对应回归；布局和交互变更需要浏览器验证，不能只凭 JS 语法检查判断通过。历史结果见 [verification](verification.md)，不要把其计数视为本次运行结果。

## 资源与网络工具

KaTeX `0.16.22` 的 JS、CSS、字体、LICENSE 和来源记录位于 `qprint/static/vendor/katex/`，作为 Python 包数据分发。更新资源前阅读 [vendor_assets.py](../tools/vendor_assets.py)；脚本联网获取固定版本并校验 npm SHA-512 integrity：

```powershell
.\.conda\python.exe tools/vendor_assets.py
```

[smoke_imports.py](../tools/smoke_imports.py) 联网下载公开样例，保存至 `.qprint/network-smoke-*` 并写结果记录。它不是离线测试套件的一部分，结果受源站和网络状态影响。

## 常见排障与变更约定

- 页面无节点：核对 `--workspace`、`blueprint/` 和一级标题，运行 `check`。
- 外部编辑不生效：点击刷新；没有自动文件监听。
- 保存 409：重新载入后人工合并；403：刷新以获取新 token，并保持同源。
- TeX 仅显示源码：查看渲染 warnings 与[渲染边界](tex-rendering.md)。
- 代码定位失败：填写实际文件和行号，参见[形式化代码](formal-code.md)。
- 导入失败：查看任务错误及[导入限制](importers.md)，不要把失败任务当作已完成资料。

修改功能时同步 spec、模块说明和中英文版本；新增未完成能力记录到 TODO。业务验收记录应注明时间、命令、结果、样本和未测范围。不要为文档更新宣称执行了没有运行的业务测试。
