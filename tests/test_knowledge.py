import json
import os
import subprocess
import sys

import pytest

from qprint.knowledge import KnowledgeIndexer, KnowledgeNavigator
from qprint.knowledge.index import packed
from qprint.knowledge.tools import call_tool, tool_definitions
from qprint.paths import WorkspaceError


TEX = r'''\documentclass{article}
\providecommand{\bpnode}[1]{}
\begin{document}
% \bpnode{fake}
\bpnode{object}
\bpdesc{A homotopy fiber definition.}
\begin{definition}\label{def:object}Let $F$ be a fiber.\end{definition}
\bpnode{main}
\bpdesc{The Ganea construction.}
\begin{theorem}\label{thm:main}The result.\uses{object}\end{theorem}
\bpnode{other}
\bpdesc{A consequence.}\uses{main}
\bpnode{main}
\begin{proof}Use \ref{def:object} and \cite{Serre1951}.\end{proof}
\end{document}
'''


def write(root, file, text):
    path = root / file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def kb(tmp_path):
    write(tmp_path, "tex/Paper/main.tex", TEX)
    write(tmp_path, "blueprint/Paper/results.md", '''# Main result

```qprint
kind: theorem
tex: Paper/main.tex#main
agda:
  declaration: GaneaIso
  file: Result.agda
```

A short reviewed navigation summary.

# Consequence

```qprint
kind: lemma
tex: Paper/main.tex#other
uses: ["[[Paper/results#Main result]]"]
```

The next step.
''')
    write(tmp_path, "blueprint/Paper/object.md", '''---
id: Topology/Fiber
kind: definition
aliases: [F₁, FiberObject]
source:
  tex: Paper/main.tex
  label: object
---
# Fiber

The navigation definition.
''')
    write(tmp_path, "agda/Result.agda", "module Result where\nGaneaIso : Set\nGaneaIso = Set\n\nnext : Set\nnext = Set\n")
    KnowledgeIndexer(tmp_path).update()
    return tmp_path


def test_symbol_merge_two_stage_reading_and_repeated_tex(kb):
    with KnowledgeNavigator(kb) as nav:
        for name in ("main", "thm:main", "Paper/results#Main result", "GaneaIso", "Paper/main.tex#main"):
            result = nav.kb_resolve(name)
            assert result["status"] == "resolved"
            assert result["node"]["id"] == "Paper/main/main"
        opened = nav.kb_open("main")
        assert opened["statement"] == "A short reviewed navigation summary."
        assert "\\begin" not in json.dumps(opened)
        assert opened["formalizations"][0]["declaration"] == "GaneaIso"
        tex = nav.kb_source("main")
        assert len(tex["fragments"]) == 2
        assert "\\begin{proof}" in tex["fragments"][1]["text"]
        assert "consequence" not in tex["fragments"][0]["text"]
        assert nav.kb_source("main", "agda")["fragments"][0]["text"].startswith("GaneaIso :")
        assert nav.kb_resolve("F₁")["node"]["id"] == "Topology/Fiber"
        assert nav.kb_resolve("fake")["status"] == "not_found"


def test_search_order_filters_graph_and_safe_query(kb):
    with KnowledgeNavigator(kb) as nav:
        assert nav.kb_search("Paper/main/main")[0]["reason"] == "symbol"
        assert nav.kb_search("GaneaIso")[0]["reason"] == "alias"
        matches = nav.kb_search("homotopy fiber", radius=0)
        assert matches[0]["node"] == "Topology/Fiber" and matches[0]["reason"] == "text"
        assert any(m["reason"] == "graph" for m in nav.kb_search("GaneaIso"))
        assert nav.kb_search("GaneaIso", scope="Nonexistent") == []
        assert all(m["kind"] == "definition" for m in nav.kb_search("fiber", kinds=["definition"]))
        assert nav.kb_search('" OR * : --', radius=0) == []
        assert len(nav.kb_search("main", limit=1)) == 1


def test_dependency_direction_cycles_shortest_path_and_explanations(kb):
    with KnowledgeNavigator(kb) as nav:
        graph = nav.kb_dependencies("other", depth=2)
        assert {n["id"] for n in graph["nodes"]} == {"Paper/main/other", "Paper/main/main", "Topology/Fiber"}
        back = nav.kb_backlinks("FiberObject", depth=2)
        assert "Paper/main/other" in {n["id"] for n in back["nodes"]}
        path = nav.kb_path("other", "FiberObject", direction="out", types=["uses"])
        assert path["nodes"] == ["Paper/main/other", "Paper/main/main", "Topology/Fiber"]
        assert not nav.kb_path("FiberObject", "other", direction="out", types=["uses"])["found"]
        assert nav.kb_explain_edge("main", "FiberObject")["status"] == "unexplained"
        nav.explain_link("main", "FiberObject", "Identifies the homotopy fiber.")
        assert nav.kb_explain_edge("main", "FiberObject", "uses")["edges"][0]["reason"] == "Identifies the homotopy fiber."
        assert nav.kb_dependencies("other", limit=1)["truncated"]
    path = kb / "tex/Paper/main.tex"
    path.write_text(TEX.replace("Let $F$", "\\uses{other}Let $F$"), encoding="utf-8")
    KnowledgeIndexer(kb).update()
    with KnowledgeNavigator(kb) as nav:
        assert len(nav.kb_dependencies("main", depth=20)["nodes"]) == 3
        assert nav.kb_explain_edge("main", "FiberObject")["status"] == "explained"


