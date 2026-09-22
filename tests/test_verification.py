import json
from pathlib import Path
import shutil
import sys
from threading import Event
import time

from fastapi.testclient import TestClient
import pytest

from qprint.__main__ import main
from qprint.paths import WorkspaceError
from qprint.server import create_app
from qprint.verification import Check, load_projects, run_command, verify_bindings as real_verify_bindings
from qprint.formal_environment import FormalExecutionContext
from qprint.toolchains import ToolchainManager


class TestResolver:
    __test__ = False

    def resolve(self, project):
        return FormalExecutionContext(project.language, "test", Path(project.language),
                                      Path("lake" if project.language == "lean" else "agda"),
                                      project.root, project.source_root, project.include_paths, {},
                                      safe=project.safe, mode=project.mode)


def verify_bindings(*args, **kwargs):
    kwargs.setdefault("resolver", TestResolver())
    return real_verify_bindings(*args, **kwargs)


def fixture_project(root, language="lean", nested=""):
    base = root / language / nested
    base.mkdir(parents=True, exist_ok=True)
    if language == "lean":
        (base / "lean-toolchain").write_text("leanprover/lean4:v4.19.0\n", encoding="utf-8")
        (base / "lakefile.toml").write_text('name = "verification_test"\n[[lean_lib]]\nname = "A"\n', encoding="utf-8")
        (base / "A.lean").write_text("namespace A\ndef identity (n : Nat) := n\nend A\n", encoding="utf-8")
    else:
        (base / "project.yaml").write_text('schema_version: 1\nformal:\n  agda:\n    version: "2.8.0"\n', encoding="utf-8")
        (base / "A.agda").write_text("module A where\nidentity : {X : Set} → X → X\nidentity x = x\n", encoding="utf-8")
    filename = (nested + "/" if nested else "") + ("A.lean" if language == "lean" else "A.agda")
    return {"language": language, "declaration": "A.identity", "file": filename, "lines": [1, 1]}


class RecordingRunner:
    def __init__(self, failure=None):
        self.calls = []
        self.failure = failure

    def __call__(self, stage, command, cwd, timeout):
        probe = Path(command[-1])
        text = probe.read_text(encoding="utf-8") if stage == "declaration" else ""
        self.calls.append((stage, command, cwd, timeout, text))
        return Check(stage, self.failure[1] if self.failure and stage == self.failure[0] else "passed", command)


@pytest.mark.parametrize("language,first_stage", [("lean", "build"), ("agda", "typecheck")])
def test_success_is_semantic_and_does_not_use_lines(tmp_path, language, first_stage):
    binding = fixture_project(tmp_path, language)
    runner = RecordingRunner()
    report = verify_bindings(tmp_path, [binding], runner=runner)
    assert report["status"] == "passed"
    result = report["results"][0]
    assert len(result["source_sha256"]) == 64
    assert [c[0] for c in runner.calls] == [first_stage, "declaration"]
    assert not list((tmp_path / language).glob("qprint-verify-*"))
    if language == "lean":
        assert runner.calls[0][1] == ["lake", "build", "+A"]
        assert 'Lean.Name.mkStr' in runner.calls[1][4] and '"identity"' in runner.calls[1][4]
        assert '(← Lean.getEnv).contains' in runner.calls[1][4]
    else:
        assert "--safe" not in runner.calls[0][1] and "--ignore-all-interfaces" not in runner.calls[0][1]
        assert "--warning=error" in runner.calls[1][1]
        assert "open A using (identity)" in runner.calls[1][4]


@pytest.mark.parametrize("status", ["failed", "timeout", "unavailable", "error"])
def test_failed_build_stops_declaration_check(tmp_path, status):
    runner = RecordingRunner(("build", status))
    report = verify_bindings(tmp_path, [fixture_project(tmp_path)], runner=runner)
    assert report["status"] == "incomplete"
    assert report["results"][0]["status"] == status
    assert len(runner.calls) == 1


def test_missing_declaration_does_not_pass_despite_valid_lines(tmp_path):
    binding = fixture_project(tmp_path)
    binding["declaration"] = "A.nonexistent"
    runner = RecordingRunner(("declaration", "failed"))
    report = verify_bindings(tmp_path, [binding], runner=runner)
    assert report["results"][0]["status"] == "failed"
    assert '"nonexistent"' in runner.calls[1][4]


