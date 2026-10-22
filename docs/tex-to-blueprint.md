# TeX 到 Blueprint

> 文中命令已更新为项目内 `.conda` 的复现写法；历史结果与耗时保持原样，此次命令迁移不表示重新运行了这些实验。

[English](tex-to-blueprint.en.md) · [渲染模块](tex-rendering.md)

流程为：自动标注 → agent 调整（可选）→ 自动生成 → agent 对照论文 review（可选）。无 agent 时只执行两项自动步骤，生成结果仍标为待 review。项目/milestone/node 是目录、文件和一级标题的组织方式，没有增加节点类型字段。

## 使用

导入 arXiv 论文时默认勾选“自动标注 TeX 并生成 Blueprint 草稿”，取消后只下载 PDF 和源码。API 字段为 `auto_blueprint`（默认 true）；命令行使用 `--no-auto-blueprint` 取消。自动输出与论文使用相同项目目录，已有 Blueprint 不会被覆盖。标注或生成失败时不会发布部分下载结果。

```powershell
.\.conda\python.exe -m qprint import-paper --workspace WORKSPACE 2003.03925 --dest Topology --name Paper
.\.conda\python.exe -m qprint import-paper --workspace WORKSPACE 2003.03925 --dest Topology --name Paper --no-auto-blueprint
.\.conda\python.exe -m qprint.tex_to_blueprint annotate --workspace WORKSPACE --tex Paper/main.tex --dry-run
```

`annotate` 在非 proof 环境之前最近的环境结尾或章节标题之后插入 `bpnode`，采用该块首个 label，保留前导叙述；无 label 时使用该块的显示名称和编号（例如 `Theorem 2.1`），不自动添加 `bpdesc`。名称由有超时限制的渲染器解析，保留章节/共享计数器、显式计数器设置及标准 book/report 章节编号。对已传入文件中的 input/include 按出现顺序在内存中展开以计算编号，不读取额外文件。无编号的同名环境加 `(2)`、`(3)` 等后缀以免合并；没有显示标题的排版环境、缺失 include 或无法可靠解析的名称写入诊断，留待人工处理。为保持 TeX 片段完整，嵌套环境归入外层节点，其 label 引用解析到外层节点。第二遍将 ref/eqref/cref/Cref/autoref 显式引用映射到 label 所属节点并追加 uses，跨文件使用完整 TeX 绑定。注释、verbatim、导言区不参与标注，人工节点和已有 uses 保留，重复运行不重复插入。主文档补充无排版效果的标注宏。


工作区保存 `tex/` 和 `blueprint/`。使用 [skill](../skills/tex-to-blueprint/SKILL.md) 阅读论文、识别隐式依赖及无环境包裹的共享定义，并添加 `\bpnode`、`\bpdesc`、`\uses`。同文件重复标签合并为一个节点；不改原有 `ref`、`cite`。

```powershell
.\.conda\python.exe -m qprint.tex_to_blueprint search --workspace WORKSPACE --query "关键词"
.\.conda\python.exe -m qprint.tex_to_blueprint generate --workspace WORKSPACE --tex Paper/main.tex --dest Topology/Paper --title "论文标题" --author "作者" --year 2025 --keyword "拓扑" --dry-run
```

去掉 `--dry-run` 才写入文件。`--tex` 相对工作区的 `tex/`，`--dest` 相对 `blueprint/`；两者均限制在工作区内。多文件、作者、关键词可重复传参。`--dependency-map MAP.json` 接受短标签到完整节点 ID 的 JSON 对象，用于外部引用消歧。search 只读取其他项目的 Markdown。

每个 subsection 生成一份 Markdown，一级标题为节点；没有 subsection 的已标注内容按所属 section 单独成稿，避免遗漏。重复节点归入第一次出现的位置，同时收集所有片段的描述及依赖。整个节点没有 bpdesc 时，以各片段起始至第一个 begin 之间的引导文字作为描述；空描述合法。空 subsection 保留为待 review 草稿。已声明的 `newtheorem` 别名用于推断 kind，proposition/corollary 映射到现有 theorem 类别。

索引 `index.md` 保存标题、作者、年份、关键词、文件索引及已解析的外部依赖项目；使用 frontmatter 和二级标题，不制造节点。`generation-report.json` 保存待处理的缺失或歧义依赖，自动导入还保存标注统计和无法确定显示名称的环境等诊断。自动导入的标题、作者、关键词从源码提取，缺失标题暂用导入名称，年份来自 arXiv 编号；这些元信息仍需 review 核实。目标项目已存在时拒绝覆盖，先完整准备所有文件再发布目录。报告 `review_required: true` 表示仍需数学 review，不是失败。

生成后对照原文调整 milestone 边界、核实描述、补全隐式依赖；节点移动后同步修正链接和索引。脚本不执行外部 TeX 编译器；相关正文文件须分别传入，只有自动命名计算按已加载的 `input/include` 顺序合并，生成 Markdown 仍保留原文件绑定；不自动推断数学语义。复杂宏、图片和宏包仍受现有渲染器限制。

## 测试与复现

