from html import escape
from pathlib import Path
import os
import tempfile
from threading import RLock
from urllib.parse import quote

from markdown_it import MarkdownIt

from .blueprint import WIKILINK, parse_markdown, resolve_link, revision
from .formal import locate_code
from .graph_index import build_graph_index
from .paths import WorkspaceError, read_text, safe_path
from .tex import TexDocument, render_tex


class ConflictError(WorkspaceError):
    pass


class Workspace:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.lock = RLock()
        self.reload()

    def reload(self):
        with self.lock:
            self.nodes, self.documents, self.tex, self.diagnostics = {}, {}, {}, []
            self.render_cache = {}
            for path in sorted((self.root / "blueprint").rglob("*.md")):
                relative = path.relative_to(self.root / "blueprint").as_posix()
                try:
                    text = read_text(safe_path(self.root, f"blueprint/{relative}"))
                    nodes, diagnostics = parse_markdown(relative, text)
                    self.documents[relative] = text
                    self.nodes.update((n.id, n) for n in nodes)
                    self.diagnostics.extend(diagnostics)
                except (OSError, UnicodeError, WorkspaceError) as exc:
                    self.diagnostics.append({"severity": "error", "path": relative, "message": str(exc)})
            for path in sorted((self.root / "tex").rglob("*.tex")):
                relative = path.relative_to(self.root / "tex").as_posix()
                try:
                    doc = TexDocument(relative, read_text(safe_path(self.root, f"tex/{relative}")))
                    self.tex[relative] = doc
                    for message in doc.diagnostics:
                        self.diagnostics.append({"severity": "error", "path": relative, "message": message})
                except (OSError, UnicodeError, WorkspaceError) as exc:
                    self.diagnostics.append({"severity": "error", "path": relative, "message": str(exc)})
            self.edges, self.locations = [], {}
            for node in self.nodes.values():
                for relation in ("uses", "inspired_by"):
                    for link in getattr(node, relation):
                        target = resolve_link(link, node.id, self.nodes)
                        if target:
                            self.edges.append({"source": target, "target": node.id, "kind": relation})
                        else:
                            self.diagnostics.append({"severity": "warning", "path": node.path, "line": node.line, "message": f"链接不存在或不唯一: {link}"})
                if node.tex:
                    path, label = node.tex.rsplit("#", 1) if "#" in node.tex else (node.path.removesuffix(".md"), node.tex)
                    path = path.removesuffix(".tex") + ".tex"
                    doc = self.tex.get(path)
                    if doc and doc.fragment(label) is not None:
                        self.locations[node.id] = (path, label)
                    else:
                        self.diagnostics.append({"severity": "error", "path": node.path, "line": node.line, "message": f"TeX 标签不存在或不唯一: {node.tex}"})
            self.order = sorted(self.locations, key=lambda key: (self.locations[key][0], next(a["start"] for a in self.tex[self.locations[key][0]].anchors if a["label"] == self.locations[key][1])))
            self.graph_index = build_graph_index(self.documents, self.nodes)

    def project(self):
        with self.lock:
            papers = []
            for path, doc in self.tex.items():
                located = [(key, next(a["start"] for a in doc.anchors if a["label"] == label)) for key, (p, label) in self.locations.items() if p == path]
                sections = [{**section, "node_id": next((key for key, offset in sorted(located, key=lambda item: item[1]) if offset >= section["offset"]), None)} for section in doc.sections]
                papers.append({"path": path, "sections": sections, "nodes": [key for key in self.order if self.locations[key][0] == path]})
            return {"name": self.root.name, "nodes": [n.public() for n in self.nodes.values()], "edges": self.edges, "graph": self.graph_index, "papers": papers, "diagnostics": self.diagnostics, "stats": {"nodes": len(self.nodes), "complete": sum(n.status == "complete" for n in self.nodes.values()), "edges": len(self.edges), "papers": len(self.tex)}}

    def detail(self, node_id: str):
        with self.lock:
            if node_id not in self.nodes:
                raise KeyError(node_id)
            node = self.nodes[node_id]
            html = MarkdownIt("commonmark", {"html": False}).render(node.body)
            def replace(match):
                # Match on already escaped HTML: unescape for resolving, escape label again.
                from html import unescape
                raw = unescape(match[0])
                target = resolve_link(raw, node.id, self.nodes)
                label = unescape(match[1]).split("|")[-1]
                if target:
                    return f'<a class="wikilink" href="#node={quote(target, safe="")}">{escape(label)}</a>'
                return f'<span class="unresolved">{escape(label)}</span>'
            html = WIKILINK.sub(replace, html)
            result = {**node.public(), "body_html": html, "formal": [locate_code(self.root, b) for b in node.bindings], "tex_content": None, "previous": None, "next": None}
            if node_id in self.locations:
                path, label = self.locations[node_id]
                doc = self.tex[path]
                source = doc.fragment(label)
                if node_id not in self.render_cache:
                    self.render_cache[node_id] = render_tex(source, doc.preamble)
                rendered, warnings = self.render_cache[node_id]
                anchor = next(a for a in doc.anchors if a["label"] == label)
                result["tex_content"] = {"path": path, "label": label, "line": anchor["line"], "source": source, "html": rendered, "warnings": warnings}
                order = [key for key in self.order if self.locations[key][0] == path]
                i = order.index(node_id)
                result["previous"] = order[i - 1] if i else None
                result["next"] = order[i + 1] if i + 1 < len(order) else None
            result["relations"] = [{"kind": e["kind"], "id": e["source"], "title": self.nodes[e["source"]].title} for e in self.edges if e["target"] == node_id]
            result["backlinks"] = [{"kind": e["kind"], "id": e["target"], "title": self.nodes[e["target"]].title} for e in self.edges if e["source"] == node_id]
            return result

    def document(self, path: str):
        safe = safe_path(self.root, f"blueprint/{path}")
        if safe.suffix != ".md":
            raise WorkspaceError("只允许编辑 Markdown 文件")
        text = read_text(safe)
        return {"path": path, "text": text, "revision": revision(text)}

    def save_document(self, path: str, text: str, expected: str):
        with self.lock:
            safe = safe_path(self.root, f"blueprint/{path}")
            current = self.document(path)
            if current["revision"] != expected:
                raise ConflictError("文件已被其他编辑器修改，请重新载入后合并")
            if len(text.encode("utf-8")) > 5 * 1024 * 1024:
                raise WorkspaceError("Markdown 超过 5 MiB")
            _, diagnostics = parse_markdown(path, text)
            errors = [d["message"] for d in diagnostics if d["severity"] == "error"]
            if errors:
                raise WorkspaceError("；".join(errors))
            fd, temporary = tempfile.mkstemp(prefix=".qprint-", dir=safe.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                    stream.write(text)
                if self.document(path)["revision"] != expected:
                    raise ConflictError("保存期间文件发生变化，请重新载入")
                os.replace(temporary, safe)
            finally:
                Path(temporary).unlink(missing_ok=True)
            self.reload()
            return self.document(path)