@pytest.mark.parametrize("explicit_file", [False, True])
def test_literate_agda_binding_navigation_and_verification(tmp_path, explicit_file):
    from qprint.formal import locate_code
    binding = fixture_project(tmp_path, "agda")
    source = tmp_path / "agda/A.agda"
    source.rename(tmp_path / "agda/A.lagda.md")
    if explicit_file:
        binding["file"] = "A.lagda.md"
    else:
        binding.pop("file")
    located = locate_code(tmp_path, binding)
    assert located["error"] is None and located["file"] == "A.lagda.md"
    runner = RecordingRunner()
    report = verify_bindings(tmp_path, [binding], runner=runner)
    assert report["status"] == "passed"
    assert runner.calls[0][1][-1].endswith("A.lagda.md")
    assert "import A\nopen A using (identity)" in runner.calls[1][4]


def test_unsupported_missing_remote_and_empty_selection(tmp_path):
    bindings = [{"language": "coq", "declaration": "A.x"},
                {"language": "agda", "declaration": "A.x", "url": "https://example.com/A.agda"}]
    runner = RecordingRunner()
    report = verify_bindings(tmp_path, bindings, runner=runner)
    assert [r["status"] for r in report["results"]] == ["unsupported", "error"]
    assert not runner.calls
    assert verify_bindings(tmp_path, [])["status"] == "not_run"


@pytest.mark.parametrize("name", ["A.x\n#eval 42", "A.x;evil", "A.x\npostulate y : Set"])
@pytest.mark.parametrize("language", ["lean", "agda"])
def test_probe_rejects_injected_code(tmp_path, name, language):
    binding = fixture_project(tmp_path, language)
    binding["declaration"] = name
    runner = RecordingRunner()
    assert verify_bindings(tmp_path, [binding], runner=runner)["results"][0]["status"] == "error"
    assert runner.calls == []


def test_config_multiple_projects_source_root_and_agda_policy(tmp_path):
    binding = fixture_project(tmp_path, "agda", "repository/src")
    config = {"version": 1, "projects": [{"language": "agda", "root": "repository", "source_root": "src",
                                         "include_paths": ["src"], "safe": False, "mode": "cubical"}]}
    (tmp_path / "qprint-verification.json").write_text(json.dumps(config))
    runner = RecordingRunner()
    report = verify_bindings(tmp_path, [binding], runner=runner)
    assert report["status"] == "passed"
    assert report["results"][0]["project"] == "agda/repository"
    assert report["results"][0]["policy"] == {"safe": "off", "mode": "cubical", "source_options": "preserved"}
    assert "--safe" not in runner.calls[0][1]
    assert "--cubical" not in runner.calls[0][1]
    assert "{-# OPTIONS --cubical #-}" in runner.calls[1][4]
    assert "import A\n" in runner.calls[1][4]


@pytest.mark.parametrize("project", [
    {"language": "lean", "root": "../escape"},
    {"language": "lean", "root": "C:/escape"},
    {"language": "lean", "command": ["evil"]},
    {"language": "agda", "safe": "false"},
    {"language": "agda", "include_paths": ["../../escape"]},
    {"language": "lean", "source_root": "../escape"},
])
def test_invalid_config_and_path_escape(tmp_path, project):
    (tmp_path / "lean").mkdir()
    (tmp_path / "agda").mkdir()
    (tmp_path / "qprint-verification.json").write_text(json.dumps({"version": 1, "projects": [project]}))
    with pytest.raises(WorkspaceError):
        load_projects(tmp_path)


def test_binding_cannot_escape_language_directory(tmp_path):
    binding = fixture_project(tmp_path)
    binding["file"] = "../A.lean"
    runner = RecordingRunner()
    assert verify_bindings(tmp_path, [binding], runner=runner)["results"][0]["status"] == "error"
    assert not runner.calls


@pytest.mark.parametrize("timeout", [0, 3601, float("inf"), float("nan"), True])
def test_invalid_timeout(tmp_path, timeout):
    with pytest.raises(WorkspaceError):
        verify_bindings(tmp_path, [], timeout=timeout)


def test_changed_source_is_stale(tmp_path):
    binding = fixture_project(tmp_path)
    def runner(stage, command, cwd, timeout):
        if stage == "declaration":
            (cwd / "A.lean").write_text("-- changed", encoding="utf-8")
        return Check(stage, "passed")
    result = verify_bindings(tmp_path, [binding], runner=runner)["results"][0]
    assert result["status"] == "stale"


def test_real_runner_errors_bounded_logs_and_timeout(tmp_path):
    result = run_command("test", [sys.executable, "-c", "print('x' * 40000); raise SystemExit(3)"], tmp_path, 10)
    assert result.status == "failed" and result.returncode == 3
    assert result.truncated and len(result.output) <= 32768
    assert run_command("test", [str(tmp_path / "missing-tool")], tmp_path, 10).status == "unavailable"
    result = run_command("test", [sys.executable, "-c", "import time; time.sleep(30)"], tmp_path, 0.1)
    assert result.status == "timeout"


