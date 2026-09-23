---
name: tex-to-blueprint
description: 将数学论文 TeX 标注并转换为 Qprint Blueprint，检索已有节点建立依赖，再按数学 milestone review Markdown 与项目索引。用于完整论文的标注、转换与 review，不用于形式化证明代码修复。
---

# TeX to Blueprint

将给定论文完成为可阅读、可导航的 Blueprint：阅读与标注 → 自动生成 → 数学 review → 校验。所有固定资料和脚本都在本 skill 目录中，不需要读取 Qprint 仓库或外部工作流文档。

## 输入与运行

输入是工作区根目录、当前论文 `tex/` 下的源码目录，以及 `blueprint/` 下的目标项目目录。论文对应 PDF、引用文件和 `.qprint-source.json` 属于当前项目材料，可以读取。先阅读 [Blueprint 格式](references/blueprint-format.md)。按论文规模分段阅读源文，记录已阅读范围，完成全文而非仅处理摘要或抽样。

以下 `SKILL_DIR` 替换为本文件所在目录的绝对路径。脚本使用随 skill 打包的运行库，不依赖当前目录或已安装的 qprint 包。运行环境为 Conda `qprint`，需要 PyYAML、markdown-it-py、plasTeX。Windows 上若 `conda` 不在 PATH，可查找并使用已有的 `%USERPROFILE%/anaconda3/Scripts/conda.exe`，仍须 `run -n qprint`；UTF-8 输出可设置当前进程的 `PYTHONIOENCODING=utf-8`、`PYTHONUTF8=1`。并行运行 Conda 时，可为各任务设置当前项目内独立的 TMP/TEMP 临时目录，避免共享临时文件冲突。无需安装或修改全局配置。

只修改当前项目的 TeX（含引用文件）与 Blueprint；临时辅助脚本/报告放在当前项目目录中。其他项目仅通过 search 脚本检索 Markdown，不读取或修改其 TeX 或证明代码。无需修改 skill 的脚本；如工具失效，报告具体输入和错误。不要用批量正则抽取代替数学理解，可以在理解后用辅助脚本落盘已确定的标注。

## 阅读与标注

识别定义、引理、命题、定理、猜想及相关证明。无环境包裹、被多个节点使用的定义和数学对象也需要节点。在节点起始处、环境外添加 `\bpnode{稳定标签}` 和 `\bpdesc{数学描述}`；唯一环境已有良好 `\label` 时优先沿用其标签。

同文件同标签允许多次出现，用于定理和分离的证明；它们按原文顺序合并为一个节点。每段止于下一 bpnode、章节标题或参考文献区，避免把标注插进环境内部。跨文件重复标签分别生成节点，引用时用完整节点 ID 消歧。保留原论文内容、`\ref`、`\cite` 和引用文件。

在每次依赖内容的引用后添加 `\uses{label1, label2}`，覆盖显式 ref、已存在 Blueprint 的文献引用，以及没有 ref 的隐式对象依赖。数学依赖需由原文判定；不要把每个文献引用或叙述性引用都视作证明依赖，也不要伪造不存在的外部节点。描述应说明对象、前提、结论或证明作用，不使用“结构测试占位”等无内容描述。

已有标注宏应兼容；缺失时在主文件导言区添加 `\providecommand{\bpnode}[1]{}`、`\providecommand{\bpdesc}[1]{}`、`\providecommand{\uses}[1]{}`，使原 LaTeX 排版不变。

```powershell
conda run -n qprint python "SKILL_DIR/scripts/convert.py" search --workspace WORKSPACE --query "数学对象或标签" --limit 30
```

search 返回节点 ID、TeX 绑定和描述。外部引用可直接标注完整 `路径#节点`；短标签有歧义时，用 `{"label": "领域/项目/文件#节点"}` JSON 映射，通过生成命令的 `--dependency-map MAP.json` 指定。外部节点不存在时在 review 报告中记录，不猜测。

## 自动生成

```powershell
conda run -n qprint python "SKILL_DIR/scripts/convert.py" generate --workspace WORKSPACE --tex Paper/main.tex --dest Topology/Paper --title "论文标题" --author "作者" --year 2025 --keyword "关键词" --dry-run
```

核实输出后去掉 `--dry-run` 写入。多作者、关键词、正文文件分别重复 `--author`、`--keyword`、`--tex`。脚本不展开 `input/include`，需显式传入相关正文文件。依据论文和来源记录填写元信息，不从文件修改时间猜测年份。

脚本按 subsection 生成 Markdown；同标签归入首次出现的分组并汇总所有 bpdesc/uses，空 subsection 留作 review，其他已标注章节内容不会丢弃。目标项目存在时拒绝覆盖；生成一次后直接 review 已有文件，不重新生成覆盖人工修改。

## 数学 review 与验收

对照完整 TeX 和生成的 Markdown，核实节点完整性、描述、前提条件、定理和证明对应关系及显式/隐式依赖。按数学目标调整每份 Markdown 为一个 milestone，可合并纯叙述小节、拆分多个独立目标；不要机械保留空文件或全部 subsection 边界。移动节点时同步修正 uses 链接和索引，保留 TeX 绑定。

完善项目索引的标题、作者、年份、关键词、全部 milestone 文件和已存在的外部依赖项目。检视 `generation-report.json` 的待处理诊断，并保留生成记录；将人工处理结果与仍未解决的问题写入项目 `review.md`（使用二级及以下标题，避免形成伪节点）。记录全文阅读范围、边界调整、隐式定义/依赖处理、外部依赖检索结果和渲染限制。只有实际完成这些工作时才注明语义 review 完成；未确定之处明确列出，不把结构转换测试当成完整数学 review。

```powershell
conda run -n qprint python "SKILL_DIR/scripts/convert.py" validate --workspace WORKSPACE --project Topology/Paper --render-limit 5
```

validate 检查当前项目 Markdown、依赖、标注覆盖和 TeX 绑定，并返回部分节点的渲染 HTML、行内链接数和警告；结构诊断非空时退出码为 1。默认抽查 3 个，可用 `--render-limit 0` 仅检查结构，最多 1000 个。消除可修复的结构问题，再抽查行内依赖、重复标签和数学内容。复杂宏或图片回退时保留原文并报告，不修改论文来隐藏渲染限制。最后提供项目索引、review 报告位置、节点/文件/依赖数、校验结果及未完成事项。
