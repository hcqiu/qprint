"""Deterministic annotation extraction; mathematical annotation/review stays with the agent."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import posixpath
import re
import tempfile

import yaml

from .blueprint import Node, parse_markdown, resolve_link, resolve_tex_use
from .graph_index import build_graph_index
from .paths import WorkspaceError, read_text, safe_path
from .tex import TexDocument, mask_comments, render_tex, tex_commands
from .tex_support import compact_label_source


def _environment_names(sources, candidates):
    """Ask the bounded renderer for headings in the loaded paper's input order.

    Probes and include expansion exist only in memory, never in saved TeX.
    No file outside the explicitly supplied source mapping is read.
    """
    marked = dict(sources)
    keys, values, diagnostics = {}, defaultdict(set), []
    for path, blocks in candidates.items():
        edits = []
        for block in blocks:
            key = f"qprint-auto-name-{len(keys)}"
            keys[key] = (path, block["start"])
            edits.append((block["begin_end"], rf"\qprintnameprobe{{{key}}}"))
        for offset, insertion in reversed(edits):
            marked[path] = marked[path][:offset] + insertion + marked[path][offset:]
    if not keys:
        return {}, []
    children, includes = set(), {}
    for path, source in marked.items():
        includes[path] = []
        for command in tex_commands(source, {"input", "include"}):
            value = command["value"]
            target = None
            if value and not value.startswith("/") and not any(c in value for c in "\\{}:#"):
                value = value if value.endswith(".tex") else value + ".tex"
                folder = posixpath.dirname(path)
                while True:
                    possible = posixpath.normpath(posixpath.join(folder, value))
                    if possible in marked:
                        target = possible
                        break
                    if not folder:
                        break
                    folder = posixpath.dirname(folder)
            includes[path].append((command, target))
            if target:
                children.add(target)

    def expand(path, active):
        if path in active or len(active) >= 32:
            raise ValueError(f"input/include 循环或嵌套过深: {path}")
        source = marked[path]
        for command, target in reversed(includes[path]):
            if target is None:
                raise ValueError(f"{path}: 缺少用于计算编号的 input/include: {command['value']}")
            source = source[:command["start"]] + expand(target, active | {path}) + source[command["end"]:]
            if len(source) > 2_000_000:
                raise ValueError("计算环境名称的合并源码超过 2 MiB")
        return source

    roots = sorted(set(marked) - children)
    if not roots:
        return {}, ["input/include 存在循环，无法确定环境显示名称"]
    for root in roots:
        try:
            source = expand(root, set())
            if not any(key in source for key in keys):
                continue
            doc = TexDocument(root, source)
            begin = next((c for c in tex_commands(source, {"begin"}) if c["value"] == "document"), None)
            preamble = source[:begin["start"]] if begin else ""
            body = source[begin["end"] if begin else 0: min([doc.body_end, *doc.bibliography_offsets])]
            # Preserve counter-bearing structure without expanding figures or
            # arbitrary paper content just to obtain a heading.
            body = compact_label_source(mask_comments(body), preamble)
            names, warnings = render_tex(body, preamble, index_only=True, environment_names=True)
            if not isinstance(names, dict):
                raise ValueError("; ".join(warnings) or "环境显示名称解析失败")
            for key, name in names.items():
                if key in keys:
                    values[keys[key]].add(name)
        except ValueError as exc:
            diagnostics.append(f"{root}: {exc}")
    return {key: next(iter(names)) for key, names in values.items() if len(names) == 1}, diagnostics


def annotate_sources(sources: dict[str, str]):
    """Annotate literal environments, then resolve explicit refs across all files.

    Keep nested environments in their enclosing node so fragments stay balanced.
    Unlabelled blocks use their rendered heading; proofs are skipped. Existing manual
    anchors win; comments, verbatim and the document preamble are left alone.
    """
    output, diagnostics, all_spans, candidates = {}, [], {}, {}
    marked_nodes = marked_references = 0
    for path, source in sources.items():
        doc = TexDocument(path, source)
        if doc.diagnostics:
            raise WorkspaceError(f"{path}: {'; '.join(doc.diagnostics)}")
        begin = next((c for c in tex_commands(source, {"begin"}) if c["value"] == "document"), None)
        start = begin["end"] if begin else 0
        stop = min([doc.body_end, *doc.bibliography_offsets])
        commands = list(tex_commands(source[start:stop], {"begin", "end", "label", "chapter", "section", "subsection", "subsubsection"}))
        stack, spans = [], []
        boundary = start
        for command in commands:
            offset, end = start + command["start"], start + command["end"]
            name, value = command["name"], command["value"]
            if name == "begin":
                stack.append({"name": value, "start": offset, "begin_end": end, "boundary": boundary, "labels": []})
            elif name == "label":
                for block in stack:
                    block["labels"].append(value)
            elif name == "end":
                if not stack or stack[-1]["name"] != value:
                    raise WorkspaceError(f"{path}: begin/end 不匹配: {value}")
                block = stack.pop()
                # Only outer blocks can form independent balanced fragments.
                if not stack:
                    spans.append({**block, "end": end})
                boundary = end
            else:
                boundary = end
        if stack:
            raise WorkspaceError(f"{path}: begin/end 未闭合: {stack[-1]['name']}")
        all_spans[path] = spans
        candidates[path] = [block for block in spans if not block["labels"]
                            and block["name"].rstrip("*") != "proof"
                            and not any(block["boundary"] <= a["start"] < block["end"] for a in doc.anchors)]
    names, name_diagnostics = _environment_names(sources, candidates)
    diagnostics.extend(name_diagnostics)
    for path, source in sources.items():
        doc = TexDocument(path, source)
        reserved = {a["label"] for a in doc.anchors} | {b["labels"][0] for b in all_spans[path] if b["labels"]}
        edits = []
        for block in all_spans[path]:
            if block["name"].rstrip("*") == "proof":
                continue
            if any(block["boundary"] <= a["start"] < block["end"] for a in doc.anchors):
                continue
            label = block["labels"][0] if block["labels"] else names.get((path, block["start"]))
            if not label:
                diagnostics.append(f"{path}: {block['name']} 环境无 label 且无法确定唯一显示名称，留待 agent 标注")
                continue
            if not block["labels"]:
                base, number = label, 2
                while label in reserved:
                    label = f"{base} ({number})"
                    number += 1
                reserved.add(label)
            if any(c in label for c in "{}\n#|\\") or "]]" in label or not label:
                diagnostics.append(f"{path}: 无法用 label 生成节点: {label!r}")
                continue
            edits.append((block["boundary"], f"\n\\bpnode{{{label}}}\n"))
            marked_nodes += 1
        for offset, insertion in reversed(edits):
            source = source[:offset] + insertion + source[offset:]
        output[path] = source

    # Associate every label, including equations inside proofs, with its node.
    owners = defaultdict(set)
    has_anchors = any(TexDocument(path, source).anchors for path, source in output.items())
    for path, source in output.items():
        doc = TexDocument(path, source)
        for label in dict.fromkeys(a["label"] for a in doc.anchors):
            for part in doc.fragments(label):
                for command in tex_commands(part, {"label"}):
                    owners[command["value"]].add((path, label))
    for path, source in output.items():
        doc = TexDocument(path, source)
        begin = next((c for c in tex_commands(source, {"begin"}) if c["value"] == "document"), None)
        start = begin["end"] if begin else 0
        edits = []
        for command in tex_commands(source[start:doc.body_end], {"ref", "eqref", "cref", "Cref", "autoref"}):
            targets = []
            for value in command["value"].split(","):
                choices = owners.get(value.strip(), set())
                local = {item for item in choices if item[0] == path}
                choices = local or choices
                if len(choices) == 1:
                    target_path, label = next(iter(choices))
                    targets.append(label if target_path == path else f"{target_path}#{label}")
            end = start + command["end"]
            if targets and not re.match(r"\s*\\uses\s*\{", mask_comments(source[end:])):
                edits.append((end, "\\uses{" + ", ".join(dict.fromkeys(targets)) + "}"))
                marked_references += len(set(targets))
        for offset, insertion in reversed(edits):
            source = source[:offset] + insertion + source[offset:]
        # No-op macros preserve the original printed paper when compiled.
        if has_anchors:
            begin = next((c for c in tex_commands(source, {"begin"}) if c["value"] == "document"), None)
            if begin:
                macros = "".join(f"\\providecommand{{\\{name}}}[1]{{}}\n" for name in ("bpnode", "bpdesc", "uses")
                                 if not re.search(r"\\(?:providecommand|newcommand|renewcommand)\*?\s*\{?\\" + name + r"\b", mask_comments(source[:begin["start"]])))
                source = source[:begin["start"]] + macros + source[begin["start"]:]
        output[path] = source
    return output, {"marked_nodes": marked_nodes, "marked_references": marked_references,
                    "diagnostics": diagnostics, "review_required": True}


def annotate(root: Path, sources: list[str], *, dry_run: bool = False):
    root = root.resolve()
    paths = {}
    for relative in dict.fromkeys(sources):
        path = safe_path(root, f"tex/{relative}")
        if path.suffix != ".tex" or "#" in relative:
            raise WorkspaceError("源文件必须是 tex/ 下的 .tex 相对路径，且不能含 #")
        paths[relative] = path
    output, report = annotate_sources({relative: read_text(path) for relative, path in paths.items()})
    if not dry_run:
        for relative, source in output.items():
            paths[relative].write_text(source, encoding="utf-8")
    return {**report, "files": list(paths), "dry_run": dry_run}


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
    mark = sub.add_parser("annotate", help="自动标注环境及显式引用，保留已有人工标注")
    mark.add_argument("--workspace", type=Path, required=True)
    mark.add_argument("--tex", action="append", required=True)
    mark.add_argument("--dry-run", action="store_true")
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
        elif args.command == "annotate":
            result = annotate(args.workspace, args.tex, dry_run=args.dry_run)
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
