import gzip
import io
import json
from pathlib import Path
import stat
import tarfile
import zipfile

import pytest
import httpx

from qprint.importers import arxiv_id, extract_archive, import_code, import_paper
from qprint.paths import WorkspaceError


def zip_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output.getvalue()


def tar_bytes(files):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
    return output.getvalue()


def test_repository_default_branch_nested_code_license_and_no_overwrite(tmp_path):
    calls = []
    def download(url):
        calls.append(url)
        if "/commits/" in url:
            return json.dumps({"sha": "a" * 40}).encode()
        if "api.github.com" in url:
            return json.dumps({"default_branch": "main"}).encode()
        return zip_bytes({"repo-main/Topology/Test.agda": "module Test where", "repo-main/LICENSE": "License"})
    result = import_code(tmp_path, "https://github.com/test/repo", "agda", "serre-finiteness", downloader=download, verify_after_download=False)
    assert result["files"] == 2
    assert (tmp_path / "agda/serre-finiteness/Topology/Test.agda").exists()
    assert (tmp_path / "agda/serre-finiteness/LICENSE").exists()
    assert (tmp_path / "agda/serre-finiteness/.qprint-source.json").exists()
    assert len(calls) == 3 and calls[-1].endswith("a" * 40)
    with pytest.raises(WorkspaceError):
        import_code(tmp_path, "https://github.com/test/repo", "agda", "serre-finiteness", downloader=download)


@pytest.mark.parametrize("name", ["../escape", "root/../../escape", "/absolute", "C:/escape", "root/file:ads", "root/nul.txt"])
def test_archive_rejects_traversal_before_writing(tmp_path, name):
    with pytest.raises(WorkspaceError):
        extract_archive(zip_bytes({"ok.txt": "ok", name: "bad"}), tmp_path)
    assert not (tmp_path / "ok.txt").exists()


def test_archives_reject_symlinks_and_expansion_limits(tmp_path, monkeypatch):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        member = tarfile.TarInfo("escape")
        member.type = tarfile.SYMTYPE
        member.linkname = "../outside"
        archive.addfile(member)
    with pytest.raises(WorkspaceError):
        extract_archive(output.getvalue(), tmp_path)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        member = zipfile.ZipInfo("escape")
        member.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(member, "../outside")
    with pytest.raises(WorkspaceError):
        extract_archive(output.getvalue(), tmp_path)
    monkeypatch.setattr("qprint.importers.MAX_EXPANDED", 5)
    with pytest.raises(WorkspaceError):
        extract_archive(zip_bytes({"large": "123456"}), tmp_path)


@pytest.mark.parametrize("value,expected", [("2001.00001", "2001.00001"), ("https://arxiv.org/pdf/2001.00001v2.pdf", "2001.00001v2"), ("arXiv:math/0301234", "math/0301234")])
def test_arxiv_identifiers(value, expected):
    assert arxiv_id(value) == expected


@pytest.mark.parametrize("format", ["tar", "gzip", "plain"])
def test_paper_formats_and_matching_output_names(tmp_path, format):
    tex = b"\\documentclass{article}\n\\begin{document}Hello\\end{document}"
    source = tar_bytes({"main.tex": tex, "images/fig.txt": b"figure"}) if format == "tar" else gzip.compress(tex) if format == "gzip" else tex
    result = import_paper(tmp_path, "2001.00001", "Topology", "Lin20K3", downloader=lambda url: b"%PDF-1.7\nexample" if "/pdf/" in url else source)
    assert result["pdf"] == "pdf/Topology/Lin20K3.pdf"
    assert (tmp_path / result["pdf"]).exists()
    assert list((tmp_path / result["tex"]).rglob("*.tex"))


def test_paper_error_rolls_back_and_preserves_existing_files(tmp_path):
    def download(url):
        return b"%PDF-1.7" if "/pdf/" in url else b"<html>Source unavailable</html>"
    with pytest.raises(WorkspaceError):
        import_paper(tmp_path, "2001.00001", "Topology", "Test", downloader=download)
    assert not (tmp_path / "pdf/Topology/Test.pdf").exists()
    assert not (tmp_path / "tex/Topology/Test").exists()
    assert not list(tmp_path.glob(".qprint-import-*"))


def test_invalid_external_sources(tmp_path):
    for url in ["https://evil.com/abs/2001.00001", "../../bad", "2001.00001;cmd"]:
        with pytest.raises(WorkspaceError):
            arxiv_id(url)
    with pytest.raises(WorkspaceError):
        import_code(tmp_path, "https://evil.com/test/repo", "lean", "repo")


def test_download_rejects_offsite_redirect_and_large_body(monkeypatch):
    from qprint import importers
    original_client = httpx.Client
    def handler(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
    monkeypatch.setattr(importers.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(WorkspaceError, match="HTTPS"):
        importers.fetch("https://arxiv.org/pdf/2001.00001")
    monkeypatch.setattr(importers, "MAX_DOWNLOAD", 5)
    monkeypatch.setattr(importers.httpx, "Client", lambda **kwargs: original_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"123456")), **kwargs))
    with pytest.raises(WorkspaceError, match="byte limit"):
        importers.fetch("https://arxiv.org/pdf/2001.00001")
