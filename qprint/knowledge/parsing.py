"""Deterministic source contributions for the navigator; never executes TeX."""
from pathlib import PurePosixPath
import re

import yaml
from markdown_it import MarkdownIt

from ..blueprint import parse_markdown
from ..paths import WorkspaceError
from ..tex import TexDocument, mask_comments, tex_commands

EDGE_TYPES = {"uses", "ref", "defines", "proves", "proof_of", "same_node",
              "formalizes", "cites", "mentions", "parent"}


def _list(value):
    return value if isinstance(value, list) else [] if value is None else [value]


def _record(file, key, title, kind, body, start, end, **extra):
    return {"key": key, "id": key, "title": title, "kind": kind,
            "description": body, "body": body, "proof_summary": "",
            "project": "/".join(PurePosixPath(file).parent.parts[1:]) or ".",
            "aliases": [title, key], "relations": [], "formalizations": [],
            "chunks": [{"file": file, "start_line": start, "end_line": end,
                        "text": body, "kind": kind}], **extra}


def _relations(metadata, file, line):
    result = []
    for kind in EDGE_TYPES:
        for value in _list(metadata.get(kind)):
            if isinstance(value, str):
                value = {"target": value}
            if not isinstance(value, dict) or not isinstance(value.get("target"), str):
                raise WorkspaceError(f"{file}:{line}: {kind} needs a target string")
            result.append({"type": kind, "target": value["target"],
                           "reason": str(value.get("reason", "")), "file": file, "line": line})
    return result


def _wiki_relations(body, file, start):
    result, section = [], "mentions"
    masked = re.sub(r"<!--.*?-->", lambda m: "\n" * m[0].count("\n"), body, flags=re.S)
    for token in MarkdownIt("commonmark").parse(masked):
        if token.type != "inline":
            continue
        if token.content.strip().rstrip(":").casefold() in {"uses", "dependencies", "依赖"}:
            section = "uses"
        elif token.level == 1 and not token.content.startswith("[["):
            section = "mentions"
        for child in token.children or []:
            if child.type == "text":
                for match in re.finditer(r"\[\[([^\]\n]+)\]\]", child.content):
                    result.append({"type": section, "target": match[1].split("|", 1)[0],
                                   "reason": "", "file": file,
                                   "line": start + (token.map or [0])[0]})
    return result


def _metadata(record, metadata, file, line):
    if metadata.get("id"):
        if not isinstance(metadata["id"], str):
            raise WorkspaceError(f"{file}:{line}: id must be a string")
        record.update(id=metadata["id"], explicit_id=True)
    for name in ("description", "proof_summary", "statement", "milestone", "status", "project"):
        if name in metadata:
            record[name] = str(metadata[name])
    record["aliases"] += [str(a) for a in _list(metadata.get("aliases"))]
    record["relations"] += _relations(metadata, file, line)
    source = metadata.get("source") or {}
    if not isinstance(source, dict):
        raise WorkspaceError(f"{file}:{line}: source must be a mapping")
    binding = metadata.get("tex")
    if source.get("tex"):
        binding = str(source["tex"]) + ("#" + str(source["label"]) if source.get("label") else "")
    if binding:
        path, label = str(binding).rsplit("#", 1) if "#" in str(binding) else (file.removeprefix("blueprint/")[:-3], str(binding))
        path = path.removeprefix("tex/").removesuffix(".tex") + ".tex"
        record["binding"] = f"tex/{path}#{label}"
        record["aliases"].append(label)
    formal = metadata.get("formal") or {}
    if not isinstance(formal, dict):
        raise WorkspaceError(f"{file}:{line}: formal must be a mapping")
    for language in ("agda", "lean", "coq"):
        for binding in _list(formal.get(language, metadata.get(language))):
            if isinstance(binding, str):
                if "#" in binding:
                    path, declaration = binding.rsplit("#", 1)
                    binding = {"file": path, "declaration": declaration}
                else:
                    binding = {"declaration": binding}
            if not isinstance(binding, dict) or not isinstance(binding.get("declaration"), str):
                raise WorkspaceError(f"{file}:{line}: formal binding needs declaration")
            record["formalizations"].append({**binding, "language": language})
            record["aliases"] += [binding["declaration"], binding["declaration"].rsplit(".", 1)[-1]]


