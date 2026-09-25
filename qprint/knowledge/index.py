"""Transactional, incremental SQLite symbol, graph and full-text indexes."""
from collections import defaultdict
import hashlib
import json
import math
import os
import posixpath
from pathlib import Path, PurePosixPath
import re
import sqlite3
from typing import Protocol

from ..paths import WorkspaceError, read_text, safe_path
from .parsing import parse_md, parse_tex

SCHEMA_VERSION = 1
# Bump when parsing/identity/projection rules change; source caches then refresh
# automatically while review notes and working sets remain in the database.
INDEXER_VERSION = 1


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clean_ref(value):
    value = value.removeprefix("[[").removesuffix("]]").split("|", 1)[0]
    return value.replace(".md#", "#").removesuffix(".md")


class EmbeddingProvider(Protocol):
    """Optional local/caller-supplied model; model_id must include its revision."""
    model_id: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def valid_vector(vector):
    if not vector or any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in vector):
        raise WorkspaceError("Embedding provider returned an invalid vector")
    norm = math.sqrt(sum(x * x for x in vector))
    if not norm:
        raise WorkspaceError("Embedding provider returned a zero vector")
    return [x / norm for x in vector]


def connect(root, *, readonly=False):
    root = Path(root).resolve()
    if not root.is_dir():
        raise WorkspaceError("Workspace does not exist; check the runtime or relative --workspace setting")
    path = safe_path(root, ".qprint/index/knowledge.sqlite")
    if readonly:
        if not path.is_file():
            raise WorkspaceError("Knowledge index is missing; ask the host to run .\\.conda\\python.exe -m qprint index for the active workspace")
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version != SCHEMA_VERSION:
                raise WorkspaceError(f"Unsupported knowledge index version {version}")
            return db
        except sqlite3.Error as exc:
            db.close()
            raise WorkspaceError("Cannot read knowledge index; ask the host to run .\\.conda\\python.exe -m qprint index to refresh legacy WAL storage, and check directory permissions") from exc
        except Exception:
            db.close()
            raise
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    # Rollback journaling lets read-only clients use the index without creating
    # WAL/SHM sidecars (notably in Windows sandboxed nested workspaces).
    db.execute("PRAGMA journal_mode=DELETE")
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version not in (0, SCHEMA_VERSION):
        db.close()
        raise WorkspaceError(f"Unsupported knowledge index version {version}")
    db.executescript("""
        CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER, hash TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS nodes (
            id TEXT PRIMARY KEY, project TEXT, title TEXT, description TEXT, kind TEXT,
            md_file TEXT, tex_file TEXT, tex_label TEXT, start_line INTEGER, end_line INTEGER,
            node_hash TEXT, data TEXT);
        CREATE TABLE IF NOT EXISTS aliases (
            alias TEXT, node_id TEXT REFERENCES nodes(id) ON DELETE CASCADE, type TEXT,
            PRIMARY KEY(alias,node_id));
        CREATE INDEX IF NOT EXISTS aliases_node ON aliases(node_id);
        CREATE TABLE IF NOT EXISTS edges (
            id TEXT PRIMARY KEY, source TEXT REFERENCES nodes(id) ON DELETE CASCADE,
            target TEXT REFERENCES nodes(id) ON DELETE SET NULL, target_ref TEXT,
            type TEXT, reason TEXT, file TEXT, line INTEGER);
        CREATE INDEX IF NOT EXISTS edges_source ON edges(source,type);
        CREATE INDEX IF NOT EXISTS edges_target ON edges(target,type);
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY, node_id TEXT REFERENCES nodes(id) ON DELETE CASCADE,
            file TEXT, start_line INTEGER, end_line INTEGER, text TEXT, kind TEXT, hash TEXT);
        CREATE INDEX IF NOT EXISTS chunks_node ON chunks(node_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            text, content='chunks', content_rowid='rowid', tokenize='unicode61');
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
            INSERT INTO chunks_fts(rowid,text) VALUES(new.rowid,new.text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',old.rowid,old.text);
        END;
        CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
            INSERT INTO chunks_fts(chunks_fts,rowid,text) VALUES('delete',old.rowid,old.text);
            INSERT INTO chunks_fts(rowid,text) VALUES(new.rowid,new.text);
        END;
        CREATE TABLE IF NOT EXISTS embeddings (
            chunk_id TEXT REFERENCES chunks(id) ON DELETE CASCADE, model TEXT, hash TEXT,
            vector TEXT, PRIMARY KEY(chunk_id,model));
        CREATE TABLE IF NOT EXISTS working_set (
            session TEXT, node_id TEXT REFERENCES nodes(id) ON DELETE CASCADE,
            touched INTEGER, PRIMARY KEY(session,node_id));
        CREATE TABLE IF NOT EXISTS edge_notes (
            source TEXT, target TEXT, type TEXT, reason TEXT,
            PRIMARY KEY(source,target,type));
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
    """)
    db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    return db


