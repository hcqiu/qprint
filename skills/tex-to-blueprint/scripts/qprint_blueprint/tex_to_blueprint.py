"""Deterministic annotation extraction; mathematical annotation/review stays with the agent."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import tempfile

import yaml

from .blueprint import Node, parse_markdown, resolve_link, resolve_tex_use
from .graph_index import build_graph_index
from .paths import WorkspaceError, read_text, safe_path
from .tex import TexDocument, mask_comments, render_tex


def catalog(root: Path):
    documents, nodes = {}, {}
    for file in sorted((root / "blueprint").rglob("*.md")):
        relative = file.relative_to(root / "blueprint").as_posix()
        text = read_text(safe_path(root, f"blueprint/{relative}"))
        parsed, diagnostics = parse_markdown(relative, text)
        if any(d["severity"] == "error" for d in diagnostics):
            raise WorkspaceError(f"已有 Blueprint 无法解析: {relative}")
        documents[relative] = text
        nodes.update((node.id, node) for node in parsed)
    return documents, nodes


def search(root: Path, query: str, limit: int = 30):
    """Read only Markdown; do not inspect other projects' TeX or proof code."""
    _, nodes = catalog(root)
    return [{"id": node.id, "tex": node.tex, "description": node.body[:500]}
            for node in nodes.values()
            if query.casefold() in f"{node.id}\n{node.tex}\n{node.body}".casefold()][:limit]


def _slug(title: str) -> str:
    value = re.sub(r"[^\w-]+", "-", title, flags=re.UNICODE).strip("-_")[:60]
    return value or "section"


def validate(root: Path, project: str, render_limit: int = 3):
    """Check one project; inspect other projects only through Markdown."""
    root = root.resolve()
    if not safe_path(root, f"blueprint/{project}").is_dir():
        raise WorkspaceError("Blueprint 项目目录不存在")
    documents, nodes = catalog(root)
    selected = [n for n in nodes.values() if n.path.startswith(project + "/")]
    diagnostics, renders, edges, tex_cache, bound = [], [], [], {}, set()
    for node in selected:
        for link in node.uses:
            target = resolve_link(link, node.id, nodes)
            if target:
                edges.append((target, node.id))
            else:
                diagnostics.append(f"{node.id}: 未解析依赖 {link}")
        if not node.tex:
            diagnostics.append(f"{node.id}: 无 TeX 绑定")
            continue
        path, label = node.tex.rsplit("#", 1) if "#" in node.tex else (node.path[:-3], node.tex)
        path = path.removesuffix(".tex") + ".tex"
        if path not in tex_cache:
            source = safe_path(root, f"tex/{path}")
            if not source.is_file():
                diagnostics.append(f"{node.id}: TeX 文件不存在: {path}")
                continue
            tex_cache[path] = TexDocument(path, read_text(source))
            diagnostics.extend(f"{path}: {message}" for message in tex_cache[path].diagnostics)
        doc = tex_cache[path]
        fragment = doc.fragment(label)
        if fragment is None:
            diagnostics.append(f"{node.id}: TeX 标签不存在: {label}")
            continue
        bound.add((path, label))
        annotations = doc.annotations(label)
        references = {value: resolved for value in annotations["uses"]
                      if (resolved := resolve_tex_use(value, node, nodes))}
        declared = {resolve_link(link, node.id, nodes) for link in node.uses}
        for value in annotations["uses"]:
            if value not in references:
                diagnostics.append(f"{node.id}: TeX 依赖未解析: {value}")
            elif references[value] not in declared:
                diagnostics.append(f"{node.id}: Markdown 遗漏 TeX 依赖: {value}")
        if not annotations["descriptions"]:
            diagnostics.append(f"{node.id}: 缺少 bpdesc 描述")
        if len(renders) < render_limit:
            html, warnings = render_tex(fragment, doc.preamble, references)
            renders.append({"node": node.id, "warnings": warnings,
                            "fallback": 'class="tex-fallback"' in html,
                            "inline_links": html.count('class="wikilink tex-use"'), "html": html})
    for path, doc in tex_cache.items():
        for label in dict.fromkeys(a["label"] for a in doc.anchors):
            if (path, label) not in bound:
                diagnostics.append(f"{path}#{label}: 标注尚无 Blueprint 节点")
    return {"project": project, "files": sum(p.startswith(project + "/") for p in documents),
            "nodes": len(selected), "edges": len(edges), "diagnostics": diagnostics,
            "renders": renders, "semantic_review": "agent_required"}


