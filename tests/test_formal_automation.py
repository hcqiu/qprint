from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import zipfile

import httpx
import pytest

from qprint.formal_agda import source_options
from qprint.formal_archives import extract
from qprint.formal_downloads import download_file, recording
from qprint.formal_environment import FormalExecutionContext
from qprint.formal_git import pinned_package, PACKAGE_RECEIPT, release_metadata
from qprint.formal_policy import safe_policy
from qprint.formal_preparation import config_fingerprints, repair_cache_objects, prepare_environment
from qprint.formal_recovery import inspect_case, recover_case
from qprint.formal_reports import save_report
from qprint.formal_runner import Check
from qprint.formal_service import formal_project
from qprint.importers import import_code
from qprint.paths import WorkspaceError


def context(root, language="agda", **kwargs):
    return FormalExecutionContext(language, "2.8.0", Path("compiler"), Path("driver"), root, root, (), {}, **kwargs)


class Resolver:
    def __init__(self, ctx):
        self.context = ctx

    def resolve(self, project):
        return self.context


@pytest.mark.parametrize("policy,expected", [(True, "require"), (False, "off"), ("inherit", "inherit")])
def test_policy_compatibility(policy, expected):
    assert safe_policy(policy) == expected


def test_source_options_excludes_comments_strings_and_literate_prose(tmp_path):
    path = tmp_path / "A.lagda"
    path.write_text('prose {-# OPTIONS --safe #-}\n\\begin{code}\n'
                    '{- nested {-# OPTIONS --safe #-} -}\n'
                    '-- {-# OPTIONS --safe #-}\n{-# OPTIONS --rewriting --warning=noError #-}\n'
                    'x = "{-# OPTIONS --safe #-}"\n\\end{code}\n')
    assert source_options(path) == ["--rewriting"]


@pytest.mark.parametrize("suffix,text", [
    (".lagda.org", '#+begin_src agda\n{-# OPTIONS --safe #-}\n#+end_src\n#+begin_src agda2\n{-# OPTIONS --rewriting #-}\n#+end_src'),
    (".lagda.rst", 'prose {-# OPTIONS --safe #-}\n\n::\n\n  {-# OPTIONS --rewriting #-}\n  module A where\n\nmore prose\n'),
    (".lagda.tex", '% \\begin{code}\n{-# OPTIONS --safe #-}\n\\end{code}\n\\begin{code}[{-# OPTIONS --safe #-}]\n{-# OPTIONS --rewriting #-}\n\\end{code}')])
def test_literate_probe_uses_only_native_code_blocks(tmp_path, suffix, text):
    path = tmp_path / ("A" + suffix)
    path.write_text(text)
    assert source_options(path) == ["--rewriting"]


@pytest.mark.parametrize("policy,required", [(None, False), ("require", True), ("off", False)])
def test_safe_policy_and_failed_audit_outcomes(tmp_path, policy, required):
    (tmp_path / "A.agda").write_text("{-# OPTIONS --rewriting #-}\nmodule A where\n")
    def run(stage, command, cwd, timeout):
        assert ("--safe" in command) == required
        assert ("--ignore-all-interfaces" in command) == required
        return Check(stage, "failed" if required else "passed", command=command,
                     output="[SafeFlagPragma] Cannot set OPTIONS pragma --rewriting with safe flag" if required else "")
    result = formal_project(tmp_path, "agda", safe=policy, resolver=Resolver(context(tmp_path)), runner=run)
    assert result["outcomes"] == {"typecheck": "unknown" if required else "passed", "safe_audit": "failed" if required else "not_run"}
    if required:
        assert result["diagnosis"]["code"] == "policy_conflict"
        assert not result["runtime_helper"]["candidate"]


def test_native_entry_selection_and_configuration_change(tmp_path):
    (tmp_path / "AllModulesIndex.agda").write_text("module AllModulesIndex where")
    (tmp_path / "A.agda").write_text("module A where")
    (tmp_path / ".qprint-formal.yaml").write_text('toolchain: {agda: "2.8.0"}')
    def run(stage, command, cwd, timeout):
        assert command[-1].endswith("AllModulesIndex.agda")
        (tmp_path / ".qprint-formal.yaml").write_text('toolchain: {agda: "2.9.0"}')
        return Check(stage, "passed")
    result = formal_project(tmp_path, "agda", entry_strategy="auto", resolver=Resolver(context(tmp_path)), runner=run)
    assert result["scope"]["selection"] == "native_entry"
    assert result["status"] == result["outcomes"]["typecheck"] == "stale"


