from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest
import yaml

from qprint.formal_projects import FormalProjectResolver, ResolutionError
from qprint.formal_artifacts import ArtifactProvider, release_asset
from qprint.formal_environment import FormalExecutionContext, ToolchainResolver
from qprint.formal_reports import diagnose
from qprint.formal_service import formal_project, source_files
from qprint.formal_workspace import Project, load_projects
from qprint.formal_runner import Check
from qprint.toolchains import ToolchainManager

REVISION = "a" * 40


def agda_project(root, *, readme=True):
    root.mkdir(parents=True, exist_ok=True)
    (root / "example.agda-lib").write_text("name: example\ninclude: .\ndepend: cubical\nflags: --cubical --guardedness\n")
    (root / "A.agda").write_text("module A where\n")
    if readme:
        (root / "README.md").write_text(f"Checked against agda/cubical (commit {REVISION}) using Agda 2.8.0\n")
    return Project("agda", root, root)


def test_native_readme_resolution_materializes_reproducible_metadata(tmp_path):
    project = agda_project(tmp_path)
    resolved = FormalProjectResolver().resolve(project)
    assert resolved.version == "2.8.0" and resolved.mode == "cubical"
    assert resolved.libraries == [{"name": "cubical", "revision": REVISION}]
    data = yaml.safe_load((tmp_path / ".qprint-formal.yaml").read_text())
    assert data["dependencies"]["cubical"]["revision"] == REVISION
    assert any(p.get("line") == 1 for p in data["provenance"])
    (tmp_path / "README.md").unlink()
    assert FormalProjectResolver().resolve(project).libraries == resolved.libraries


def test_metadata_and_native_flags_win_over_lower_priority_hints(tmp_path):
    project = agda_project(tmp_path)
    content = 'toolchain:\n  agda: "2.7.0"\ndependencies:\n  cubical:\n    version: "0.8"\npolicy:\n  mode: standard\n'
    path = tmp_path / ".qprint-formal.yaml"
    path.write_text(content)
    resolved = FormalProjectResolver().resolve(project)
    assert resolved.version == "2.7.0" and resolved.libraries[0]["version"] == "0.8"
    assert resolved.mode == "cubical"
    assert path.read_text() == content


def test_recipe_supplies_missing_native_pins(tmp_path):
    project = agda_project(tmp_path, readme=False)
    (tmp_path / ".qprint-formal.lock.yaml").write_text(f'toolchain:\n  agda: "2.8.0"\ndependencies:\n  cubical:\n    revision: {REVISION}\n')
    resolved = FormalProjectResolver().resolve(project)
    assert resolved.version == "2.8.0" and resolved.libraries[0]["revision"] == REVISION


def test_native_library_comments_and_continued_flags(tmp_path):
    project = agda_project(tmp_path)
    (tmp_path / "example.agda-lib").write_text("name: example -- inline comment\ninclude: .\ndepend: cubical\nflags: --cubical\n       --guardedness\n-- full comment\n")
    result = FormalProjectResolver().resolve(project)
    assert result.native["name"] == ["example"]
    assert result.native["flags"] == ["--cubical", "--guardedness"]


@pytest.mark.parametrize("text,code", [("No version here", "missing_version"),
                                     ("Agda 2.8.0 and Agda 2.7.0", "ambiguous_version")])
def test_readme_does_not_guess_missing_or_conflicting_versions(tmp_path, text, code):
    project = agda_project(tmp_path)
    (tmp_path / "README.md").write_text(text)
    with pytest.raises(ResolutionError) as error:
        FormalProjectResolver().resolve(project)
    assert error.value.code == code
    assert not (tmp_path / ".qprint-formal.yaml").exists()


def test_unknown_native_dependency_requires_pin(tmp_path):
    project = agda_project(tmp_path)
    (tmp_path / "example.agda-lib").write_text("name: example\ndepend: standard-library\n")
    with pytest.raises(ResolutionError, match="standard-library"):
        FormalProjectResolver().resolve(project)


def test_lean_native_toolchain_and_lake_lock_are_preserved(tmp_path):
    (tmp_path / "lean-toolchain").write_text("leanprover/lean4:v4.19.0\n")
    lock = {"version": "1.1.0", "packages": [{"name": "mathlib", "rev": REVISION}]}
    (tmp_path / "lake-manifest.json").write_text(json.dumps(lock))
    resolved = FormalProjectResolver().resolve(Project("lean", tmp_path, tmp_path))
    assert resolved.native["lake-manifest.json"] == lock
    assert not (tmp_path / ".qprint-formal.yaml").exists()


