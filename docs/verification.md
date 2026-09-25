# Qprint v1 验收记录

[中文](verification.md) | [English](verification.en.md) · [文档目录](index.md)

下列内容是各标注日期的实测记录，不表示本次双语文档整理重新执行了这些业务测试。v1 指首版产品，Python 包版本为 `0.1.0`。

## 2026-09-25：三种图谱展示范围

后续修复验收：范围切换事件现在调用统一的 `changeGraphScope`，以图中选中节点/阅读节点重新选择 Milestone，更新跨项目归属并保留焦点；项目颗粒度切入 Milestone 时展开节点，关闭旧邻域筛选。`node --test tests/graph_view.test.mjs` **16 项通过**，两个 JS 模块语法检查通过。浏览器实际切换 Topology 当前项目（8 节点 / 10 边）到 Maps.md（3 节点 / 3 边）；手选 Notes 后重新进入 Milestone 自动回到阅读节点 Continuous 所在 Maps；图中选中 Identity map 后切换自动选择 Notes（5 节点 / 5 边）并保留选中；项目颗粒度的单个项目圆点正确展开为 Maps 的 3 个节点。未记录 JavaScript error。本次未重跑 Python 套件。

新增“当前 Milestone”范围及文件选择器；全范围、当前项目、当前 Milestone 与颗粒度独立，项目级不再锁定全范围。初始文件来自阅读节点，手选文件可在刷新后保留；项目切换、删除和空文件有明确回退。

执行 `node --test tests/graph_view.test.mjs`：**11 项通过**；`node --check qprint/static/app.js` 和 `node --check qprint/static/graph-view.js` 通过。覆盖单文件节点/内部边、全范围恢复、各颗粒度保留范围、阅读和手选上下文、删除/空文件，以及既有两级下钻高亮。本次未修改 Python 逻辑，未重跑 Python 套件。

本地浏览器实测当前工作区：全范围 267 节点 / 560 边；`Topology/KPT25TwoStabilizations` 项目 216 节点 / 468 边；`01-lattice-foundations.md` 为 12 节点 / 16 边，切到 `02-pin-spectrum.md` 为 10 节点 / 11 边。保持 Milestone 范围切到项目颗粒度显示 1 项目；手选全范围恢复 4 项目。重载后初始化正常，窄窗口文件选择器显示项目相对文件名；本次检查未记录浏览器 JavaScript error。以上计数对应当前资料快照，不是固定示例基线。

## 2026-09-22：FLT3 报告与旧版工具链

下载器复现旧 Lean 发布物无 digest 的失败，确认原始报告已保存但缺少浏览器入口。新增报告查看/下载/持久历史、异常与保存失败呈现，以及旧工具链、旧 Lake 包名/Git 元数据和缓存目录兼容。FLT3 原生默认目标实际构建通过，源码和原生配置哈希未变。详见 [FLT3 实验](flt3-experiment.md)。全量 Python **216 passed**（两个既有提示），Node **12 passed**。浏览器点击真实历史报告成功显示错误和诊断。

## 2026-09-22：sphere-eversion 等待排查

生产下载器复现同一固定提交，修复新版 ProofWidgets 发布策略后，原生 mathlib 缓存准备及 `lake build` 均通过。配置和选定源码未改动；范围为原生默认目标，未执行额外安全审计。完整过程、报告与耗时见 [实验记录](sphere-eversion-experiment.md)。

新增请求局部进度、下载字节/解压项数、构建活动与任务耗时展示。全量 Python 测试 **184 passed**（两个既有依赖弃用提示），Node 前端测试 **10 passed**。覆盖运行中 API 快照、无总量时不伪造百分比、进度回调故障、子进程超时和新旧 ProofWidgets 分支。本次前端通过纯函数与 API 测试验证，未声称重新进行了浏览器交互验收；用户正在运行的旧服务未重启。

## 2026-09-22：下载后验证与受限恢复

Conda `qprint` 全量 pytest：**176 passed**，两个既有 FastAPI/Starlette 弃用提示。新增覆盖策略、原生入口、续传与校验、归档路径、固定提交、缓存修复、release 收据、helper 权限边界与重试预算、源码/配置变化，以及 API/CLI 导入开关。runtime skill 的 quick_validate 通过。

真实 Agda 2.8.0 的 inherit/require/off 边界符合预期；TypeTopology 上游 `AllModulesIndex.lagda` 在 inherit 下通过（约 566 秒），未做额外安全审计。新 Lean 拓扑导入自动获得九个锁定依赖，修复 Windows release 收据问题后，由干净 runtime helper 重试通过原生 Lake 默认目标。复用了 7740 个已有官方缓存对象，不是无缓存性能测试。另一个无历史上下文的 skill 小样例也完成了真实 Lean 重试。报告路径见[外部实验](external-topology-experiment.md)。

