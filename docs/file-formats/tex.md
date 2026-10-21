# TeX 文件格式

[返回格式总索引](index.md)

## 文件位置与结构

论文源文件使用 `.tex`，保存于工作区的 `tex/` 下。完整论文通常包含导言区、`\begin{document}`、章节及数学正文、`\end{document}`。Qprint 不要求自创 TeX 文件容器；节点定位通过正文中的标记实现。

| 标记 | 用途 | 写法 |
| --- | --- | --- |
| `\bpnode{label}` | 为其后的数学片段建立节点锚点 | `\bpnode{identity-value}` |
| `\bpdesc{description}` | 提供生成 Blueprint 时使用的数学描述（可选） | `\bpdesc{For every natural number $n$, ...}` |
| `\uses{dependencies}` | 声明证明或定义所需的节点 | `\uses{identity-function}` |
| `\label`、`\ref`、`\eqref`、`\cite` | 原论文的编号和文献引用 | 保留原有写法，不代替节点标记 |

导言区为三个 Qprint 命令提供空定义，可以保持普通 LaTeX 编译兼容性。空定义只影响普通 LaTeX 排版；Qprint 仍读取其参数，并将 `uses` 渲染为依赖链接。

## 完整示例

保存为 `examples/format-demo/tex/Identity/main.tex`：

```tex
\documentclass{article}
\providecommand{\bpnode}[1]{}
\providecommand{\bpdesc}[1]{}
\providecommand{\uses}[1]{}
\newtheorem{definition}{Definition}
\newtheorem{theorem}{Theorem}

\begin{document}
\section{Identity on natural numbers}
\subsection{Identity function and its value}

\bpnode{identity-function}
\bpdesc{Define the identity function on natural numbers by $i(n)=n$.}
\begin{definition}\label{def:identity}
The identity function on natural numbers is defined by $i(n)=n$.
\end{definition}

\bpnode{identity-value}
\bpdesc{For every natural number $n$, the identity function satisfies $i(n)=n$.}
\begin{theorem}\label{thm:identity}
For every natural number $n$, we have $i(n)=n$.
\end{theorem}
\paragraph{Proof.}
Unfold Definition~\ref{def:identity}\uses{identity-function}.
The equality follows by reflexivity.

\end{document}
```

对应 Blueprint 绑定为 `tex: Identity/main.tex#identity-value`。这里的 `Identity/main.tex` 相对工作区的 `tex/`，后半部分准确对应 `bpnode` 参数，而不是普通 `label` 参数。

## 标注规则

- 将 `bpnode` 放在要绑定的内容之前、定理或证明环境之外，避免在环境中间切断片段。
- 同一个 TeX 文件内，相同标签可重复出现以合并同一节点的陈述与分离证明；不同数学对象使用不同标签。合并节点收集所有片段的描述及去重依赖。
- 片段到下一个节点标记、章节边界、参考文献区或文档末尾截止。跨章节的独立证明需要重新使用同一节点标记。
- `uses` 可列出逗号分隔的多个标签，例如 `\uses{identity-function, other-result}`；这些目标必须真实存在。跨项目引用推荐使用完整节点 ID，例如 `\uses{Basics/Identity/results#identity-function}`。
- 导言区、注释和 verbatim 类内容中的标记不作为正文节点。
- `bpdesc` 应概括数学对象、假设和结论；生成脚本不负责推断未标注的数学依赖。

## 转换为 Blueprint

保存上面的 TeX 后，在尚未保存手写 Blueprint 示例的工作区中，可从 Qprint 根目录预览自动生成结果：

```powershell
.\.conda\python.exe -m qprint.tex_to_blueprint generate --workspace examples/format-demo --tex Identity/main.tex --dest Basics/Identity --title "Identity on natural numbers" --author "Example Author" --year 2026 --keyword "identity" --dry-run
```

去掉 `--dry-run` 才会写入。`--tex` 相对 `tex/`，`--dest` 相对 `blueprint/`；目标目录必须尚不存在。自动生成与 [手写 Blueprint 示例](blueprint.md) 是两种建稿方式，选择一种即可；不要为同一批 TeX 标签重复建立示例项目，以免依赖解析出现多个候选。自动生成的 milestone 文件名由章节派生，不保证叫 `results.md`。生成后仍需检查数学描述、依赖和 milestone 边界，也需另行填写真实的 Lean/Agda 绑定。

多文件论文应重复传入 `--tex`，生成器不展开 `\input` 或 `\include`。Qprint 的阅读渲染器也不等同于完整 LaTeX 编译器；复杂宏包、外部图片、多行宏或不支持的命令可能导致警告或原文回退。详见 [TeX 渲染说明](../tex-rendering.md)。