def test_missing_lean_version_emits_unique_timestamped_reports(tmp_path):
    first = formal_project(tmp_path, "lean", offline=True)
    second = formal_project(tmp_path, "lean", offline=True)
    assert first["status"] == second["status"] == "unavailable"
    assert first["diagnosis"]["code"] == "missing_version"
    assert first["report_path"] != second["report_path"]
    assert Path(first["report_path"]).is_file()
    assert Path(first["report_path"]).with_suffix(".md").is_file()
    assert first["version_helper"]["retry"]["project"] == str(tmp_path)


def test_native_project_discovery(tmp_path):
    project = agda_project(tmp_path / "agda/topic/proof")
    assert [p.root for p in load_projects(tmp_path)] == [project.root]


def context_for(root):
    return FormalExecutionContext("agda", "2.8.0", Path("agda"), Path("agda"), root, root, (), {}, mode="cubical")


def test_lean_project_does_not_build_lake_configuration_as_a_proof_module(tmp_path):
    for name in ("lakefile.lean", "Proof.lean"):
        (tmp_path / name).write_text("-- example")
    context = replace(context_for(tmp_path), language="lean", mode="standard")
    assert source_files(context) == [tmp_path / "Proof.lean"]


class Resolver:
    def __init__(self, context):
        self.context = context

    def resolve(self, project):
        return self.context


def test_project_checks_every_module_once_and_records_source_hashes(tmp_path):
    (tmp_path / "A.agda").write_text("module A where\n")
    (tmp_path / "Nested").mkdir()
    (tmp_path / "Nested/B.agda").write_text("module Nested.B where\n")
    (tmp_path / ".qprint").mkdir()
    (tmp_path / ".qprint/Hidden.agda").write_text("module Hidden where\n")
    calls = []
    def runner(stage, command, cwd, timeout):
        calls.append(command)
        assert Path(command[-1]) in {tmp_path / "A.agda", tmp_path / "Nested/B.agda"}
        assert "--cubical" not in command and "--safe" not in command
        return Check(stage, "passed", command, returncode=0)
    report = formal_project(tmp_path, "agda", resolver=Resolver(context_for(tmp_path)), runner=runner)
    assert report["status"] == "passed" and len(calls) == 2
    assert set(report["sources"]) == {"A.agda", "Nested/B.agda"}
    assert not list(tmp_path.glob("qprint-project-*"))


def test_report_marks_changed_sources_stale(tmp_path):
    path = tmp_path / "A.agda"
    path.write_text("module A where")
    def runner(stage, *args):
        path.write_text("module A where\n-- changed")
        return Check(stage, "passed")
    report = formal_project(tmp_path, "agda", resolver=Resolver(context_for(tmp_path)), runner=runner)
    assert report["status"] == "stale"


@pytest.mark.parametrize("suffix", [".lagda", ".lagda.tex", ".lagda.md", ".lagda.rst", ".lagda.org", ".lagda.typ"])
def test_literate_agda_discovery_entry_and_declaration(tmp_path, suffix):
    nested = tmp_path / "Topology"
    nested.mkdir()
    source = nested / ("Compact" + suffix)
    source.write_text("literate Agda example")
    (nested / "Notes.md").write_text("not a source module")
    context = context_for(tmp_path)
    assert source_files(context) == [source]
    calls = []
    def runner(stage, command, cwd, timeout):
        calls.append(stage)
        if stage == "declaration":
            generated = Path(command[-1]).read_text()
            assert "import Topology.Compact\n" in generated
            assert "Compact.lagda" not in generated
            if stage == "declaration":
                assert "open Topology.Compact using (compact)" in generated
        else:
            assert Path(command[-1]) == source
        return Check(stage, "passed", command, returncode=0)
    for entries, declaration in [(None, None), ([source.relative_to(tmp_path).as_posix()], None),
                                 ([source.relative_to(tmp_path).as_posix()], "Topology.Compact.compact")]:
        result = formal_project(tmp_path, "agda", entries=entries, declaration=declaration,
                                resolver=Resolver(context), runner=runner)
        assert result["status"] == "passed"
        assert list(result["sources"]) == [source.relative_to(tmp_path).as_posix()]
    assert calls == ["typecheck-project", "typecheck-project", "typecheck", "declaration"]


