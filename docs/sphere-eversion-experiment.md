# sphere-eversion 下载等待排查

[中文](sphere-eversion-experiment.md) | [English](sphere-eversion-experiment.en.md) · [文档目录](index.md)

2026-09-22，使用生产 `import_code` 下载器复现 [sphere-eversion](https://github.com/leanprover-community/sphere-eversion)，默认开启下载后验证。固定用户下载时的 commit `e03dfec32debbef8736185d6778bf3aa2f1d0572`，源码归档 SHA-256 为 `3f411ff4fc71735f4709b8c7b94c60e550690e6cefec628e1ef0e3e7e6db5b44`。独立复现目录为 `.qprint/sphere-repro/lean/sphere-eversion`。

## 为什么界面看起来卡住

用户运行任务时，本机尚未安装上游声明的 Lean `4.34.0-rc2`。官方 Windows ZIP 为 850,663,032 字节（约 811 MiB）；本地记录显示约 01:14:03 开始，01:21:47 下载完成，01:22:15 安装发布（北京时间）。界面一直只显示“下载完成，正在准备环境并验证…”，无法区分安装、缓存和编译。

安装之后还暴露了准备器错误：上游锁定 ProofWidgets commit `a8acbfd87375ff4abe14ce09db5b7664d383bc7f`、`inputRev: main`，其新版原生配置已不要求 cloud release；Qprint 却一律要求精确发布 tag，报 `Release preparation requires an exact upstream tag in the native lock`，类型检查未启动。用户原始失败报告时间为 `20260921T172249.058690Z-c0aa096e`。

## 修复和实测结果

准备器现在根据锁定的原生 `lakefile.lean` 发布策略选择流程。新版走源码与 mathlib 缓存；旧版仍校验 tag、commit、发布物摘要。新增请求局部的进度模块，界面显示下载字节、解压项数、依赖准备、缓存/构建阶段和总耗时。

| 实测阶段 | 结果 |
| --- | --- |
| 独立下载器复现 | 源码约 4 秒下载完成；约 45 秒复现相同 tag 错误，已复用安装好的编译器 |
| 修复后准备 | 原生 mathlib 缓存准备 257.781 秒，下载并解压 8893 个缓存对象 |
| 原生默认目标检查 | `lake build` 124.032 秒，成功完成 2967 个构建任务 |
| 最终报告 | `status: passed`，`outcomes.typecheck: passed`，`safe_audit: not_run` |

失败复现报告：`.qprint/sphere-repro/lean/sphere-eversion/.qprint/reports/20260921T172353.595119Z-c1e594fa.json`。修复后报告：同目录 `20260921T173455.861358Z-08ae92e0.json`。

依照 [runtime helper skill](../skills/formalization-runtime-helper/SKILL.md)，把报告、项目和工具链路径交给无历史上下文的新 agent，只通过 Python `inspect` / `recover` 操作；首次恢复通过。报告确认配置和选定源码均未改变。通过范围是上游 Lake 默认目标，并非额外证明安全审计或仓库全部文件逐个检查。缓存耗时与首次工具链安装是不同运行的记录，不能合并为一次端到端基准。

已运行的旧服务需重启才能载入 Python 修复；刷新页面加载新前端。失败导入保留源码和报告，无须重复下载已存在目标。首次工具链获取和后续构建各自有超时，导入的 `timeout: 600` 不是端到端十分钟期限。