def _paths(root):
    suffixes = {"blueprint": {".md"}, "tex": {".tex"}, "lean": {".lean"},
                "agda": {".agda"}, "coq": {".v"}}
    ignored = {".git", ".lake", "_build", "node_modules", "__pycache__", ".qprint"}
    for folder, extensions in suffixes.items():
        base = safe_path(root, folder)
        if not base.is_dir():
            continue
        for directory, dirs, files in os.walk(base, followlinks=False):
            dirs[:] = sorted(d for d in dirs if d not in ignored and not (Path(directory) / d).is_symlink())
            for name in sorted(files):
                if Path(name).suffix.lower() in extensions:
                    relative = (Path(directory) / name).relative_to(root).as_posix()
                    yield relative, safe_path(root, relative)


def _formal_chunk(binding, texts):
    language, declaration = binding["language"], binding["declaration"]
    file = binding.get("file")
    if not file:
        suffix = {"lean": ".lean", "agda": ".agda", "coq": ".v"}[language]
        parts = declaration.split(".")
        file = next(("/".join(parts[:i]) + suffix for i in range(len(parts), 0, -1)
                     if language + "/" + "/".join(parts[:i]) + suffix in texts), None)
    if not file:
        return None
    file = language + "/" + file.removeprefix(language + "/")
    if file not in texts:
        return None
    lines = texts[file].splitlines()
    bounds = binding.get("lines")
    if bounds is None:
        name = re.escape(declaration.rsplit(".", 1)[-1])
        prefix = {"lean": r"\s*(?:@\[[^\]]*\]\s*)?(?:(?:private|protected|noncomputable|unsafe)\s+)*(?:def|theorem|lemma|abbrev|axiom|opaque|structure|inductive|class|instance)\s+",
                  "coq": r"\s*(?:(?:Local|Global)\s+)?(?:Definition|Theorem|Lemma|Corollary|Proposition|Fixpoint|Inductive|Record|Axiom|Parameter|Example)\s+",
                  "agda": r"\s*"}[language]
        matches = [i for i, line in enumerate(lines) if re.match(prefix + name + r"(?=\s|:|\(|\{|$)", line)
                   and (language != "agda" or ":" in line)]
        if len(matches) != 1:
            return None
        start = matches[0]
        if language == "agda":
            end = next((i for i in range(start + 1, len(lines))
                        if re.match(prefix + r"[^\s:]+\s*:", lines[i])), len(lines))
        else:
            end = next((i for i in range(start + 1, len(lines))
                        if re.match(prefix, lines[i]) or re.match(r"^(?:end|namespace|section)\b", lines[i])), len(lines))
        bounds = [start + 1, end]
    if (not isinstance(bounds, list) or len(bounds) != 2 or any(type(i) is not int for i in bounds)
            or not 1 <= bounds[0] <= bounds[1] <= len(lines)):
        raise WorkspaceError(f"Invalid formal source lines: {file}: {bounds}")
    return {"file": file, "start_line": bounds[0], "end_line": bounds[1],
            "text": "\n".join(lines[bounds[0] - 1:bounds[1]]), "kind": "formalization"}