def test_working_set_is_session_local_and_ambiguity_is_explicit(kb):
    write(kb, "blueprint/Elsewhere.md", "---\nid: Elsewhere/Fiber\naliases: [FiberObject]\n---\n# Second fiber\n")
    KnowledgeIndexer(kb).update()
    with KnowledgeNavigator(kb, session="a") as nav:
        assert nav.kb_resolve("FiberObject")["status"] == "ambiguous"
        nav.kb_open("Topology/Fiber")
        assert nav.kb_resolve("FiberObject")["node"]["id"] == "Topology/Fiber"
    with KnowledgeNavigator(kb, session="a") as nav:
        assert nav.kb_resolve("FiberObject")["reason"] == "working_set"
    with KnowledgeNavigator(kb, session="b") as nav:
        assert nav.kb_resolve("FiberObject")["status"] == "ambiguous"
        with pytest.raises(WorkspaceError, match="ambiguous"):
            nav.kb_open("FiberObject")


def test_context_byte_budget_and_source_bounds(kb):
    with KnowledgeNavigator(kb) as nav:
        for budget in (128, 400, 6000):
            context = nav.kb_context("main", token_budget=budget)
            assert len(packed(context).encode("utf-8")) <= budget
            assert context["token_upper_bound"] <= budget
        assert nav.kb_context("main")["items"][0]["id"] == "Paper/main/main"
        source = nav.kb_source("main", max_lines=1)
        assert source["truncated"] and len(source["fragments"]) == 1
        source = nav.kb_source("main", max_chars=5)
        assert sum(len(f["text"]) for f in source["fragments"]) <= 5
        with pytest.raises(WorkspaceError):
            nav.kb_source("main", lines=[1000, 1001])


def test_incremental_noop_changed_deleted_rename_and_stale_source(kb, monkeypatch):
    import qprint.knowledge.index as indexing
    report = KnowledgeIndexer(kb).update()
    assert report["parsed_files"] == report["updated_nodes"] == report["updated_chunks"] == 0
    monkeypatch.setattr(indexing, "parse_tex", lambda *args: pytest.fail("unchanged TeX reparsed"))
    path = kb / "blueprint/Paper/results.md"
    path.write_text(path.read_text(encoding="utf-8").replace("short reviewed", "new reviewed"), encoding="utf-8")
    with KnowledgeNavigator(kb) as nav:
        with pytest.raises(WorkspaceError, match="changed since indexing"):
            nav.kb_source("main", "md")
    report = KnowledgeIndexer(kb).update()
    assert report["changed_files"] == ["blueprint/Paper/results.md"]
    assert report["updated_nodes"] == 1
    path.rename(path.with_name("renamed.md"))
    KnowledgeIndexer(kb).update()
    with KnowledgeNavigator(kb) as nav:
        assert nav.kb_resolve("Paper/results#Main result")["status"] == "not_found"
        assert nav.kb_resolve("Paper/renamed#Main result")["node"]["id"] == "Paper/main/main"
    (kb / "blueprint/Paper/object.md").unlink()
    KnowledgeIndexer(kb).update()
    with KnowledgeNavigator(kb) as nav:
        assert nav.kb_resolve("FiberObject")["status"] == "not_found"
        assert nav.kb_resolve("object")["node"]["id"] == "Paper/main/object"
        assert not nav.kb_search("FiberObject", radius=0)


def test_hash_verification_and_atomic_parse_failure(kb):
    path = kb / "blueprint/Paper/results.md"
    original = path.read_text(encoding="utf-8")
    stat = path.stat()
    path.write_text(original.replace("short", "other"), encoding="utf-8")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert not KnowledgeIndexer(kb).update()["changed_files"]
    assert KnowledgeIndexer(kb).update(verify_hashes=True)["parsed_files"] == 1
    write(kb, "blueprint/bad.md", "---\nid: [bad]\n---\n# Bad\n")
    path.write_text(original.replace("short", "broken"), encoding="utf-8")
    with pytest.raises(WorkspaceError):
        KnowledgeIndexer(kb).update()
    with KnowledgeNavigator(kb) as nav:
        assert "other reviewed" in nav.kb_open("main")["statement"]
        assert nav.kb_resolve("bad")["status"] == "not_found"


