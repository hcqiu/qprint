# 外部拓扑项目实测（2026-09-21）

[中文](external-topology-experiment.md) | [English](external-topology-experiment.en.md)

这次从网上另选两个项目，下载固定提交，在 Windows x64、Conda `qprint` 下测试。项目与报告位于 `.qprint/external-topology/`，不提交 Git。`downloads.json` 记录官方归档 URL、提交、下载时间和 SHA-256；`source-audit.json` 将实际源码逐文件与下载归档比对。

| 语言 | 上游 | 固定提交 | 编译器 |
| --- | --- | --- | --- |
| Lean | [CounterExamplesInTopology](https://github.com/dleijnse/CounterExamplesInTopology) | `f7710027fa73fa2c16fa08929037d8c96283c564` | `4.26.0-rc2` |
| Agda | [TypeTopology](https://github.com/martinescardo/TypeTopology) | `19b7895d644def0dbbced98a097f7e4e3a46f633` | `2.8.0` |

## Agda 结果

首次解析得到 `missing_version`。全新上下文的 subagent 使用 [version helper skill](../skills/formalization-version-helper/SKILL.md)，从固定提交的 `Makefile:11`、`source/AllModulesIndex.lagda:13` 和 `source/index.lagda:14` 找到已发布 Agda 2.8.0 的明确依据，仅新增 `.qprint-formal.yaml` 和来源记录，复用现有编译器。

同一全量请求随后选中 `source/` 下 995 个文件，返回 **failed**（退出码 42）：`AllModulesIndex.lagda:31` 的 `--rewriting` 被 `--safe` 拒绝。上游明确区分 safe 与 unsafe 总入口；这不是需要继续调版本的问题，helper 按 skill 停止。

另行选择上游安全拓扑入口 `source/TypeTopology/index.lagda`，保留 `--safe`、`--warning=error` 和 `--ignore-all-interfaces`，入口及其传递依赖 **passed**，用时 **112.656 秒**。这不表示全仓库 unsafe 模块通过了安全检查。全项目 996 个证明源文件（含 source 目录外文件）与原下载归档一致。

报告均位于 `agda/.qprint/reports/`：

- 首次缺版本：`20260921T112547.878085Z-3045a5d6.json`。
- helper 解析成功：`20260921T113331.828808Z-2b853776.json`。
- 全量安全检查失败：`20260921T113335.954315Z-e358c8f2.json`。
- 安全拓扑入口通过：`20260921T113631.098568Z-c0a66f28.json`。
- helper 配置及源码哈希审计：`typetopology-version-helper-audit.json`。

```powershell
conda run -n qprint python -m qprint formal verify --project .qprint/external-topology/agda --language agda --entry source/TypeTopology/index.lagda --timeout 600 --offline
```

## Lean 结果与环境准备

最终 **5 个项目源文件全部编译通过**，退出码 0，缓存就绪后的构建用时 **26.250 秒**。报告：`lean/.qprint/reports/20260921T120936.371315Z-02f4ec47.json`。检查显式指定全部五个模块，包含根模块未导入的 `DiscreteTopology`，而非只构建默认入口。

`DiscreteTopology.lean` 保留上游的 linter 警告：未使用的 section 变量、长行、空格及 flexible tactic 等。特别是 `discr_top_finest` 未使用离散拓扑假设，说明编译通过不替作者确认命题表达是否符合预期；本实验不改第三方定理。Lean 仍使用上游的警告策略，没有将所有警告升级为错误，也未执行公理审计。

全程没有调用 Lean version helper。编译器版本直接来自 `lean-toolchain`，mathlib 固定于原生 `lake-manifest.json` 的 `790901a8c97c730ae7af9bd44fe60c733a21d9ba`。Qprint 自动发现、下载并校验官方 Lean Windows 发行物；SHA-256 为 `f142276ea81a3761624d6218bb792714789e3349a462a02a007b77ea0106c153`。

正常 Git 传输在当前机器反复连接失败；原生验证产生 `lean/.qprint/reports/20260921T114339.593559Z-5a2c43d8.json`，退出码 1，底层 Git 退出码 128。随后从官方 codeload 取得 lock 中相同的九个固定提交，记录于 `lean-dependencies/downloads.json`，使用 Lake 原生 `.lake/package-overrides.json` 指向标准 `.lake/packages/` 目录。原 `lean-toolchain`、`lakefile.toml`、`lake-manifest.json` 及五个项目源码文件保持不变。

这是本次实验的网络替代步骤，尚不是 Qprint 自动下载 Lake 依赖的功能。Batteries 的内部文档链接 `docs/README.md → ../README.md` 展开为相同文档内容，未修改 Lean 源码。

Mathlib 官方 `lake exe cache get` 还要求 ProofWidgets 发布标签。实验通过 GitHub API 恢复其真实签名提交对象，计算出的 Git SHA 必须等于 lock 中 `2aaad968dd10a168b644b6a5afd4b92496af4710`，并核实上游 `v0.0.82` 标签指向该提交。这仅恢复发布包识别所需元数据，不冒充完整 Git 克隆。Windows `tar` 的非 UTF-8 输出导致 Lake 解包失败后，按官方 SHA-256 `bc998b1516f8527b8dc29116972bfe55d1382e0025d3b96872cbd8704d175614` 校验发布包并完整解包。缓存与这些准备脚本都留在实验目录中，全局 Git/PATH 配置未修改。

首次缓存下载中三个连接停滞，另一个条目在解包时被识别为损坏；同源重试后，官方缓存工具完整解包 **7,740 个条目**。最终缓存报告为 `lean-cache-20260921T120817Z.json`，没有截断或损坏提示；首次长日志与失败阶段也保留。完整实验依赖准备耗时远高于最终的 26 秒编译耗时，不能将两者混为一谈。

准备完成后的重现命令：

```powershell
conda run -n qprint python -m qprint formal verify --project .qprint/external-topology/lean --language lean --timeout 600 --offline
```

本机实验另留 `verify_lean.ps1`，仅对当前子进程设置测试目录的 Git 所有者信任与本地缓存路径，处理 sandbox/用户账户切换产生的目录所有者差异。

结论：该 Lean 样本的原生 pin 足以确定版本，**不需要 version helper 推断或改配版本**；本次仍需要处理下载、包布局与 Windows 工具行为。网络替代步骤尚未产品化，不能称为完全自动的一键验证。

## 实测带来的模块修正

TypeTopology 暴露了仅识别 `.agda` 的缺口。新增 `formal_sources.py`，集中处理 `.lean`、`.agda` 和 Agda 文学化后缀，供项目扫描、显式入口、模块名转换、Blueprint 文件推断和声明探针共用。后缀细节见 [项目解析文档](formal-resolution.md)。helper 本身不修改 Qprint 实现。

回归结果：**144 passed，无 skipped**；两条既有 FastAPI/Starlette 依赖弃用警告。真实示例测试只检查自身所需的工具链，额外版本下载中或在另一个执行账户下不可读，不再导致无关测试跳过。


## 自动验证后续实验（2026-09-22，保留上面的历史结果）

Agda 现在默认 `safe: inherit`。同一 TypeTopology 提交、同一 Agda 2.8.0，通过原生 `source/AllModulesIndex.lagda`（上游声明递归导入全部模块）检查通过，未追加 `--safe`，未执行额外安全审计。报告：`.qprint/external-topology/agda/.qprint/reports/20260921T155821.155101Z-298459e7.json`。之前强制 safe 的失败仍是有效的历史策略实验，两次结果的含义不同。

另用真实 Agda 检查三种边界：含 `--rewriting` 和 postulate 的样例默认通过；显式 require 返回策略冲突、原生检查结果 unknown；off 仍尊重源码自己的 `--safe`，带 postulate 的安全源码仍失败。小样例报告在 `.qprint/automation-experiment/agda/.qprint/reports/`。

对相同 CounterExamplesInTopology 固定提交做了一次新的 GitHub 导入，保持“下载后验证”默认开启，自动获取全部九个锁定依赖。为避免重复大规模下载，预置了此前取得的 7740 个官方 mathlib 缓存对象，因此这不是无缓存性能测试。首轮暴露了 Windows ProofWidgets release 获取失败后没有原生下载收据的恢复缺口，报告 `20260921T155504.923390Z-a613d84e.json` 被保留。修复准备模块后，由原生 Lake API 记录已校验 release 的下载收据，`--no-build` 确认可复用；随后一个无历史上下文的 agent 只通过 runtime helper 的 inspect/recover 重试原始报告，第一次重试通过。最终报告：`.qprint/automation-download/lean/topology/.qprint/reports/20260921T160633.874691Z-27957600.json`，范围为原生 Lake 默认目标。

独立 helper 小样例也通过了真实 Lean 重试。没有使用 version helper 修改 Lean pin；新 runtime helper 处理的是准备故障。脚本确认配置与源码未改变；归档对比也确认新 Lean 项目的源码/原生配置和原始提交一致，原先 5 个 Lean 与 996 个 Agda 源文件无变化。

界面检查确认下载后验证默认勾选、可以关闭、论文导入时隐藏。pytest 全量结果与模块边界见[验收记录](verification.md)和[解析文档](formal-resolution.md)。仍不承诺所有上游项目可自动恢复，不把原生检查通过解释为无公理证明。