def assemble(payloads):
    records = [dict(r) for p in payloads.values() for r in p.get("records", [])]
    texts = {f: p["text"] for f, p in payloads.items() if "text" in p}
    # source.label may name a LaTeX label inside a bpnode, rather than the
    # bpnode itself. Both bindings must converge before choosing a node ID.
    tex_bindings = defaultdict(set)
    for r in records:
        if r.get("binding") and r["chunks"][0]["file"].startswith("tex/"):
            for alias in r["aliases"]:
                if alias.startswith("tex/") and "#" in alias:
                    tex_bindings[alias].add(r["binding"])
    for r in records:
        matches = tex_bindings.get(r.get("binding"), set())
        if len(matches) == 1:
            r["binding"] = next(iter(matches))
    binding_ids = defaultdict(set)
    for r in records:
        if r.get("binding") and r.get("explicit_id"):
            binding_ids[r["binding"]].add(r["id"])
    if any(len(ids) > 1 for ids in binding_ids.values()):
        raise WorkspaceError("Conflicting explicit IDs for the same TeX source")
    tex_ids = {r["binding"]: r["id"] for r in records if r.get("binding") and r["chunks"][0]["file"].startswith("tex/")}
    groups = defaultdict(list)
    for r in records:
        binding = r.get("binding")
        fallback = r["id"]
        if binding and not r.get("explicit_id"):
            path, label = binding.removeprefix("tex/").rsplit("#", 1)
            fallback = path.removesuffix(".tex") + "/" + label
        node_id = next(iter(binding_ids[binding])) if binding_ids[binding] else tex_ids.get(binding, fallback)
        groups[node_id].append(r)
    nodes, aliases, chunks, raw_edges = {}, defaultdict(set), {}, []
    for node_id, group in sorted(groups.items()):
        group.sort(key=lambda r: (not r["chunks"][0]["file"].startswith("blueprint/"), r["key"]))
        md = [r for r in group if r["chunks"][0]["file"].startswith("blueprint/")]
        if len(md) > 1 and not all(r.get("binding") == md[0].get("binding") and r.get("binding") for r in md):
            raise WorkspaceError(f"Duplicate node ID: {node_id}")
        head = group[0]
        data = {k: head.get(k, "") for k in ("title", "description", "kind", "project", "body", "proof_summary", "statement", "milestone", "status")}
        data.update(id=node_id, formalizations=[], source_locations=[])
        for r in group:
            aliases[node_id].update(clean_ref(a) for a in [*r["aliases"], r["id"], r["key"], node_id] if a)
            for c in r["chunks"]:
                chunk_id = digest(packed([node_id, c["file"], c["start_line"], c["kind"]]))
                chunks[chunk_id] = {**c, "id": chunk_id, "node_id": node_id, "hash": digest(c["text"])}
                data["source_locations"].append({k: c[k] for k in ("file", "start_line", "end_line", "kind")})
            for b in r["formalizations"]:
                data["formalizations"].append(b)
                c = _formal_chunk(b, texts)
                if c:
                    chunk_id = digest(packed([node_id, c["file"], c["start_line"], "formalization"]))
                    chunks[chunk_id] = {**c, "id": chunk_id, "node_id": node_id, "hash": digest(c["text"])}
                    location = {k: c[k] for k in ("file", "start_line", "end_line", "kind")}
                    if location not in data["source_locations"]:
                        data["source_locations"].append(location)
                else:
                    b["location_status"] = "unresolved"
            raw_edges.extend({**e, "source": node_id} for e in r["relations"])
        md_locations = [s for s in data["source_locations"] if s["file"].startswith("blueprint/")]
        tex_locations = [s for s in data["source_locations"] if s["file"].startswith("tex/")]
        first = (md_locations or tex_locations or data["source_locations"])[0]
        binding = next((r["binding"] for r in group if r.get("binding")), "")
        data.update(md_file=md_locations[0]["file"] if md_locations else None,
                    tex_file=tex_locations[0]["file"] if tex_locations else (binding.split("#")[0] or None),
                    tex_label=binding.split("#", 1)[-1] if binding else None,
                    start_line=first["start_line"], end_line=first["end_line"])
        nodes[node_id] = data
        # Index navigation metadata alongside source fragments.
        value = "\n".join(str(data.get(k, "")) for k in ("id", "title", "description", "body"))
        cid = digest("summary:" + node_id)
        chunks[cid] = {"id": cid, "node_id": node_id, "file": first["file"], "start_line": first["start_line"],
                       "end_line": first["end_line"], "kind": "summary", "text": value, "hash": digest(value)}
    # Connect Markdown documents/single-node pages to the nearest folder index.
    indexes = {}
    for node_id, data in nodes.items():
        file = data.get("md_file")
        if file and data["kind"] == "document":
            path = PurePosixPath(file)
            if path.stem == path.parent.name:
                indexes[path.parent] = node_id
            elif path.name.lower() == "index.md":
                indexes.setdefault(path.parent, node_id)
    parent_sources = {e["source"] for e in raw_edges if e["type"] == "parent"}
    for node_id, data in nodes.items():
        file = data.get("md_file")
        if not file or node_id in parent_sources:
            continue
        parent = PurePosixPath(file).parent
        target = next((indexes[p] for p in (parent, *parent.parents) if p in indexes and indexes[p] != node_id), None)
        if target:
            raw_edges.append({"source": node_id, "target": target, "type": "parent", "reason": "",
                              "file": file, "line": data["start_line"]})
    # Bibliographic keys are explicit external entities; no invented paper metadata.
    for e in raw_edges:
        if e["type"] == "cites":
            node_id = "cite:" + str(PurePosixPath(e["file"]).parent) + "#" + e["target"]
            nodes.setdefault(node_id, {"id": node_id, "project": nodes[e["source"]]["project"],
                                      "title": e["target"], "description": "", "kind": "citation",
                                      "source_locations": [], "formalizations": [], "external": True})
            aliases[node_id].update([node_id, e["target"]])
            e["resolved"] = node_id
    lookup = defaultdict(set)
    for node_id, names in aliases.items():
        for name in names:
            lookup[name].add(node_id)
    edges = {}
    for e in raw_edges:
        ref = clean_ref(e["target"])
        source = nodes[e["source"]]
        candidates = {ref} if ref in nodes else set(lookup.get(ref, ()))
        if ref not in nodes and e["file"].startswith("blueprint/"):
            current = e["file"].removeprefix("blueprint/")[:-3]
            relative = current + ref if ref.startswith("#") else str(PurePosixPath(current).parent / ref)
            # Normalize ../ links without ever using them as filesystem paths.
            local = lookup.get(posixpath.normpath(relative), set())
            if local:
                candidates = local
        elif ref not in nodes and e["file"].startswith("tex/"):
            local = {n for n in candidates if nodes[n].get("tex_file") == e["file"]}
            if local:
                candidates = local
        same_project = {n for n in candidates if nodes[n]["project"] == source["project"]}
        if len(candidates) > 1 and same_project:
            candidates = same_project
        target = e.get("resolved") or (next(iter(candidates)) if len(candidates) == 1 else None)
        edge = {"source": e["source"], "target": target, "target_ref": ref, "type": e["type"],
                "reason": e["reason"], "file": e["file"], "line": e["line"]}
        edge_id = digest(packed([edge[k] for k in ("source", "target_ref", "type", "file", "line")]))
        edges[edge_id] = {"id": edge_id, **edge}
    return nodes, aliases, chunks, edges


