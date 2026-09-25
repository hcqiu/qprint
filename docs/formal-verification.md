# 统一形式化验证适配层

[中文](formal-verification.md) | [English](formal-verification.en.md) · [文档目录](index.md)

实现：[verification.py](../qprint/verification.py)。测试：[test_verification.py](../tests/test_verification.py)。本模块通过已安装的工具链检查绑定；[formal.py](../qprint/formal.py) 仍只负责源码导航。读取节点、刷新与保存不会触发验证；GitHub 导入默认开启可关闭的“下载后验证”。节点 `status`、图谱颜色和完成数量始终是作者进度，不会被验证结果改写。

独立项目全模块验证、原生配置解析、自动安装和版本修复工作流见[模块化解析文档](formal-resolution.md)。显式验证可补齐支持的缺失版本，CLI `--offline` 禁止下载；语言适配器位于 `formal_adapters.py`。

## 检查范围

| 适配器 | 第一阶段 | 声明阶段 | 通过的含义 |
| --- | --- | --- | --- |
| Lean 4 / Lake | `lake build +Module`，显式构建绑定模块及依赖 | 临时 Lean 文件导入 `Lean` 与目标模块，以 `Lean.getEnv` / `contains` 查询完整声明名；通过 `lake env lean` 执行 | 构建成功，声明存在于导入后的环境中 |
| Agda | Agda 按上游 OPTIONS 检查绑定文件；默认 `safe: inherit`，不额外强加安全策略 | 临时模块导入目标模块，用 `open Scope using (name)` 解析导出的声明；所有启用的警告视为错误 | 文件类型检查成功，导出的名称能解析 |
| Coq | 未实现 | 未实现 | 返回 `unsupported`，不会因为源码可读而通过 |

Lean 查询使用精确环境名称，不能用 `file` / `lines` 冒充存在性检查。名称可以来自目标模块导入的依赖，不保证声明定义在绑定文件中。Lean `sorry`、公理和不安全依赖的审计尚未实现；声明存在不代表证明不依赖公理。Agda 默认保留上游 OPTIONS，只报告原生类型与名称检查；`safe: require` 或 `formal audit` 另行要求安全审计。`off` 也不会移除源码自身的 `--safe`。任何结果都不能证明形式化声明与 Markdown/TeX 数学内容语义一致。

Agda 只需类型检查，不生成 Haskell/JavaScript 可执行程序。首版探针支持公开导出的名称、限定子模块名称及普通 mixfix 名称；参数化顶层模块、需额外实例化的模块和特殊语法可能检查失败。Lean 首版支持普通点分标识符，暂不支持 `«转义名»` 或表达式。私有声明不能通过公共 Agda 导入探针访问。

## 项目配置

执行前先通过[工具链管理](toolchains.md)解析项目要求和托管安装。Lean 需 `lean-toolchain`，Agda 需子项目 `project.yaml`；适配器接收解析后的 `FormalExecutionContext`，结果增加 `environment`。Agda mode 用于生成探针的模块选项，源码应使用自己的原生 OPTIONS/.agda-lib；全局库清单被隔离。

没有配置文件时，通过 `lean-toolchain` / `project.yaml` 自动发现语言目录内的子项目；没有声明时保留语言目录候选，但执行会报告缺少版本。Lean 必须存在 `lakefile.lean` 或 `lakefile.toml`。导航 demo 不是完整 Lake 项目，不能直接当作编译验收项目。

多个导入仓库或自定义源码目录可在**工作区根目录**创建 `qprint-verification.json`：

```json
{
  "version": 1,
  "projects": [
    {"language": "lean", "root": "my-lean-repo", "source_root": "."},
    {
      "language": "agda",
      "root": "my-agda-repo",
      "source_root": "src",
      "include_paths": ["vendor/library"],
      "safe": "inherit",
      "mode": "cubical"
    }
  ]
}
```

| 字段 | 契约 |
| --- | --- |
| `version` | 必须是整数 `1` |
| `projects` | 项目数组；存在配置时完全替代默认推断，可为空 |
| `language` | `lean` 或 `agda` |
| `root` | 相对于对应语言目录，默认 `.` |
| `source_root` | 相对于项目根目录，默认 `.`；必须对应实际模块路径根（如 Lake 的 `srcDir`） |
| `include_paths` | 仅 Agda；项目内相对目录数组，默认空；源码根自动加入搜索路径 |
| `safe` | 仅 Agda；`inherit`（默认）、`require`、`off`；旧 `true/false` 映射为 `require/off` |
| `mode` | 仅 Agda；探针模块选项 `standard`（默认）、`cubical`、`erased-cubical`，源码仍声明原生 OPTIONS/.agda-lib |

配置目录必须存在，解析符号链接后仍需处于指定根内；拒绝绝对路径、`..`、Windows 特殊路径及任意命令配置。安装和精确版本解析见[工具链管理](toolchains.md)。Lean 依赖保留原生 Lake 管理，Agda 使用声明的托管库与临时库清单；工具链本身的构建可能下载依赖、产生构建文件、运行宏或项目配置代码。

绑定格式不变。例如 `file: my-agda-repo/src/Topology/Maps.agda` 仍相对 `agda/`；由 `source_root` 推导模块 `Topology.Maps`。验证独立推导文件，不依赖启发式源码截取是否成功，也不使用 `lines`。无 `file` 时沿用声明点分路径的候选文件规则。一个文件匹配多个项目时使用最深的 `source_root`；同语言重复源码根拒绝加载。配置全局错误会使请求失败。