浏览器确认默认勾选、取消勾选、论文导入隐藏选项。归档比较确认原有 5 个 Lean、996 个 Agda 源文件及新 Lean 源码/原生配置未变。默认开启不保证任何仓库都能通过；下载、检查和安全审计分别报告。本轮未重建完整 Release；清单已加入 runtime skill。

## 2026-09-21：仓库内托管形式化环境

后续模块化扩展已完成：136 项回归测试通过，并用 serre-finiteness 完成干净 agent 的版本修复实验，35 模块全通过。详情见[实验记录](serre-finiteness-experiment.md)；下列 115 项测试和 ZIP 属于此前阶段。

已安装到 Git 忽略目录：Lean 4.19.0、Agda 2.8.0、Cubical 0.9（固定提交 `b150186d2544e7efeddd31e5d14a8b9ecbb100f7`）。原有用户导入目录未迁移。实现 manager、resolver、执行上下文、项目声明、安装记录及 light/full Release 清单。

执行 `conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-toolchain-release-final --tb=short`：**115 passed、2 warnings，无跳过**，6.85 秒。原有两条第三方弃用提示仍存在。新增验证包括多版本选择、浮动/冲突/rc 版本拒绝、显式 PATH 回退、Agda 库和数据目录隔离、哈希/归档/原子安装/删除保护、自动发现、两种 ZIP 输入规则及真实工具链。

`conda run -n qprint python -m qprint verify --workspace examples/verification` 实测 Lean 构建与环境声明查询、Agda/Cubical 类型检查与声明探针全部通过。不存在声明的真实工具链测试能正确失败。Agda 最初遇到全局 Cubical 参数破坏内置模块 full/erased 模式边界的问题；现已保留库选项作用域、在探针中设置模式，并重查全部接口，示例回归通过。

实际构建了约 502 MB 的 full 测试 ZIP，解压到 `.qprint/relocated full environment/Qprint`，从解压后的代码重新验证两种语言成功；报告中的 compiler/include 路径均在新目录内，不依赖原安装路径。测试产物不包含 Python 运行时，使用已有 Conda 环境。`git check-ignore` 确认编译器及 Cubical 库被忽略；36 份 Markdown 本地链接检查通过。本次无前端改动。安装、移植和打包边界详见[工具链文档](toolchains.md)。

## 2026-09-20：统一形式化验证适配层

新增 Lean / Agda 适配器、统一阶段报告、CLI、显式启用的后台 API、项目配置、进程超时与日志限制。作者进度保持独立，Coq 明确返回未支持。

执行：

```powershell
conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-verification-final --tb=short
conda run -n qprint python -m qprint verify --workspace examples/demo --language agda
```

Python 结果：**85 passed、2 skipped、2 warnings**，耗时 1.73 秒。新增测试覆盖命令与探针构造、失败阶段短路、正确行号配错误声明、缺少工具、超时、限长日志、配置与路径限制、探针注入、源码变化、API token/Origin/执行开关/队列、CLI 退出码及作者状态不变。两条第三方弃用提示与历史记录相同。

本机 Conda 环境没有 `lake`、`lean` 或 `agda`；两项真实工具链测试跳过，不能据此声称真实 Lean/Agda 工程已经编译验证。CLI 冒烟正确输出 `incomplete` / `unavailable`，退出 1。Windows Conda 捕获中文输出的编码问题通过验证报告使用 ASCII JSON 转义解决；解码后的名称和诊断不变。本次没有前端改动或浏览器验收。详细能力及限制见[验证模块](formal-verification.md)。

## 2026-09-20：blueprint 分级指南扩展

依据 `blueprint分级指南.md` 实现图谱的节点 / Milestone / 项目颗粒度及全范围 / 当前项目范围。磁盘节点格式未增加分级字段，分组由索引 Markdown 和目录派生。

自动验证：

```powershell
conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-granularity-final --tb=short
node --test tests/graph_view.test.mjs
node --check qprint/static/app.js
node --check qprint/static/graph.js
```

结果：**53 项 Python 测试通过、6 项前端状态测试通过**。Python 仍有下文记录的两条第三方弃用提示。新增覆盖包括最近索引归属、无索引目录回退、同名文件、空索引、普通 Markdown / wikilink 引用、跨文件去重、项目边合并、保存后重建、循环、排除示例代码与外链、默认范围、强制全范围及两级下钻高亮。API 测试改为复制固定示例文件，避免把用户另行导入的仓库当作测试夹具。

浏览器实测（示例工程）：

