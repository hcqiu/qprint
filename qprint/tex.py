"""TeX anchors and a deliberately bounded plasTeX DOM-to-HTML adapter."""
from dataclasses import dataclass
from html import escape
import json
import re
import subprocess
import sys
from threading import RLock

_PARSE_LOCK = RLock()


def mask_comments(source: str) -> str:
    # Preserve offsets so extracted text and line numbers refer to the original.
    masked = list(source)
    for m in re.finditer(r"\\begin\{(verbatim\*?|lstlisting|minted)\}.*?\\end\{\1\}|\\verb\*?([^\w\s]).*?\2", source, re.S):
        for i in range(m.start(), m.end()):
            if masked[i] != "\n":
                masked[i] = " "
    for m in re.finditer(r"(?<!\\)(?:\\\\)*(%[^\n]*)", "".join(masked)):
        for i in range(m.start(1), m.end(1)):
            masked[i] = " "
    return "".join(masked)


@dataclass
class TexDocument:
    path: str
    source: str

    def __post_init__(self):
        masked = mask_comments(self.source)
        begin = re.search(r"\\begin\{document\}", masked)
        self.preamble = self.source[:begin.start()] if begin else ""
        body_start = begin.end() if begin else 0
        self.anchors = []
        self.diagnostics = []
        seen = set()
        for m in re.finditer(r"\\(?:bpnode|node)\s*\{([^{}]+)\}", masked):
            if m.start() < body_start:
                continue
            label = m[1].strip()
            if label in seen:
                self.diagnostics.append(f"重复 TeX 标签: {label}")
            seen.add(label)
            self.anchors.append({"label": label, "start": m.start(), "content_start": m.end(), "line": self.source.count("\n", 0, m.start()) + 1})
        self.sections = []
        for m in re.finditer(r"\\(chapter|section|subsection|subsubsection)\*?\s*\{((?:[^{}]|\{[^{}]*\})*)\}", masked):
            if m.start() < body_start:
                continue
            self.sections.append({"title": m[2], "level": ["chapter", "section", "subsection", "subsubsection"].index(m[1]), "offset": m.start(), "line": self.source.count("\n", 0, m.start()) + 1})

    def fragment(self, label: str) -> str | None:
        matches = [i for i, a in enumerate(self.anchors) if a["label"] == label]
        if len(matches) != 1:
            return None
        i = matches[0]
        start = self.anchors[i]["content_start"]
        end = self.anchors[i + 1]["start"] if i + 1 < len(self.anchors) else len(self.source)
        end_doc = re.search(r"\\end\{document\}", mask_comments(self.source[start:end]))
        if end_doc:
            end = start + end_doc.start()
        return self.source[start:end].strip()


def render_tex(fragment: str, preamble: str = "") -> tuple[str, list[str]]:
    """Isolate macro expansion so malformed/recursive TeX cannot hang the server."""
    if len(fragment) + len(preamble) > 200_000:
        return f"<pre>{escape(fragment)}</pre>", ["片段或宏定义过大，已显示原文。"]
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "qprint._tex_worker"],
            input=json.dumps({"fragment": fragment, "preamble": preamble}),
            capture_output=True, text=True, encoding="utf-8", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if completed.returncode:
            raise ValueError("解析子进程未正常完成")
        html, warnings = json.loads(completed.stdout)
        return html, warnings
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return f'<pre class="tex-fallback">{escape(fragment)}</pre>', ["TeX 解析超时或失败，已停止解析并保留原文。"]


def _render_tex_dom(fragment: str, preamble: str = "") -> tuple[str, list[str]]:
    from plasTeX.TeX import TeX

    warnings = []
    # Only retain local macro/theorem definitions, never package loader directives.
    definitions = []
    for line in preamble.splitlines():
        if re.match(r"\s*\\(?:newcommand|renewcommand|providecommand|newtheorem|DeclareMathOperator)\b", line):
            definitions.append(line)
    source = "\n".join(definitions) + "\n" + fragment
    forbidden = r"\\(?:input|include|includeonly|usepackage|documentclass|openin|openout|read|write|immediate|special|catcode|csname|def|gdef|edef|xdef|loop|repeat|includegraphics|bibliography)\b"
    if re.search(forbidden, mask_comments(source)):
        return f'<pre class="tex-fallback">{escape(fragment)}</pre>', ["此片段包含外部资源或未支持命令，请查看 TeX 原文；未执行这些命令。"]
    if len(source) > 100_000:
        return f"<pre>{escape(fragment)}</pre>", ["片段过大，已显示原文。"]

    def children(node):
        return "".join(convert(child) for child in node.childNodes)

    def convert(node):
        if getattr(node, "nodeType", None) == 3:
            return escape(str(node))
        name = node.nodeName
        if name in {"math", "displaymath", "equation", "equation*", "align", "align*", "gather", "gather*"}:
            raw = node.source
            return f'<span class="math" data-display="{str(name != "math").lower()}" data-tex="{escape(raw, quote=True)}">{escape(raw)}</span>'
        if name in {"documentclass", "newcommand", "renewcommand", "providecommand", "newtheorem", "DeclareMathOperator", "label", "bpnode", "node"}:
            return ""
        if name in {"#document", "#document-fragment", "document", "bgroup", "egroup"}:
            return children(node)
        if name in {"section", "subsection", "subsubsection", "chapter"}:
            title = node.attributes.get("title")
            heading = children(title) if hasattr(title, "childNodes") else escape(str(title or ""))
            return f"<h3>{heading}</h3>{children(node)}"
        tags = {"par": "p", "textbf": "strong", "emph": "em", "textit": "em", "texttt": "code", "itemize": "ul", "enumerate": "ol", "item": "li", "quote": "blockquote", "verbatim": "pre"}
        if name in tags:
            tag = tags[name]
            return f"<{tag}>{children(node)}</{tag}>"
        if name in {"ref", "eqref", "cite"}:
            return f'<span class="reference">{escape(node.source)}</span>'
        if name in {"theorem", "lemma", "definition", "proof", "proposition", "corollary", "remark", "conjecture"} or hasattr(node, "thmName"):
            title = getattr(node, "thmName", name)
            title = title.textContent if hasattr(title, "textContent") else str(title)
            return f'<section class="theorem"><div class="theorem-label">{escape(title.title())}</div>{children(node)}</section>'
        if node.childNodes:
            return children(node)
        raw = getattr(node, "source", "")
        if raw.strip():
            warnings.append(f"未完整渲染命令: {name}")
        return escape(raw)

    try:
        with _PARSE_LOCK:
            tex = TeX()
            tex.ownerDocument.config["general"]["load-tex-packages"] = False
            tex.input("\\documentclass{article}\n" + source)
            document = tex.parse()
            html = convert(document)
        return html, list(dict.fromkeys(warnings))
    except Exception as exc:
        return f'<pre class="tex-fallback">{escape(fragment)}</pre>', [f"plasTeX 渲染失败，已保留原文: {exc}"]
