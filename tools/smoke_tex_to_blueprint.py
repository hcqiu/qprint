"""Offline structural smoke test on an arXiv source archive; not semantic annotation.

Example: conda run -n qprint python tools/smoke_tex_to_blueprint.py ARCHIVE
    --output .qprint/paper-smoke --title TITLE --author AUTHOR --year YEAR
Only disposable extracted copies are annotated. No network or source-paper edits.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qprint.importers import extract_source
from qprint.tex import mask_comments, TexDocument
from qprint.tex_to_blueprint import generate
from qprint.workspace import Workspace


def annotate_for_smoke(source):
    """Mark outer theorem environments and explicit refs solely as parser fixtures."""
    masked = mask_comments(source)
    environments = set(re.findall(r"\\newtheorem\*?\s*\{([^{}]+)\}", masked)) | {"proof"}
    begin = re.search(r"\\begin\{document\}", masked)
    start = begin.end() if begin else 0
    stack, spans = [], []
    for token in re.finditer(r"\\(begin|end)\{([^{}]+)\}", masked[start:]):
        name = token[2]
        offset = start + token.start()
        if token[1] == "begin":
            stack.append((name, offset, any(n in environments for n, _o, _b in stack)))
        elif stack and stack[-1][0] == name:
            name, offset, nested = stack.pop()
            if name in environments and not nested:
                spans.append((offset, start + token.end(), name))
    spans.sort()
    labels, edits, previous = {}, [], None
    used = set()
    for number, (start, end, name) in enumerate(spans, 1):
        body = masked[start:end]
        found = re.search(r"\\label\{([^{}]+)\}", body)
        label = found[1].strip() if found else f"smoke-{name}-{number}"
        if name == "proof" and previous:
            label = previous
        elif label in used:
            label = f"smoke-{number}-{label}"
        else:
            previous = label
        used.add(label)
        if found:
            labels[found[1].strip()] = label
        edits.append((start, rf"\bpnode{{{label}}}" + "\n" + rf"\bpdesc{{Structural smoke fixture: {name} {number}.}}" + "\n"))
    references = 0
    for match in re.finditer(r"\\(?:ref|eqref|cref|Cref)\{([^{}]+)\}", masked[begin.end() if begin else 0:]):
        targets = [labels[v.strip()] for v in match[1].split(",") if v.strip() in labels]
        if targets:
            edits.append(((begin.end() if begin else 0) + match.end(), rf"\uses{{{', '.join(targets)}}}"))
            references += len(targets)
    for offset, insertion in sorted(edits, reverse=True):
        source = source[:offset] + insertion + source[offset:]
    return source, {"marked_environments": len(spans), "marked_references": references}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", action="append", required=True)
    parser.add_argument("--year", required=True)
    parser.add_argument("--render-limit", type=int, default=12)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        parser.error("output already exists; choose a new disposable directory")
    root.mkdir(parents=True)
    tex = root / "tex"
    tex.mkdir()
    raw = args.archive.read_bytes()
    files = extract_source(raw, tex, "paper")
    counts, sources = {}, []
    for relative in files:
        if not relative.endswith(".tex"):
            continue
        path = tex / relative
        annotated, counts[relative] = annotate_for_smoke(path.read_text(encoding="utf-8-sig"))
        path.write_text(annotated, encoding="utf-8")
        if TexDocument(relative, annotated).anchors:
            sources.append(relative)
    started = perf_counter()
    generated = generate(root, sources, "Smoke/Paper", title=args.title, authors=args.author,
                         year=args.year, keywords=["structural smoke fixture"])
    conversion_seconds = perf_counter() - started
    workspace = Workspace(root)
    assert not workspace.diagnostics, workspace.diagnostics
    assert not generated["diagnostics"], generated["diagnostics"]
    assert len(workspace.nodes) == generated["nodes"]
    nodes = list(workspace.nodes)
    count = min(max(args.render_limit, 0), len(nodes))
    selected = [nodes[i * len(nodes) // count] for i in range(count)]
    renders = []
    started = perf_counter()
    for node_id in selected:
        detail = workspace.detail(node_id)["tex_content"]
        assert detail and detail["html"]
        renders.append({"node": node_id, "fallback": "tex-fallback" in detail["html"],
                        "warnings": detail["warnings"], "inline_links": detail["html"].count('class="wikilink tex-use"')})
    report = {"archive": args.archive.name, "sha256": hashlib.sha256(raw).hexdigest(),
              "semantic_review": False, "annotation": counts,
              "conversion_seconds": round(conversion_seconds, 3),
              "render_seconds": round(perf_counter() - started, 3),
              "generation": generated, "edges": len(workspace.edges),
              "diagnostics": workspace.diagnostics, "renders": renders}
    (root / "smoke-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "renders"}, ensure_ascii=False, indent=2))
    print(f"Rendered {len(renders)}; fallbacks {sum(r['fallback'] for r in renders)}; report: {root / 'smoke-report.json'}")


if __name__ == "__main__":
    main()