## CLI

```powershell
.\.conda\python.exe -m qprint verify --workspace my-math
.\.conda\python.exe -m qprint verify --workspace my-math --language lean
.\.conda\python.exe -m qprint verify --workspace my-math --node "Topology/Notes#My theorem" --timeout 180
```

`--node` 与 `--language` 可组合。标准输出为 JSON 报告；全部选中绑定通过且没有索引错误时退出 `0`，检查失败、工具缺失、未支持、空选择或错误退出 `1`。不存在的节点、无效配置等请求级错误写入标准错误。`check` 命令仍只检查索引，不运行工具链。超时范围为 1–3600 秒，默认 120 秒，**对每个阶段单独计时**，并非整个批次的时间上限。

## API

CLI JSON 将非 ASCII 字符转义为 `\u...`，避免 Windows/Conda 捕获输出时编码不一致；JSON 解码后保留原始名称和诊断。

验证会执行工作区中的工具链代码，因此 HTTP 服务默认禁用执行。对可信工作区启动：

```powershell
.\.conda\python.exe -m qprint serve --workspace my-math --allow-verification
```

`GET /api/project` 返回 `verification_enabled`。使用同源写入 token 显式提交：

```javascript
const project = await fetch('/api/project').then(r => r.json());
const response = await fetch('/api/verify', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'x-qprint-token': project.token},
  body: JSON.stringify({node_id: 'Topology/Notes#My theorem', language: 'lean', timeout: 120})
});
const job = await response.json();
if (!response.ok) throw new Error(JSON.stringify(job.detail));
// 轮询，直到 status 不再是 queued/running。
const progress = await fetch('/api/jobs/' + job.id).then(r => r.json());
```

`node_id`、`language` 均可省略或为 null；默认选择全部节点和语言。202 表示已入队；403 表示未启用或写入凭证无效，404 表示节点不存在，422 表示参数错误，429 表示验证队列已满。验证有独立单工作线程，最多五个排队/运行任务；不持有工作区锁执行编译。绑定和索引诊断在提交时取快照，配置与源码在执行时读取。导入队列保持独立。

任务 `kind: verification`，状态为 `queued → running → succeeded | failed`。任务 `succeeded` 仅表示报告生成完毕，必须读取 `result.status` 才能判断检查是否全部通过。配置错误等无法生成报告的异常使任务 `failed`。记录只存服务内存，重启丢失，无取消接口。浏览器现有代码栏保持源码导航；本次没有新增验证按钮或自动展示历史结果。

## 结果契约与生命周期

报告字段：`schema_version: 1`、UTC `checked_at`（报告完成时间）、总 `status`、`results`；CLI/API 另附索引 `diagnostics`。总状态为 `passed`、`incomplete`、`not_run`（空选择）；索引错误使总状态为 `incomplete`。

每个绑定结果包含原 `binding`（CLI/API 附 `node_id`）、项目相对路径 `project`、`policy`、`source_sha256`、`status`、`message` 和 `checks`。每个阶段含 `stage`、`status`、`command` 数组、`returncode`、合并 stdout/stderr 的 `output`、`truncated`、`duration_ms`。工具缺失或超时可以没有退出码。

绑定/阶段状态：`passed` 检查通过；`failed` 工具返回非零；`unavailable` 可执行程序缺失；`timeout` 超时；`error` 输入、路径或执行环境错误；`unsupported` 适配器未实现；`stale` 检查期间绑定源码变化；`not_run` 尚未运行。第一阶段失败后不会继续声明探针，未执行阶段不出现在 `checks` 中。日志只返回最后 32 KiB 字节，UTF-8 解码错误替换，截断用布尔值标记。

结果是某次运行的历史证据，不是实时状态，也不作为成功缓存复用。绑定失败会保存带时间的报告；独立项目命令保存每次 resolve/verify 报告，见[项目解析与版本修复](formal-resolution.md)。每次请求重新执行。绑定源码哈希只覆盖绑定文件；独立项目报告记录全部选中文件。均不完整覆盖外部依赖、配置和工具链变化。编辑后必须重新运行，不应据旧报告自动更新节点。

执行器不使用 shell，标准输入关闭，Windows 隐藏窗口；超时尝试终止进程树，临时探针正常退出后清理。磁盘日志和工具链构建产物没有总配额，故不能将此层视为运行恶意项目的操作系统沙箱。只对可信工作区显式执行验证。

## 扩展及验证

新增适配器实现 `VerificationAdapter.verify(context, source, declaration, runner, timeout)` 并注册到 `ADAPTERS`，返回统一 `Check` 阶段结果；同时扩展项目配置/语言校验、路径规则与测试。`Runner` 可注入以便测试命令构造和各种返回结果，不依赖测试机器安装工具链。现有真实工具链测试在安装 Lake/Agda 后自动运行，否则明确跳过。

实现参考：[Lake 官方文档](https://lean-lang.org/doc/reference/latest/Build-Tools-and-Distribution/Lake/)、[Agda 命令行选项](https://agda.readthedocs.io/en/latest/tools/command-line-options.html)、[Agda 模块系统](https://agda.readthedocs.io/en/latest/language/module-system.html)。本机执行结果及限制见[验收记录](verification.md)。