def _kind(fragment: str, preamble: str) -> str:
    aliases = dict(re.findall(r"\\newtheorem\*?\s*\{([^{}]+)\}(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}", mask_comments(preamble)))
    for match in re.finditer(r"\\begin\{([^{}]+)\}", mask_comments(fragment)):
        name = aliases.get(match[1], match[1]).casefold()
        if name in {"definition", "lemma", "theorem", "conjecture", "proof"}:
            return name
        if name in {"proposition", "corollary"}:
            return "theorem"
    return "other"


def generate(root: Path, sources: list[str], dest: str, *, title: str,
             authors: list[str], year: str, keywords: list[str],
             dependency_map: dict[str, str] | None = None, dry_run: bool = False):
    """Write one draft per subsection plus an index, without overwriting any project.

    Repeated anchors belong to their first subsection and collect all fragments.
    Section-level content outside a subsection gets a separate draft, never dropped.
    """
    root = root.resolve()
    target = safe_path(root, f"blueprint/{dest}")
    if target.exists():
        raise WorkspaceError("目标项目已存在；请 review 现有文件或选择新的草稿目录")
    if any(c in dest for c in "#[]"):
        raise WorkspaceError("项目路径不能包含 # 或方括号")
    documents, existing = catalog(root)
    diagnostics, drafts, generated, annotations = [], {}, {}, {}
    overrides = dependency_map or {}
    if not isinstance(overrides, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in overrides.items()):
        raise WorkspaceError("dependency-map 必须是标签到节点 ID 的 JSON 对象")
    for file_number, relative in enumerate(dict.fromkeys(sources), 1):
        path = safe_path(root, f"tex/{relative}")
        if path.suffix != ".tex" or "#" in relative:
            raise WorkspaceError("源文件必须是 tex/ 下的 .tex 相对路径，且不能含 #")
        doc = TexDocument(relative, read_text(path))
        if doc.diagnostics:
            raise WorkspaceError(f"{relative}: {'; '.join(doc.diagnostics)}")
        if not doc.anchors:
            diagnostics.append(f"{relative}: 没有 bpnode 标注；需要 agent 标注")
        if re.search(r"\\(?:input|include)\b", mask_comments(doc.source[ len(doc.preamble):])):
            diagnostics.append(f"{relative}: 存在 input/include；不会执行 TeX，请将相关正文文件分别通过 --tex 传入")
        # Only chapter/section/subsection split files. Subsubsections stay inside.
        boundaries = [{"title": "Preamble content", "offset": -1, "level": -1},
                      *(s for s in doc.sections if s["level"] <= 2)]
        groups, seen_labels = defaultdict(list), set()
        for anchor in doc.anchors:
            if anchor["label"] in seen_labels:
                continue
            seen_labels.add(anchor["label"])
            group = max(i for i, section in enumerate(boundaries) if section["offset"] < anchor["start"])
            groups[group].append(anchor)
        for group, section in enumerate(boundaries):
            if group not in groups and section["level"] != 2:
                continue
            filename = f"{file_number:02d}-{group:03d}-{_slug(section['title'])}.md"
            md_path = f"{dest}/{filename}"
            drafts[md_path] = []
            for anchor in groups[group]:
                label = anchor["label"]
                node = Node(f"{md_path[:-3]}#{label}", label, md_path, 1, "",
                            tex=f"{relative}#{label}")
                fragment = doc.fragment(label)
                node.kind = _kind(fragment, doc.preamble)
                generated[node.id] = node
                annotations[node.id] = doc.annotations(label)
                drafts[md_path].append(node)
    if not generated:
        raise WorkspaceError("没有可生成的节点；请先完成 TeX 标注")
    all_nodes = {**existing, **generated}
    for node in generated.values():
        info = annotations[node.id]
        node.body = "\n\n".join(info["descriptions"])
        for value in info["uses"]:
            if value in overrides:
                resolved = resolve_link(overrides[value], node.id, all_nodes)
                if resolved is None:
                    raise WorkspaceError(f"dependency-map 目标不存在: {value} -> {overrides[value]}")
            else:
                resolved = resolve_tex_use(value, node, all_nodes)
            if resolved is None:
                diagnostics.append(f"{node.tex}: 依赖不存在或不唯一: {value}")
                # Preserve the exact annotation for review, without inventing a target.
                unresolved = value if "#" in value else f"#{value}"
                node.uses.append(f"[[{unresolved}]]" if not unresolved.startswith("[[") else unresolved)
            else:
                node.uses.append(f"[[{resolved}]]")
        node.uses = list(dict.fromkeys(node.uses))
    output = {}
    for md_path, nodes in drafts.items():
        sections = []
        for node in nodes:
            metadata = yaml.safe_dump({"kind": node.kind, "status": node.status,
                                       "tex": node.tex, "uses": node.uses}, allow_unicode=True, sort_keys=False).strip()
            # Keep arbitrary description text as prose, not accidental node headings.
            body = re.sub(r"(?m)^#(?=\s)", r"\\#", node.body)
            sections.append(f"# {node.title}\n\n```qprint\n{metadata}\n```\n\n{body}\n")
        output[md_path] = "\n".join(sections) if sections else "<!-- 此 subsection 尚无节点；待 review。 -->\n"
        parsed, errors = parse_markdown(md_path, output[md_path])
        if any(d["severity"] == "error" for d in errors) or len(parsed) != len(nodes):
            raise WorkspaceError(f"生成 Markdown 无法解析: {md_path}")
    graph = build_graph_index(documents, existing)
    projects = {p["id"]: p for p in graph["projects"]}
    dependencies = set()
    for node in generated.values():
        for link in node.uses:
            resolved = resolve_link(link, node.id, all_nodes)
            if resolved in existing:
                project = graph["node_projects"][resolved]
                dependencies.add(projects[project]["index_path"] or existing[resolved].path)
    index_path = f"{dest}/index.md"
    frontmatter = yaml.safe_dump({"title": title, "authors": authors, "year": str(year), "keywords": keywords},
                                allow_unicode=True, sort_keys=False).strip()
    output[index_path] = f"---\n{frontmatter}\n---\n\n## Blueprint 索引\n\n" + "\n".join(
        f"- [[{path}]]" for path in output) + "\n\n## 依赖项目\n\n" + (
        "\n".join(f"- [[{path}]]" for path in sorted(dependencies)) or "暂无已解析的外部项目依赖。") + "\n"
    report = {"files": list(output), "nodes": len(generated), "diagnostics": diagnostics,
              "review_required": True, "dry_run": dry_run}
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".qprint-blueprint-", dir=target.parent) as temp:
            stage = Path(temp) / "project"
            stage.mkdir()
            for relative, content in output.items():
                (stage / Path(relative).name).write_text(content, encoding="utf-8")
            (stage / "generation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if target.exists():
                raise WorkspaceError("生成期间目标已被创建")
            stage.rename(target)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    find = sub.add_parser("search", help="只检索已有 Blueprint Markdown")
    find.add_argument("--workspace", type=Path, required=True)
    find.add_argument("--query", required=True)
    find.add_argument("--limit", type=int, default=30)
    create = sub.add_parser("generate", help="从已标注 TeX 生成待 review 的 Blueprint")
    create.add_argument("--workspace", type=Path, required=True)
    create.add_argument("--tex", action="append", required=True)
    create.add_argument("--dest", required=True)
    create.add_argument("--title", required=True)
    create.add_argument("--author", action="append", required=True)
    create.add_argument("--year", required=True)
    create.add_argument("--keyword", action="append", default=[])
    create.add_argument("--dependency-map", type=Path)
    create.add_argument("--dry-run", action="store_true")
    check = sub.add_parser("validate", help="校验当前项目并抽查渲染")
    check.add_argument("--workspace", type=Path, required=True)
    check.add_argument("--project", required=True)
    check.add_argument("--render-limit", type=int, default=3)
    args = parser.parse_args(argv)
    try:
        if args.command == "search":
            if not 1 <= args.limit <= 200:
                raise WorkspaceError("limit 必须在 1 到 200 之间")
            result = search(args.workspace, args.query, args.limit)
        elif args.command == "validate":
            if not 0 <= args.render_limit <= 1000:
                raise WorkspaceError("render-limit 必须在 0 到 1000 之间")
            result = validate(args.workspace, args.project, args.render_limit)
        else:
            mapping = json.loads(read_text(args.dependency_map)) if args.dependency_map else None
            result = generate(args.workspace, args.tex, args.dest, title=args.title, authors=args.author,
                              year=args.year, keywords=args.keyword, dependency_map=mapping, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if args.command == "validate" and result["diagnostics"]:
            return 1
    except (ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