def write_blueprint(root):
    fixture_project(root)
    (root / "blueprint").mkdir()
    text = '# X\n```qprint\nstatus: complete\nlean: {declaration: A.identity, file: A.lean}\n```\n'
    (root / "blueprint/A.md").write_text(text, encoding="utf-8")
    return text


def wait_job(client, job_id):
    for _ in range(100):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] not in ("queued", "running"):
            return job
        time.sleep(0.01)
    raise AssertionError("job did not finish")


def test_api_opt_in_token_validation_and_report(tmp_path, monkeypatch):
    original = write_blueprint(tmp_path)
    calls = []
    def verify(root, bindings, **kwargs):
        calls.append(bindings)
        return verify_bindings(root, bindings, runner=RecordingRunner(("declaration", "failed")), **kwargs)
    monkeypatch.setattr("qprint.server.verify_bindings", verify)
    with TestClient(create_app(tmp_path)) as client:
        project = client.get("/api/project").json()
        assert project["verification_enabled"] is False
        client.headers["x-qprint-token"] = project["token"]
        assert client.post("/api/verify", json={}).status_code == 403
        assert not calls
    with TestClient(create_app(tmp_path, allow_verification=True)) as client:
        project = client.get("/api/project").json()
        client.get("/api/node", params={"id": "A#X"})
        assert not calls
        assert client.post("/api/verify", json={}).status_code == 403
        client.headers["x-qprint-token"] = project["token"]
        assert client.post("/api/verify", json={}, headers={"origin": "https://evil.example"}).status_code == 403
        assert client.post("/api/verify", json={"node_id": "absent"}).status_code == 404
        assert client.post("/api/verify", json={"timeout": 0}).status_code == 422
        response = client.post("/api/verify", json={"node_id": "A#X", "language": "lean"})
        assert response.status_code == 202
        job = wait_job(client, response.json()["id"])
        assert job["status"] == "succeeded" and job["kind"] == "verification"
        assert job["result"]["status"] == "incomplete"
        assert calls[0][0]["node_id"] == "A#X"
        assert client.get("/api/node", params={"id": "A#X"}).json()["status"] == "complete"
    assert (tmp_path / "blueprint/A.md").read_text(encoding="utf-8") == original


def test_api_queue_is_bounded_and_reads_remain_available(tmp_path, monkeypatch):
    write_blueprint(tmp_path)
    release, started = Event(), Event()
    def verify(*args, **kwargs):
        started.set()
        release.wait(10)
        return {"status": "not_run", "results": []}
    monkeypatch.setattr("qprint.server.verify_bindings", verify)
    with TestClient(create_app(tmp_path, allow_verification=True)) as client:
        client.headers["x-qprint-token"] = client.get("/api/project").json()["token"]
        try:
            jobs = [client.post("/api/verify", json={}) for _ in range(5)]
            assert all(j.status_code == 202 for j in jobs)
            assert started.wait(2)
            assert client.post("/api/verify", json={}).status_code == 429
            assert client.get("/api/node", params={"id": "A#X"}).status_code == 200
        finally:
            release.set()
        for response in jobs:
            assert wait_job(client, response.json()["id"])["status"] == "succeeded"


def test_cli_success_empty_and_compiler_failure(tmp_path, monkeypatch, capsys):
    write_blueprint(tmp_path)
    def verify(root, bindings, **kwargs):
        return verify_bindings(root, bindings, runner=RecordingRunner(), **kwargs)
    monkeypatch.setattr("qprint.verification.verify_bindings", verify)
    monkeypatch.setattr(sys, "argv", ["qprint", "verify", "--workspace", str(tmp_path), "--node", "A#X"])
    assert main() == 0
    output = capsys.readouterr().out
    assert output.isascii()
    assert json.loads(output)["status"] == "passed"
    monkeypatch.setattr(sys, "argv", ["qprint", "verify", "--workspace", str(tmp_path), "--language", "coq"])
    assert main() == 1
    assert json.loads(capsys.readouterr().out)["status"] == "not_run"
    monkeypatch.setattr(sys, "argv", ["qprint", "verify", "--workspace", str(tmp_path), "--node", "missing"])
    assert main() == 1


@pytest.mark.parametrize("language,tool", [("lean", "lake"), ("agda", "agda")])
def test_installed_toolchain_success_and_missing_declaration(tmp_path, language, tool):
    if not any(i["language"] == language and i["kind"] == "toolchain" and i["status"] == "installed"
               for i in ToolchainManager().list()):
        pytest.skip(f"managed {tool} is not installed")
    binding = fixture_project(tmp_path, language)
    assert real_verify_bindings(tmp_path, [binding])["status"] == "passed"
    binding["declaration"] = "A.doesNotExist"
    result = real_verify_bindings(tmp_path, [binding])["results"][0]
    assert result["status"] == "failed"
    assert result["checks"][-1]["stage"] == "declaration"