class Interrupted(httpx.SyncByteStream):
    def __iter__(self):
        yield b"abc"
        raise httpx.ReadError("connection interrupted")


def test_download_resumes_only_matching_etag(tmp_path):
    calls, events = [], []
    def handle(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, headers={"ETag": '"same"', "Content-Length": "6"}, stream=Interrupted())
        assert request.headers["Range"] == "bytes=3-"
        assert request.headers["If-Range"] == '"same"'
        return httpx.Response(206, headers={"ETag": '"same"', "Content-Range": "bytes 3-5/6"}, content=b"def")
    with httpx.Client(transport=httpx.MockTransport(handle)) as client, recording(events):
        result = download_file("https://github.com/test/object", tmp_path / "out", client=client, sleep=lambda _: None,
                               expected_sha256=hashlib.sha256(b"abcdef").hexdigest())
    assert (tmp_path / "out").read_bytes() == b"abcdef"
    assert result["attempts"] == 2 and events[-1]["resumed"]


def test_checksum_mismatch_restarts_without_range(tmp_path):
    requests, events = [], []
    def handle(request):
        requests.append(request)
        assert "Range" not in request.headers
        return httpx.Response(200, headers={"ETag": '"v1"'}, content=b"bad" if len(requests) == 1 else b"good")
    with httpx.Client(transport=httpx.MockTransport(handle)) as client, recording(events):
        download_file("https://github.com/test/object", tmp_path / "out", client=client, sleep=lambda _: None,
                      expected_sha256=hashlib.sha256(b"good").hexdigest())
    assert any(e["kind"] == "checksum_mismatch" for e in events)
    assert (tmp_path / "out").read_bytes() == b"good"


def test_failed_download_does_not_publish_and_rejects_redirect(tmp_path):
    for code, headers in [(503, {}), (302, {"Location": "http://localhost/private"})]:
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(code, headers=headers))) as client:
            with pytest.raises((httpx.HTTPError, WorkspaceError)):
                download_file("https://github.com/test/object", tmp_path / "out", client=client, sleep=lambda _: None)
        assert not (tmp_path / "out").exists()
        assert not list(tmp_path.glob(".qprint-download-*"))


def archive_bytes(alias="../README.md"):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("repo/README.md", "documentation")
        archive.writestr("repo/lakefile.toml", 'name = "test"')
        archive.writestr("repo/A.lean", "def a := 1")
        entry = zipfile.ZipInfo("repo/docs/README.md")
        entry.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(entry, alias)
    return stream.getvalue()


@pytest.mark.parametrize("alias,valid", [("../README.md", True), ("../../../outside", False), ("/root", False)])
def test_source_archive_aliases_are_materialized_only_inside_archive(tmp_path, alias, valid):
    archive = tmp_path / "source.zip"
    archive.write_bytes(archive_bytes(alias))
    stage = tmp_path / "stage"
    stage.mkdir()
    if valid:
        extract(archive, stage, strip_root=True, internal_aliases=True)
        assert (stage / "docs/README.md").read_text() == "documentation"
        assert not (stage / "docs/README.md").is_symlink()
    else:
        with pytest.raises(WorkspaceError):
            extract(archive, stage, strip_root=True, internal_aliases=True)
        assert not list(stage.iterdir())


