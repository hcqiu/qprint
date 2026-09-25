"""Small, bounded, JSON-compatible tools over a prebuilt knowledge index."""
from collections import deque
import json
from pathlib import Path
import re
import sqlite3

from ..paths import WorkspaceError, read_text, safe_path
from .index import clean_ref, connect, digest, packed, valid_vector
from .state import NavigationState
from .runtime import active_runtime


def bounded(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise WorkspaceError(f"{name} must be an integer in {minimum}..{maximum}")


class KnowledgeNavigator:
    def __init__(self, root, *, session="default", embedding_provider=None, runtime_root=None):
        self.root = Path(root).resolve()
        self.runtime_root = Path(runtime_root).resolve() if runtime_root is not None else self.root
        if not self.root.is_relative_to(self.runtime_root):
            raise WorkspaceError("workspace must stay inside the Qprint folder")
        self.workspace = self.root.relative_to(self.runtime_root).as_posix()
        if not isinstance(session, str) or not 1 <= len(session) <= 200:
            raise WorkspaceError("session must contain 1..200 characters")
        self._db = None
        self.session = session
        self.state = NavigationState(self.root, session)
        self.embedding_provider = embedding_provider

    @property
    def db(self):
        # State discovery must work before the host has prepared an index.
        # Mathematical queries still require a valid, read-only index.
        if self._db is None:
            db = connect(self.root, readonly=True)
            try:
                if not db.execute("SELECT 1 FROM metadata WHERE key='indexed'").fetchone():
                    raise WorkspaceError("Knowledge index is missing; ask the host to run qprint index for the active workspace")
            except Exception:
                db.close()
                raise
            self._db = db
        return self._db

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _data(self, node):
        row = self.db.execute("SELECT data FROM nodes WHERE id=?", (node,)).fetchone()
        if row is None:
            raise WorkspaceError(f"Unknown node: {node}")
        return json.loads(row[0])

    def _summary(self, node):
        data = self._data(node)
        result = {key: data.get(key) for key in ("id", "title", "description", "kind", "project", "source_locations", "formalizations")}
        result["description"] = (result["description"] or "")[:1200]
        result["source_locations"] = [{**s, "file": self._file(s["file"])} for s in result["source_locations"]]
        result["formalizations"] = [{**f, "file": self._file(f["language"] + "/" + f["file"].removeprefix(f["language"] + "/"))} if f.get("file") else f for f in result["formalizations"]]
        return result

    def _file(self, relative):
        return (Path(self.workspace) / relative).as_posix()

    def _touch(self, node):
        try:
            self.state.write(node)
        except (OSError, sqlite3.Error):
            # History is a convenience, never a precondition for reading math.
            # In read-only hosts the UI can still publish focus separately.
            return "Session history could not be saved; source/query results remain valid. Browser focus is unchanged."

    def _recent(self):
        return [r for r in self.state.read()["recent"]
                if self.db.execute("SELECT 1 FROM nodes WHERE id=?", (r["node_id"],)).fetchone()]

    def kb_state(self, limit=8):
        """Read host focus and query history without moving either cursor."""
        bounded(limit, "limit", 1, 32)
        runtime_status = "published" if active_runtime(self.runtime_root) else "not_published"
        stored = self.state.read()
        focus = stored["focus"]
        try:
            self.db
        except (WorkspaceError, sqlite3.Error, OSError) as exc:
            # Report the persisted host snapshot without guessing node metadata
            # or silently rebuilding the mathematical index in an agent query.
            document = focus.get("document") if focus else None
            return {"workspace": self.workspace, "session": self.session, "path_base": "qprint",
                    "runtime_status": runtime_status,
                    "current_document": self._file(document) if document else None,
                    "current_node": {"id": focus["node_id"]} if focus and focus["node_id"] else None,
                    "current_project": None, "focus_origin": focus["origin"] if focus else None,
                    "view": focus["view"] if focus else None,
                    "selection": focus["selection"] if focus else "",
                    "focus_updated_ns": focus["updated"] if focus else None,
                    "stale_focus": False, "stale_node_id": None, "focus_verified": False,
                    "recent_nodes": [], "recent_truncated": bool(stored["recent"]), "projects": [],
                    "index": {}, "index_status": "unavailable", "index_error": str(exc),
                    "next_action": (
                        "No UI runtime was published in this folder. Run agent commands from the same Qprint folder used to launch the UI. "
                        "An installed qprint command does not select that folder. If the UI has not started, start it there."
                        if runtime_status == "not_published" else
                        "UI runtime was found, but this workspace index is unavailable. Restart the Qprint UI host or refresh its index.")}
        recent = self._recent()
        node = focus["node_id"] if focus else recent[0]["node_id"] if recent else None
        missing = bool(node and not self.db.execute("SELECT 1 FROM nodes WHERE id=?", (node,)).fetchone())
        current = self._summary(node) if node and not missing else None
        document = focus.get("document") if focus else None
        if not document and node and not missing:
            locations = self._data(node)["source_locations"]
            preferred = "blueprint/" if focus and focus["view"] == "edit" else "tex/"
            document = next((s["file"] for s in locations if s["file"].startswith(preferred)), locations[0]["file"] if locations else None)
        return {"workspace": self.workspace, "session": self.session, "path_base": "qprint",
                "runtime_status": runtime_status,
                "current_document": self._file(document) if document else None,
                "current_node": current, "current_project": current["project"] if current else None,
                "focus_origin": focus["origin"] if focus else "navigator" if node else None,
                "view": focus["view"] if focus else None,
                "selection": focus["selection"] if focus else "",
                "focus_updated_ns": focus["updated"] if focus else None,
                "stale_focus": missing, "stale_node_id": node if missing else None,
                "recent_nodes": [{**self._summary(r["node_id"]), "visited_ns": r["touched"]} for r in recent[:limit]],
                "recent_truncated": len(recent) > limit,
                "projects": [r[0] for r in self.db.execute("SELECT DISTINCT project FROM nodes ORDER BY project")],
                "index": dict(self.db.execute("SELECT key,value FROM metadata")), "index_status": "ready",
                "focus_verified": True}

    def set_focus(self, node=None, *, view="rendered", selection="", origin="host", document=None):
        """Host/UI bridge; deliberately excluded from agent query tools."""
        if view not in {"rendered", "tex", "edit", "graph", "references", "paper"}:
            raise WorkspaceError("Unknown navigator view")
        if not isinstance(selection, str) or len(selection) > 2000:
            raise WorkspaceError("selection must be a string of at most 2000 characters")
        if origin not in {"host", "browser"}:
            raise WorkspaceError("origin must be host or browser")
        node = self._resolve(node) if node is not None else None
        if document is not None:
            safe_path(self.root, document)
            if not self.db.execute("SELECT 1 FROM files WHERE path=?", (document,)).fetchone():
                raise WorkspaceError("Current document is not indexed")
            if node and document not in {s["file"] for s in self._data(node)["source_locations"]}:
                raise WorkspaceError("Current document does not belong to this node")
        self.state.write(node, focus=True, view=view, selection=selection, origin=origin, document=document)
        return self.kb_state()

    def _accept(self, node, scope, kinds):
        return (not scope or node["project"] == scope or node["project"].startswith(scope.rstrip("/") + "/")
                or node["id"] == scope or node["id"].startswith(scope.rstrip("/") + "/")) and (not kinds or node["kind"] in kinds)

    def kb_resolve(self, query, scope=None):
        """Exact ID, then alias; return ambiguity explicitly, prefer this session."""
        if not isinstance(query, str) or not query.strip():
            raise WorkspaceError("query must be a nonempty string")
        query = clean_ref(query.strip())
        exact = self.db.execute("SELECT id FROM nodes WHERE id=?", (query,)).fetchone()
        ids = [exact[0]] if exact else [r[0] for r in self.db.execute("SELECT node_id FROM aliases WHERE alias=? ORDER BY node_id", (query,))]
        candidates = [self._summary(node) for node in ids]
        candidates = [n for n in candidates if self._accept(n, scope, None)]
        recent = {r["node_id"] for r in self._recent()}
        preferred = [n for n in candidates if n["id"] in recent]
        selected = candidates[0] if len(candidates) == 1 else preferred[0] if len(preferred) == 1 else None
        return {"query": query, "status": "resolved" if selected else "ambiguous" if candidates else "not_found",
                "node": selected, "candidates": candidates,
                "reason": "symbol" if exact else "working_set" if selected and len(candidates) > 1 else "alias"}

    def _resolve(self, node):
        result = self.kb_resolve(node)
        if result["status"] != "resolved":
            raise WorkspaceError(packed(result))
        return result["node"]["id"]

    def kb_search(self, query, scope=None, kinds=None, limit=20, radius=1):
        """Symbol → alias → lexical FTS → graph expansion → optional semantics."""
        bounded(limit, "limit", 1, 200)
        bounded(radius, "radius", 0, 3)
        if kinds is not None and (not isinstance(kinds, list) or any(not isinstance(k, str) for k in kinds)):
            raise WorkspaceError("kinds must be a list of strings")
        resolved = self.kb_resolve(query, scope)
        hits = {}

        def add(node_id, reason, score, snippet=None, via=None):
            if node_id in hits or len(hits) >= limit:
                return
            node = self._summary(node_id)
            if self._accept(node, scope, kinds):
                hits[node_id] = {"node": node_id, "title": node["title"], "kind": node["kind"],
                                 "score": score, "reason": reason,
                                 "snippet": (snippet or node["description"] or "")[:500]}
                if via:
                    hits[node_id]["via"] = via
        ordered = sorted(resolved["candidates"], key=lambda n: n["id"] != (resolved.get("node") or {}).get("id"))
        for node in ordered:
            add(node["id"], "symbol" if node["id"] == clean_ref(query) else "alias", 1.0)
        tokens = re.findall(r"\w+", query, flags=re.UNICODE)
        if tokens and len(hits) < limit:
            expression = " OR ".join('"' + token + '"' for token in tokens[:64])
            # Filters are applied before LIMIT, so another project's matches
            # cannot hide the requested scope. Query text is never SQL/FTS code.
            conditions, parameters = ["chunks_fts MATCH ?"], [expression]
            if scope:
                conditions.append("(n.project=? OR substr(n.project,1,?)=? OR n.id=? OR substr(n.id,1,?)=?)")
                prefix = scope.rstrip("/") + "/"
                parameters.extend([scope, len(prefix), prefix, scope, len(prefix), prefix])
            if kinds:
                conditions.append("n.kind IN (" + ",".join("?" for _ in kinds) + ")")
                parameters.extend(kinds)
            rows = self.db.execute("""SELECT c.node_id, snippet(chunks_fts,0,'','', ' … ',36) AS snippet,
                bm25(chunks_fts) AS rank FROM chunks_fts JOIN chunks c ON c.rowid=chunks_fts.rowid
                JOIN nodes n ON n.id=c.node_id WHERE """ + " AND ".join(conditions) + " ORDER BY rank,c.node_id", parameters)
            for row in rows:
                add(row["node_id"], "text", 0.9, row["snippet"])
                if len(hits) >= limit:
                    break
        frontier = list(hits)
        for _ in range(radius):
            following = []
            for seed in frontier:
                for row in self.db.execute("""SELECT source,target,type FROM edges WHERE target IS NOT NULL
                    AND (source=? OR target=?) ORDER BY type,source,target LIMIT 24""", (seed, seed)):
                    other = row["target"] if row["source"] == seed else row["source"]
                    if other not in hits:
                        add(other, "graph", 0.6, via={"node": seed, "type": row["type"]})
                        if other in hits:
                            following.append(other)
            frontier = following
        if self.embedding_provider and len(hits) < limit:
            vectors = self.embedding_provider.embed([query])
            if len(vectors) != 1:
                raise WorkspaceError("Embedding provider returned the wrong number of vectors")
            query_vector = valid_vector(vectors[0])
            ranked = []
            for row in self.db.execute("""SELECT c.node_id,c.text,e.vector FROM embeddings e JOIN chunks c
                ON c.id=e.chunk_id WHERE e.model=? AND e.hash=c.hash""", (self.embedding_provider.model_id,)):
                vector = json.loads(row["vector"])
                if len(vector) != len(query_vector):
                    raise WorkspaceError("Query embedding dimension does not match the index")
                score = sum(a * b for a, b in zip(vector, query_vector))
                ranked.append((score, row["node_id"], row["text"]))
            for score, node_id, snippet in sorted(ranked, reverse=True):
                add(node_id, "semantic", score, snippet)
        return list(hits.values())

    def kb_open(self, node):
        node = self._resolve(node)
        data = self._data(node)
        result = self._summary(node)
        result.update(statement=(data.get("statement") or data.get("body") or "")[:4000],
                      proof_summary=data.get("proof_summary", "")[:2000],
                      milestone=data.get("milestone", ""), status=data.get("status", ""),
                      dependencies=self._edges(node, "out", ["uses", "proof_of", "defines"]),
                      content_truncated=len(data.get("statement") or data.get("body") or "") > 4000)
        warning = self._touch(node)
        if warning:
            result["state_warning"] = warning
        return result

    def kb_source(self, node, source="tex", lines=None, max_lines=120, max_chars=20000):
        """Read only indexed fragments and reject stale line mappings."""
        bounded(max_lines, "max_lines", 1, 1000)
        bounded(max_chars, "max_chars", 1, 100000)
        if source not in {"tex", "md", "lean", "agda", "coq"}:
            raise WorkspaceError("source must be tex, md, lean, agda or coq")
        if lines is not None and (not isinstance(lines, list) or len(lines) != 2 or
                                  any(type(n) is not int for n in lines) or not 1 <= lines[0] <= lines[1]):
            raise WorkspaceError("lines must be [start,end] with positive inclusive line numbers")
        node = self._resolve(node)
        prefix = "blueprint/" if source == "md" else source + "/"
        locations = [s for s in self._data(node)["source_locations"] if s["file"].startswith(prefix)]
        if not locations:
            raise WorkspaceError(f"No indexed {source} source for {node}")
        fragments, cache, remaining_lines, remaining_chars = [], {}, max_lines, max_chars
        truncated = False
        for location in locations:
            first, last = location["start_line"], location["end_line"]
            if lines:
                first, last = max(first, lines[0]), min(last, lines[1])
                if first > last:
                    continue
            if remaining_lines <= 0 or remaining_chars <= 0:
                truncated = True
                break
            file = location["file"]
            if file not in cache:
                text = read_text(safe_path(self.root, file))
                indexed = self.db.execute("SELECT hash FROM files WHERE path=?", (file,)).fetchone()
                if not indexed or digest(text) != indexed[0]:
                    raise WorkspaceError(f"Source changed since indexing; run qprint index: {self._file(file)}")
                cache[file] = text.splitlines()
            actual_last = min(last, first + remaining_lines - 1)
            text = "\n".join(cache[file][first - 1:actual_last])
            if len(text) > remaining_chars:
                text = text[:remaining_chars]
                actual_last = first + text.count("\n")
                truncated = True
            truncated |= actual_last < last
            fragments.append({"file": self._file(file), "start_line": first, "end_line": actual_last,
                              "kind": location["kind"], "text": text})
            remaining_lines -= actual_last - first + 1
            remaining_chars -= len(text)
        if not fragments:
            raise WorkspaceError("Requested lines do not overlap this node's source fragments")
        result = {"node": node, "source": source, "fragments": fragments, "truncated": truncated}
        warning = self._touch(node)
        if warning:
            result["state_warning"] = warning
        return result

    def _edges(self, node, direction, types=None):
        column = "source" if direction == "out" else "target"
        query = """SELECT e.*,coalesce(n.reason,nullif(e.reason,''),'') AS explanation
            FROM edges e LEFT JOIN edge_notes n ON e.source=n.source AND e.target=n.target AND e.type=n.type
            WHERE e.""" + column + "=?"
        parameters = [node]
        if types:
            query += " AND e.type IN (" + ",".join("?" for _ in types) + ")"
            parameters.extend(types)
        result = []
        for row in self.db.execute(query + " ORDER BY e.type,e.source,e.target_ref,e.file,e.line", parameters):
            edge = dict(row)
            if edge.get("file"):
                edge["file"] = self._file(edge["file"])
            edge["reason"] = edge.pop("explanation")
            result.append(edge)
        return result

    def kb_dependencies(self, node, depth=1, direction="out", types=None, limit=200):
        bounded(depth, "depth", 0, 20)
        bounded(limit, "limit", 1, 2000)
        if direction not in {"out", "in", "both"}:
            raise WorkspaceError("direction must be out, in or both")
        node = self._resolve(node)
        queue, distances, edges = deque([(node, 0)]), {node: 0}, {}
        truncated = False
        while queue:
            current, distance = queue.popleft()
            if distance >= depth:
                continue
            for way in (["out", "in"] if direction == "both" else [direction]):
                for edge in self._edges(current, way, types or ["uses"]):
                    if len(edges) >= limit * 4 and edge["id"] not in edges:
                        truncated = True
                        continue
                    target = edge["target"] if way == "out" else edge["source"]
                    if target and target not in distances:
                        if len(distances) >= limit:
                            truncated = True
                            continue
                        distances[target] = distance + 1
                        queue.append((target, distance + 1))
                    edges[edge["id"]] = edge
        return {"node": node, "nodes": [{**self._summary(n), "distance": d} for n, d in distances.items()],
                "edges": list(edges.values()), "truncated": truncated}

    def kb_backlinks(self, node, depth=1, types=None, limit=200):
        return self.kb_dependencies(node, depth, "in", types or ["uses", "ref", "mentions", "proof_of", "formalizes"], limit)

    def kb_path(self, start, end, direction="both", types=None, max_depth=12, limit=2000):
        bounded(max_depth, "max_depth", 0, 50)
        bounded(limit, "limit", 1, 10000)
        if direction not in {"out", "in", "both"}:
            raise WorkspaceError("direction must be out, in or both")
        start, end = self._resolve(start), self._resolve(end)
        queue, previous = deque([(start, 0)]), {start: None}
        truncated = False
        while queue:
            current, depth = queue.popleft()
            if current == end:
                nodes, edges = [end], []
                while previous[current]:
                    current, edge = previous[current]
                    nodes.append(current)
                    edges.append(edge)
                return {"nodes": list(reversed(nodes)), "edges": list(reversed(edges)), "found": True, "truncated": False}
            if depth >= max_depth:
                truncated = True
                continue
            for way in (["out", "in"] if direction == "both" else [direction]):
                for edge in self._edges(current, way, types):
                    target = edge["target"] if way == "out" else edge["source"]
                    if target and target not in previous:
                        if len(previous) >= limit:
                            truncated = True
                            continue
                        previous[target] = (current, edge)
                        queue.append((target, depth + 1))
        return {"nodes": [], "edges": [], "found": False, "truncated": truncated}

    def kb_context(self, node, token_budget=6000):
        """Conservative UTF-8 byte bound, including JSON framing, on token use.

        UTF-8 bytes upper-bound byte-level tokenizer tokens. This intentionally
        underfills budgets instead of claiming a model-independent exact count.
        """
        bounded(token_budget, "token_budget", 128, 100000)
        node = self._resolve(node)
        graph = self.kb_dependencies(node, depth=2, limit=100)
        candidates = [node]
        candidates += [n["id"] for n in graph["nodes"] if n["distance"] == 1]
        candidates += [n["id"] for n in graph["nodes"] if n["distance"] == 2 and n["kind"] == "definition"]
        candidates += [r["node_id"] for r in self._recent()]
        result = {"node": node, "items": [], "truncated": False, "token_upper_bound": 0}

        def fits():
            # A fixed-point count includes the digits of the count itself.
            for _ in range(4):
                result["token_upper_bound"] = len(packed(result).encode("utf-8"))
            return result["token_upper_bound"] <= token_budget

        if not fits():
            raise WorkspaceError("token_budget is too small for this node ID")
        for candidate in dict.fromkeys(candidates):
            data = self._data(candidate)
            item = {"id": candidate, "title": data["title"], "kind": data["kind"],
                    "description": data["description"], "statement": (data.get("statement") or data.get("body") or "")[:4000]}
            result["items"].append(item)
            if not fits():
                result["truncated"] = True
                # Preserve current-node metadata even under a small budget.
                for key in ("statement", "description", "title"):
                    while item[key] and not fits():
                        item[key] = item[key][:len(item[key]) // 2]
                if not fits():
                    result["items"].pop()
                break
        fits()
        warning = self._touch(node)
        if warning:
            # Keep even warning-bearing responses inside the context budget.
            result["state_warning"] = "history_not_saved"
            while result["items"] and not fits():
                result["items"].pop()
                result["truncated"] = True
            if not fits():
                del result["state_warning"]
                fits()
        return result

    def kb_explain_edge(self, source, target, type=None):
        source, target = self._resolve(source), self._resolve(target)
        edges = [e for e in self._edges(source, "out", [type] if type else None) if e["target"] == target]
        return {"source": source, "target": target, "edges": edges,
                "status": "explained" if any(e["reason"] for e in edges) else "unexplained" if edges else "not_found"}

    def explain_link(self, source, target, reason, type="uses"):
        """Store a human/agent review note without fabricating an explanation."""
        source, target = self._resolve(source), self._resolve(target)
        if not isinstance(reason, str) or not reason.strip():
            raise WorkspaceError("reason must be nonempty")
        if not self.kb_explain_edge(source, target, type)["edges"]:
            raise WorkspaceError("Cannot annotate a nonexistent edge")
        writer = connect(self.root)
        try:
            with writer:
                writer.execute("INSERT OR REPLACE INTO edge_notes VALUES(?,?,?,?)", (source, target, type, reason))
        finally:
            writer.close()
        return self.kb_explain_edge(source, target, type)
