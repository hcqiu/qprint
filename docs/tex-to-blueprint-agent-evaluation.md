# 独立 skill 双论文验收

本轮使用全新下载的论文，而不是上一轮机械标注的结构烟雾测试副本。

## 输入隔离

两个 subagent 均以 `fork_turns=none` 创建。初始消息只有已安装 `tex-to-blueprint/SKILL.md` 的路径、各自工作区、源码目录和 Blueprint 目标目录；没有提供历史讨论、产品 prompt、参考答案、预期节点数或机械标注结果。各 agent 独立读取 skill 内置格式说明与脚本，并负责阅读、标注、生成、数学 review 与校验。

| 案例 | 下载器参数 | 正确的 TeX 目录 |
| --- | --- | --- |
| arXiv 2003.03925v6 | `--dest Topology/Lin20K3 --name Lin20K3` | `tex/Topology/Lin20K3` |
| arXiv 2510.12394v2 | `--dest Topology/KPT25TwoStabilizations --name KPT25TwoStabilizations` | `tex/Topology/KPT25TwoStabilizations` |

下载均通过 `conda run -n qprint python -m qprint import-paper` 完成，同时获取 PDF、完整 TeX 源码和来源记录。工作区分别位于 `.qprint/blueprint-skill-evaluation/basic` 与 `stress`，互不读取对方的论文资料。skill 的固定说明、格式文档、转换/检索/校验脚本和运行库全部位于 skill 内。

## 初步案例

subagent 完成 main.tex 全文和 main.bbl 阅读，新增/汇总 41 个节点，整理为 7 个数学 milestone、80 条依赖边。项目共 9 份 Markdown（含索引及 review）。外部 Blueprint 检索未找到可用项目，保留文献引用并在 review 记录外部数学输入，不虚构依赖节点。

初次全节点校验诊断为空，41 个节点均做渲染检查，95 个行内依赖链接。发现最后的重复标签片段纳入 bibliography 命令，造成主定理回退。此问题由独立测试暴露，随后在 TexDocument 中增加参考文献边界，不修改论文。修复后复查 41 个节点，0 个原文回退，109 个行内链接，结构诊断仍为空。复杂 split 等命令仍有排版警告，完整公式保真不在此测试结论中。

主代理另行对照原始下载文本：移除新增标注和兼容宏、忽略空白/注释后，原文内容保持一致；没有空描述、未绑定节点或结构测试占位描述。

## 压力案例

subagent 报告按连续区段完成 9,599 行正文与三个附录的阅读，并在原文保留的基础上形成 218 个标注片段、216 个唯一节点。33 份 subsection 草稿重组为 26 个数学 milestone，468 条依赖边，含索引和 review 共 28 份 Markdown。定理与分离证明通过重复标签合并；长 proof 内的局部定义和引理按完整环境聚合，并说明边界选择。

首次全 216 节点渲染和最终结构校验均无结构诊断：83 个节点无渲染警告、133 个有警告、2 个回退；共 550 个行内链接。两个回退分别由 Mazur PDF 图和尾部 bibliography 命令引起。索引、review、生成记录、milestone 调整记录和完整渲染 HTML 均保留。review 明列源文的方向约定、示例名称、局部化公式、模块基范围及附录公式等疑点，没有把结构通过等同于证明认证。

独立原文对照同样通过，未发现空描述、失效绑定或测试占位描述。两篇论文各自在隔离工作区中处理，所以本次没有测试两篇论文互相连接的跨项目依赖；两位 agent 均记录了外部 Blueprint 检索未找到匹配项。

## 证据与复现

输入与 skill 文件摘要记录在 `.qprint/blueprint-skill-evaluation/evidence/run-inputs.json`。原始 TeX 副本也保存在该 evidence 目录中，未提供给 agent 作为标注参考。各项目的 `index.md`、`review.md`、`generation-report.json` 与验证 JSON 在对应 `blueprint/Topology/<项目>/` 下。生成报告保留首次转换记录；review 后的文件组织以索引为准。

固定脚本的独立性通过自动测试验证：将整个 skill 复制到没有 Qprint 仓库的目录，清空 `PYTHONPATH`，执行生成和带渲染的 validate。发布包也检查了内置文档和运行库是否齐全。维护者通过 `tools/bundle_blueprint_skill.py` 同步应用模块副本；该维护脚本没有提供给论文处理 agent。

数学 review 是论文陈述、依赖与证明结构的审阅，不是形式化验证；节点的形式化 status 保持 `not_started`。原文中发现的记号或类型疑点保留并记录，不能把 agent 的解释当作对原论文的修订。

## 最终代码检查

全量回归为 245 项通过，仅有两条既有 FastAPI/Starlette 弃用警告。新增检查包括重复项目目录、归档外壳、多根归档、发布回滚、相对路径、skill 独立运行、worker 不被当前目录包遮蔽，以及 bibliography 边界。两篇源文在去除新增标注、忽略空白/注释后的保留检查均通过。

## 更新后 skill 的原代理复验

两个原 subagent 各自使用同一路径的更新后 skill 重新校验，保留首次报告，未重新标注或更改数学内容。初步案例：41 节点、80 依赖、零结构诊断、109 个行内链接、0 个回退；仍有 2 节点共 8 条排版警告。压力案例：216 节点、468 依赖、零结构诊断、555 个行内链接（210 节点含链接）、1 个回退；83 节点无警告、133 节点有警告。剩余回退来自主定理段的 Mazur PDF 图片，末尾定理已恢复 HTML。两个项目的 review 和校验摘要均已据实际结果更新。