def test_frontmatter_links_edge_reason_and_code_exclusion(tmp_path):
    write(tmp_path, "blueprint/a.md", '''---
id: A
kind: theorem
uses:
  - target: B
    reason: Defines the fiber.
---
# A
Uses:

- [[B]]

`[[fake]]`

```text
[[fake]]
```
<!-- [[fake]] -->
''')
    write(tmp_path, "blueprint/b.md", "---\nid: B\nkind: definition\n---\n# B\nDefinition.\n")
    KnowledgeIndexer(tmp_path).update()
    with KnowledgeNavigator(tmp_path) as nav:
        graph = nav.kb_dependencies("A")
        assert {n["id"] for n in graph["nodes"]} == {"A", "B"}
        assert all(e["target_ref"] != "fake" for e in graph["edges"])
        assert nav.kb_explain_edge("A", "B")["status"] == "explained"


def test_unresolved_edges_are_repaired_when_target_arrives(tmp_path):
    write(tmp_path, "blueprint/a.md", "---\nid: A\nuses: [B]\n---\n# A\n")
    assert KnowledgeIndexer(tmp_path).update()["unresolved_edges"][0]["target_ref"] == "B"
    write(tmp_path, "blueprint/b.md", "---\nid: B\n---\n# B\n")
    assert not KnowledgeIndexer(tmp_path).update()["unresolved_edges"]
    (tmp_path / "blueprint/b.md").unlink()
    assert KnowledgeIndexer(tmp_path).update()["unresolved_edges"]


class FakeEmbedding:
    model_id = "test-v1"

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.extend(texts)
        return [[1.0, 0.5 if "fiber" in text.lower() else 0.0] for text in texts]


def test_optional_semantics_cached_and_invalidated(kb):
    provider = FakeEmbedding()
    assert KnowledgeIndexer(kb, provider).update()["embedded_chunks"] > 0
    provider.calls.clear()
    assert KnowledgeIndexer(kb, provider).update()["embedded_chunks"] == 0
    assert provider.calls == []
    with KnowledgeNavigator(kb, embedding_provider=provider) as nav:
        matches = nav.kb_search("unmentioned paraphrase", radius=0)
        assert matches and all(m["reason"] == "semantic" for m in matches)
        assert nav.kb_search("GaneaIso", limit=1)[0]["reason"] == "alias"
    path = kb / "blueprint/Paper/results.md"
    path.write_text(path.read_text(encoding="utf-8").replace("short", "tiny"), encoding="utf-8")
    report = KnowledgeIndexer(kb, provider).update()
    assert 0 < report["embedded_chunks"] < 5


def test_tools_and_cli(kb):
    definitions = tool_definitions()
    assert len(definitions) == 10
    assert all(d["inputSchema"]["additionalProperties"] is False for d in definitions)
    with KnowledgeNavigator(kb) as nav:
        assert call_tool(nav, "kb_resolve", {"query": "main"})["status"] == "resolved"
        with pytest.raises(WorkspaceError):
            call_tool(nav, "close", {})
    for arguments in (["index"], ["watch", "--once"], ["agent", "state"], ["agent", "search", "GaneaIso"],
                      ["agent", "batch", "--calls", '[{"tool":"kb_state","arguments":{}},{"tool":"kb_open","arguments":{"node":"main"}}]'],
                      ["agent", "source", "main", "--max-lines", "2"], ["agent", "refs", "main"],
                      ["agent", "context", "main"], ["agent", "path", "other", "FiberObject"],
                      ["agent", "call", "kb_open", "--args", '{"node":"main"}']):
        process = subprocess.run([sys.executable, "-m", "qprint", *arguments, "--workspace", "."],
                                 cwd=kb, capture_output=True, text=True)
        assert process.returncode == 0, process.stderr
        assert json.loads(process.stdout)


