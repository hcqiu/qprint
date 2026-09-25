import hashlib
import json
import os
from pathlib import Path
import stat
import shutil
import zipfile

import pytest

from qprint.formal_environment import ToolchainResolver
from qprint.paths import WorkspaceError
from qprint.release import build_release
from qprint.toolchains import EnvironmentUnavailable, RECEIPT, ToolchainManager, extract_zip, host_platform
from qprint.verification import Check, Project, load_projects, verify_bindings


def installed_manager(root):
    artifacts = {}
    for language, version in (("lean", "4.19.0"), ("lean", "4.23.0"), ("agda", "2.8.0")):
        key = f"{language}-{version}"
        artifacts[key] = {"kind": "toolchain", "language": language, "version": version,
                          "platform": host_platform(), "path": f"{language}/{version}",
                          "sha256": "a" * 64, "executables": {language: f"bin/{language}.exe"}}
        if language == "lean":
            artifacts[key]["executables"]["lake"] = "bin/lake.exe"
    artifacts["cubical"] = {"kind": "package", "language": "agda", "version": "0.9", "name": "cubical",
                            "revision": "b" * 40, "path": "agda/cubical/" + "b" * 40,
                            "sha256": "c" * 64, "include_paths": ["src"], "library_file": "cubical.agda-lib",
                            "flags": ["--guardedness"]}
    manager = ToolchainManager(root, catalog={"schema_version": 1, "artifacts": artifacts})
    for key, item in artifacts.items():
        target = manager.target(item)
        target.mkdir(parents=True)
        (target / RECEIPT).write_text(json.dumps({"id": key, "sha256": item["sha256"]}))
        for relative in item.get("executables", {}).values():
            binary = target / relative
            binary.parent.mkdir(exist_ok=True)
            binary.write_bytes(b"test executable; never run")
        if item["language"] == "agda" and item["kind"] == "toolchain":
            (target / "data").mkdir()
        if item["kind"] == "package":
            (target / "src").mkdir()
            (target / "cubical.agda-lib").write_text("name: cubical\ninclude: src\n")
    return manager


def project(root, language="lean", version="4.19.0"):
    path = root / language / version
    path.mkdir(parents=True)
    if language == "lean":
        (path / "lean-toolchain").write_text(f"leanprover/lean4:v{version}\n")
    else:
        (path / "project.yaml").write_text(f'schema_version: 1\nformal:\n  agda:\n    version: "{version}"\n')
    return Project(language, path, path)


def test_two_lean_versions_are_resolved_independently(tmp_path, monkeypatch):
    manager = installed_manager(tmp_path / "app")
    resolver = ToolchainResolver(manager=manager)
    monkeypatch.setenv("LEAN_PATH", "unrelated-global-project")
    monkeypatch.setenv("LEAN_SYSROOT", "wrong")
    first = resolver.resolve(project(tmp_path / "workspace", version="4.19.0"))
    second = resolver.resolve(project(tmp_path / "workspace", version="4.23.0"))
    assert "4.19.0" in str(first.driver) and "4.23.0" in str(second.driver)
    assert first.driver.is_absolute()
    assert first.environment["PATH"].split(os.pathsep)[0] == str(first.driver.parent)
    assert "LEAN_PATH" not in first.environment and "LEAN_SYSROOT" not in first.environment
    assert os.environ["LEAN_PATH"] == "unrelated-global-project"


@pytest.mark.parametrize("pin", ["stable", "leanprover/lean4:nightly", "leanprover/lean4:v4.19", "../../bad"])
def test_floating_or_invalid_lean_versions_rejected(tmp_path, pin):
    p = project(tmp_path / "work")
    (p.root / "lean-toolchain").write_text(pin)
    with pytest.raises(WorkspaceError):
        ToolchainResolver(manager=installed_manager(tmp_path / "app")).resolve(p)


def test_manifest_cannot_override_lean_toolchain(tmp_path):
    p = project(tmp_path / "work")
    (p.root / "project.yaml").write_text('schema_version: 1\nformal:\n  lean:\n    version: "4.23.0"\n')
    with pytest.raises(WorkspaceError, match="lean-toolchain"):
        ToolchainResolver(manager=installed_manager(tmp_path / "app")).resolve(p)


