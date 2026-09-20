# Qprint v1 验收记录

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
