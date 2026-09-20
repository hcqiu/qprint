from pathlib import Path
import subprocess

from qprint.formal import locate_code
from qprint.tex import TexDocument, render_tex


def test_tex_offsets_ignore_comments_and_verbatim_and_support_plain_text():
    source = r'''\documentclass{article}
\newcommand{\bpnode}[1]{}
\begin{document}
\section{First}
% \bpnode{fake}
\begin{verbatim}
\bpnode{not-real}
\end{verbatim}
\bpnode{one}
Unwrapped definition.
\subsection{Second}
\node{two}
\begin{theorem}A theorem.\end{theorem}
\end{document}'''
    doc = TexDocument("A.tex", source)
    assert [a["label"] for a in doc.anchors] == ["one", "two"]
    assert "Unwrapped definition." in doc.fragment("one")
    assert "A theorem" not in doc.fragment("one")
    assert r"\end{document}" not in doc.fragment("two")
    assert len(doc.sections) == 2


def test_duplicate_tex_anchor_and_missing_label():
    doc = TexDocument("A.tex", r"\bpnode{x} first \bpnode{x} second")
    assert doc.fragment("x") is None
    assert doc.fragment("missing") is None
    assert doc.diagnostics


def test_plastex_dom_theorems_math_and_escaped_content():
    html, warnings = render_tex(r"\begin{theorem}For $x$, we have $x=x$.\end{theorem}", r"\newtheorem{theorem}{Theorem}")
    assert 'class="theorem"' in html and 'class="math"' in html
    assert "Theorem" in html
    assert not warnings
    html, _ = render_tex("<script>alert(1)</script>")
    assert "<script>" not in html


def test_unsafe_tex_is_not_executed():
    html, warnings = render_tex(r"\input{../../secret}")
    assert warnings and "tex-fallback" in html


def test_render_timeout_preserves_source(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("renderer", 8)
    monkeypatch.setattr("qprint.tex.subprocess.run", timeout)
    html, warnings = render_tex("A difficult TeX fragment")
    assert warnings and "A difficult TeX fragment" in html


def test_three_language_code_ranges(tmp_path):
    sources = {"lean": ("A.lean", "namespace A\ndef ident (x : Nat) := x\n\ntheorem eq : 1 = 1 := rfl\nend A\n", "A.ident", "def ident (x : Nat) := x"), "agda": ("A.agda", "module A where\nidentity : {A : Set} → A → A\nidentity x = x\n\nnext : Set → Set\nnext A = A", "identity", "identity : {A : Set} → A → A\nidentity x = x"), "coq": ("A.v", "Theorem eq : 1 = 1.\nProof. reflexivity.\nQed.\n\nDefinition one := 1.", "eq", "Theorem eq : 1 = 1.\nProof. reflexivity.\nQed.")}
    for lang, (name, source, declaration, expected) in sources.items():
        folder = tmp_path / lang
        folder.mkdir()
        (folder / name).write_text(source, encoding="utf-8")
        result = locate_code(tmp_path, {"language": lang, "declaration": declaration, "file": name})
        assert result["error"] is None
        assert result["code"] == expected


def test_missing_remote_ambiguous_and_explicit_bounds(tmp_path):
    (tmp_path / "lean").mkdir()
    (tmp_path / "lean" / "A.lean").write_text("namespace A\ndef x := 1\nend A\nnamespace B\ndef x := 2\nend B", encoding="utf-8")
    assert locate_code(tmp_path, {"language": "lean", "declaration": "x", "file": "A.lean"})["error"]
    result = locate_code(tmp_path, {"language": "lean", "declaration": "A.x"})
    assert result["code"] == "def x := 1"
    assert locate_code(tmp_path, {"language": "lean", "declaration": "A.x", "lines": [1, 99]})["error"]
    assert locate_code(tmp_path, {"language": "lean", "declaration": "Missing", "url": "https://github.com/example/repo"})["code"] is None