单元及集成测试覆盖重复标签、嵌套描述、空 subsection、多文件、外部依赖及消歧、行内和公式链接、HTML 转义、原文回退、路径校验、dry-run 与拒绝覆盖。

```powershell
.\.conda\python.exe -m pytest tests/test_tex_auto_annotation.py tests/test_tex_formal.py tests/test_tex_to_blueprint.py tests/test_importers.py tests/test_workspace_api.py
.\.conda\python.exe tools/smoke_tex_to_blueprint.py SOURCE_ARCHIVE --output NEW_TEST_WORKSPACE --title TITLE --author AUTHOR --year YEAR --auto-annotate --render-limit 12
```

结构烟雾测试只修改新解压的副本，保留原下载归档。`--auto-annotate` 使用产品自动标注器；不加该参数时保留历史合成标注模式（最外层数学环境、重复证明标签及占位描述），用于复现旧报告。**它不是完整数学标注或语义 review**。真实论文不随仓库分发。测试脚本不联网，输入可以是从 arXiv 下载的源归档。

2026-10-22，使用项目 `.conda` 和本地缓存源归档验证新自动流程：

| 源码版本 | 节点 | Markdown（含索引） | 依赖边 | 全节点渲染 | 原文回退 | 含渲染警告的节点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2003.03925v6 | 36 | 6 | 40 | 36/36 | 0 | 2 |
| 2510.12394v2 | 138 | 33 | 225 | 138/138 | 0 | 24 |

两份工作区结构诊断均为空。该轮使用早期无 label 跳过策略，标注诊断分别为 14、160 条；未完成语义 review。报告保存于 `.qprint/auto-blueprint-production-basic/smoke-report.json` 和 `.qprint/auto-blueprint-production-stress/smoke-report.json`。另通过下载器注入本地归档验证了默认导入流程（PDF 使用测试占位数据，未测实时网络下载）。147 项相关 Python 回归与 47 项前端测试通过。

下面为历史合成标注模式的结果，与新流程节点数不直接比较。

2026-09-22，在 Conda `qprint` 中实测：

| 源码版本 | 数学环境标记 | Blueprint 节点 | Markdown（含索引） | 依赖边 | 转换耗时 | 渲染检查 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [2003.03925v6](https://arxiv.org/abs/2003.03925v6) | 44 | 32 | 6 | 20 | 0.055 秒 | 32/32，无原文回退 |
| [2510.12394v2](https://arxiv.org/abs/2510.12394v2) | 311 | 216 | 34 | 234 | 0.444 秒 | 216/216，2 个原文回退（总渲染 47.274 秒） |

两份工作区的解析及依赖索引诊断均为空。压力论文的回退包含外部资源/未支持命令；其余部分片段还有复杂排版命令警告，不能据此宣称完整还原 LaTeX。完整 JSON 报告位于本地 `.qprint/tex-to-blueprint-tests/{basic-smoke,stress-full}/smoke-report.json`；报告记录源归档 SHA-256、渲染警告、链接数及耗时。

初轮全量 Python 回归：`.\.conda\python.exe -m pytest -q`，227 项通过；仅有两条既有 FastAPI/Starlette 弃用警告。skill 通过 `quick_validate.py` 校验，并安装到本机默认技能目录；安装后的检索入口已执行验证。

## 独立 skill

所有固定资源均在 skill 内：`references/blueprint-format.md`、`scripts/convert.py` 和 `scripts/qprint_blueprint/` 运行库。skill 运行时不读取产品 prompt、仓库文档或仓库模块；Python 第三方依赖来自 Qprint 根目录的 `.conda`。在 Qprint 根目录用 `.\.conda\python.exe skills/tex-to-blueprint/scripts/convert.py` 调用脚本。新增 `validate --workspace WORKSPACE --project PROJECT --render-limit 5` 检查 TeX 绑定、标注覆盖与依赖，并输出渲染 HTML 和警告。

仅维护者使用 `tools/bundle_blueprint_skill.py` 从应用模块同步运行库；回归测试验证副本一致性和搬移到仓库外后的独立生成/渲染。该维护工具不是给处理论文的 agent 的输入。

本轮完成独立 skill 与正式下载器的双论文测试，见 [独立双论文验收](tex-to-blueprint-agent-evaluation.md)。


## 无 label 环境的名称回退

2026-10-22 更新：优先沿用 label；缺失时写入如 `\bpnode{Theorem 2.1}` 的显示名称，计数包括此前已有 label 的环境。计数探针只存在于内存，保存的 TeX 不增加 label。无编号同名环境使用稳定后缀避免误合并，重复标注保持不变。

使用相同缓存源码重跑生产自动标注器后，2003.03925v6 生成 47 个节点、7 份 Markdown、40 条依赖边；2510.12394v2 生成 220 个节点、34 份 Markdown、245 条边。两份结构诊断均为空，各抽查渲染 3 个节点；仍有 3、78 个主要为 itemize、图形或其他无显示标题环境的标注诊断。报告位于 `.qprint/auto-names-basic/smoke-report.json` 与 `.qprint/auto-names-stress/smoke-report.json`。