* 从 Topology 节点进入图谱，默认当前项目：8 节点、10 边；切换全范围：10 节点、12 边。
* 项目颗粒度：2 项目、1 条跨项目引用；范围锁定全范围。
* 双击 Topology：进入全范围 Milestone 图谱，3 文件、2 边，其中 Topology 的 2 个文件高亮。
* 双击 Notes26Continuity：进入 Topology 节点图谱，准确高亮该文件的 5 个节点，其他成员保持可见。
* 手选 Algebra：2 节点；双击 Associativity 正常定位 Lean 第 6–8 行。
* 1440 × 900 桌面和约 535 px 宽的小窗口检查通过；新增控件与画布分开排列，适配缩放后仍保留标签可读性。
* 力导向和分层两种布局均验证下钻；浏览器没有 JavaScript error。

以下为首版验收历史记录。

日期：2026-09-18。环境：Windows、Conda `qprint`、Python 3.12.14。

## 自动测试

执行：

```powershell
conda run -n qprint pytest -q --basetemp D:/Qprint_v2/.qprint/tests-final --tb=short
```

结果：**47 passed，2 warnings**，测试耗时 1.29 秒。

两条 warning 来自 Starlette 测试客户端对 httpx / AnyIO 接口的弃用提示，不是业务测试失败。实际项目依赖版本已记录于 `requirements-lock.txt`。初次测试遇到系统临时目录权限问题，改用项目内测试目录后运行成功。

| Spec | 覆盖情况 |
| --- | --- |
| A1 | 多节点、frontmatter、代码围栏、子标题、重复标题、无效 YAML、状态/行号校验、wikilink、歧义链接、循环图 |
| A2 | 标签片段边界、注释/verbatim 排除、章节、重复标签、plasTeX DOM、数学、HTML 转义、危险命令回退、解析超时回退 |
| A3 | Lean/Agda/Coq 定位、namespace、显式行号、模块简写、远程绑定、缺失或有歧义的声明 |
| A5 | API 保存及重建、版本冲突、非法元数据不写入、空工作区 |
| A6 | zip/tar/gzip/纯 TeX、默认分支、保留许可证、PDF 与源码配对、导入失败、后台任务成功/失败 |
| A7 | 相对路径与 Windows 特殊路径、链接文件、归档大小、外站重定向、下载限额、token / Origin / Host 检查 |
| A8 | 页面及本地 JS/CSS/数学字体资源可访问 |

## 浏览器验收

在实际本地服务 `http://127.0.0.1:8765` 中完成：

* 桌面 1440 × 960：论文文件夹、文件及章节目录正常；正文与代码双栏显示。
* 窄屏约 303 px：修复初次发现的栏宽挤压；顶部操作分两行，正文与代码上下排列。
* Lean → Agda → Coq 切换，源码路径和行号随绑定更新。
* 阅读 → TeX 切换，KaTeX 数学正常渲染。
* 前后节点按钮，正文触底后再次滚动到下一节点，同步更新代码。
* 搜索 Homotopy 返回唯一匹配。
* Markdown 增加验收文本，保存成功并重新载入；随后恢复示例原文并保存。
* 代码栏折叠与恢复。
* 力导向与分层图切换；状态筛选返回 2 个进行中节点；当前节点邻域返回 5 个节点、6 条边。
* 图谱单击 Homotopy 显示描述；双击 Composition of continuous maps 同时定位正文及 Lean 第 8–10 行。
* 修复节点标签区域点击命中问题；节点拖动、画布平移、滚轮缩放均实际操作验证。
* 导入界面提交非法仓库，后台任务返回具体失败原因；论文表单显示 arXiv 输入及论文文件名。
* 浏览器未记录 JavaScript error。

## 真实网络导入

运行 `conda run -n qprint python tools/smoke_imports.py`。测试下载保存至 `.qprint/network-smoke-*`，未改动 demo 内容。

| 来源 | 结果 |
| --- | --- |
| GitHub `CMU-HoTT/serre-finiteness` | 自动识别 `main` 分支，导入 40 个文件，保留目录和来源记录 |
| arXiv `1603.04246` | 成功获取 PDF 和 3 个源码文件，保存为配对的论文目录 |

这验证了实际下载端点与归档处理，不代表所有仓库和论文都提供可下载源码，也不代表下载的形式化代码已经编译。网络结果同时记录在 `.qprint/network-smoke.json`。

## 启动与限制

`start.ps1` 已实际启动服务，并在新进程中检查页面可用。示例索引为 10 个节点、12 条关系、1 篇论文；索引诊断为空。

TeX 渲染使用独立解析进程，8 秒超时后保留源码。它支持常见段落、定理、章节、列表和数学，复杂宏包、图像、跨文件 input 与多行宏定义仍是首版限制。图谱大规模性能未做基准测试；浏览器记录对应 10 节点示例。没有运行 Lean/Agda/Coq 编译器；形式化进度由作者标注。后续目标见 spec。
