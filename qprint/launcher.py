"""Workspace launchers and one local server per workspace."""
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import socket
import sys
import time
from urllib.request import ProxyHandler, build_opener
import uuid

from .agent_paths import relative_output
from .knowledge.runtime import relative_workspace
from .paths import WorkspaceError, safe_path


def install_launcher(workspace: Path) -> Path:
    """Do not replace a launcher the workspace owner may have customized."""
    target = safe_path(workspace, "start-qprint.bat")
    try:
        with target.open("xb") as stream:
            stream.write(Path(__file__).with_name("start-qprint.bat").read_bytes())
    except FileExistsError:
        pass
    return target


@contextmanager
def server_lock(path: Path):
    """OS locks survive stale files and are released even after a process crash."""
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"\0")
            stream.flush()
        stream.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError as exc:
            if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise
        try:
            yield acquired
        finally:
            if acquired:
                stream.seek(0)
                if os.name == "nt":
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def running_url(state: Path, workspace: str) -> str | None:
    """Only accept a live instance matching this workspace and launch ID."""
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("workspace") != workspace:
            return None
        port = data.get("port")
        if type(port) is not int or not 1 <= port <= 65535 or not data.get("instance"):
            return None
        url = f"http://127.0.0.1:{port}"
        # Local discovery must not use system HTTP proxies.
        with build_opener(ProxyHandler({})).open(url + "/api/instance", timeout=.5) as response:
            live = json.load(response)
        if live == {"instance": data["instance"], "workspace": workspace}:
            return url
    except (OSError, ValueError):
        pass
    return None


def bind_listener(port: int, auto_port: bool) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        if os.name == "nt":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", port))
        except OSError as exc:
            if not auto_port or exc.errno not in {errno.EADDRINUSE, errno.EACCES}:
                raise
            listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        return listener
    except BaseException:
        listener.close()
        raise


def serve(workspace: Path, *, runtime_root: Path, port: int = 8765,
          auto_port: bool = False, allow_verification: bool = False,
          toolchain_home: Path | None = None, allow_system_toolchains: bool = False):
    import uvicorn
    from .server import create_app

    runtime_root = runtime_root.resolve()
    workspace = relative_workspace(runtime_root, workspace)
    if not workspace.is_dir():
        raise WorkspaceError("Workspace does not exist")
    if not 0 <= port <= 65535:
        raise WorkspaceError("Port must be between 0 and 65535")
    relative = workspace.relative_to(runtime_root).as_posix()
    state = safe_path(workspace, ".qprint/runtime/server.json")
    lock = safe_path(workspace, ".qprint/runtime/server.lock")
    state.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + 60
    while True:
        with server_lock(lock) as acquired:
            if acquired:
                # Ignore stale metadata once we own the OS lock.
                state.unlink(missing_ok=True)
                install_launcher(workspace)
                with bind_listener(port, auto_port) as listener:
                    actual_port = listener.getsockname()[1]
                    instance = uuid.uuid4().hex
                    app = create_app(workspace, runtime_root=runtime_root,
                                     allow_verification=allow_verification, toolchain_home=toolchain_home,
                                     allow_system_toolchains=allow_system_toolchains, instance_id=instance)
                    payload = {"instance": instance, "workspace": relative, "port": actual_port}
                    temporary = state.with_suffix(".tmp")
                    try:
                        temporary.write_text(json.dumps(payload), encoding="utf-8")
                        os.replace(temporary, state)
                        print(f"http://127.0.0.1:{actual_port}", flush=True)
                        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=actual_port))
                        server.run(sockets=[listener])
                        return 0 if server.started else 1
                    finally:
                        temporary.unlink(missing_ok=True)
                        state.unlink(missing_ok=True)
            url = running_url(state, relative)
            if url:
                print(url, flush=True)
                return 0
        if time.monotonic() >= deadline:
            raise WorkspaceError("This workspace is already starting or unresponsive; no second server was started")
        time.sleep(.1)


def main():
    """The BAT passes its location via the environment, without shell interpolation."""
    try:
        base = Path.cwd().resolve()
        workspace = Path(os.environ["QPRINT_LAUNCH_WORKSPACE"]).resolve().relative_to(base)
        return serve(workspace, runtime_root=base, auto_port=True)
    except (KeyError, OSError, ValueError) as exc:
        print(relative_output(str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
