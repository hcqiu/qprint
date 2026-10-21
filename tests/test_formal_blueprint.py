import io
import json
from pathlib import Path
import zipfile

import pytest

from qprint.formal import locate_code
from qprint.formal_blueprint import annotate_tex, convert_project, lean_declarations
from qprint.importers import extract_archive
from qprint.paths import WorkspaceError
from qprint.tex import TexDocument, tex_commands
from qprint.workspace import Workspace


def write(root, name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def fixture(root):
    source = root / "upstream"
    write(source, "Theory/blueprint/chapters/one.tex", r"""\section{Basics}
% \label{fake}
\begin{definition}\label{def:one}
\lean{A.one}\leanok
One.
\end{definition}
\begin{lemma}\label{lem:one}
\uses{def:one}\lean{A.result, A.second}
\bpdesc{An existing {description}.}
Statement.
\end{lemma}
\begin{proof}\uses{def:one}Proof.\end{proof}
""")
    write(source, "Theory/blueprint/chapters/two.tex", r"""\begin{theorem}\label{thm:final}
\lean{A.final}\uses{lem:one}\end{theorem}
""")
    write(source, "Theory/A.lean", """namespace A
section Hidden
/-- theorem fake : False := sorry -/
def one : Nat := 1
end Hidden
@[simp]
theorem result : one = 1 := by
  rfl
theorem second : True := by
  trivial
theorem final : True := second
end A
""")
    write(source, "Theory/lean-toolchain", "leanprover/lean4:v4.19.0\n")
    write(source, "Theory/lakefile.toml", 'name = "example"\n')
    write(source, "LICENSE", "Upstream license\n")
    write(source, "Theory/blueprint/refs.bib", "@book{x,title={X}}\n")
    return source


def test_roundtrip_preserves_source_annotations_and_native_code(tmp_path):
    source = fixture(tmp_path)
    original = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    report = convert_project(str(source), "Imported", root=tmp_path)
    output = tmp_path / "Imported"
    workspace = Workspace(output)
    assert not workspace.diagnostics
    assert report["nodes"] == 3
    assert report["bpnode_added"] == 3
    assert report["located_lean_bindings"] == 4
    assert report["descriptions"] == 1
    assert report["leanok_nodes"] == 1
    assert report["diagnostics"] == []
    assert {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()} == original
    for relative, data in original.items():
        assert (output / "lean" / relative).read_bytes() == data
        if relative.suffix == ".tex":
            converted = (output / "tex" / relative).read_text(encoding="utf-8")
            for name in ("label", "uses", "lean", "bpdesc"):
                before = [c["value"] for c in tex_commands(data.decode(), {name})]
                after = [c["value"] for c in tex_commands(converted, {name})]
                assert before == after
    nodes = {n.title: n for n in workspace.nodes.values()}
    assert nodes["def:one"].body == ""
    assert nodes["lem:one"].body == "An existing {description}."
    for n in workspace.nodes.values():
        for binding in n.bindings:
            located = locate_code(output, binding)
            assert not located["error"]
            assert binding["declaration"].split(".")[-1] in located["code"]
    binding = nodes["lem:one"].bindings[0]
    assert binding["lines"] == [6, 8]
    assert "theorem second" not in locate_code(output, binding)["code"]
    doc = workspace.tex["Theory/blueprint/chapters/one.tex"]
    assert doc.fragment("def:one").startswith(r"\begin{definition}\label{def:one}")
    assert r"\begin{proof}" in doc.fragment("lem:one")


def test_existing_anchors_comments_preamble_and_repeated_labels():
    source = r"""\documentclass{article}
\newcommand{\example}{\label{#1}}
\begin{document}
\bpnode{a}
\begin{lemma}\label{a}\lean{A.a}\end{lemma}
\verb|\label{fake}| % \label{fake2}
\section{Proof}
\begin{proof}\label{a}Proof.\end{proof}
\end{document}
\label{outside}
"""
    converted, count = annotate_tex(source)
    assert count == 1
    doc = TexDocument("main.tex", converted)
    assert len(doc.fragments("a")) == 2
    assert r"\begin{proof}" in doc.fragment("a")
    converted, count = annotate_tex(r"\begin{lemma}\label{x}X\end{lemma}")
    assert count == 1
    assert annotate_tex(converted) == (converted, 0)


def test_exact_names_sections_nested_comments_multiline_and_root():
    source = """/- namespace Bogus
/- theorem fake : False := sorry -/
-/
namespace A
section
namespace B
noncomputable def
  value : Nat := 1
end B
end
def text := "namespace Bogus\\\" -- theorem fake"
theorem _root_.Global.result : True := by
  trivial
end A
"""
    declarations = lean_declarations(source, "Code.lean")
    assert [b["declaration"] for b in declarations] == ["A.B.value", "A.text", "Global.result"]
    assert declarations[0]["lines"] == [7, 8]


def test_project_scoping_and_unresolved_declarations(tmp_path):
    source = fixture(tmp_path)
    write(source, "Other/blueprint/one.tex", r"\begin{lemma}\label{def:one}\lean{A.one}\end{lemma}")
    write(source, "Other/B.lean", "namespace A\ndef one := 2\nend A\n")
    write(source, "Theory/blueprint/missing.tex", r"\label{missing}\lean{one, No.such}\uses{not-found}")
    report = convert_project(str(source), "Imported", root=tmp_path)
    assert [d["kind"] for d in report["diagnostics"]] == ["unresolved_lean", "unresolved_lean", "unresolved_use"]
    workspace = Workspace(tmp_path / "Imported")
    own = next(n for n in workspace.nodes.values() if n.title == "def:one" and n.path.startswith("Theory/"))
    assert own.bindings[0]["file"] == "Theory/A.lean"
    assert any(e["source"] == own.id and e["target"].endswith("#lem:one") for e in workspace.edges)


def test_no_overwrite_and_atomic_failure(tmp_path):
    source = fixture(tmp_path)
    write(source, "Theory/blueprint/invalid.tex", r"\label{unclosed")
    with pytest.raises(ValueError, match="未闭合"):
        convert_project(str(source), "Imported", root=tmp_path)
    assert not (tmp_path / "Imported").exists()
    assert not list(tmp_path.glob(".qprint-convert-*"))
    (source / "Theory/blueprint/invalid.tex").unlink()
    convert_project(str(source), "Imported", root=tmp_path)
    with pytest.raises(WorkspaceError, match="已存在"):
        convert_project(str(source), "Imported", root=tmp_path)
    for destination in ("../escape", "a/b", "CON", ".", "bad#name"):
        with pytest.raises(WorkspaceError):
            convert_project(str(source), destination, root=tmp_path)


def test_github_commit_pinning_and_archive_paths(tmp_path):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("repo/blueprint/content.tex", r"\label{x}\lean{X.x}")
        z.writestr("repo/X.lean", "namespace X\ndef x := 0\nend X")
    calls = []
    sha = "a" * 40

    def download(url):
        calls.append(url)
        if url.endswith("/commits/main"):
            return json.dumps({"sha": sha}).encode()
        if "codeload" in url:
            assert url.endswith(sha)
            return archive.getvalue()
        return b'{"default_branch":"main"}'

    report = convert_project("https://github.com/example/repo", "Imported", root=tmp_path, downloader=download)
    assert report["provenance"]["commit"] == sha
    assert report["located_lean_bindings"] == 1
    assert len(calls) == 3
    malicious = io.BytesIO()
    with zipfile.ZipFile(malicious, "w") as z:
        z.writestr("repo/../../escape.tex", r"\label{x}")
    path = tmp_path / "bad.zip"
    path.write_bytes(malicious.getvalue())
    with pytest.raises(WorkspaceError):
        convert_project(str(path), "Bad", root=tmp_path)
    assert not (tmp_path / "Bad").exists()


def test_unsupported_label_is_preserved_and_reported(tmp_path):
    source = fixture(tmp_path)
    raw = r"\label{bad\macro} Text."
    write(source, "Theory/blueprint/bad.tex", raw)
    report = convert_project(str(source), "Imported", root=tmp_path)
    assert report["nodes"] == 3
    assert report["diagnostics"] == [{"kind": "unsupported_label", "label": r"bad\macro",
                                       "line": 1, "file": "Theory/blueprint/bad.tex"}]
    assert (tmp_path / "Imported/tex/Theory/blueprint/bad.tex").read_text() == raw


def test_separate_lean_repository_and_tex_root_filter(tmp_path):
    source = fixture(tmp_path)
    companion = tmp_path / "proof"
    write(companion, "Extra.lean", "namespace Extra\ndef value := 1\nend Extra\n")
    write(source, "Supplement/blueprint/content.tex", r"\label{extra}\lean{Extra.value}")
    report = convert_project(str(source), "Imported", root=tmp_path,
                             lean_source=str(companion), tex_roots=["Supplement"])
    assert report["nodes"] == 1 and report["located_lean_bindings"] == 1
    node = next(iter(Workspace(tmp_path / "Imported").nodes.values()))
    assert node.bindings[0]["file"] == "companion/Extra.lean"


def test_archive_limits_and_excluded_history(tmp_path):
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w") as z:
        z.writestr("repo/blueprint/main.tex", r"\label{x}")
        z.writestr("repo/archive/old.tex", r"\label{old}")
    with pytest.raises(WorkspaceError, match="限制"):
        extract_archive(data.getvalue(), tmp_path / "small", strip_root=True, max_files=1)
    files = extract_archive(data.getvalue(), tmp_path / "large", strip_root=True,
                            max_files=2, excluded_directories=frozenset({"archive"}))
    assert files == ["blueprint/main.tex"]
    assert not (tmp_path / "large/archive").exists()


def test_citation_inside_uses_is_preserved_without_invalid_yaml(tmp_path):
    source = fixture(tmp_path)
    raw = "\\label{citation}\\uses{\\cite{book}\n\\dcref{A.1}}"
    write(source, "Theory/blueprint/cite.tex", raw)
    report = convert_project(str(source), "Imported", root=tmp_path)
    assert report["diagnostics"][0]["kind"] == "unsupported_use"
    workspace = Workspace(tmp_path / "Imported")
    assert not workspace.diagnostics
    node = next(n for n in workspace.nodes.values() if n.title == "citation")
    assert node.uses == []
    assert raw in (tmp_path / "Imported/tex/Theory/blueprint/cite.tex").read_text()
