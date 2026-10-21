"""Audit an imported workspace against its original GitHub zip, without compiling Lean."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qprint.formal import locate_code
from qprint.tex import tex_commands
from qprint.workspace import Workspace


def audit(archive, output):
    conversion = json.loads((output / "conversion-report.json").read_text(encoding="utf-8"))
    excluded = set(conversion["excluded_directories"])
    errors, checked, tex_count, lean_count = [], Counter(), 0, 0
    with zipfile.ZipFile(archive) as z:
        archive_revision = z.comment.decode("utf-8", errors="replace")
        for entry in z.infolist():
            if entry.is_dir():
                continue
            relative = entry.filename.split("/", 1)[1]
            if any(p in excluded for p in Path(relative).parts[:-1]):
                continue
            if relative.endswith(".lean"):
                lean_count += 1
                if (output / "lean" / relative).read_bytes() != z.read(entry):
                    errors.append(f"Lean source changed: {relative}")
            elif relative.endswith(".tex"):
                tex_count += 1
                original = z.read(entry).decode("utf-8-sig")
                converted = (output / "tex" / relative).read_text(encoding="utf-8-sig")
                for command in ("label", "uses", "lean", "bpdesc"):
                    before = [original[c["start"]:c["end"]] for c in tex_commands(original, {command})]
                    after = [converted[c["start"]:c["end"]] for c in tex_commands(converted, {command})]
                    checked[command] += len(before)
                    if before != after:
                        errors.append(f"Annotation changed: {relative}: {command}")
    print("Source preservation checked; loading Qprint workspace", flush=True)
    workspace = Workspace(output)
    errors.extend(d for d in workspace.diagnostics if d["severity"] == "error")
    located = 0
    for node in workspace.nodes.values():
        path, label = node.tex.rsplit("#", 1)
        descriptions = "\n\n".join(workspace.tex[path].annotations(label)["descriptions"])
        if node.body != descriptions:
            errors.append(f"Description changed or invented: {node.id}")
        for binding in node.bindings:
            if "file" in binding:
                result = locate_code(output, binding)
                if result["error"] or not result["code"]:
                    errors.append({"node": node.id, "binding": binding, "error": result["error"]})
                else:
                    located += 1
    report = {"archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
              "archive_revision_comment": archive_revision,
              "lean_files_unchanged": lean_count, "tex_files_checked": tex_count,
              "annotations_preserved": dict(checked), "nodes": len(workspace.nodes),
              "edges": len(workspace.edges), "located_lean_bindings": located,
              "workspace_diagnostics": dict(Counter(d["severity"] for d in workspace.diagnostics)),
              "conversion_diagnostics": dict(Counter(d["kind"] for d in conversion["diagnostics"])),
              "errors": errors, "lean_compiled": False}
    (output / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = audit(args.archive, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(bool(result["errors"]))
