import json
from pathlib import Path
import sys
import threading
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from qprint.formal_downloads import download_file
from qprint.formal_environment import FormalExecutionContext
from qprint.formal_git import uses_cloud_release
from qprint.formal_preparation import prepare_environment
from qprint.formal_progress import Progress, observed, update, with_progress
from qprint.formal_runner import Check, run_command
from qprint.server import create_app


def test_nested_progress_and_reset_even_on_failure(tmp_path):
    seen = []
    @with_progress
    def inner(on_progress=None):
        update("resolve", "inner")
    @with_progress
    def outer(on_progress=None):
        inner()
        raise ValueError("expected")
    with pytest.raises(ValueError):
        outer(on_progress=seen.append)
    assert [p["message"] for p in seen] == ["inner"]
    assert not observed()


def test_progress_throttled_without_losing_stage_changes(monkeypatch):
    now = [1.0]
    monkeypatch.setattr("qprint.formal_progress.time.monotonic", lambda: now[0])
    seen = []
    progress = Progress(seen.append)
    progress.update("download", "archive", bytes=1)
    progress.update("download", "archive", bytes=2)
    now[0] += 1.1
    progress.update("download", "archive", bytes=3)
    progress.update("extract", "archive", completed_files=1)
    assert len(seen) == 3
    assert seen[1]["bytes"] == 3 and seen[1]["elapsed_seconds"] == 1.1
    assert seen[2]["stage_seconds"] == 0


def test_download_reports_size_and_checksum_stage(tmp_path):
    seen = []
    @with_progress
    def run(on_progress=None):
        with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"data"))) as client:
            download_file("https://github.com/example/archive.zip", tmp_path / "archive", client=client)
    run(on_progress=seen.append)
    assert any(p.get("total_bytes") == 4 for p in seen)
    assert seen[-1]["stage"] == "checksum" and seen[-1]["bytes"] == 4


def test_broken_progress_observer_does_not_interrupt_process(tmp_path):
    def broken(_):
        raise RuntimeError("UI disconnected")
    @with_progress
    def run(on_progress=None):
        return run_command("build", [sys.executable, "-c", "print('done')"], tmp_path, 5)
    result = run(on_progress=broken)
    assert result.status == "passed" and "done" in result.output


def test_observed_process_keeps_timeout_and_reports_activity(tmp_path):
    seen = []
    @with_progress
    def run(on_progress=None):
        return run_command("build", [sys.executable, "-u", "-c", "import time; print('started'); time.sleep(10)"], tmp_path, .4)
    result = run(on_progress=seen.append)
    assert result.status == "timeout" and result.duration_ms < 5000
    assert seen[0]["stage"] == "build"


@pytest.mark.parametrize("legacy", [True, False])
def test_only_native_release_projects_require_release_metadata(tmp_path, monkeypatch, legacy):
    widget = tmp_path / ".lake/packages/proofwidgets"
    widget.mkdir(parents=True)
    (widget / "lakefile.lean").write_text("package proofwidgets where\n" + ("  preferReleaseBuild := true\n" if legacy else ""))
    assert uses_cloud_release(widget) == legacy
    entry = {"name": "proofwidgets", "type": "git", "url": "https://github.com/leanprover-community/ProofWidgets4",
             "rev": "a" * 40, "inputRev": "main"}
    ctx = FormalExecutionContext("lean", "4.34.0-rc2", Path("lean"), Path("lake"), tmp_path, tmp_path, (), {},
                                 requirements={"native": {"lake-manifest.json": {"packages": [entry]}}})
    calls = []
    monkeypatch.setattr("qprint.formal_preparation.pinned_package", lambda *a, **kw: widget)
    monkeypatch.setattr("qprint.formal_preparation.release_metadata", lambda *a, **kw: calls.append(a))
    prepare_environment(ctx)
    assert len(calls) == int(legacy)


def test_job_exposes_progress_while_import_is_still_running(tmp_path, monkeypatch):
    ready, finish = threading.Event(), threading.Event()
    def imported(*args, **kwargs):
        kwargs["on_phase"]("verifying")
        kwargs["on_progress"]({"stage": "download", "message": "Lean 4.34.0-rc2", "bytes": 10, "total_bytes": 100})
        ready.set()
        assert finish.wait(5)
        return {"verification": {"status": "incomplete"}}
    monkeypatch.setattr("qprint.server.import_code", imported)
    with TestClient(create_app(tmp_path)) as client:
        client.headers["x-qprint-token"] = client.get("/api/project").json()["token"]
        try:
            response = client.post("/api/import", json={"kind": "code", "source": "https://github.com/a/b", "dest": "test"})
            assert ready.wait(2)
            job_id = response.json()["id"]
            job = client.get("/api/jobs/" + job_id).json()
            assert job["status"] == "running" and job["progress"]["bytes"] == 10
            assert job["phase"] == "verifying" and job["elapsed_seconds"] >= 0
        finally:
            finish.set()
        for _ in range(100):
            job = client.get("/api/jobs/" + job_id).json()
            if job["status"] != "running":
                break
            time.sleep(.01)
        assert job["status"] == "succeeded" and job["result"]["verification"]["status"] == "incomplete"
        assert job["finished_at"] >= job["started_at"]
