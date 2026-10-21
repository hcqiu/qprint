r"""Import existing LaTeX Blueprint annotations and Lean sources without executing them."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from urllib.parse import quote

import httpx
import yaml

from .blueprint import Node, WIKILINK, parse_markdown, resolve_link
from .importers import extract_archive, fetch
from .paths import WorkspaceError, read_text, safe_path
from .tex import TexDocument, mask_comments, tex_commands
from .tex_to_blueprint import _kind


TITLE = "Formal Blueprint Project to QPrint"
SKIP = {".git", ".lake", ".conda", ".qprint", "__pycache__", "node_modules",
        "_build", "build", "dist", "toolchains", "packages", "archive"}
TEX_ASSETS = {".tex", ".bib", ".bbl", ".bst", ".sty", ".cls", ".def", ".tikz",
              ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".eps"}


def source_files(root):
    """Never traverse links, caches, archived copies, or generated dependencies."""
    for directory, folders, files in os.walk(root, followlinks=False):
        folders[:] = sorted(name for name in folders if name not in SKIP
                            and not (Path(directory) / name).is_symlink()
                            and not (Path(directory) / name).is_junction())
        for name in sorted(files):
            path = Path(directory) / name
            if not path.is_symlink():
                yield path


def acquire(source, stage, *, ref=None, downloader=fetch):
    """Resolve GitHub refs to commits; also accept a local directory or archive."""
    match = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?", source)
    if match:
        owner, repo = match.groups()
        api = f"https://api.github.com/repos/{owner}/{repo}"
        if not ref:
            ref = json.loads(downloader(api)).get("default_branch")
        if not isinstance(ref, str) or not re.fullmatch(r"[\w./-]+", ref) or ".." in ref:
            raise WorkspaceError("无效的 GitHub ref")
        commit = json.loads(downloader(f"{api}/commits/{quote(ref, safe='')}" )).get("sha")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise WorkspaceError("无法将 GitHub ref 解析为固定 commit")
        data = downloader(f"https://codeload.github.com/{owner}/{repo}/zip/{commit}")
        extract_archive(data, stage, strip_root=True, max_files=100_000, excluded_directories=frozenset(SKIP))
        return stage, {"source": source, "ref": ref, "commit": commit,
                       "archive_sha256": hashlib.sha256(data).hexdigest()}
    if "://" in source:
        raise WorkspaceError("网址必须是 GitHub 仓库根地址；也可输入本地工程目录或 zip/tar")
    path = Path(source).resolve()
    if path.is_dir():
        return path, {"source": source, "type": "local-directory"}
    if path.is_file():
        data = path.read_bytes()
        extract_archive(data, stage, max_files=100_000, excluded_directories=frozenset(SKIP))
        children = list(stage.iterdir())
        root = children[0] if len(children) == 1 and children[0].is_dir() else stage
        return root, {"source": source, "archive_sha256": hashlib.sha256(data).hexdigest()}
    raise WorkspaceError(f"源工程不存在: {source}")


def annotate_tex(source, diagnostics=None):
    r"""Keep every label/uses byte intact; insert anchors before labelled environments."""
    masked = mask_comments(source)
    begin = re.search(r"\\begin\s*\{document\}", masked)
    start = begin.end() if begin else 0
    finish = re.search(r"\\end\s*\{document\}", masked[start:])
    stop = start + finish.start() if finish else len(source)
    commands = list(tex_commands(source[start:stop], {"label", "bpnode", "node"}))
    document = TexDocument("source.tex", source)
    covered = []
    for i, anchor in enumerate(document.anchors):
        end = document.anchors[i + 1]["start"] if i + 1 < len(document.anchors) else document.body_end
        end = min([end, *(s["offset"] for s in document.sections if anchor["content_start"] <= s["offset"] < end)])
        covered.append((anchor["label"], anchor["content_start"], end))
    # Track containing environments. A node belongs before the theorem's opening,
    # not halfway through the theorem, so Qprint can render its full statement.
    spans, stack = [], []
    for token in re.finditer(r"\\(begin|end)\s*\{([^{}]+)\}", masked[start:stop]):
        name = token[2]
        if token[1] == "begin":
            stack.append((name, start + token.start()))
        elif stack and stack[-1][0] == name:
            name, offset = stack.pop()
            if name != "document":
                spans.append((offset, start + token.end(), name))
    labels = [dict(c, start=c["start"] + start, end=c["end"] + start)
              for c in commands if c["name"] == "label"]
    edits = []
    for label in labels:
        value = label["value"]
        if not value or any(c in value for c in "{}\n#|\\") or "]]" in value:
            if diagnostics is not None:
                diagnostics.append({"kind": "unsupported_label", "label": value,
                                    "line": source.count("\n", 0, label["start"]) + 1})
            continue
        if any(value == name and a <= label["start"] < b for name, a, b in covered):
            continue
        enclosing = [(a, b) for a, b, name in spans if a <= label["start"] < b
                     and name not in {"itemize", "enumerate", "description", "figure", "table"}
                     and sum(a <= other["start"] < b for other in labels) == 1]
        offset = min((a for a, _ in enclosing), default=label["start"])
        edits.append((offset, rf"\bpnode{{{value}}}" + "\n"))
    for offset, text in sorted(edits, reverse=True):
        source = source[:offset] + text + source[offset:]
    if edits:
        # Safe even in a separately included chapter; never redefine source macros.
        source = "\\providecommand{\\bpnode}[1]{}\n" + source
    return source, len(edits)


def mask_lean(source):
    """Mask nested Lean comments and strings, retaining offsets and newlines."""
    result = list(source)
    i, depth, string = 0, 0, False
    while i < len(source):
        if depth:
            if source.startswith("/-", i):
                result[i:i + 2] = "  "
                depth += 1
                i += 2
                continue
            if source.startswith("-/", i):
                result[i:i + 2] = "  "
                depth -= 1
                i += 2
                continue
            if source[i] != "\n":
                result[i] = " "
        elif string:
            if source[i] == "\\":
                result[i] = " "
                i += 1
                if i < len(source) and source[i] != "\n":
                    result[i] = " "
            else:
                string = source[i] != '"'
                if source[i] != "\n":
                    result[i] = " "
        elif source.startswith("/-", i):
            result[i:i + 2] = "  "
            depth = 1
            i += 2
            continue
        elif source.startswith("--", i):
            end = source.find("\n", i)
            end = len(source) if end < 0 else end
            result[i:end] = " " * (end - i)
            i = end
            continue
        elif source[i] == '"':
            string = True
            result[i] = " "
        i += 1
    return "".join(result)


IDENTIFIER = r"(?:«[^»\n]+»|[^\W\d][\w'!?₀-₉]*)(?:\.(?:«[^»\n]+»|[^\W\d][\w'!?₀-₉]*))*"
DECL = re.compile(r"(?m)^[ \t]*(?:@\[[^\]]*\]\s*)*"
                  r"(?:(?:noncomputable|private|protected|unsafe|partial|nonrec)\s+)*"
                  r"(?:def|theorem|lemma|abbrev|axiom|opaque|structure|inductive|class|instance)\s+"
                  rf"(?P<name>{IDENTIFIER})" + r"(?=\s|[:({\[]|$)")
SCOPE = re.compile(rf"(?m)^[ \t]*(?:(?:noncomputable|public)\s+)?"
                   rf"(?P<kind>namespace|section|end)\b[ \t]*(?P<name>{IDENTIFIER})?")
BOUNDARY = re.compile(r"(?m)^[ \t]*(?:@\[|(?:namespace|section|end|variable|variables|open|"
                      r"set_option|attribute|include|omit|export|notation|infixl?|infixr|"
                      r"prefix|postfix|syntax|macro|elab|example|initialize|mutual)\b|#)")


def lean_declarations(source, file):
    """Static source navigation, not an elaborator or proof check. No short-name guessing."""
    masked = mask_lean(source)
    declarations = list(DECL.finditer(masked))
    scopes = list(SCOPE.finditer(masked))
    boundaries = sorted({m.start() for m in declarations + scopes + list(BOUNDARY.finditer(masked))})
    stack, result = [], []
    events = sorted([(m.start(), "scope", m) for m in scopes]
                    + [(m.start(), "decl", m) for m in declarations])
    for offset, kind, match in events:
        if kind == "scope":
            name = match["name"] or ""
            if match["kind"] == "end":
                if stack and (not name or stack[-1][1] == name):
                    stack.pop()
            else:
                stack.append((match["kind"], name))
            continue
        name = match["name"]
        if name.startswith("_root_."):
            full = name.removeprefix("_root_.")
        else:
            names = []
            for scope, value in stack:
                if scope == "namespace":
                    if value.startswith("_root_."):
                        names = [value.removeprefix("_root_.")]
                    else:
                        names.append(value)
            full = ".".join([*names, name])
        indent = len(masked[offset:]) - len(masked[offset:].lstrip(" \t"))
        end = next((p for p in boundaries if p >= match.end()
                    and len(masked[p:]) - len(masked[p:].lstrip(" \t")) <= indent), len(source))
        # Trim trailing comments/blank lines from the display range.
        while end > match.end() and masked[end - 1].isspace():
            end -= 1
        result.append({"declaration": full, "file": file,
                       "lines": [source.count("\n", 0, offset) + 1,
                                 source.count("\n", 0, max(offset, end - 1)) + 1]})
    return result


def blueprint_scope(path):
    parts = Path(path).parts
    if "blueprint" in parts:
        return Path(*parts[:parts.index("blueprint")]).as_posix()
    return "."


def write_workspace(source, output, provenance, *, tex_roots=None, lean_source=None, on_progress=None):
    files = list(source_files(source))
    tex_files = [p for p in files if p.suffix == ".tex"]
    if tex_roots:
        roots = [source if value == "." else safe_path(source, value) for value in tex_roots]
        if any(not root.is_dir() for root in roots):
            raise WorkspaceError("--tex-root 必须是源工程内已存在的目录")
        tex_files = [p for p in tex_files if any(p.is_relative_to(root) for root in roots)]
    elif any("blueprint" in p.relative_to(source).parts for p in tex_files):
        tex_files = [p for p in tex_files if "blueprint" in p.relative_to(source).parts]
    if not tex_files:
        raise WorkspaceError("未找到 Blueprint TeX 文件")
    diagnostics, documents, nodes, info = [], {}, {}, {}
    output.mkdir()
    for directory in ("blueprint", "tex", "lean"):
        (output / directory).mkdir()
    # Keep a source snapshot, including native Lake files and license notices.
    # Lean uses the original relative layout; TeX assets retain theirs as well.
    if on_progress:
        on_progress(f"Copying {len(files)} source files; {len(tex_files)} Blueprint TeX files selected")
    copies = []
    for path in files:
        relative = path.relative_to(source).as_posix()
        for directory in ["lean", *(["tex"] if path.suffix.lower() in TEX_ASSETS else [])]:
            # relative comes from a link-free walk; output is a private fresh tree.
            # Avoid resolving every ancestor again for tens of thousands of files.
            target = output / directory / relative
            copies.append((path, target))
    for directory in sorted({target.parent for _, target in copies}):
        directory.mkdir(parents=True, exist_ok=True)
    # Bounded I/O concurrency matters for large, finely split proof libraries.
    with ThreadPoolExecutor(max_workers=8) as executor:
        for _ in executor.map(lambda pair: shutil.copyfile(*pair), copies):
            pass
    if lean_source:
        for path in source_files(lean_source):
            relative = "companion/" + path.relative_to(lean_source).as_posix()
            target = output / "lean" / relative
            if target.exists():
                raise WorkspaceError("源工程与 companion Lean 工程路径冲突")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    index = defaultdict(list)
    if on_progress:
        on_progress("Indexing Lean declarations")
    def index_file(path):
        return lean_declarations(read_text(path), path.relative_to(output / "lean").as_posix())

    lean_files = [path for path in source_files(output / "lean") if path.suffix == ".lean"]
    with ThreadPoolExecutor(max_workers=8) as executor:
        for bindings in executor.map(index_file, lean_files):
            for binding in bindings:
                index[binding["declaration"]].append(binding)
    added = 0
    if on_progress:
        on_progress("Converting TeX annotations and Blueprint bindings")
    for path in tex_files:
        relative = path.relative_to(source).as_posix()
        annotation_diagnostics = []
        annotated, count = annotate_tex(read_text(path), annotation_diagnostics)
        diagnostics.extend({"file": relative, **d} for d in annotation_diagnostics)
        added += count
        (output / "tex" / relative).write_text(annotated, encoding="utf-8", newline="")
        doc = TexDocument(relative, annotated)
        if doc.diagnostics:
            raise WorkspaceError(f"{relative}: {'; '.join(doc.diagnostics)}")
        if not doc.anchors:
            continue
        md_path = str(Path(relative).with_suffix(".md")).replace("\\", "/")
        # Reserve the project index without stealing a source's index.tex.
        if Path(md_path).name == "index.md":
            md_path = md_path[:-3] + "-nodes.md"
        if md_path in documents:
            raise WorkspaceError(f"Blueprint 输出路径冲突: {md_path}")
        documents[md_path] = []
        for label in dict.fromkeys(a["label"] for a in doc.anchors):
            node = Node(f"{md_path[:-3]}#{label}", label, md_path, 1, "", tex=f"{relative}#{label}")
            fragment = doc.fragment(label)
            annotations = doc.annotations(label)
            node.body = "\n\n".join(annotations["descriptions"])
            node.kind = _kind(fragment, doc.preamble)
            node.status = "complete" if re.search(r"\\leanok\b", mask_comments(fragment)) else "not_started"
            declarations = list(dict.fromkeys(value.strip() for c in tex_commands(fragment, {"lean"})
                                              for value in c["value"].split(",") if value.strip()))
            scope = blueprint_scope(relative)
            for declaration in declarations:
                matches = index.get(declaration, [])
                local = [b for b in matches if scope != "." and b["file"].startswith(scope + "/")]
                candidates = local or matches
                if len(candidates) == 1:
                    node.bindings.append(dict(candidates[0]))
                else:
                    node.bindings.append({"declaration": declaration})
                    diagnostics.append({"kind": "unresolved_lean", "node": node.id,
                                        "declaration": declaration, "candidates": candidates})
            nodes[node.id] = node
            info[node.id] = {"scope": scope, "uses": annotations["uses"]}
            documents[md_path].append(node)
    if not nodes:
        raise WorkspaceError("未找到 label 或 bpnode；不会凭空生成 Blueprint 节点")
    by_label = defaultdict(list)
    for node in nodes.values():
        by_label[node.title].append(node)
    for node in nodes.values():
        for label in info[node.id]["uses"]:
            candidates = by_label.get(label, [])
            same_file = [n for n in candidates if n.path == node.path]
            same_project = [n for n in candidates if info[n.id]["scope"] == info[node.id]["scope"]]
            candidates = same_file or same_project or candidates
            explicit = resolve_link(label, node.id, nodes) if "#" in label else None
            target = explicit or (candidates[0].id if len(candidates) == 1 else None)
            if target:
                node.uses.append(f"[[{target}]]")
            else:
                # Retain the dependency text, without selecting an arbitrary namesake.
                link = label if label.startswith("[[") else f"[[{label if '#' in label else '#' + label}]]"
                valid = bool(WIKILINK.fullmatch(link)) and not any(c in label for c in "{}\\\n")
                if valid:
                    node.uses.append(link)
                diagnostics.append({"kind": "unresolved_use" if valid else "unsupported_use",
                                    "node": node.id, "label": label})
    for path, group in documents.items():
        blocks = []
        for node in group:
            metadata = {"kind": node.kind, "status": node.status, "tex": node.tex, "uses": node.uses}
            if node.bindings:
                metadata["lean"] = node.bindings
            header = yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False).strip()
            body = re.sub(r"(?m)^#(?=\s)", r"\\#", node.body)
            blocks.append(f"# {node.title}\n\n```qprint\n{header}\n```\n" + (f"\n{body}\n" if body else ""))
        text = "\n".join(blocks)
        parsed, errors = parse_markdown(path, text)
        if errors or len(parsed) != len(group):
            raise WorkspaceError(f"生成的 Blueprint 无法解析: {path}: {errors}")
        target = safe_path(output / "blueprint", path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    scopes = defaultdict(list)
    for path in documents:
        scopes[blueprint_scope(path)].append(path)
    for scope, paths in scopes.items():
        name = "Imported project" if scope == "." else scope
        relative = "index.md" if scope == "." else f"{scope}/index.md"
        if relative in documents:
            raise WorkspaceError(f"索引路径冲突: {relative}")
        text = "---\n" + yaml.safe_dump({"title": name}, allow_unicode=True) + "---\n\n## Blueprint\n\n"
        text += "\n".join(f"- [[{p}]]" for p in paths) + "\n"
        target = safe_path(output / "blueprint", relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    report = {"tool": TITLE, "provenance": provenance, "nodes": len(nodes), "blueprint_files": len(documents),
              "tex_files": len(tex_files), "bpnode_added": added,
              "lean_bindings": sum(len(n.bindings) for n in nodes.values()),
              "located_lean_bindings": sum("file" in b for n in nodes.values() for b in n.bindings),
              "dependencies": sum(len(n.uses) for n in nodes.values()),
              "descriptions": sum(bool(n.body) for n in nodes.values()),
              "leanok_nodes": sum(n.status == "complete" for n in nodes.values()),
              "verification": "source navigation only; Lean was not compiled",
              "excluded_directories": sorted(SKIP), "diagnostics": diagnostics}
    (output / "conversion-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def convert_project(source, destination, *, root=None, ref=None, tex_roots=None,
                    lean_source=None, lean_ref=None, downloader=fetch, on_progress=None):
    root = (root or Path(__file__).resolve().parents[1]).resolve()
    if "/" in destination or "\\" in destination or any(c in destination for c in "#[]"):
        raise WorkspaceError("目标必须是 Qprint 根目录下的新文件夹名字")
    target = safe_path(root, destination)
    if target.exists():
        raise WorkspaceError("目标已存在；转换不会覆盖现有文件夹")
    with tempfile.TemporaryDirectory(prefix=".qprint-convert-", dir=root) as temporary:
        stage = Path(temporary)
        if on_progress:
            on_progress("Reading source project")
        origin, provenance = acquire(source, stage / "source", ref=ref, downloader=downloader)
        if stage.is_relative_to(origin) or target.is_relative_to(origin):
            raise WorkspaceError("输出目录不能位于源工程内；请先将源工程放到独立目录")
        companion = None
        if lean_source:
            companion, companion_provenance = acquire(lean_source, stage / "companion", ref=lean_ref, downloader=downloader)
            if stage.is_relative_to(companion) or target.is_relative_to(companion):
                raise WorkspaceError("输出目录不能位于 Lean 源工程内")
            provenance["companion"] = companion_provenance
        report = write_workspace(origin, stage / "workspace", provenance,
                                 tex_roots=tex_roots, lean_source=companion, on_progress=on_progress)
        if target.exists():
            raise WorkspaceError("转换期间目标已被创建")
        (stage / "workspace").rename(target)
    return {"destination": destination, **report}


def main(argv=None):
    parser = argparse.ArgumentParser(description=TITLE)
    parser.add_argument("source", help="现有工程的 GitHub 仓库地址、本地目录或 zip/tar")
    parser.add_argument("destination", help="保存在 Qprint 根目录下的新文件夹名字")
    parser.add_argument("--ref", help="GitHub 分支、tag 或 commit；默认默认分支")
    parser.add_argument("--tex-root", action="append", help="仅转换源工程内此目录的 TeX；可重复")
    parser.add_argument("--lean-source", help="可选的独立 Lean 工程地址或本地目录")
    parser.add_argument("--lean-ref", help="独立 Lean 仓库的 ref")
    args = parser.parse_args(argv)
    try:
        report = convert_project(args.source, args.destination, ref=args.ref, tex_roots=args.tex_root,
                                 lean_source=args.lean_source, lean_ref=args.lean_ref,
                                 on_progress=lambda message: print(message, file=sys.stderr, flush=True))
    except (OSError, ValueError, httpx.HTTPError) as exc:
        print(f"{TITLE}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({k: v for k, v in report.items() if k != "diagnostics"}, ensure_ascii=False, indent=2))
    print(f"Diagnostics: {len(report['diagnostics'])}; {args.destination}/conversion-report.json")
    return 0