def test_agda_pinned_packages_and_isolated_environment(tmp_path):
    manager = installed_manager(tmp_path / "app")
    p = project(tmp_path / "work", "agda", "2.8.0")
    (p.root / "project.yaml").write_text('schema_version: 1\nformal:\n  agda:\n    version: "2.8.0"\n    mode: cubical\n    libraries:\n      - name: cubical\n        revision: ' + "b" * 40 + "\n")
    context = ToolchainResolver(manager=manager).resolve(p)
    assert context.mode == "cubical" and context.safe
    assert context.artifacts == ("agda-2.8.0", "cubical")
    assert context.include_paths[0].is_relative_to(manager.home / "packages")
    assert Path(context.environment["AGDA_DIR"]).is_relative_to(manager.home)
    assert Path(context.environment["Agda_datadir"]).is_dir()
    assert context.library_files[0].name == "cubical.agda-lib"
    assert context.flags == ("--guardedness",)


def test_missing_version_never_runs_compiler(tmp_path):
    manager = installed_manager(tmp_path / "app")
    p = project(tmp_path / "work", "agda", "9.9.9")
    (p.root / "A.agda").write_text("module A where\n")
    called = []
    report = verify_bindings(tmp_path / "work", [{"language": "agda", "declaration": "A.x", "file": "9.9.9/A.agda"}],
                             runner=lambda *args: called.append(args), resolver=ToolchainResolver(manager=manager))
    assert report["results"][0]["status"] == "unavailable"
    assert not called


@pytest.mark.parametrize("actual", ["4.19.0", "4.99.0-rc1"])
def test_explicit_system_fallback_checks_version(tmp_path, monkeypatch, actual):
    manager = installed_manager(tmp_path / "app")
    p = project(tmp_path / "work", version="4.99.0")
    monkeypatch.setattr("qprint.formal_environment.shutil.which", lambda name: str(tmp_path / (name + ".exe")))
    monkeypatch.setattr("qprint.verification.run_command", lambda *args, **kwargs: Check("version", "passed", output=f"Lean (version {actual})"))
    with pytest.raises(EnvironmentUnavailable, match="does not satisfy"):
        ToolchainResolver(manager=manager, allow_system=True).resolve(p)
    with pytest.raises(EnvironmentUnavailable, match="catalog"):
        ToolchainResolver(manager=manager).resolve(p)


def test_auto_discovery_preserves_nested_code_project_roots(tmp_path):
    a = project(tmp_path, version="4.19.0")
    b = project(tmp_path, version="4.23.0")
    c = project(tmp_path, "agda", "2.8.0")
    assert {p.root for p in load_projects(tmp_path)} == {a.root, b.root, c.root}


def package_archive(tmp_path, names=("source/A.agda",)):
    archive = tmp_path / "package.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name in names:
            output.writestr(name, "module A where\n")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    item = {"kind": "package", "language": "agda", "name": "example", "version": "1.0",
            "path": "agda/example/1.0", "sha256": digest, "strip_prefix": "source",
            "url": "https://github.com/example/archive.zip"}
    return archive, {"schema_version": 1, "artifacts": {"example": item}}


def test_install_inventory_idempotency_and_remove(tmp_path):
    archive, catalog = package_archive(tmp_path)
    manager = ToolchainManager(tmp_path / "app", catalog=catalog)
    assert manager.list()[0]["status"] == "missing"
    first = manager.install("example", archive=archive)
    assert manager.list()[0]["status"] == "installed"
    assert manager.install("example", archive=archive) == first
    assert (manager.target(catalog["artifacts"]["example"]) / "A.agda").exists()
    assert manager.remove("example")["status"] == "removed"
    assert manager.list()[0]["status"] == "missing"


def test_hash_failure_does_not_publish_or_leave_lock(tmp_path):
    archive, catalog = package_archive(tmp_path)
    archive.write_bytes(b"tampered")
    manager = ToolchainManager(tmp_path / "app", catalog=catalog)
    with pytest.raises(WorkspaceError, match="SHA-256"):
        manager.install("example", archive=archive)
    assert not manager.target(catalog["artifacts"]["example"]).exists()
    assert not list(manager.home.rglob(".install-*"))
    assert not (manager.home / ".qprint/toolchain-manager.lock").exists()


