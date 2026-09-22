# Serre finiteness：模块化验证与版本修复实验

日期：2026-09-21。Windows x64，Conda `qprint`，Agda 2.8.0。实验副本：`.qprint/formal-experiment/serre-finiteness`；其 35 个 `.agda` 文件与 `examples/demo/agda/Topology/serre-finiteness` 的 SHA-256 全部一致。原目录与证明源码均未修改。

## 过程与结果

1. **原生解析**：读取 `finiteness.agda-lib` 和 README 第 8 行，生成 `.qprint-formal.yaml`，固定 Agda 2.8.0 与 Cubical `d0b9c7b0e9e4f816422c3447d7983b03274dd829`。Artifact provider 登记已有的精确提交安装，未重复下载。
2. **访问错误诊断**：首次读取 Agda 安装收据出现 `WinError 5`，自动保存报告。第一个 `fork_turns=none` subagent 按 [helper skill](../skills/formalization-version-helper/SKILL.md) 检查，发现配置匹配，保持版本不变后重新 resolve/verify；35 模块通过。访问错误未复现，根因未确定。
3. **旧依赖对照组**：仅在实验副本将 Cubical pin 改为发布版 `0.9`。正式 `formal verify` 检查全部模块，71.265 秒后退出码 42，在 `FiberOrCofiberSequences/Base.agda:148` 报 `[NoParseForLHS]`，表达式为 `Iso.sec (IsoFiberSeqs A B C) F`。
4. **独立版本修复**：第二个 `fork_turns=none` subagent 只得到该失败报告、项目、store 路径和 skill，不读取历史诊断。它对照 README 和两版库的源码，确认 0.9 使用 `rightInv/leftInv`，项目指定提交使用 `sec/ret`。只改版本配置，再执行 skill 的 `retry.py`。
5. **复验通过**：重新 resolve 后，35 个模块全部通过，退出码 0，耗时 221.359 秒。保持 `--safe`、`--warning=error`、`--ignore-all-interfaces`。失败报告、修复前、修复后和成功报告中的全部源码哈希一致。

唯一修复：

```diff
-    version: "0.9"
+    revision: d0b9c7b0e9e4f816422c3447d7983b03274dd829
```

对照错误为本实验主动引入，不代表原项目新增了证明错误。聚合检查的首个错误不同于先前单独检查 `Summary.agda` 时的缺失模块，因为检查顺序不同。

## 证据

以下文件位于实验副本的 `.qprint/reports/`，不提交 Git：

| 内容 | 文件 |
| --- | --- |
| 初次访问错误 | `20260921T101211.715022Z-57983a0b.json` |
| 首个 agent 的验证成功 | `20260921T101906.287166Z-8e4ecab4.json` |
| 旧依赖失败 | `20260921T102130.850626Z-014a62bb.json` |
| 修复后解析成功 | `20260921T102628.976657Z-ab5acfea.json` |
| 修复后验证成功 | `20260921T103010.351934Z-53c42647.json` |
| 配置差异、接口证据、前后哈希 | `version-helper-control-evidence.json` |

与原目录的比较：`.qprint/formal-experiment/original-source-comparison.json`。日志保留最后 32 KiB 并标记截断；完整模块清单、源哈希、环境、命令、退出码均在报告中。命题与论文正文是否一致不在本实验范围。

## 复现与回归

```powershell
conda run -n qprint python -m qprint formal verify --project .qprint/formal-experiment/serre-finiteness --language agda --timeout 600 --offline
```

普通项目可省略 `--offline`，自动补齐支持的固定版本。本实验复用已安装编译器/库；下载、哈希记录、安装复用、官方资产 digest 检查及离线不联网有自动化测试。

最终执行 `conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-formal-modular-final --tb=short`：**136 passed，2 个既有依赖弃用警告，无跳过，6.93 秒**。Skill 的 `quick_validate.py` 检查通过，helper 脚本由两个独立 agent 实际执行；相关文档 126 个本地链接无断链。本次未重新生成历史 Release ZIP。模块说明见[项目解析与版本修复](formal-resolution.md)。
