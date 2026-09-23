"""TeX anchors and a deliberately bounded plasTeX DOM-to-HTML adapter."""
from dataclasses import dataclass
from html import escape
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import RLock
from urllib.parse import quote

_PARSE_LOCK = RLock()


def tex_commands(source: str, names: set[str]):
    """Scan literal braced commands, retaining offsets and balanced arguments.

    This is annotation syntax, not TeX expansion. Comments and verbatim are inert.
    """
    masked = mask_comments(source)
    pattern = re.compile(r"\\([A-Za-z]+)\*?(?:\s*\[[^\]\n]*\])?\s*\{")
    end = 0
    for match in pattern.finditer(masked):
        if match.start() < end or match[1] not in names:
            continue
        preceding, cursor = 0, match.start() - 1
        while cursor >= 0 and masked[cursor] == "\\":
            preceding += 1
            cursor -= 1
        if preceding % 2:
            continue
        depth, cursor = 1, match.end()
        while cursor < len(masked) and depth:
            if masked[cursor] == "\\":
                cursor += 2
                continue
            depth += (masked[cursor] == "{") - (masked[cursor] == "}")
            cursor += 1
        if depth:
            raise ValueError(f"未闭合的 TeX 标注: \\{match[1]} (line {source.count(chr(10), 0, match.start()) + 1})")
        end = cursor
        yield {"name": match[1], "value": masked[match.end():cursor - 1].strip(),
               "start": match.start(), "end": cursor}


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
        end_doc = re.search(r"\\end\{document\}", masked[body_start:])
        self.body_end = body_start + end_doc.start() if end_doc else len(self.source)
        try:
            for command in tex_commands(self.source[body_start:self.body_end], {"bpnode", "node", "bpdesc", "uses"}):
                if command["name"] not in {"bpnode", "node"}:
                    continue
                label = command["value"]
                if not label or any(c in label for c in "{}\n#|\\") or "]]" in label:
                    self.diagnostics.append(f"不合法的 TeX 标签: {label!r}")
                    continue
                start = body_start + command["start"]
                self.anchors.append({"label": label, "start": start, "content_start": body_start + command["end"], "line": self.source.count("\n", 0, start) + 1})
        except ValueError as exc:
            self.diagnostics.append(str(exc))

        self.bibliography_offsets = [m.start() for m in re.finditer(
            r"\\(?:bibliographystyle|bibliography|printbibliography)\b|\\begin\{thebibliography\}", masked)
            if body_start <= m.start() < self.body_end]
        self.sections = []
        try:
            for command in tex_commands(self.source[body_start:self.body_end], {"chapter", "section", "subsection", "subsubsection"}):
                start = body_start + command["start"]
                self.sections.append({"title": command["value"], "level": ["chapter", "section", "subsection", "subsubsection"].index(command["name"]), "offset": start, "line": self.source.count("\n", 0, start) + 1})
        except ValueError as exc:
            self.diagnostics.append(str(exc))

    def fragments(self, label: str) -> list[str]:
        result = []
        for i, anchor in enumerate(self.anchors):
            if anchor["label"] != label:
                continue
            start = anchor["content_start"]
            end = self.anchors[i + 1]["start"] if i + 1 < len(self.anchors) else self.body_end
            # A following heading belongs to the next section, not this node.
            end = min([end, *(s["offset"] for s in self.sections if start <= s["offset"] < end),
                       *(offset for offset in self.bibliography_offsets if start <= offset < end)])
            result.append(self.source[start:end].strip())
        return result

    def fragment(self, label: str) -> str | None:
        parts = self.fragments(label)
        return "\n\n".join(parts) if parts else None

    def annotations(self, label: str) -> dict[str, list[str]]:
        descriptions, uses = [], []
        for part in self.fragments(label):
            for command in tex_commands(part, {"bpdesc", "uses"}):
                if command["name"] == "bpdesc":
                    descriptions.append(command["value"])
                else:
                    uses.extend(v.strip() for v in command["value"].split(",") if v.strip())
        return {"descriptions": descriptions, "uses": list(dict.fromkeys(uses))}


def tex_label_anchor(label: str) -> str:
    return "tex-label-" + label.encode("utf-8").hex()


