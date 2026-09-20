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

标签必须在单文件内唯一。`fragment(label)` 返回该标记之后、下一标记之前的内容，遇到 `\end{document}` 截止；缺失或重复标签返回空结果。不能在同一定理内部插入多个边界后仍期待获得完整环境。

章节索引支持 chapter、section、subsection、subsubsection，含星号形式。工作区把章节连接到其后第一个已绑定节点；没有节点的章节仍可查看 TeX 源文件。前后导航只在同一 TeX 文件的已绑定节点间进行。

## 渲染管线

`render_tex(fragment, preamble)` 启动独立 Python worker，以 JSON 传入内容、返回 HTML 与 warnings。合计超过 200,000 字符直接回退；子进程最长 8 秒。worker 保留 preamble 中匹配的单行宏/定理定义，组合内容超过 100,000 字符也回退。

worker 通过 plasTeX 生成 DOM，再由受控适配器输出段落、标题、列表、强调、定理、引用与数学占位元素。数学源文经属性转义放入 `data-tex`；浏览器使用本地 KaTeX 渲染。TeX 引用可保留为文本，并不等于完整 LaTeX 编号交叉引用系统。

禁止列表中的外部输入、文件操作、宏包加载、低级宏定义、图片等命令会触发原文回退；适配器不直接输出任意 TeX 生成的 HTML。超时、进程失败和不支持命令均保留可读源文及提示。

## 限制与排障

这是受限阅读渲染器，不是完整 LaTeX 引擎，也不是完整的操作系统安全沙箱。多行宏、复杂宏包、外部图像和跨文件 `\input` 尚不支持完整还原；下载保留多文件结构不代表渲染器会展开它。

标签缺失时核对相对路径和拼写；重复标签需在文件中修正。片段残缺时把标记移到环境外。渲染提示出现时可切换 TeX 查看原文；修改后刷新以清空缓存。对应未来工作见 [TODO](../TODO.md)。