@pytest.mark.parametrize("member", ["../escape", "C:/escape", "source/../../escape", "source/NUL", "source/file:stream"])
def test_archive_escape_is_rejected_before_writes(tmp_path, member):
    archive, _ = package_archive(tmp_path, ("source/A.agda", member))
    stage = tmp_path / "stage"
    stage.mkdir()
    with pytest.raises(WorkspaceError):
        extract_zip(archive, stage, "source")
    assert list(stage.iterdir()) == []


def test_archive_links_and_case_collisions_rejected(tmp_path):
    archive = tmp_path / "link.zip"
    with zipfile.ZipFile(archive, "w") as output:
        info = zipfile.ZipInfo("source/link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        output.writestr(info, "../outside")
    with pytest.raises(WorkspaceError, match="link"):
        extract_zip(archive, tmp_path / "stage", "source")
    archive, _ = package_archive(tmp_path, ("source/A.agda", "source/a.agda"))
    with pytest.raises(WorkspaceError, match="Duplicate"):
        extract_zip(archive, tmp_path / "stage", "source")


def test_unmanaged_or_mismatched_installation_is_not_overwritten(tmp_path):
    archive, catalog = package_archive(tmp_path)
    manager = ToolchainManager(tmp_path / "app", catalog=catalog)
    target = manager.target(catalog["artifacts"]["example"])
    target.mkdir(parents=True)
    (target / "user.txt").write_text("keep")
    with pytest.raises(WorkspaceError, match="Unmanaged"):
        manager.install("example", archive=archive)
    with pytest.raises(WorkspaceError):
        manager.remove("example")
    assert (target / "user.txt").read_text() == "keep"


def test_release_manifest_separates_sources_from_ignored_stores(tmp_path, monkeypatch):
    manager = installed_manager(tmp_path)
    (tmp_path / "qprint").mkdir()
    (tmp_path / "qprint/app.py").write_text("print('Qprint')")
    (tmp_path / "qprint/__pycache__").mkdir()
    (tmp_path / "qprint/__pycache__/app.pyc").write_bytes(b"cache")
    manifest = {"schema_version": 1, "version": "test", "source_paths": ["qprint"], "full_artifacts": ["lean-4.19.0"]}
    monkeypatch.setattr("qprint.release.ToolchainManager", lambda root: manager)
    for full in (False, True):
        output = tmp_path / f"release-{full}.zip"
        build_release(tmp_path, output, full=full, manifest=manifest)
        with zipfile.ZipFile(output) as archive:
            names = archive.namelist()
            assert "Qprint/qprint/app.py" in names
            assert not any("__pycache__" in n for n in names)
            assert any("toolchains/" in n for n in names) == full
        with pytest.raises(FileExistsError):
            build_release(tmp_path, output, full=full, manifest=manifest)


@pytest.mark.parametrize("path", ["../outside", ".qprint", ".conda", "toolchains", "packages", ".git"])
def test_release_rejects_private_or_escaping_sources(tmp_path, path):
    with pytest.raises(WorkspaceError):
        build_release(tmp_path, tmp_path / "out.zip", manifest={"schema_version": 1, "version": "test", "source_paths": [path]})


def test_missing_data_directory_is_unavailable_instead_of_profile_fallback(tmp_path):
    manager = installed_manager(tmp_path / "app")
    (manager.home / "toolchains/agda/2.8.0/data").rmdir()
    with pytest.raises(EnvironmentUnavailable, match="data directory"):
        ToolchainResolver(manager=manager).resolve(project(tmp_path / "work", "agda", "2.8.0"))


def test_real_bundled_cubical_project_and_probe_options(tmp_path):
    manager = ToolchainManager()
    required = {"lean-4.19.0-windows-x64", "agda-2.8.0-windows-x64", "cubical-0.9"}
    installed = {item["id"] for item in manager.list() if item["status"] == "installed"}
    if not required <= installed:
        pytest.skip("bundled example toolchains/packages are not installed")
    source = Path(__file__).parents[1] / "examples/verification"
    target = tmp_path / "relocated workspace"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(".lake", "_build", "*.agdai"))
    from qprint.workspace import Workspace
    report = verify_bindings(target, Workspace(target).verification_bindings())
    assert report["status"] == "passed", report
    agda = next(result for result in report["results"] if result["binding"]["language"] == "agda")
    assert all("--cubical" not in check["command"] for check in agda["checks"])
    assert "cubical-0.9" in agda["environment"]["artifacts"]
