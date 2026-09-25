# TeX 定位与渲染模块

[中文](tex-rendering.md) | [English](tex-rendering.en.md) · [文档目录](index.md)

实现：[tex.py](../qprint/tex.py)、[_tex_worker.py](../qprint/_tex_worker.py)。测试：[test_tex_formal.py](../tests/test_tex_formal.py)。

## 编写与绑定

```tex
\documentclass{article}
\newcommand{\bpnode}[1]{}
\newtheorem{theorem}{Theorem}
\begin{document}
\section{Continuity}
\bpnode{identity-map}
\begin{theorem}
The identity map is continuous.
\end{theorem}
\bpnode{next-result}
The next fragment begins here.
\end{document}
```

标记放在内容之前、定理等环境之外。`tex: Topology/Notes#identity-map` 绑定 `tex/Topology/Notes.tex` 中的标签；若 Markdown 位于 `blueprint/Topology/Notes.md`，可简写 `tex: identity-map`。旧拼写 `\node{label}` 也可识别。

## 索引与片段

`TexDocument(path, source)` 提供 `preamble`、`anchors`、`sections`、`diagnostics`。扫描前遮蔽注释、verbatim/lstlisting/minted 和 `\verb` 内容，但保留偏移与行号。文档开始前的标签不计入正文索引。

同文件内允许重复标签，用于定理和分离的证明。`fragment(label)` 按原文顺序合并全部同标签片段；每段到下一标记、章节标题、参考文献区或 `\end{document}` 截止。只有缺失标签返回空结果。`fragments(label)` 返回独立片段，`annotations(label)` 汇总全部 `\bpdesc` 和去重的 `\uses`。参数支持嵌套花括号。不能在同一定理内部插入多个边界后仍期待获得完整环境。

章节索引支持 chapter、section、subsection、subsubsection，含星号形式。工作区把章节连接到其后第一个已绑定节点；没有节点的章节仍可查看 TeX 源文件。前后导航只在同一 TeX 文件的已绑定节点间进行。

## 渲染管线

`render_tex(fragment, preamble, references=None)` 启动独立 Python worker，以 JSON 传入内容、返回 HTML 与 warnings。合计超过 200,000 字符直接回退；子进程最长 8 秒。worker 保留 preamble 中匹配的单行宏/定理定义，组合内容超过 100,000 字符也回退。

worker 通过 plasTeX 生成 DOM，再由受控适配器输出段落、标题、列表、强调、定理、引用与数学占位元素。数学源文经属性转义放入 `data-tex`；浏览器使用本地 KaTeX 渲染。

正文中的 `~`、`\thinspace`、`\enspace`、`\quad`、`\qquad` 等转换为对应 Unicode 空格。`\hrulefill` / `\dotfill` 近似为 CSS 横线，`\vspace` / `\hspace` 和段间距近似为受限的 CSS 留白，换行转为 `<br>`；纸张分页、`\noindent`、`\relax`、`\leavevmode` 等纯排版控制安全忽略。盒子的 `to` / `spread` 尺寸指令会被消费，保留盒内内容。数学环境仍由 KaTeX 处理，verbatim 内容保持字面形式。未支持的排版命令在整页（包括正文与 BBL）去重汇总为一条提示；引用缺失、外部命令限制和解析失败仍单独报告。

普通 `\label` 生成隐藏定位锚点，`\ref` / `\eqref` 显示可点击的引用编号（后者带括号）。工作区按 TeX 文件缓存整篇论文的标签编号，因此前向引用、跨节点引用和重复 `bpnode` 合并片段都共享论文上下文。同节点引用直接滚动到标签；跨节点引用打开目标节点后定位标签。未绑定到节点的标签打开对应 TeX 源文件行。普通标签与 Blueprint 依赖分别解析，不改变 `\uses` / `\bpnode` 的行为。

公式中的 `\label` 从 KaTeX 输入移除；公式内的引用替换为编号，并在公式之后附上跳转链接。缺失或重复的普通标签显示引用文字和警告，不猜测目标。如果整篇论文因大小、超时或不支持的外部命令无法解析编号，仍按标签名提供定位，不使用片段局部编号冒充论文编号。跨文件 `\input` 展开仍不支持；同名标签不会在其他论文中自动匹配。

禁止列表中的外部输入、文件操作、宏包加载、低级宏定义、图片等命令会触发原文回退；适配器不直接输出任意 TeX 生成的 HTML。超时、进程失败和不支持命令均保留可读源文及提示。

## 限制与排障

这是受限阅读渲染器，不是完整 LaTeX 引擎，也不是完整的操作系统安全沙箱。多行宏、复杂宏包、外部图像和跨文件 `\input` 尚不支持完整还原；下载保留多文件结构不代表渲染器会展开它。

标签缺失时核对相对路径和拼写；重复标签应确实指向同一个数学节点。片段残缺时把标记移到环境外。渲染提示出现时可切换 TeX 查看原文；修改后刷新以清空缓存。对应未来工作见 [TODO](../TODO.md)。

## 文献引用与 References 页面

按 [跨文件引用指南](../产品经理prompt/跨文件引用指南.md) 的渲染规则，`\cite{KM}` 在 TeX 所在目录没有 `.bbl` 时保留原文；仅有 `.bib` 不触发排版。有 `.bbl` 时读取 BibTeX 生成的 `thebibliography` / `bibitem`，显示数字或显式标签，支持多键引用和 `\cite[定理 2]{KM}` 附注。点击引用打开该论文的完整 References 列表并定位条目；侧栏也提供参考文献入口，可以返回引用节点，支持页面刷新和浏览器前进、后退。

优先使用与 TeX 同名的 `.bbl`，否则使用同目录唯一的 `.bbl`。多个候选且没有同名文件时保留原文并提示，不混合不同论文的编号。缺失或重复的引用键显示 `?` 并提示。读取、解析或格式不支持（例如 biblatex 的 `\entry` 数据格式）时保留可读原文；BBL 也受既有大小、超时和外部命令限制。修改文件后点击刷新以清空缓存。`/api/references?path=...` 返回已索引论文的文献列表。

文献引用与 Blueprint 依赖分开处理：`\cite` 跳到文献列表，已有 `\uses` 继续跳到节点。指南中由 agent 检索现有项目并添加 `\uses` 的规则属于标注流程，渲染器不会仅凭引用键自动创建跨项目依赖。

## Blueprint 标注与转换

`bpnode` 和 `bpdesc` 不显示在论文正文中；描述写入 Blueprint 正文。`uses` 在标注位置显示依赖链接，保留原有 `ref`、`cite`。公式内的依赖链接显示在公式之后，避免污染 KaTeX 输入。工作区依次按完整节点 ID、同文件 TeX 标签、节点已声明的依赖及全局唯一别名解析；未解决的依赖显示文字和警告。链接目标经过 URL 编码，显示文字经过 HTML 转义。

标注、批量转换、项目索引和 agent review 使用 [tex-to-blueprint skill](../skills/tex-to-blueprint/SKILL.md)。脚本入口为 `.\.conda\python.exe skills/tex-to-blueprint/scripts/convert.py` 或 `.\.conda\python.exe -m qprint.tex_to_blueprint`。参见 [流程与实测](tex-to-blueprint.md)。
