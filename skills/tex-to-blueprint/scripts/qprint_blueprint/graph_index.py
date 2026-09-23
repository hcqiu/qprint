"""Read-only graph projections over ordinary Markdown files and folders.

No project/milestone declarations are required in the stored node schema.
"""
from collections import defaultdict
from pathlib import PurePosixPath
import posixpath
import re
from urllib.parse import unquote

from markdown_it import MarkdownIt

from .blueprint import WIKILINK

EXTERNAL = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def resolve_document(reference: str, current: str, documents: dict) -> str | None:
    target = reference.removeprefix("[[").removesuffix("]]").split("|", 1)[0].split("#", 1)[0]
    if not target:
        return current
    if EXTERNAL.match(target) or target.startswith(("/", "\\")):
        return None
    target = unquote(target)
    if not target.endswith(".md"):
        target += ".md"
    if target in documents:
        return target
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(current), target))
    if relative in documents:
        return relative
    if "/" not in target:
        matches = [path for path in documents if posixpath.basename(path) == target]
        if len(matches) == 1:
            return matches[0]
    return None


def document_references(text: str):
    """Include node metadata and prose links, but exclude example code/comments."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    for token in MarkdownIt("commonmark").parse(text):
        if token.type == "fence" and token.info.strip() == "qprint":
            yield from (m[0] for m in WIKILINK.finditer(token.content))
        if token.type == "inline":
            for child in token.children or []:
                if child.type == "text":
                    yield from (m[0] for m in WIKILINK.finditer(child.content))
                elif child.type == "link_open":
                    href = child.attrGet("href") or ""
                    if not EXTERNAL.match(href) and not href.startswith("//"):
                        yield unquote(href)


def aggregate_status(nodes):
    statuses = {node.status for node in nodes}
    if statuses == {"complete"}:
        return "complete"
    if statuses and statuses != {"not_started"}:
        return "in_progress"
    return "not_started"


def build_graph_index(documents: dict[str, str], nodes: dict) -> dict:
    indexes = {}
    for path in sorted(documents):
        file = PurePosixPath(path)
        folder = file.parent.as_posix()
        # Prefer the named index when a folder also contains index.md.
        if file.stem == file.parent.name:
            indexes[folder] = path
        elif file.name.casefold() == "index.md":
            indexes.setdefault(folder, path)

    file_projects = {}
    grouped_files = defaultdict(list)
    grouped_nodes = defaultdict(list)
    for node in nodes.values():
        grouped_nodes[node.path].append(node)
    for path in sorted(documents):
        parent = PurePosixPath(path).parent
        project = next((folder.as_posix() for folder in (parent, *parent.parents) if folder.as_posix() in indexes), parent.as_posix())
        file_projects[path] = project
        grouped_files[project].append(path)

    files = []
    for path in sorted(documents):
        members = grouped_nodes[path]
        files.append({"id": path, "title": PurePosixPath(path).stem, "path": path,
                      "project_id": file_projects[path], "node_ids": [n.id for n in members],
                      "status": aggregate_status(members), "kind": "other",
                      "body": f"{path}\n{len(members)} 个 blueprint 节点"})
    projects = []
    for folder, paths in sorted(grouped_files.items()):
        members = [node for path in paths for node in grouped_nodes[path]]
        projects.append({"id": folder, "title": PurePosixPath(folder).name if folder != "." else "blueprint 根目录",
                         "path": folder, "index_path": indexes.get(folder), "file_ids": paths,
                         "node_ids": [n.id for n in members], "kind": "other",
                         "status": aggregate_status(members),
                         "body": f"{folder}\n{len(paths)} 个 Markdown 文件 · {len(members)} 个 blueprint 节点"})

    file_pairs = set()
    for path, text in documents.items():
        for reference in document_references(text):
            target = resolve_document(reference, path, documents)
            if target and target != path:
                # Same arrow convention as the node graph: referenced -> referring.
                file_pairs.add((target, path))
    project_pairs = defaultdict(int)
    for source, target in file_pairs:
        a, b = file_projects[source], file_projects[target]
        if a != b:
            project_pairs[a, b] += 1
    return {"files": files, "projects": projects, "file_projects": file_projects,
            "node_projects": {n.id: file_projects[n.path] for n in nodes.values()},
            "file_edges": [{"source": a, "target": b, "kind": "reference"} for a, b in sorted(file_pairs)],
            "project_edges": [{"source": a, "target": b, "kind": "reference", "count": count}
                              for (a, b), count in sorted(project_pairs.items())]}