def test_missing_index_and_symlink_escape(tmp_path):
    with KnowledgeNavigator(tmp_path) as nav:
        assert nav.kb_state()['index_status'] == 'unavailable'
        with pytest.raises(WorkspaceError, match="qprint index"):
            nav.kb_search('anything')
    outside = tmp_path.parent / (tmp_path.name + "-outside.md")
    outside.write_text("secret", encoding="utf-8")
    (tmp_path / "blueprint").mkdir()
    try:
        (tmp_path / "blueprint/escape.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(WorkspaceError):
        KnowledgeIndexer(tmp_path).update()


def test_empty_workspace_and_label_only_tex(tmp_path):
    assert KnowledgeIndexer(tmp_path).update()["nodes"] == 0
    write(tmp_path, "tex/labels.tex", r"\label{first} First. \ref{second}" + "\n" + r"\label{second} Second.")
    KnowledgeIndexer(tmp_path).update()
    with KnowledgeNavigator(tmp_path) as nav:
        assert nav.kb_resolve("first")["status"] == "resolved"
        assert nav.kb_path("first", "second", types=["ref"])["found"]


def test_binding_to_internal_label_merges_and_orphan_labels_are_indexed(kb):
    path = kb / "blueprint/Paper/object.md"
    path.write_text(path.read_text(encoding="utf-8").replace("label: object", "label: def:object"), encoding="utf-8")
    tex = kb / "tex/Paper/main.tex"
    tex.write_text(TEX.replace(r"\bpnode{object}", r"\label{before}Intro." + "\n" + r"\bpnode{object}")
                   .replace(r"\end{document}", r"\section{Appendix}\label{after}Appendix." + "\n" + r"\end{document}"), encoding="utf-8")
    KnowledgeIndexer(kb).update()
    with KnowledgeNavigator(kb) as nav:
        assert nav.kb_resolve("def:object")["node"]["id"] == "Topology/Fiber"
        assert nav.kb_resolve("object")["node"]["id"] == "Topology/Fiber"
        assert nav.kb_source("Topology/Fiber")["fragments"]
        assert nav.kb_resolve("before")["status"] == "resolved"
        assert nav.kb_resolve("after")["status"] == "resolved"
        assert nav.kb_resolve("results#Main result")["status"] == "resolved"


def test_formal_file_changes_invalidate_bound_source_without_reparsing_md(kb, monkeypatch):
    import qprint.knowledge.index as indexing
    monkeypatch.setattr(indexing, "parse_md", lambda *args: pytest.fail("unchanged Markdown reparsed"))
    write(kb, "agda/Result.agda", "module Result where\nGaneaIso : Set\nGaneaIso = Updated\n")
    report = KnowledgeIndexer(kb).update()
    assert report["changed_files"] == ["agda/Result.agda"]
    with KnowledgeNavigator(kb) as nav:
        assert "Updated" in nav.kb_source("GaneaIso", "agda")["fragments"][0]["text"]
        assert nav.kb_search("Updated", radius=0)[0]["node"] == "Paper/main/main"


def test_frontmatter_parent_context_and_stable_id_before_tex_arrives(tmp_path):
    write(tmp_path, "blueprint/Project/index.md", "## Project index\n")
    write(tmp_path, "blueprint/Project/a.md", '# A\n```qprint\ntex: Project/main.tex#a\n```\nSummary\n')
    KnowledgeIndexer(tmp_path).update()
    with KnowledgeNavigator(tmp_path) as nav:
        assert nav.kb_resolve("Project/a#A")["node"]["id"] == "Project/main/a"
        path = nav.kb_path("Project/main/a", "Project/index", types=["parent"], direction="out")
        assert path["found"]
    write(tmp_path, "tex/Project/main.tex", r"\bpnode{a}The statement.")
    KnowledgeIndexer(tmp_path).update()
    with KnowledgeNavigator(tmp_path) as nav:
        assert nav.kb_resolve("Project/a#A")["node"]["id"] == "Project/main/a"


def test_duplicate_explicit_ids_roll_back(tmp_path):
    write(tmp_path, "blueprint/a.md", "---\nid: same\n---\n# One\n")
    KnowledgeIndexer(tmp_path).update()
    write(tmp_path, "blueprint/b.md", "---\nid: same\n---\n# Two\n")
    with pytest.raises(WorkspaceError, match="Duplicate node ID"):
        KnowledgeIndexer(tmp_path).update()
    with KnowledgeNavigator(tmp_path) as nav:
        assert nav.kb_open("same")["title"] == "One"


def test_edge_source_lines_and_indexer_version_refresh(tmp_path, monkeypatch):
    import qprint.knowledge.index as indexing
    text = "# A\n\n```qprint\nkind: theorem\n```\n\n<!-- hidden\ncomment -->\n\nUses:\n\n- [[B]]\n"
    write(tmp_path, "blueprint/a.md", text)
    write(tmp_path, "blueprint/b.md", "---\nid: B\n---\n# B\n")
    KnowledgeIndexer(tmp_path).update()
    with KnowledgeNavigator(tmp_path) as nav:
        edge = nav.kb_dependencies("a#A")["edges"][0]
        assert text.splitlines()[edge["line"] - 1] == "- [[B]]"
        with pytest.raises(WorkspaceError, match="types"):
            call_tool(nav, "kb_dependencies", {"node": "a#A", "types": "uses"})
    monkeypatch.setattr(indexing, "INDEXER_VERSION", indexing.INDEXER_VERSION + 1)
    assert KnowledgeIndexer(tmp_path).update()["parsed_files"] == 2
    assert KnowledgeIndexer(tmp_path).update()["parsed_files"] == 0
