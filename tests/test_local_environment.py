import json
from pathlib import Path
import shutil
import zipfile

import pytest
import yaml

from qprint.release import build_release


REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("script", ["start.ps1", "scripts/build-release.ps1"])
def test_launchers_use_local_python_and_propagate_exit_code(local_python_shell, script):
    root, run = local_python_shell
    target = root / script
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(REPO / script, target)
    probe = ("import json, os, sys\n"
             "print(json.dumps({'args': sys.argv[1:], 'cwd': os.getcwd(), 'prefix': sys.prefix}))\n"
             "raise SystemExit(23)\n")
    if script == "start.ps1":
        (root / "qprint").mkdir()
        (root / "qprint/__init__.py").write_text("")
        (root / "qprint/__main__.py").write_text(probe)
        arguments = "-Workspace 'examples/custom folder' -Port 9876 -AllowVerification -ToolchainHome . -AllowSystemToolchains"
        expected = ["serve", "--workspace", "examples/custom folder", "--port", "9876",
                    "--toolchain-home", ".", "--allow-verification", "--allow-system-toolchains"]
    else:
        (root / "tools").mkdir()
        (root / "tools/build_release.py").write_text(probe)
        arguments = "-Full -Output 'dist/custom archive.zip'"
        expected = ["--full", "--output", "dist/custom archive.zip"]
    result = run(f"& (Join-Path $env:QPRINT_TEST_ROOT '{script}') {arguments}; exit $LASTEXITCODE", cwd=root.parent)
    assert result.returncode == 23, result.stderr
    info = json.loads(result.stdout)
    assert info["args"] == expected
    assert Path(info["cwd"]).resolve() == root.resolve()
    assert Path(info["prefix"]).resolve() == (REPO / ".conda").resolve()


@pytest.mark.parametrize("script", ["start.ps1", "scripts/build-release.ps1"])
def test_launchers_report_setup_when_local_python_is_missing(local_python_shell, script):
    root, run = local_python_shell
    empty = root / "empty installation"
    target = empty / script
    target.parent.mkdir(parents=True)
    shutil.copyfile(REPO / script, target)
    result = run(f"try {{ & './{script}' }} catch {{ [Console]::Error.WriteLine($_.Exception.Message); exit 1 }}", cwd=empty)
    assert result.returncode != 0
    assert r"conda env create -p .\.conda -f environment.yml" in result.stderr


def test_start_defaults_to_packaged_verification_workspace(local_python_shell):
    root, run = local_python_shell
    shutil.copyfile(REPO / "start.ps1", root / "start.ps1")
    (root / "qprint").mkdir()
    (root / "qprint/__init__.py").write_text("")
    (root / "qprint/__main__.py").write_text("import json, sys; print(json.dumps(sys.argv[1:]))")
    result = run("& ./start.ps1")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == ["serve", "--workspace", "examples/verification",
                                      "--port", "8765", "--toolchain-home", "."]


def test_release_contains_first_install_inputs_without_local_environment(tmp_path):
    output = tmp_path / "Qprint.zip"
    build_release(REPO, output)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        environment = yaml.safe_load(archive.read("Qprint/environment.yml"))
        assert "name" not in environment and "prefix" not in environment
        assert any(isinstance(dependency, dict) and "-e .[dev]" in dependency.get("pip", [])
                   for dependency in environment["dependencies"])
        assert "Qprint/skills/knowledge-navigator/SKILL.md" in names
        assert "Qprint/AGENTS.md" in names and "Qprint/start.ps1" in names
        assert not any(".conda" in Path(name).parts for name in names)
