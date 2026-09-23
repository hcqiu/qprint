import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from qprint.paths import WorkspaceError
from qprint.tex import TexDocument, render_tex, tex_commands
from qprint.tex_to_blueprint import generate, search
from qprint.workspace import Workspace


SOURCE = r'''\documentclass{article}
\providecommand{\bpnode}[1]{}
\providecommand{\bpdesc}[1]{}
\providecommand{\uses}[1]{}
\newtheorem{theorem}{Theorem}
\begin{document}
\section{Intro}
\bpnode{object}\bpdesc{An unwrapped {shared} object.}
Let $X$ be a space.
\subsection{Main}
\bpnode{main}\bpdesc{Main statement.}
\begin{theorem}\label{main}Apply the object\uses{object, ext}.\end{theorem}
\bpnode{other}\bpdesc{Another result.}\label{other}Other content.
\subsection{Proofs}
\bpnode{main}\bpdesc{Proof {with $x$}.}
\begin{proof}See \ref{other}\uses{other, object}.\end{proof}
\subsection{Empty}
\end{document}
\bpnode{after-document}
'''


def setup_project(root):
    (root / "tex").mkdir()
    (root / "tex" / "paper.tex").write_text(SOURCE, encoding="utf-8")
    external = root / "blueprint" / "Library"
    external.mkdir(parents=True)
    (external / "index.md").write_text("## Library\n", encoding="utf-8")
    (external / "Objects.md").write_text('# ext\nAn external object.\n', encoding="utf-8")


def convert(root, **kwargs):
    return generate(root, ["paper.tex"], "Topology/Paper", title="Paper", authors=["A", "B"],
                    year="2025", keywords=["Topology"], **kwargs)


def test_balanced_annotations_and_repeated_fragments():
    doc = TexDocument("paper.tex", SOURCE)
    assert not doc.diagnostics
    assert doc.annotations("main") == {"descriptions": ["Main statement.", "Proof {with $x$}."],
                                       "uses": ["object", "ext", "other"]}
    assert doc.fragment("after-document") is None
    assert r"\subsection" not in doc.fragment("main")
    assert "Other content" not in doc.fragment("main")
    assert r"\begin{proof}" in doc.fragment("main")
    source = r'''% \uses{fake}
\verb|\uses{fake}| \begin{verbatim}\bpnode{fake}\end{verbatim}
\bpdesc{nested {value} and \{escaped\}} \uses{real}'''
    assert [c["name"] for c in tex_commands(source, {"bpnode", "bpdesc", "uses"})] == ["bpdesc", "uses"]


def test_generation_roundtrip_and_inline_rendering(tmp_path):
    setup_project(tmp_path)
    report = convert(tmp_path)
    assert report["nodes"] == 3 and not report["diagnostics"]
    assert len(report["files"]) == 5  # intro, three subsections, index
    workspace = Workspace(tmp_path)
    assert not workspace.diagnostics
    main = next(n for n in workspace.nodes.values() if n.title == "main")
    assert main.body == "Main statement.\n\nProof {with $x$}."
    assert len(main.uses) == 3
    detail = workspace.detail(main.id)
    html = detail["tex_content"]["html"]
    assert not detail["tex_content"]["warnings"]
    assert "bpdesc" not in html and "qprintdependency" not in html
    assert "Main statement." not in html
    assert html.count('class="wikilink tex-use"') == 4
    assert "href=\"#node=Library%2FObjects%23ext\"" in html
    assert r"\ref{other}" not in html
    assert 'class="reference tex-ref"' in html
    other = next(n for n in workspace.nodes.values() if n.title == "other")
    assert f'data-tex-node="{other.id}"' in html
    assert "Theorem" in html and "Proof" in html
    index = (tmp_path / "blueprint/Topology/Paper/index.md").read_text(encoding="utf-8")
    assert "[[Library/index.md]]" in index and "authors:" in index
    assert all(n.path != "Topology/Paper/index.md" for n in workspace.nodes.values())
    assert search(tmp_path, "external")[0]["id"] == "Library/Objects#ext"


def test_dry_run_and_no_overwrite(tmp_path):
    setup_project(tmp_path)
    assert convert(tmp_path, dry_run=True)["dry_run"]
    target = tmp_path / "blueprint/Topology/Paper"
    assert not target.exists()
    convert(tmp_path)
    before = {p.name: p.read_bytes() for p in target.iterdir()}
    with pytest.raises(WorkspaceError, match="已存在"):
        convert(tmp_path)
    assert before == {p.name: p.read_bytes() for p in target.iterdir()}


def test_ambiguous_external_dependency_and_override(tmp_path):
    setup_project(tmp_path)
    (tmp_path / "blueprint/Library/Duplicate.md").write_text("# ext\nDuplicate", encoding="utf-8")
    report = convert(tmp_path, dry_run=True)
    assert len(report["diagnostics"]) == 1 and "ext" in report["diagnostics"][0]
    report = convert(tmp_path, dependency_map={"ext": "Library/Objects#ext"})
    assert not report["diagnostics"]
    workspace = Workspace(tmp_path)
    main = next(n for n in workspace.nodes.values() if n.title == "main")
    assert 'href="#node=Library%2FObjects%23ext"' in workspace.detail(main.id)["tex_content"]["html"]