def test_pinned_package_reuse_and_conflicting_revision(tmp_path):
    calls = []
    entry = {"name": "test", "type": "git", "url": "https://github.com/example/test.git", "rev": "a" * 40, "configFile": "lakefile.toml"}
    def fetch(url, path, **kwargs):
        calls.append(url)
        path.write_bytes(archive_bytes())
        return {"sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    target = pinned_package(tmp_path, entry, downloader=fetch)
    assert pinned_package(tmp_path, entry, offline=True) == target
    assert calls == ["https://codeload.github.com/example/test/zip/" + "a" * 40]
    with pytest.raises(WorkspaceError, match="conflicts"):
        pinned_package(tmp_path, {**entry, "rev": "b" * 40}, downloader=fetch)
    assert (target / "A.lean").read_text() == "def a := 1"


def test_release_metadata_requires_authentic_commit_and_exact_tag(tmp_path):
    (tmp_path / PACKAGE_RECEIPT).write_text("{}")
    payload, signature = "tree " + "a" * 40 + "\nauthor A <a@b> 1 +0000\ncommitter A <a@b> 1 +0000\n\nmessage\n", "signature\n"
    header, body = payload.split("\n\n", 1)
    data = (header + "\ngpgsig " + signature.replace("\n", "\n ") + "\n\n" + body).encode()
    revision = hashlib.sha1(b"commit " + str(len(data)).encode() + b"\0" + data).hexdigest()
    entry = {"url": "https://github.com/example/project", "rev": revision, "inputRev": "v1.0.0"}
    def query(path):
        return {"object": {"type": "commit", "sha": revision}} if "/ref/" in path else {"verification": {"payload": payload, "signature": signature}}
    release_metadata(tmp_path, entry, query=query)
    assert (tmp_path / ".git/HEAD").read_text().strip() == revision
    assert not (tmp_path / ".git/index").exists()


def test_cache_repairs_only_missing_or_explicitly_corrupt_objects(tmp_path):
    good, damaged, missing = "a" * 16, "b" * 16, "c" * 16
    (tmp_path / "curl.cfg").write_text("\n".join(f'url = "https://lakecache.blob.core.windows.net/mathlib4/f/{key}.ltar"' for key in [good, damaged, missing]))
    (tmp_path / (good + ".ltar")).write_bytes(b"keep")
    (tmp_path / (damaged + ".ltar")).write_bytes(b"broken")
    calls = []
    def fetch(url, path, **kwargs):
        calls.append(url)
        path.write_bytes(b"repaired")
    assert repair_cache_objects(tmp_path, damaged + ".ltar: removing corrupted file", downloader=fetch) == 2
    assert (tmp_path / (good + ".ltar")).read_bytes() == b"keep"
    assert len(calls) == 2


def test_preparation_retries_runtime_failure_but_not_type_errors(tmp_path, monkeypatch):
    entry = {"name": "mathlib", "type": "git", "url": "https://github.com/leanprover-community/mathlib4", "rev": "a" * 40}
    ctx = context(tmp_path, "lean", requirements={"native": {"lake-manifest.json": {"packages": [entry]}}})
    monkeypatch.setattr("qprint.formal_preparation.pinned_package", lambda *a, **kw: None)
    calls, events = [], []
    def run(stage, command, cwd, timeout, **kwargs):
        calls.append(kwargs)
        return Check(stage, "timeout" if len(calls) == 1 else "passed", output="curl stalled" if len(calls) == 1 else "done")
    with recording(events):
        prepare_environment(ctx, runner=run)
    assert len(calls) == 2 and calls[0]["idle_timeout"] == 90
    assert any(e["kind"] == "cache_retry" for e in events)
    assert not (tmp_path / ".qprint/preparation/lock").exists()
    calls.clear()
    def bad(*a, **kw):
        calls.append(1)
        return Check("mathlib-cache", "failed", output="type mismatch")
    with pytest.raises(WorkspaceError):
        prepare_environment(ctx, runner=bad)
    assert len(calls) == 1
    prepare_environment(ctx, offline=True, runner=lambda *a, **kw: pytest.fail("offline cache execution"))


def make_case(root, home):
    root.mkdir(parents=True, exist_ok=True)
    (root / "A.agda").write_text("module A where\n")
    (root / ".qprint-formal.yaml").write_text('toolchain: {agda: "2.8.0"}\n')
    report = {"status": "error", "message": "Network connection failed", "checks": [],
              "request": {"project": str(root), "toolchain_home": str(home), "language": "agda", "action": "audit",
                          "entries": ["A.agda"], "safe": "require", "offline": True, "entry_strategy": "all"},
              "configuration_sha256": config_fingerprints(root),
              "sources": {"A.agda": hashlib.sha256((root / "A.agda").read_bytes()).hexdigest()}}
    return save_report(root, report, home=home)


def test_runtime_helper_scope_replay_and_attempt_budget(tmp_path):
    root, home = tmp_path / "project", tmp_path / "home"
    report = make_case(root, home)
    case = inspect_case(report["report_path"], root, home)
    assert case["route"] == "runtime_recovery" and "entries" not in case["request"]
    assert "module A" not in json.dumps(case)
    calls = []
    def verify(project, language, **kwargs):
        calls.append(kwargs)
        assert project == root and language == "agda"
        assert kwargs["safe"] == "require" and kwargs["action"] == "audit" and kwargs["offline"]
        return {"status": "error", "report_path": "new-report"}
    for _ in range(3):
        recover_case(report["report_path"], root, home, verify=verify)
    assert recover_case(report["report_path"], root, home, verify=verify)["status"] == "stopped"
    assert len(calls) == 3
    with pytest.raises(WorkspaceError):
        inspect_case(report["report_path"], root, tmp_path / "other")


@pytest.mark.parametrize("changed", ["A.agda", ".qprint-formal.yaml"])
def test_runtime_helper_refuses_changed_inputs(tmp_path, changed):
    report = make_case(tmp_path / "project", tmp_path / "home")
    root = tmp_path / "project"
    (root / changed).write_text("changed")
    with pytest.raises(WorkspaceError, match="changed"):
        recover_case(report["report_path"], root, tmp_path / "home", verify=lambda *a, **kw: pytest.fail("must not replay"))


def test_runtime_helper_detects_unselected_proof_changes(tmp_path):
    root, home = tmp_path / "project", tmp_path / "home"
    report = make_case(root, home)
    (root / "B.agda").write_text("module B where")
    def verify(*args, **kwargs):
        (root / "B.agda").write_text("changed")
        return {"status": "passed", "report_path": "new-report"}
    assert recover_case(report["report_path"], root, home, verify=verify)["status"] == "stale"
    assert not (root / ".qprint/preparation/helper.lock").exists()


def test_release_recovery_records_native_receipt_before_retry(tmp_path, monkeypatch):
    widget = tmp_path / ".lake/packages/proofwidgets"
    widget.mkdir(parents=True)
    (widget / "lakefile.lean").write_text("package proofwidgets where\n  preferReleaseBuild := true\n")
    entries = [{"name": "mathlib", "type": "git", "url": "https://github.com/leanprover-community/mathlib4"},
               {"name": "proofwidgets", "type": "git", "url": "https://github.com/leanprover-community/ProofWidgets4"}]
    ctx = context(tmp_path, "lean", requirements={"native": {"lake-manifest.json": {"packages": entries}}})
    monkeypatch.setattr("qprint.formal_preparation.pinned_package", lambda *args, **kwargs: None)
    archive = tmp_path / "ProofWidgets4.tar.gz"
    url = "https://github.com/leanprover-community/ProofWidgets4/releases/download/v0.0.82/ProofWidgets4.tar.gz"
    monkeypatch.setattr("qprint.formal_preparation._release_fallback", lambda *a, **kw: (archive, url))
    calls = []
    def runner(stage, command, cwd, timeout, **kwargs):
        calls.append(stage)
        if stage == "release-trace":
            program = Path(command[-1]).read_text()
            assert "BuildMetadata.writeFile" in program and url in program
            assert archive.name + ".trace" in program
        return Check(stage, "failed" if len(calls) == 1 else "passed", output="Fetching ProofWidgets cloud release; non UTF-8")
    prepare_environment(ctx, runner=runner)
    assert calls == ["mathlib-cache", "release-trace", "mathlib-cache"]


@pytest.mark.parametrize("enabled", [True, False])
def test_import_default_verification_and_optout_preserve_download(tmp_path, enabled):
    def fetch(url):
        return json.dumps({"sha": "a" * 40}).encode() if "api.github.com" in url else archive_bytes()
    calls, phases = [], []
    def verify(root, language, **kwargs):
        calls.append(root)
        assert (root / "A.lean").exists()
        return {"status": "incomplete", "reports": [{"status": "failed"}]}
    kwargs = {} if enabled else {"verify_after_download": False}
    # The import transport deliberately rejects archive symlinks; use plain members.
    def plain(url):
        if "api.github.com" in url:
            return fetch(url)
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr("repo/A.lean", "def a := 1")
        return stream.getvalue()
    result = import_code(tmp_path, "https://github.com/example/project", "lean", "project", ref="main",
                         downloader=plain, verifier=verify, on_phase=phases.append, **kwargs)
    assert result["verification"]["status"] == ("incomplete" if enabled else "not_run")
    assert len(calls) == int(enabled)
    assert (tmp_path / "lean/project/A.lean").exists()
    assert ("verifying" in phases) == enabled


@pytest.mark.parametrize("enabled,status,exitcode", [(True, "passed", 0), (True, "incomplete", 1), (False, "not_run", 0)])
def test_import_cli_default_switch_and_exit_status(monkeypatch, tmp_path, enabled, status, exitcode):
    from qprint.__main__ import main
    def imported(*args, **kwargs):
        assert kwargs["verify_after_download"] == enabled
        return {"verification": {"status": status}}
    monkeypatch.setattr("qprint.__main__.import_code", imported)
    args = ["qprint", "import-code", "https://github.com/example/repo", "--dest", "repo", "--language", "lean", "--workspace", str(tmp_path)]
    if not enabled:
        args.append("--no-verify-after-download")
    monkeypatch.setattr(sys, "argv", args)
    assert main() == exitcode