def parse_md(file, text):
    relative = file.removeprefix("blueprint/")
    front = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.S)
    metadata = yaml.safe_load(front[1]) or {} if front else {}
    if not isinstance(metadata, dict):
        raise WorkspaceError(f"{file}: front matter must be a mapping")
    lines = text.splitlines()
    if metadata.get("id"):
        body = text[front.end():].strip()
        heading = re.search(r"(?m)^#\s+(.+)$", body)
        node = _record(file, relative[:-3], str(metadata.get("title") or (heading[1] if heading else metadata["id"])),
                       str(metadata.get("kind", "other")), body, 1, max(1, len(lines)))
        _metadata(node, metadata, file, 1)
        body_start = text.find(body, front.end())
        node["relations"] += _wiki_relations(body, file, text[:body_start].count("\n") + 1)
        node["chunks"][0]["text"] = text
        return [node]
    nodes, diagnostics = parse_markdown(relative, text)
    errors = [d for d in diagnostics if d["severity"] == "error"]
    if errors:
        raise WorkspaceError(str(errors))
    records = []
    for i, node in enumerate(nodes):
        end = nodes[i + 1].line - 1 if i + 1 < len(nodes) else len(lines)
        raw = "\n".join(lines[node.line - 1:end])
        fence = re.search(r"\A#[^\n]*\n\s*```qprint\s*\n(.*?)\n```", raw, re.S)
        meta = yaml.safe_load(fence[1]) or {} if fence else {}
        record = _record(file, node.id, node.title, node.kind, node.body, node.line, end, status=node.status)
        record["aliases"].append(PurePosixPath(relative).stem + "#" + node.title)
        _metadata(record, meta, file, node.line)
        body_start = raw.find(node.body, fence.end() if fence else len(raw.splitlines()[0]))
        body_line = node.line + raw[:body_start].count("\n")
        record["relations"] += _wiki_relations(node.body, file, body_line)
        record["chunks"][0]["text"] = raw
        record["relations"].append({"type": "parent", "target": relative[:-3], "reason": "",
                                    "file": file, "line": node.line})
        records.append(record)
    document = _record(file, relative[:-3], str(metadata.get("title", PurePosixPath(file).stem)),
                       "document", "" if nodes else text, 1, max(1, len(lines)))
    document["aliases"] += [relative, file, PurePosixPath(file).stem]
    if not nodes:
        document["relations"] = _wiki_relations(text, file, 1)
    records.append(document)
    return records


def parse_tex(file, text):
    doc = TexDocument(file, text)
    if doc.diagnostics:
        raise WorkspaceError(f"{file}: {'; '.join(doc.diagnostics)}")
    records = {}
    anchors = list(doc.anchors)
    # Labels outside annotated fragments are independently navigable. Labels
    # inside a bpnode become aliases, including in partly annotated papers.
    ranges = []
    for i, anchor in enumerate(anchors):
        end = anchors[i + 1]["start"] if i + 1 < len(anchors) else doc.body_end
        end = min([end, *(s["offset"] for s in doc.sections if anchor["content_start"] <= s["offset"] < end),
                   *(p for p in doc.bibliography_offsets if anchor["content_start"] <= p < end)])
        ranges.append((anchor["start"], end))
    begin = re.search(r"\\begin\{document\}", mask_comments(text))
    offset = begin.end() if begin else 0
    for c in tex_commands(text[offset:doc.body_end], {"label", "bpdesc", "uses", "bpnode", "node"}):
        if c["name"] == "label" and not any(a <= offset + c["start"] < b for a, b in ranges):
            anchors.append({"label": c["value"], "start": offset + c["start"], "content_start": offset + c["end"]})
    anchors.sort(key=lambda a: a["start"])
    for i, anchor in enumerate(anchors):
        start = anchor["start"]
        end = anchors[i + 1]["start"] if i + 1 < len(anchors) else doc.body_end
        end = min([end, *(s["offset"] for s in doc.sections if anchor["content_start"] <= s["offset"] < end),
                   *(p for p in doc.bibliography_offsets if anchor["content_start"] <= p < end)])
        raw = text[start:end].rstrip()
        first = text.count("\n", 0, start) + 1
        last = first + raw.count("\n")
        key = file.removeprefix("tex/")[:-4] + "/" + anchor["label"]
        commands = list(tex_commands(raw, {"bpdesc", "uses", "label", "ref", "eqref", "autoref", "cite", "citep", "citet"}))
        description = "\n\n".join(c["value"] for c in commands if c["name"] == "bpdesc")
        env = re.search(r"\\begin\{(theorem|lemma|definition|corollary|proposition|proof)\}", mask_comments(raw))
        kind = env[1] if env else "other"
        binding = file + "#" + anchor["label"]
        record = records.setdefault(key, _record(file, key, anchor["label"], kind, "", first, last,
                                                 binding=binding, chunks=[]))
        record["description"] += ("\n\n" if record["description"] else "") + description
        record["aliases"] += [anchor["label"], binding, binding.removeprefix("tex/")]
        record["chunks"].append({"file": file, "start_line": first, "end_line": last, "text": raw,
                                 "kind": "proof" if kind == "proof" else "statement"})
        for c in commands:
            if c["name"] == "label":
                record["aliases"] += [c["value"], file + "#" + c["value"], file.removeprefix("tex/") + "#" + c["value"]]
            elif c["name"] != "bpdesc":
                relation = "uses" if c["name"] == "uses" else "cites" if c["name"].startswith("cite") else "ref"
                for target in c["value"].split(","):
                    record["relations"].append({"type": relation, "target": target.strip(), "reason": "",
                                                "file": file, "line": first + raw.count("\n", 0, c["start"])})
    if not records:
        key = file.removeprefix("tex/")[:-4]
        records[key] = _record(file, key, PurePosixPath(file).stem, "document", "", 1, max(1, len(text.splitlines())))
        records[key]["chunks"][0]["text"] = text
    return list(records.values())
