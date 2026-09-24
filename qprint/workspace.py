from html import escape
from collections import Counter
from pathlib import Path
import os
import tempfile
from threading import RLock
from urllib.parse import quote

from markdown_it import MarkdownIt

from .blueprint import WIKILINK, parse_markdown, resolve_link, resolve_tex_use, revision
from .formal import locate_code
from .graph_index import build_graph_index
from .paths import WorkspaceError, read_text, safe_path
from .tex import TexDocument, render_tex, tex_commands, merge_tex_warnings


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
            self.tex_label_cache = {}
            self.bibliography_cache = {}
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
                        self.diagnostics.append({"severity": "error", "path": node.path, "line": node.line, "message": f"TeX 标签不存在: {node.tex}"})
            self.order = sorted(self.locations, key=lambda key: (self.locations[key][0], next(a["start"] for a in self.tex[self.locations[key][0]].anchors if a["label"] == self.locations[key][1])))
            self.graph_index = build_graph_index(self.documents, self.nodes)

    def project(self):
        with self.lock:
            papers = []
            for path, doc in self.tex.items():
                located = [(key, next(a["start"] for a in doc.anchors if a["label"] == label)) for key, (p, label) in self.locations.items() if p == path]
                sections = [{**section, "node_id": next((key for key, offset in sorted(located, key=lambda item: item[1]) if offset >= section["offset"]), None)} for section in doc.sections]
                papers.append({"path": path, "sections": sections, "nodes": [key for key in self.order if self.locations[key][0] == path],
                               "has_bibliography": bool(self.bibliography_files(path))})
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
                    try:
                        references = {value: target for value in doc.annotations(label)["uses"]
                                      if (target := resolve_tex_use(value, node, self.nodes))}
                    except ValueError:
                        references = {}
                    bibliography = self.bibliography(path)
                    rendered, warnings = render_tex(source, doc.preamble, references,
                                                    labels=self.tex_labels(path, node_id),
                                                    bibliography=bibliography["citations"])
                    self.render_cache[node_id] = rendered, merge_tex_warnings([*bibliography["warnings"], *warnings])
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

    def bibliography_files(self, path: str):
        """Only consider BBL files beside this paper, never another project."""
        if path not in self.tex:
            raise KeyError(path)
        folder = safe_path(self.root, "tex/" + path).parent
        return sorted(p for p in folder.iterdir() if p.suffix.lower() == ".bbl" and p.is_file())

    def bibliography(self, path: str):
        with self.lock:
            if path not in self.tex:
                raise KeyError(path)
            if path in self.bibliography_cache:
                return self.bibliography_cache[path]
            files = self.bibliography_files(path)
            data = {"path": path, "bbl": None, "entries": [], "html": "", "warnings": [], "citations": None}
            matching = [p for p in files if p.stem == Path(path).stem]
            chosen = matching[0] if len(matching) == 1 else files[0] if len(files) == 1 else None
            if chosen is None:
                if files:
                    data["warnings"].append("同目录有多个 BBL，且没有与 TeX 同名的文件；引用保留原文。")
            else:
                try:
                    relative = chosen.relative_to(self.root).as_posix()
                    source = read_text(safe_path(self.root, relative))
                    parsed, warnings = render_tex(source, bibliography_only=True)
                    data.update(bbl=relative.removeprefix("tex/"), warnings=warnings)
                    if isinstance(parsed, dict):
                        entries = parsed["entries"]
                        counts = Counter(entry["key"] for entry in entries)
                        data["entries"] = entries
                        if entries:
                            data["citations"] = {"path": path, "entries": {
                                entry["key"]: {"label": entry["label"]} for entry in entries if counts[entry["key"]] == 1}}
                        else:
                            data["html"] = f'<pre class="tex-fallback">{escape(source)}</pre>'
                    else:
                        data["html"] = parsed
                except (OSError, UnicodeError, WorkspaceError) as exc:
                    data["warnings"].append(f"无法读取 BBL，引用保留原文: {exc}")
            self.bibliography_cache[path] = data
            return data

    def tex_labels(self, path: str, current_id: str):
        """Resolve ordinary LaTeX labels within their source paper, independently of uses."""
        if path not in self.tex_label_cache:
            doc = self.tex[path]
            start = len(doc.preamble)
            body = doc.source[start:min([doc.body_end, *doc.bibliography_offsets])]
            numbers, _ = render_tex(body, doc.preamble, index_only=True)
            if not isinstance(numbers, dict):
                numbers = {}
            owners = {}
            for node_id, (node_path, binding) in self.locations.items():
                if node_path != path:
                    continue
                try:
                    for command in tex_commands(doc.fragment(binding), {"label"}):
                        owners.setdefault(command["value"], set()).add(node_id)
                except ValueError:
                    continue
            targets = {}
            try:
                for command in tex_commands(body, {"label"}):
                    label = command["value"]
                    if label in targets:
                        targets[label] = {"ambiguous": True}
                        continue
                    candidates = sorted(owners.get(label, []))
                    targets[label] = {"text": numbers.get(label, {}).get("text", label),
                                      "path": path, "owners": candidates,
                                      "line": doc.source.count("\n", 0, start + command["start"]) + 1}
            except ValueError:
                pass
            self.tex_label_cache[path] = targets
        result = {}
        for label, target in self.tex_label_cache[path].items():
            target = dict(target)
            owners = target.pop("owners", [])
            if current_id in owners:
                target["local"] = True
            elif len(owners) == 1:
                target["node"] = owners[0]
            result[label] = target
        return result

    def document(self, path: str):
        safe = safe_path(self.root, f"blueprint/{path}")
        if safe.suffix != ".md":
            raise WorkspaceError("只允许编辑 Markdown 文件")
        text = read_text(safe)
        return {"path": path, "text": text, "revision": revision(text)}

    def verification_bindings(self, node_id: str | None = None, language: str | None = None):
        """Snapshot bindings only; compiler work must run outside the index lock."""
        from copy import deepcopy
        with self.lock:
            if node_id is not None and node_id not in self.nodes:
                raise KeyError(node_id)
            nodes = [self.nodes[node_id]] if node_id is not None else self.nodes.values()
            return [dict(deepcopy(binding), node_id=node.id) for node in nodes
                    for binding in node.bindings if language is None or binding["language"] == language]

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
