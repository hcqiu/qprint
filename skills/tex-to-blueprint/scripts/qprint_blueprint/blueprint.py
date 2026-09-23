from dataclasses import asdict, dataclass, field
import hashlib
import re

import yaml

from .paths import WorkspaceError

KINDS = {"definition", "lemma", "theorem", "conjecture", "proof", "other"}
STATUSES = {"not_started", "in_progress", "complete"}
LANGUAGES = ("lean", "agda", "coq")
WIKILINK = re.compile(r"\[\[([^\]\n]+)\]\]")


def revision(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Node:
    id: str
    title: str
    path: str
    line: int
    body: str
    kind: str = "other"
    status: str = "not_started"
    tex: str | None = None
    uses: list[str] = field(default_factory=list)
    inspired_by: list[str] = field(default_factory=list)
    bindings: list[dict] = field(default_factory=list)

    def public(self):
        return asdict(self)


def parse_markdown(path: str, text: str) -> tuple[list[Node], list[dict]]:
    lines = text.splitlines(keepends=True)
    headings, fence, frontmatter = [], None, False
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == "---":
            frontmatter = True
            continue
        if frontmatter:
            if line.strip() == "---":
                frontmatter = False
            continue
        m = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if m:
            if fence is None:
                fence = m[1]
            elif m[1][0] == fence[0] and len(m[1]) >= len(fence) and not m[2].strip():
                fence = None
            continue
        if fence is None and (m := re.match(r"^#\s+(.+?)\s*#*\s*$", line)):
            headings.append((i, m[1]))
    nodes, diagnostics, seen = [], [], set()
    for index, (start, title) in enumerate(headings):
        try:
            if title in seen or any(s in title for s in ("#", "|", "]]")):
                raise WorkspaceError(f"重复或不合法的节点标题: {title}")
            seen.add(title)
            end = headings[index + 1][0] if index + 1 < len(headings) else len(lines)
            body = "".join(lines[start + 1:end]).strip()
            metadata = {}
            if body.startswith("```qprint"):
                m = re.match(r"^```qprint\s*\n(.*?)\n```(?:\n|$)", body, re.S)
                if not m:
                    raise WorkspaceError("qprint 元数据围栏没有闭合")
                metadata = yaml.safe_load(m[1]) or {}
                if not isinstance(metadata, dict):
                    raise WorkspaceError("qprint 元数据必须是 YAML mapping")
                body = body[m.end():].strip()
            kind, status = metadata.get("kind", "other"), metadata.get("status", "not_started")
            if kind not in KINDS or status not in STATUSES:
                raise WorkspaceError("kind 或 status 值不合法")
            tex = metadata.get("tex")
            if tex is not None and (not isinstance(tex, str) or not tex.strip()):
                raise WorkspaceError("tex 必须是非空字符串")
            relations = {}
            for key in ("uses", "inspired_by"):
                value = metadata.get(key, [])
                if not isinstance(value, list) or any(not isinstance(v, str) or not WIKILINK.fullmatch(v) for v in value):
                    raise WorkspaceError(f"{key} 必须是加引号的 wikilink 数组")
                relations[key] = value
            bindings = []
            for language in LANGUAGES:
                values = metadata.get(language, [])
                if isinstance(values, (str, dict)):
                    values = [values]
                if not isinstance(values, list):
                    raise WorkspaceError(f"{language} 必须是绑定或绑定数组")
                for value in values:
                    binding = {"declaration": value} if isinstance(value, str) else value
                    if not isinstance(binding, dict) or not isinstance(binding.get("declaration"), str) or not binding["declaration"].strip():
                        raise WorkspaceError("代码绑定需要 declaration")
                    if set(binding) - {"declaration", "file", "lines", "url"}:
                        raise WorkspaceError("代码绑定只接受 declaration、file、lines、url 字段")
                    for key in ("file", "url"):
                        if key in binding and not isinstance(binding[key], str):
                            raise WorkspaceError(f"{key} 必须是字符串")
                    if "url" in binding and not binding["url"].startswith("https://"):
                        raise WorkspaceError("代码外链必须使用 HTTPS")
                    if "lines" in binding:
                        bounds = binding["lines"]
                        if not isinstance(bounds, list) or len(bounds) != 2 or any(type(n) is not int for n in bounds) or not 1 <= bounds[0] <= bounds[1]:
                            raise WorkspaceError("lines 必须是 [起始行, 结束行]，行号从 1 开始")
                    bindings.append({**binding, "language": language})
            nodes.append(Node(f"{path.removesuffix('.md')}#{title}", title, path, start + 1, body, kind, status, tex, bindings=bindings, **relations))
            unknown = set(metadata) - {"kind", "status", "tex", "uses", "inspired_by", *LANGUAGES}
            if unknown:
                diagnostics.append({"severity": "warning", "path": path, "line": start + 1, "message": f"未识别字段: {', '.join(sorted(map(str, unknown)))}"})
        except (ValueError, TypeError, yaml.YAMLError) as exc:
            diagnostics.append({"severity": "error", "path": path, "line": start + 1, "message": str(exc)})
    return nodes, diagnostics


def resolve_link(link: str, current: str, nodes: dict[str, Node]) -> str | None:
    target = link.removeprefix("[[").removesuffix("]]").split("|", 1)[0]
    if "#" not in target:
        return None
    path, title = target.split("#", 1)
    path = path.removesuffix(".md")
    if not path:
        path = current.split("#", 1)[0]
    exact = f"{path}#{title}"
    if exact in nodes:
        return exact
    if "/" not in path:
        matches = [key for key in nodes if key.rsplit("/", 1)[-1] == exact]
        if len(matches) == 1:
            return matches[0]
    return None


def resolve_tex_use(label: str, current: Node, nodes: dict[str, Node]) -> str | None:
    """Prefer explicit IDs, then same-paper anchors, declared edges, unique aliases."""
    if "#" in label:
        return resolve_link(label, current.id, nodes)

    def binding(node):
        if not node.tex:
            return None, None
        path, anchor = node.tex.rsplit("#", 1) if "#" in node.tex else (node.path.removesuffix(".md"), node.tex)
        return path.removesuffix(".tex"), anchor

    matches = [n for n in nodes.values() if n.title == label or binding(n)[1] == label]
    paper = binding(current)[0]
    local = [n for n in matches if paper is not None and binding(n)[0] == paper]
    declared = {resolve_link(link, current.id, nodes) for link in current.uses}
    candidates = local or [n for n in matches if n.id in declared] or matches
    return candidates[0].id if len(candidates) == 1 else None