def test_project_entry_cannot_escape_and_missing_module_is_only_suspected(tmp_path):
    report = formal_project(tmp_path, "agda", entries=["../outside.agda"], resolver=Resolver(context_for(tmp_path)))
    assert report["status"] == "error"
    diagnosis = diagnose({"status": "failed", "checks": [{"status": "failed", "output": "error: [FileNotFound]"}]})
    assert diagnosis["code"] == "dependency_resolution" and diagnosis["certainty"] == "suspected"
    assert not diagnose({"status": "timeout", "checks": [{"status": "timeout"}]})["version_helper_candidate"]
    denied = diagnose({"status": "error", "checks": []}, PermissionError("denied"))
    assert denied["code"] == "filesystem_access" and not denied["version_helper_candidate"]


def test_fixed_commit_auto_download_records_hash_and_reuses_install(tmp_path):
    manager = ToolchainManager(tmp_path / "app", catalog={"schema_version": 1, "artifacts": {}})
    calls = []
    def downloader(url, destination):
        calls.append(url)
        with zipfile.ZipFile(destination, "w") as archive:
            archive.writestr(f"cubical-{REVISION}/cubical.agda-lib", "name: cubical-0.9\ninclude: .\n")
            archive.writestr(f"cubical-{REVISION}/A.agda", "module A where\n")
    provider = ArtifactProvider(manager, downloader=downloader)
    key, item = provider.discover(kind="package", language="agda", name="cubical", revision=REVISION)
    assert manager.installed(key) is not None
    assert len(item["sha256"]) == 64 and len(calls) == 1
    again = ToolchainManager(manager.home)
    assert again.installed(key) is not None
    provider.discover(kind="package", language="agda", name="cubical", revision=REVISION)
    assert len(calls) == 1


def test_offline_resolver_never_invokes_provider(tmp_path):
    project = agda_project(tmp_path / "project")
    class ForbiddenProvider:
        def discover(self, **kwargs):
            pytest.fail("offline resolution attempted network discovery")
    manager = ToolchainManager(tmp_path / "app", catalog={"schema_version": 1, "artifacts": {}})
    resolver = ToolchainResolver(manager=manager, provider=ForbiddenProvider(), auto_install=False)
    report = formal_project(project.root, "agda", resolver=resolver, offline=True)
    assert report["status"] == "unavailable"


@pytest.mark.parametrize("digest,url_ok,passes", [("sha256:" + "b" * 64, True, True),
                                               (None, True, False), ("sha256:" + "b" * 64, False, False)])
def test_official_compiler_discovery_requires_digest_and_expected_asset(monkeypatch, digest, url_ok, passes):
    expected = "https://github.com/agda/agda/releases/download/v2.8.0/Agda-v2.8.0-win64.zip"
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"assets": [{"name": "Agda-v2.8.0-win64.zip", "digest": digest,
                                "browser_download_url": expected if url_ok else "https://example.com/compiler.zip"}]}
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            assert url == "https://api.github.com/repos/agda/agda/releases/tags/v2.8.0"
            return Response()
    monkeypatch.setattr("qprint.formal_artifacts.httpx.Client", Client)
    monkeypatch.setattr("qprint.formal_artifacts.host_platform", lambda: "windows-x64")
    if passes:
        key, artifact = release_asset("agda", "2.8.0")
        assert artifact["sha256"] == "b" * 64 and artifact["url"] == expected
    else:
        with pytest.raises(ValueError):
            release_asset("agda", "2.8.0")


def test_auto_installs_missing_catalog_artifact_before_compiler_execution(tmp_path):
    manager = ToolchainManager(tmp_path / "app", catalog={"schema_version": 1, "artifacts": {
        "agda": {"kind": "toolchain", "language": "agda", "version": "2.8.0", "path": "agda/2.8.0", "executables": {"agda": "bin/agda.exe"}}
    }})
    calls = []
    manager.installed = lambda key: None
    manager.install = lambda key: calls.append(key)
    resolver = ToolchainResolver(manager=manager, auto_install=True)
    assert resolver._artifact(kind="toolchain", language="agda", version="2.8.0")[0] == "agda"
    assert calls == ["agda"]


def test_formal_cli_propagates_failure_and_report_path(tmp_path, monkeypatch, capsys):
    from qprint.__main__ import main
    monkeypatch.setattr(sys, "argv", ["qprint", "formal", "verify", "--project", str(tmp_path), "--language", "lean", "--offline"])
    assert main() == 1
    output = json.loads(capsys.readouterr().out)
    assert Path(output["report_path"]).is_file()
