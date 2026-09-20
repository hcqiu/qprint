from qprint.workspace import Workspace


def make_workspace(tmp_path, files):
    for name, text in files.items():
        file = tmp_path / "blueprint" / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
    return Workspace(tmp_path)


def test_indexed_projects_include_nested_files_and_prefer_nearest_index(tmp_path):
    w = make_workspace(tmp_path, {
        "Topology/Paper/Paper.md": "[[Basics]] [[Proofs/Main#Result]]",
        "Topology/Paper/Basics.md": "# Definition\nA definition.",
        "Topology/Paper/Proofs/Main.md": "# Result\nA result.",
        "Topology/Paper/Subproject/index.md": "[[Lemma]]",
        "Topology/Paper/Subproject/Lemma.md": "# Lemma\nStatement",
        "Algebra/Library/Group.md": "# Group\nStatement",
        "Algebra/Library/Extra/Ring.md": "# Ring\nStatement",
    })
    graph = w.project()["graph"]
    membership = graph["file_projects"]
    assert membership["Topology/Paper/Proofs/Main.md"] == "Topology/Paper"
    assert membership["Topology/Paper/Subproject/Lemma.md"] == "Topology/Paper/Subproject"
    assert membership["Algebra/Library/Group.md"] == "Algebra/Library"
    assert membership["Algebra/Library/Extra/Ring.md"] == "Algebra/Library/Extra"
    paper = next(p for p in graph["projects"] if p["id"] == "Topology/Paper")
    assert paper["index_path"] == "Topology/Paper/Paper.md"
    assert len(paper["file_ids"]) == 3
    assert len(paper["node_ids"]) == 2
    assert len(graph["files"]) == 7  # Index-only Markdown files are included.
    assert graph["node_projects"]["Topology/Paper/Proofs/Main#Result"] == "Topology/Paper"


def test_file_edges_include_heading_file_and_markdown_links_and_deduplicate(tmp_path):
    w = make_workspace(tmp_path, {
        "A/A.md": "[[../B/B]]",
        "A/One.md": '# One\n```qprint\nuses: ["[[B/Two#First]]", "[[B/Two#Second]]"]\n```\n[[B/Two]]\n[second](../B/Two.md#Second)\n[[#One]]',
        "B/B.md": "[[Two]]",
        "B/Two.md": "# First\nText\n# Second\nText",
    })
    graph = w.project()["graph"]
    pairs = {(e["source"], e["target"]) for e in graph["file_edges"]}
    assert pairs == {("B/B.md", "A/A.md"), ("B/Two.md", "A/One.md"), ("B/Two.md", "B/B.md")}
    assert graph["project_edges"] == [{"source": "B", "target": "A", "kind": "reference", "count": 2}]
    assert len(w.edges) == 2  # File aggregation does not rewrite blueprint edges.


def test_examples_comments_external_and_ambiguous_links_do_not_make_edges(tmp_path):
    w = make_workspace(tmp_path, {
        "A/Source.md": '# X\n[[Target]]\n[[Missing]]\n[[https://[broken]]\n```md\n[[B/Target]]\n```\n`[[C/Target]]`\n<!-- [[B/Target]] -->\n[web](https://example.org/C/Target.md)',
        "B/Target.md": "# B",
        "C/Target.md": "# C",
    })
    assert w.project()["graph"]["file_edges"] == []


def test_root_fallback_empty_files_status_and_duplicate_basenames(tmp_path):
    w = make_workspace(tmp_path, {
        "Root.md": "# Root\n```qprint\nstatus: complete\n```",
        "A/Empty.md": "",
        "B/Empty.md": "# Todo",
    })
    graph = w.project()["graph"]
    assert graph["file_projects"]["Root.md"] == "."
    assert {p["id"] for p in graph["projects"]} == {".", "A", "B"}
    assert len({file["id"] for file in graph["files"]}) == 3
    assert next(f for f in graph["files"] if f["id"] == "A/Empty.md")["node_ids"] == []
    assert next(p for p in graph["projects"] if p["id"] == ".")["status"] == "complete"


def test_named_index_precedence_and_graph_rebuild_after_save(tmp_path):
    w = make_workspace(tmp_path, {"P/P.md": "", "P/index.md": "", "P/N.md": "# N", "Q/Q.md": ""})
    assert w.project()["graph"]["projects"][0]["index_path"] == "P/P.md"
    document = w.document("P/P.md")
    w.save_document(document["path"], "[[Q/Q]]", document["revision"])
    assert w.project()["graph"]["project_edges"][0]["source"] == "Q"
    assert w.project()["graph"]["project_edges"][0]["target"] == "P"


def test_empty_vault_and_project_cycles(tmp_path):
    assert Workspace(tmp_path).project()["graph"]["projects"] == []
    w = make_workspace(tmp_path, {"A/index.md": "[[B/index]]", "B/index.md": "[[A/index]]"})
    edges = w.project()["graph"]["project_edges"]
    assert {(e["source"], e["target"]) for e in edges} == {("A", "B"), ("B", "A")}