def test_unresolved_and_math_links_escape_html():
    html, warnings = render_tex(r"$x\uses{ok}$ \uses{<bad>}", references={"ok": 'A#<target>"'})
    assert 'href="#node=A%23%3Ctarget%3E%22"' in html
    assert "qprintdependency" not in html
    assert '<bad>' not in html and '&lt;bad&gt;' in html
    assert any("<bad>" in w for w in warnings)


@pytest.mark.parametrize("source", [r"\bpnode{x}\bpdesc{unclosed", r"\bpnode{bad#label}text"])
def test_invalid_annotation_does_not_publish(tmp_path, source):
    setup_project(tmp_path)
    (tmp_path / "tex/paper.tex").write_text(source, encoding="utf-8")
    with pytest.raises(WorkspaceError):
        convert(tmp_path)
    assert not (tmp_path / "blueprint/Topology/Paper").exists()


def test_script_cli_and_path_guard(tmp_path):
    setup_project(tmp_path)
    script = Path(__file__).parents[1] / "skills/tex-to-blueprint/scripts/convert.py"
    run = subprocess.run([sys.executable, str(script), "search", "--workspace", str(tmp_path),
                          "--query", "external"], capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0 and json.loads(run.stdout)[0]["id"] == "Library/Objects#ext"
    with pytest.raises(WorkspaceError):
        generate(tmp_path, ["../outside.tex"], "New", title="X", authors=["A"], year="2025", keywords=[])


def test_multiple_files_with_same_label_keep_local_dependencies(tmp_path):
    setup_project(tmp_path)
    source = r'''\newtheorem{thm}{Theorem}
\begin{document}
\subsection[Short]{Nested {title {value}}}
\bpnode{x}\bpdesc{Definition} Plain definition.
\bpnode{y}\bpdesc{Result} \begin{thm}Use x\uses{x}.\end{thm}
\end{document}'''
    for name in ("one.tex", "two.tex"):
        (tmp_path / "tex" / name).write_text(source, encoding="utf-8")
    report = generate(tmp_path, ["one.tex", "two.tex"], "Multi", title="Multiple files",
                      authors=["A"], year="2025", keywords=[])
    assert report["nodes"] == 4 and not report["diagnostics"]
    workspace = Workspace(tmp_path)
    for node in workspace.nodes.values():
        if node.title == "y":
            assert node.kind == "theorem"
            assert node.uses == [f"[[{node.path[:-3]}#x]]"]


def test_render_fallback_preserves_annotations():
    source = r"\bpdesc{Description} \uses{x} \includegraphics{figure.pdf}"
    html, warnings = render_tex(source)
    assert "tex-fallback" in html and warnings
    assert source in html and "qprintdependency" not in html


def test_literal_escaped_commands_are_not_annotations():
    commands = list(tex_commands(r"\\bpnode{fake} \\\bpnode{real}", {"bpnode"}))
    assert [c["value"] for c in commands] == ["real"]


@pytest.mark.parametrize("bibliography", [r"\bibliographystyle{plain}\bibliography{refs}",
                                         r"\printbibliography", r"\begin{thebibliography}{9}References\end{thebibliography}"])
def test_final_node_does_not_absorb_bibliography(bibliography):
    doc = TexDocument("paper.tex", r"\bpnode{main}\bpdesc{Statement}Main result. "
                      r"\bpnode{other}Other result. \bpnode{main}\bpdesc{Proof}"
                      r"\begin{proof}A proof.\end{proof}" + bibliography)
    fragment = doc.fragment("main")
    assert "Main result" in fragment and "A proof" in fragment
    assert "bibliography" not in fragment and "Other result" not in fragment
    html, warnings = render_tex(fragment)
    assert "tex-fallback" not in html and not warnings


def test_skill_is_portable_with_rendering_outside_checkout(tmp_path):
    setup_project(tmp_path)
    repository = Path(__file__).parents[1]
    skill = tmp_path / "portable-skill"
    shutil.copytree(repository / "skills/tex-to-blueprint", skill,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    script = skill / "scripts/convert.py"
    # A paper's working directory must not shadow the bundled rendering worker.
    shadow = tmp_path / "qprint_blueprint"
    shadow.mkdir()
    (shadow / "__init__.py").write_text("raise RuntimeError('untrusted working directory package')", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": "", "PYTHONIOENCODING": "utf-8"}
    command = [sys.executable, str(script)]
    result = subprocess.run(command + ["generate", "--workspace", str(tmp_path), "--tex", "paper.tex",
                            "--dest", "Topology/Paper", "--title", "Paper", "--author", "A", "--year", "2025"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    result = subprocess.run(command + ["validate", "--workspace", str(tmp_path),
                            "--project", "Topology/Paper", "--render-limit", "3"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["nodes"] == 3 and not report["diagnostics"]
    assert len(report["renders"]) == 3
    assert all(not render["fallback"] for render in report["renders"])
    assert sum(render["inline_links"] for render in report["renders"]) == 4


def test_bundled_runtime_matches_application_modules():
    repository = Path(__file__).parents[1]
    bundled = repository / "skills/tex-to-blueprint/scripts/qprint_blueprint"
    for path in bundled.glob("*.py"):
        if path.name != "__init__.py":
            assert path.read_bytes() == (repository / "qprint" / path.name).read_bytes(), path.name
