"""Bounded subprocess execution shared by adapters and installers."""
from dataclasses import dataclass, field
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
from typing import Protocol
from .formal_progress import observed, update

LOG_LIMIT = 32 * 1024


@dataclass
class Check:
    stage: str
    status: str
    command: list[str] = field(default_factory=list)
    returncode: int | None = None
    output: str = ""
    truncated: bool = False
    duration_ms: int = 0


class Runner(Protocol):
    def __call__(self, stage: str, command: list[str], cwd: Path, timeout: float) -> Check: ...


def run_command(stage: str, command: list[str], cwd: Path, timeout: float, *, env: dict | None = None,
                idle_timeout: float | None = None) -> Check:
    """No shell; bounded returned logs; terminate the process tree on timeout.

    Output is spooled to disk so verbose builds do not fill server memory.
    This is a resource boundary, not an OS sandbox for compiler plugins.
    """
    started = time.monotonic()
    message = {"mathlib-cache": "正在准备 mathlib 编译缓存", "build": "正在运行 Lake 构建",
               "typecheck-project": "正在运行 Agda 类型检查", "declaration": "正在检查声明",
               "version": "正在确认工具链版本", "release-trace": "正在记录已校验的发布物"}.get(stage, "正在运行工具链：" + stage)
    update(stage, message)
    result = Check(stage, "error", command=list(command))
    with tempfile.TemporaryFile() as log:
        try:
            options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
                       if os.name == "nt" else {"start_new_session": True})
            process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, shell=False, env=env, **options)
            try:
                if idle_timeout is None and not observed():
                    result.returncode = process.wait(timeout=timeout)
                else:
                    last_size, last_activity = -1, time.monotonic()
                    while process.poll() is None:
                        current = time.monotonic()
                        size = os.fstat(log.fileno()).st_size
                        if size != last_size:
                            last_size, last_activity = size, current
                        update(stage, message, output_bytes=size, quiet_seconds=round(current - last_activity, 1), timeout_seconds=timeout)
                        if current - started >= timeout or idle_timeout is not None and current - last_activity >= idle_timeout:
                            raise subprocess.TimeoutExpired(command, timeout)
                        time.sleep(min(0.2, idle_timeout / 2) if idle_timeout is not None else 0.2)
                    result.returncode = process.returncode
                result.status = "passed" if result.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    # Use the OS utility by absolute path, not a project executable.
                    taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/taskkill.exe"
                    try:
                        subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                       timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
                    except (OSError, subprocess.TimeoutExpired):
                        pass
                else:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                if process.poll() is None:
                    process.kill()
                process.wait()
                result.status = "timeout"
            log.seek(0, 2)
            size = log.tell()
            log.seek(max(0, size - LOG_LIMIT))
            result.output = log.read(LOG_LIMIT).decode("utf-8", errors="replace")
            result.truncated = size > LOG_LIMIT
        except FileNotFoundError as exc:
            result.status, result.output = "unavailable", str(exc)
        except OSError as exc:
            result.output = str(exc)
    result.duration_ms = round((time.monotonic() - started) * 1000)
    return result


