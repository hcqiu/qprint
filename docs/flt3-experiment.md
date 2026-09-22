# FLT3 下载验证与报告显示排查

[中文](flt3-experiment.md) | [English](flt3-experiment.en.md) · [文档目录](index.md)

2026-09-22，生产 `import_code` 下载器复现 [pitmonticone/FLT3](https://github.com/pitmonticone/FLT3)。固定用户下载时的 commit `a199fa0467f86504a9d2f6164b0456608e586821`，源码 ZIP SHA-256 `3dc3258df0a95c9f24961932cca0b970c8e94d136586520faee0fba40ba1af76`。独立测试目录 `.qprint/flt3-repro/lean/FLT3`，未覆盖用户下载目录。

## 报告为什么没看到

用户原始报告其实已写入 `examples/demo/lean/Topology/FLT3/.qprint/reports/20260921T175633.467479Z-e1cb9e0c.json`。界面把报告路径埋在整段 JSON 中，没有查看入口，重启又会丢失内存 job。另发现导入外围异常处理直接返回空 `reports`，没有持久化错误。

现在导入结果显示每个项目的错误摘要、查看报告和完整 JSON 下载链接；“查看历史验证报告”读取工作区磁盘报告，重启后仍可访问。独立 API 限定工作区内时间戳报告路径，拒绝路径越界和任意文件。单项目意外异常保存为报告并继续收集其他项目结果；报告写入失败明确显示 `report_error`。

## 通用兼容修复

- Lean `4.7.0-rc2` 官方 ZIP 存在，但 GitHub API `digest` 为 null。旧安装器把这一情况当作不可用。新流程固定官方 URL、asset ID `155141827` 和大小 `249401814`，首次下载后固定 SHA-256 `f6ed14925e4edab147add6010690963e9440ca86b85bdaf3b4fb50bfb3a13fef`；之后仍按固定哈希校验。收据和报告明确标注 `official-release-https-first-use-sha256`，不冒充发布者摘要或签名。
- 旧 Lake 使用 `«doc-gen4»` 形式的包名，目录名是 `doc-gen4`。解析器支持该格式，继续拒绝越界路径。
- Lake 4.7 不支持新版 package overrides。独立 `formal_legacy_lake.py` 按锁定提交获取真实 Git 元数据，验证 FETCH_HEAD，保持项目源码和锁文件不变。需要的 release tag 也必须解析到同一锁定提交。
- 旧 mathlib 读取 `XDG_CACHE_HOME/mathlib`，不读取 `MATHLIB_CACHE_DIR`。准备器现在为子进程指定项目内 `.qprint/preparation/legacy-cache`，保留全局环境不变。

## 实测

初始下载器约 1.9 秒复现安装失败，报告为 `20260921T180357.081218Z-b5ec532e.json`。安装旧 Lean 约 255 秒；随后暴露包名问题，报告为 `20260921T180956.130006Z-f973602a.json`。

修复后，固定依赖准备约 50 秒，mathlib 缓存约 263 秒，`lake build` 约 117 秒通过。报告 `20260921T181949.001180Z-ced1e87f.json` 的 `outcomes.typecheck` 为 `passed`，范围是原生默认目标，没有额外安全审计。本次早期缓存探针揭示了旧 mathlib 使用用户缓存目录的问题；最终复核将已有 4356 个哈希命名对象复制到项目缓存，由原生工具重新验证，未删除或改写用户缓存。因此最终复核不是冷缓存性能测试。

这些问题来自通用工具链准备流程，没有修改 FLT3 的证明或版本来求通过。哈希对比确认用户原始副本与测试副本的 10 个 Lean 文件（含 Lake 配置）及原生配置完全一致。最终复核补取原生发布标签时遇到 GitHub 连接超时，保存报告 `20260921T182154.173860Z-71fc5981.json`；新增 Git fetch 的有限瞬态重试后，交由干净 agent 使用 [runtime helper skill](../skills/formalization-runtime-helper/SKILL.md) 的 `inspect/recover` 重放，未授予源码编辑范围。

该 helper 使用完三次预算后停止，最后报告 `20260921T183157.426455Z-2866838c.json` 暴露原生 curl 的连接失败，以及 Qprint 对旧 ProofWidgets 发布物摘要的同类限制。随后在主任务修复通用准备模块：`formal_release_assets.py` 统一获取和记录旧辅助发布物；旧 Lake 使用自己的 `BuildTrace` API 记录已校验发布物；leantar 按上游固定的 `0.1.11` 获取、检查版本并安装到项目缓存。没有重置 helper 预算。

最终报告 `.qprint/flt3-repro/lean/FLT3/.qprint/reports/20260921T183613.297179Z-e802365b.json`：`status: passed`、`typecheck: passed`、`safe_audit: not_run`。复用已有缓存，约 13.3 秒完成准备与原生默认目标检查。再次哈希核对源码和原生配置未变。

浏览器实测从导入面板打开历史失败报告，独立页显示具体错误与诊断。Python 全量测试 216 项通过，Node 测试 12 项通过；两个既有依赖弃用提示保留。用户旧服务未重启，需重启服务并刷新页面加载新功能。