def render_tex(fragment: str, preamble: str = "", references: dict[str, str] | None = None,
               *, labels: dict | None = None, index_only: bool = False):
    """Isolate macro expansion so malformed/recursive TeX cannot hang the server."""
    if len(fragment) + len(preamble) > 200_000:
        return f"<pre>{escape(fragment)}</pre>", ["片段或宏定义过大，已显示原文。"]
    try:
        completed = subprocess.run(
            [sys.executable, "-m", f"{__package__}._tex_worker"],
            input=json.dumps({"fragment": fragment, "preamble": preamble, "references": references or {},
                              "labels": labels, "index_only": index_only}),
            capture_output=True, text=True, encoding="utf-8", timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            cwd=Path(__file__).resolve().parent.parent,
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent)
                 + os.pathsep + os.environ.get("PYTHONPATH", "")},
        )
        if completed.returncode:
            raise ValueError("解析子进程未正常完成")
        html, warnings = json.loads(completed.stdout)
        return html, warnings
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return f'<pre class="tex-fallback">{escape(fragment)}</pre>', ["TeX 解析超时或失败，已停止解析并保留原文。"]


def _render_tex_dom(fragment: str, preamble: str = "", references: dict[str, str] | None = None,
                    *, labels: dict | None = None, index_only: bool = False):
    from plasTeX import Command
    from plasTeX.TeX import TeX
    from plasTeX.Base.LaTeX.Crossref import ref

    warnings = []
    original_fragment = fragment
    references = references or {}
    dependencies = []
    label_targets = dict(labels or {})
    emitted_anchors = set()
    try:
        commands = list(tex_commands(fragment, {"bpnode", "node", "bpdesc", "uses"}))
        for command in reversed(commands):
            replacement = ""
            if command["name"] == "uses":
                dependencies.append(command["value"])
                replacement = rf"\qprintdependency{{{len(dependencies) - 1}}}"
            fragment = fragment[:command["start"]] + replacement + fragment[command["end"]:]
    except ValueError as exc:
        return f'<pre class="tex-fallback">{escape(original_fragment)}</pre>', [str(exc)]

    def dependency_links(index):
        try:
            labels = dependencies[int(index)].split(",")
        except (ValueError, IndexError):
            return ""
        links = []
        for label in dict.fromkeys(v.strip() for v in labels if v.strip()):
            target = references.get(label)
            if target:
                links.append(f'<a class="wikilink tex-use" href="#node={quote(target, safe="")}">↗ {escape(label)}</a>')
            else:
                warnings.append(f"Blueprint 依赖不存在或不唯一: {label}")
                links.append(f'<span class="unresolved tex-use">↗ {escape(label)}</span>')
        return " ".join(links)

    class qprintdependency(Command):
        args = "index:str"

    class eqref(ref):
        pass

    def label_anchor(label):
        if label in emitted_anchors:
            return ""
        emitted_anchors.add(label)
        return f'<span class="tex-label" id="{tex_label_anchor(label)}"></span>'

    def reference_link(label, equation=False):
        target = label_targets.get(label)
        text = (target or {}).get("text") or label
        if equation:
            text = f"({text})"
        if not target or target.get("ambiguous"):
            warnings.append(f"TeX 引用不存在或不唯一: {label}")
            return f'<span class="reference unresolved">{escape(text)}</span>'
        anchor = tex_label_anchor(label)
        if target.get("node"):
            href = "#node=" + quote(target["node"], safe="")
            attributes = f' data-tex-node="{escape(target["node"], quote=True)}"'
        elif target.get("local"):
            href, attributes = "#" + anchor, ""
        elif target.get("path"):
            href = "#" + anchor
            attributes = (f' data-paper="{escape(target["path"], quote=True)}"'
                          f' data-line="{int(target["line"])}"')
        else:
            warnings.append(f"TeX 引用没有可跳转的位置: {label}")
            return f'<span class="reference unresolved">{escape(text)}</span>'
        return (f'<a class="reference tex-ref" href="{href}"{attributes}'
                f' data-tex-anchor="{anchor}">{escape(text)}</a>')
    # Only retain local macro/theorem definitions, never package loader directives.
    definitions = []
    for line in preamble.splitlines():
        if re.match(r"\s*\\(?:newcommand|renewcommand|providecommand|newtheorem|DeclareMathOperator)\b", line):
            if re.search(r"\\(?:bpnode|node|bpdesc|uses|qprintdependency)\b", line):
                continue
            definitions.append(line)
    source = "\n".join(definitions) + "\n" + fragment
    forbidden = r"\\(?:input|include|includeonly|usepackage|documentclass|openin|openout|read|write|immediate|special|catcode|csname|def|gdef|edef|xdef|loop|repeat|includegraphics|bibliography)\b"
    if re.search(forbidden, mask_comments(source)):
        return f'<pre class="tex-fallback">{escape(original_fragment)}</pre>', ["此片段包含外部资源或未支持命令，请查看 TeX 原文；未执行这些命令。"]
    if len(source) > 100_000:
        return f"<pre>{escape(original_fragment)}</pre>", ["片段过大，已显示原文。"]

    def children(node):
        return "".join(convert(child) for child in node.childNodes)

    def convert(node):
        if getattr(node, "nodeType", None) == 3:
            return escape(str(node))
        name = node.nodeName
        if name == "qprintdependency":
            return dependency_links(node.attributes.get("index", ""))
        if name == "label":
            return label_anchor(str(node.attributes.get("label", "")))
        if name in {"ref", "eqref"}:
            return reference_link(str(node.attributes.get("label", "")), name == "eqref")
        if name in {"math", "displaymath", "equation", "equation*", "align", "align*", "gather", "gather*"}:
            raw = node.source
            links = []
            def remove_dependency(match):
                links.append(dependency_links(match[1]))
                return ""
            raw = re.sub(r"\\qprintdependency\s*\{(\d+)\}", remove_dependency, raw)
            anchors, ref_links = [], []
            for command in reversed(list(tex_commands(raw, {"label", "ref", "eqref"}))):
                label = command["value"]
                replacement = ""
                if command["name"] == "label":
                    anchors.append(label_anchor(label))
                else:
                    ref_links.append(reference_link(label, command["name"] == "eqref"))
                    value = label_targets.get(label, {}).get("text") or "?"
                    # Only generated counter text is fed back into KaTeX.
                    value = re.sub(r"[^\w.:-]", "", value) or "?"
                    replacement = "(" + value + ")" if command["name"] == "eqref" else value
                raw = raw[:command["start"]] + replacement + raw[command["end"]:]
            links.extend(reversed(ref_links))
            return "".join(anchors) + f'<span class="math" data-display="{str(name != "math").lower()}" data-tex="{escape(raw, quote=True)}">{escape(raw)}</span>' + " ".join(links)
        if name in {"documentclass", "newcommand", "renewcommand", "providecommand", "newtheorem", "DeclareMathOperator", "bpnode", "node"}:
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
        if name == "cite":
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
            tex.ownerDocument.context.addGlobal("qprintdependency", qprintdependency)
            tex.ownerDocument.context.addGlobal("eqref", eqref)
            tex.ownerDocument.config["general"]["load-tex-packages"] = False
            tex.input("\\documentclass{article}\n" + source)
            document = tex.parse()
            parsed_labels = {}
            for label, target in document.context.labels.items():
                number = getattr(getattr(target, "ref", None), "textContent", "")
                parsed_labels[label] = {"text": str(number) or label, "local": True}
            seen = set()
            for command in tex_commands(fragment, {"label"}):
                label = command["value"]
                parsed_labels.setdefault(label, {"text": label, "local": True})
                if label in seen:
                    parsed_labels[label] = {"ambiguous": True}
                seen.add(label)
            if index_only:
                return parsed_labels, []
            if labels is None:
                label_targets.update(parsed_labels)
            else:
                for label in parsed_labels:
                    if label not in label_targets:
                        label_targets[label] = {"text": label, "local": True}
            html = convert(document)
        return html, list(dict.fromkeys(warnings))
    except Exception as exc:
        return f'<pre class="tex-fallback">{escape(original_fragment)}</pre>', [f"plasTeX 渲染失败，已保留原文: {exc}"]
