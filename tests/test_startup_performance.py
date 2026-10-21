from pathlib import Path
import json
import os

import pytest

from qprint.blueprint import Node, resolve_link, resolve_tex_use
from qprint.node_lookup import NodeLookup
from qprint.paths import WorkspaceError
from qprint.knowledge.index import KnowledgeIndexer, _paths


def test_indexed_lookup_preserves_resolution_precedence_and_ambiguity():
    rows = [
        Node("A/Main#First", "First", "A/Main.md", 1, "", tex="A/paper.tex#x"),
        Node("B/Main#Second", "Second", "B/Main.md", 1, "", tex="B/paper#x"),
        Node("C/Notes#x", "x", "C/Notes.md", 1, "", tex="C/paper#y"),
        Node("A/Notes#Caller", "Caller", "A/Notes.md", 1, "", tex="A/paper#caller",
             uses=["[[B/Main#Second]]"]),
        Node("D/Notes#Caller", "Caller", "D/Notes.md", 1, "", tex="D/paper#caller",
             uses=["[[B/Main#Second]]", "[[Absent#missing]]"]),
        Node("A/Main#Shared", "Shared", "A/Main.md", 1, "", tex="local"),
        Node("B/Main#Shared", "Shared", "B/Main.md", 1, ""),
        Node("Plain#p", "p", "Plain.md", 1, ""),
    ]
    nodes = {node.id: node for node in rows}
    lookup = NodeLookup(nodes)
    labels = {n.title for n in rows} | {"x", "y", "caller", "local", "missing", "Main#Shared",
                                               "[[A/Main.md#First|display]]", "#First"}
    links = [f"[[{n.id}]]" for n in rows] + ["[[Main#Shared]]", "[[Main#First]]", "[[#p]]",
               "[[#Shared]]", "[[unknown#x]]", "[[Plain.md#p|alias]]", "[[No hash]]"]
    for node in rows:
        for label in labels:
            assert lookup.tex_use(label, node) == resolve_tex_use(label, node, nodes)
        for link in links:
            assert lookup.link(link, node.id) == resolve_link(link, node.id, nodes)


def test_queries_do_not_traverse_all_nodes_after_building_lookup():
    class NoScan(dict):
        def values(self):
            if getattr(self, "sealed", False):
                pytest.fail("A dependency lookup scanned the whole workspace")
            return super().values()

    nodes = NoScan({f"P#{i}": Node(f"P#{i}", str(i), "P.md", i + 1, "", tex=f"paper#{i}")
                    for i in range(1000)})
    lookup = NodeLookup(nodes)
    nodes.sealed = True
    for i in range(1000):
        assert lookup.tex_use(str(i), nodes["P#0"]) == f"P#{i}"
        assert lookup.link(f"[[P#{i}]]", "P#0") == f"P#{i}"
    assert lookup.tex_use("missing", nodes["P#0"]) is None


def test_scan_checks_containment_without_resolving_each_normal_file(tmp_path, monkeypatch):
    import qprint.knowledge.index as indexing
    folder = tmp_path / "lean/Deep/Proof"
    folder.mkdir(parents=True)
    for i in range(50):
        (folder / f"{i}.lean").write_text("def x := 0\n")
    hidden = tmp_path / "lean/.lake"
    hidden.mkdir()
    (hidden / "Ignored.lean").write_text("def y := 1\n")
    original = indexing.safe_path
    calls = []

    def checked(root, relative):
        calls.append(relative)
        return original(root, relative)

    monkeypatch.setattr(indexing, "safe_path", checked)
    files = list(_paths(tmp_path))
    assert len(files) == 50
    assert all(path.is_relative_to(tmp_path) for _, path in files)
    assert len(calls) == 5  # one check for each language/document root, not each file


def test_unchanged_index_does_not_decode_cached_source_payloads(tmp_path, monkeypatch):
    import qprint.knowledge.index as indexing
    (tmp_path / "blueprint").mkdir()
    path = tmp_path / "blueprint/Note.md"
    path.write_text("# A\nOld text.\n", encoding="utf-8")
    KnowledgeIndexer(tmp_path).update()
    original = json.loads
    with monkeypatch.context() as patch:
        patch.setattr(indexing.json, "loads", lambda *a, **kw: pytest.fail("decoded unchanged source cache"))
        report = KnowledgeIndexer(tmp_path).update()
        assert report["parsed_files"] == report["updated_nodes"] == 0
    path.write_text("# A\nChanged and longer text.\n", encoding="utf-8")
    assert KnowledgeIndexer(tmp_path).update()["parsed_files"] == 1
    assert json.loads is original


@pytest.mark.skipif(os.name != "nt", reason="Windows junction containment")
@pytest.mark.parametrize("external", [False, True])
def test_directory_junctions_stay_inside_workspace(tmp_path, external):
    import _winapi
    root = tmp_path / "workspace"
    base = root / "lean"
    base.mkdir(parents=True)
    target = (tmp_path if external else root) / "source"
    target.mkdir()
    (target / "Main.lean").write_text("def value := 0\n")
    junction = base / "linked"
    try:
        _winapi.CreateJunction(str(target), str(junction))
    except OSError as exc:
        pytest.skip(f"junctions unavailable: {exc}")
    try:
        if external:
            with pytest.raises(WorkspaceError, match="离开工作区"):
                list(_paths(root))
        else:
            assert list(_paths(root)) == [("lean/linked/Main.lean", target / "Main.lean")]
    finally:
        # Remove only the junction itself, never its contents.
        junction.rmdir()