class KnowledgeIndexer:
    def __init__(self, root, embedding_provider: EmbeddingProvider | None = None):
        self.root = Path(root).resolve()
        self.embedding_provider = embedding_provider

    def update(self, *, verify_hashes=False):
        db = connect(self.root)
        try:
            with db:
                # Lock before reading old state so concurrent indexers cannot race.
                db.execute("BEGIN IMMEDIATE")
                old = {r["path"]: dict(r) for r in db.execute("SELECT * FROM files")}
                version = db.execute("SELECT value FROM metadata WHERE key='indexer_version'").fetchone()
                refresh = not version or version[0] != str(INDEXER_VERSION)
                payloads, changed, touched, seen = {}, [], [], set()
                for relative, path in _paths(self.root):
                    seen.add(relative)
                    stat = path.stat()
                    previous = old.get(relative)
                    if previous and not refresh and not verify_hashes and (stat.st_mtime_ns, stat.st_size) == (previous["mtime_ns"], previous["size"]):
                        payloads[relative] = json.loads(previous["payload"])
                        continue
                    text = read_text(path)
                    file_hash = digest(text)
                    after = path.stat()
                    if (stat.st_mtime_ns, stat.st_size) != (after.st_mtime_ns, after.st_size):
                        raise WorkspaceError(f"Source changed during indexing; retry: {relative}")
                    if previous and not refresh and previous["hash"] == file_hash:
                        payload = json.loads(previous["payload"])
                    else:
                        payload = {"records": parse_md(relative, text)} if relative.endswith(".md") else {
                            "records": parse_tex(relative, text)} if relative.endswith(".tex") else {"text": text}
                        changed.append(relative)
                    payloads[relative] = payload
                    touched.append((relative, stat.st_mtime_ns, stat.st_size, file_hash, packed(payload)))
                removed = sorted(set(old) - seen)
                db.executemany("DELETE FROM files WHERE path=?", [(p,) for p in removed])
                db.executemany("INSERT OR REPLACE INTO files VALUES(?,?,?,?,?)", touched)
                report = {"changed_files": changed, "deleted_files": removed, "parsed_files": len(changed),
                          "updated_nodes": 0, "updated_chunks": 0, "embedded_chunks": 0}
                if changed or removed or not db.execute("SELECT 1 FROM metadata WHERE key='indexed'").fetchone():
                    nodes, aliases, chunks, edges = assemble(payloads)
                    self._sync(db, nodes, aliases, chunks, edges, report)
                if self.embedding_provider:
                    self._embeddings(db, report)
                db.execute("INSERT OR REPLACE INTO metadata VALUES('indexed','1')")
                db.execute("INSERT OR REPLACE INTO metadata VALUES('indexer_version',?)", (str(INDEXER_VERSION),))
                report.update(nodes=db.execute("SELECT count(*) FROM nodes").fetchone()[0],
                              edges=db.execute("SELECT count(*) FROM edges").fetchone()[0],
                              unresolved_edges=[dict(r) for r in db.execute("SELECT source,target_ref,type,file,line FROM edges WHERE target IS NULL")])
                return report
        finally:
            db.close()

    def _sync(self, db, nodes, aliases, chunks, edges, report):
        old_nodes = {r["id"]: r["node_hash"] for r in db.execute("SELECT id,node_hash FROM nodes")}
        for node_id, data in nodes.items():
            serialized = packed(data)
            node_hash = digest(serialized)
            if old_nodes.get(node_id) != node_hash:
                keys = ("id", "project", "title", "description", "kind", "md_file", "tex_file", "tex_label", "start_line", "end_line")
                db.execute("""INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    project=excluded.project,title=excluded.title,description=excluded.description,kind=excluded.kind,
                    md_file=excluded.md_file,tex_file=excluded.tex_file,tex_label=excluded.tex_label,
                    start_line=excluded.start_line,end_line=excluded.end_line,node_hash=excluded.node_hash,data=excluded.data""",
                           [*(data.get(k) for k in keys), node_hash, serialized])
                report["updated_nodes"] += 1
        desired_aliases = {(alias, node_id, "symbol" if alias == node_id else "alias") for node_id, names in aliases.items() for alias in names}
        old_aliases = {tuple(r) for r in db.execute("SELECT alias,node_id,type FROM aliases")}
        db.executemany("DELETE FROM aliases WHERE alias=? AND node_id=? AND type=?", sorted(old_aliases - desired_aliases))
        db.executemany("INSERT INTO aliases VALUES(?,?,?)", sorted(desired_aliases - old_aliases))
        old_edges = {r["id"]: dict(r) for r in db.execute("SELECT * FROM edges")}
        db.executemany("DELETE FROM edges WHERE id=?", [(i,) for i in old_edges.keys() - edges.keys()])
        for key, edge in edges.items():
            if edge != old_edges.get(key):
                db.execute("INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?,?,?)", list(edge.values()))
        old_chunks = {r["id"]: dict(r) for r in db.execute("SELECT * FROM chunks")}
        db.executemany("DELETE FROM chunks WHERE id=?", [(i,) for i in old_chunks.keys() - chunks.keys()])
        for key, chunk in chunks.items():
            if chunk != old_chunks.get(key):
                keys = ("id", "node_id", "file", "start_line", "end_line", "text", "kind", "hash")
                db.execute("""INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                    file=excluded.file,start_line=excluded.start_line,end_line=excluded.end_line,
                    text=excluded.text,kind=excluded.kind,hash=excluded.hash""", [chunk[k] for k in keys])
                report["updated_chunks"] += 1
        db.executemany("DELETE FROM nodes WHERE id=?", [(i,) for i in old_nodes.keys() - nodes.keys()])

    def _embeddings(self, db, report):
        provider = self.embedding_provider
        pending = list(db.execute("""SELECT c.* FROM chunks c LEFT JOIN embeddings e
            ON e.chunk_id=c.id AND e.model=? WHERE e.hash IS NULL OR e.hash!=c.hash""", (provider.model_id,)))
        for start in range(0, len(pending), 64):
            batch = pending[start:start + 64]
            vectors = provider.embed([r["text"] for r in batch])
            if len(vectors) != len(batch):
                raise WorkspaceError("Embedding provider returned the wrong number of vectors")
            dimension = db.execute("SELECT vector FROM embeddings WHERE model=? LIMIT 1", (provider.model_id,)).fetchone()
            size = len(json.loads(dimension[0])) if dimension else len(vectors[0])
            for row, vector in zip(batch, vectors):
                vector = valid_vector(vector)
                if len(vector) != size:
                    raise WorkspaceError("Embedding dimensions changed; use a new model_id")
                db.execute("INSERT OR REPLACE INTO embeddings VALUES(?,?,?,?)",
                           (row["id"], provider.model_id, row["hash"], packed(vector)))
                report["embedded_chunks"] += 1
