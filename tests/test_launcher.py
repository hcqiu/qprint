import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest
from fastapi.testclient import TestClient

from qprint.launcher import bind_listener, install_launcher, running_url, server_lock
from qprint.server import create_app


ROOT = Path(__file__).resolve().parents[1]


def test_instance_endpoint_and_launcher_preserves_customizations(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    with TestClient(create_app(workspace, runtime_root=tmp_path, instance_id="test-launch")) as client:
        response = client.get("/api/instance")
        assert response.json() == {"instance": "test-launch", "workspace": "workspace"}
        assert response.headers["cache-control"] == "no-store"
    launcher = install_launcher(workspace)
    launcher.write_text("@echo custom launcher\n")
    assert install_launcher(workspace).read_text() == "@echo custom launcher\n"


def test_lock_excludes_second_owner_and_recovers_after_release(tmp_path):
    lock = tmp_path / "server.lock"
    with server_lock(lock) as first:
        assert first
        with server_lock(lock) as second:
            assert not second
    with server_lock(lock) as third:
        assert third


def test_busy_port_uses_different_port_only_for_launcher():
    with bind_listener(0, False) as busy:
        port = busy.getsockname()[1]
        with pytest.raises(OSError):
            bind_listener(port, False)
        with bind_listener(port, True) as available:
            assert available.getsockname()[1] != port


def wait_for_server(workspace, process, log):
    relative = workspace.relative_to(ROOT).as_posix()
    state = workspace / ".qprint/runtime/server.json"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            pytest.fail(log.read_text(encoding="utf-8", errors="replace"))
        url = running_url(state, relative)
        if url:
            return url
        time.sleep(.1)
    pytest.fail("Server did not become ready: " + log.read_text(encoding="utf-8", errors="replace"))


@pytest.fixture
def servers(tmp_path):
    # Keep product commands relative to the real Qprint root and local Python.
    if not tmp_path.is_relative_to(ROOT):
        pytest.skip("Use --basetemp inside the Qprint root for process integration tests")
    processes = []
    navigation = ROOT / ".qprint/runtime/navigation.json"
    previous_navigation = navigation.read_bytes() if navigation.exists() else None

    def start(workspace, *, batch=False, port=0):
        workspace.mkdir(parents=True, exist_ok=True)
        log = workspace / f"process-{len(processes)}.log"
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        if batch:
            env["QPRINT_LAUNCH_WORKSPACE"] = str(workspace)
            command = [sys.executable, "-m", "qprint.launcher"]
        else:
            command = [sys.executable, "-m", "qprint", "serve", "--workspace",
                       workspace.relative_to(ROOT).as_posix(), "--port", str(port)]
        with log.open("wb") as output:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=output, stderr=output,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        processes.append(process)
        return process, log

    yield start
    for process in processes:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
    if previous_navigation is None:
        navigation.unlink(missing_ok=True)
    else:
        navigation.write_bytes(previous_navigation)


def test_cli_reuses_same_workspace_and_recovers_after_crash(tmp_path, servers):
    workspace = tmp_path / "notes"
    process, log = servers(workspace)
    url = wait_for_server(workspace, process, log)
    state = workspace / ".qprint/runtime/server.json"
    original = state.read_text()
    second, second_log = servers(workspace)
    assert second.wait(timeout=15) == 0
    assert second_log.read_text().strip() == url
    assert process.poll() is None and state.read_text() == original
    # Neither another workspace nor the wrong instance ID is accepted.
    fake = tmp_path / "fake.json"
    data = json.loads(original)
    fake.write_text(json.dumps({**data, "instance": "stale"}))
    assert running_url(fake, data["workspace"]) is None
    assert running_url(state, "another-workspace") is None
    process.terminate()
    process.wait(timeout=10)
    restarted, restart_log = servers(workspace)
    wait_for_server(workspace, restarted, restart_log)
    assert json.loads(state.read_text())["instance"] != data["instance"]


def test_simultaneous_launches_and_different_workspaces(tmp_path, servers):
    workspace = tmp_path / "first"
    first, first_log = servers(workspace, batch=True)
    second, second_log = servers(workspace, batch=True)
    deadline = time.monotonic() + 30
    while first.poll() is None and second.poll() is None and time.monotonic() < deadline:
        time.sleep(.1)
    survivor, survivor_log, reused, reused_log = ((first, first_log, second, second_log)
                                                if first.poll() is None else (second, second_log, first, first_log))
    url = wait_for_server(workspace, survivor, survivor_log)
    assert reused.wait(timeout=10) == 0
    assert reused_log.read_text().strip() == url
    other_workspace = tmp_path / "second"
    other, other_log = servers(other_workspace, batch=True)
    other_url = wait_for_server(other_workspace, other, other_log)
    assert other_url != url


@pytest.mark.skipif(os.name != "nt", reason="Windows BAT launcher")
def test_batch_from_unrelated_directory_reuses_cli_server(tmp_path, servers):
    workspace = tmp_path / "研究 notes & drafts!"
    first, first_log = servers(workspace)
    url = wait_for_server(workspace, first, first_log)
    env = dict(os.environ, QPRINT_TEST_BAT=str(workspace / "start-qprint.bat"))
    result = subprocess.run(f'"{os.environ["COMSPEC"]}" /d /s /c ""%QPRINT_TEST_BAT%""',
                            cwd=tmp_path, env=env, input="\n", capture_output=True,
                            text=True, encoding="utf-8", timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == url
    assert first.poll() is None
