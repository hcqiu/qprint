"""Local agent transports. No shell interpolation or credential copying."""
from __future__ import annotations

import json
import asyncio
from contextlib import suppress
import os
from pathlib import Path
import queue
import shutil
import subprocess
import threading
import time
from urllib.parse import urlsplit

import httpx

from .paths import WorkspaceError


BUILTINS = {
    "codex": {"name": "Codex", "kind": "codex", "command": "codex", "args": []},
    "claude": {"name": "Claude Code", "kind": "claude", "command": "claude", "args": []},
    "hermes": {"name": "Hermes", "kind": "acp", "command": "hermes", "args": ["acp"]},
    "opencode": {"name": "OpenCode", "kind": "acp", "command": "opencode", "args": ["acp"]},
    "custom": {"name": "其他 ACP Agent", "kind": "acp", "command": "", "args": []},
    "api": {"name": "OpenAI-compatible API", "kind": "api", "command": "", "args": [],
            "base_url": "https://api.openai.com/v1", "model": ""},
}


def executable_command(value: str) -> list[str]:
    """Resolve npm launchers without ever passing prompts to cmd.exe."""
    target = shutil.which(value) if value else None
    if not target and value and Path(value).is_file():
        target = str(Path(value).resolve())
    if not target:
        raise WorkspaceError("未找到 Agent，请重新查找或指定可执行文件位置")
    path = Path(target)
    if path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        entries = {"codex": "@openai/codex/bin/codex.js", "claude": "@anthropic-ai/claude-code/cli.js",
                   "opencode": "opencode-ai/bin/opencode"}
        entry = entries.get(path.stem.lower())
        script = path.parent / "node_modules" / entry if entry else None
        if not script or not script.is_file() or not shutil.which("node"):
            raise WorkspaceError("请选择 Agent 的 .exe 或 .js 文件；不执行 shell 启动脚本")
        return [shutil.which("node"), str(script)]
    if path.suffix.lower() in {".js", ".mjs", ".cjs"}:
        node = shutil.which("node")
        if not node:
            raise WorkspaceError("此 Agent 需要 Node.js")
        return [node, str(path)]
    return [str(path)]


def discover(profile):
    name = profile["command"]
    candidates = [name]
    if name and not Path(name).is_absolute() and len(Path(name).parts) == 1:
        home = Path.home()
        candidates += [str(home / ".local/bin" / f"{name}.exe"),
                       str(home / ".local/bin" / name),
                       str(home / "AppData/Roaming/npm" / f"{name}.cmd")]
        if name == "codex":
            for folder in (home / "AppData/Local/OpenAI/Codex/bin", home / "AppData/Local/Programs/OpenAI/Codex/bin"):
                candidates += [str(p) for p in sorted(folder.glob("*/codex.exe"), reverse=True)]
                candidates.append(str(folder / "codex.exe"))
        if name == "hermes":
            candidates.append(str(home / "AppData/Local/hermes/hermes-agent/venv/Scripts/hermes.exe"))
    for candidate in candidates:
        try:
            return executable_command(candidate)
        except WorkspaceError:
            continue
    return []


class Process:
    def __init__(self, command, cwd):
        self.proc = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                                     env={**os.environ, "PYTHONIOENCODING": "utf-8", "NO_COLOR": "1"},
                                     creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                     start_new_session=os.name != "nt")
        self.lines = queue.Queue(maxsize=4096)
        self.errors = ""
        self.closed = threading.Event()
        self.serial = 0
        self.write_lock = threading.Lock()
        self.readers = [threading.Thread(target=self._read, daemon=True), threading.Thread(target=self._stderr, daemon=True)]
        for reader in self.readers:
            reader.start()

    def _read(self):
        for line in self.proc.stdout:
            while not self.closed.is_set():
                try:
                    self.lines.put(line, timeout=.2)
                    break
                except queue.Full:
                    pass

    def _stderr(self):
        for line in self.proc.stderr:
            self.errors = (self.errors + line)[-4000:]

    def send(self, value):
        with self.write_lock:
            self.proc.stdin.write(json.dumps(value, ensure_ascii=False) + "\n")
            self.proc.stdin.flush()

    def next(self, cancelled, deadline):
        while True:
            if cancelled.is_set():
                raise InterruptedError("已停止")
            if time.monotonic() > deadline:
                raise TimeoutError("Agent 响应超时，请检查登录和网络后重试")
            try:
                return json.loads(self.lines.get(timeout=.2))
            except json.JSONDecodeError:
                continue
            except queue.Empty:
                if self.proc.poll() is not None:
                    raise WorkspaceError("Agent 已退出：" + (self.errors or f"exit {self.proc.returncode}"))

    def rpc(self, method, params, run, timeout=90):
        self.serial += 1
        request_id = self.serial
        self.send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            event = self.next(run.cancelled, deadline)
            if event.get("id") == request_id and "method" not in event:
                if "error" in event:
                    raise WorkspaceError(str(event["error"].get("message", event["error"])))
                return event.get("result", {})
            run.event(self, event)

    def close(self):
        self.closed.set()
        if self.proc.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                               capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
            else:
                import signal
                os.killpg(self.proc.pid, signal.SIGTERM)
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=5)
        for reader in self.readers:
            reader.join(timeout=1)
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if not pipe.closed:
                pipe.close()


def run_codex(profile, session, prompt, run):
    proc = Process(profile["resolved"] + ["app-server"], run.cwd)
    run.process = proc
    try:
        proc.rpc("initialize", {"clientInfo": {"name": "qprint", "version": "0.1.0"},
                                "capabilities": {"experimentalApi": True}}, run)
        proc.send({"method": "initialized", "params": {}})
        params = {"cwd": str(run.cwd), "sandbox": "read-only", "approvalPolicy": "on-request"}
        if profile.get("model"):
            params["model"] = profile["model"]
        if session.get("remote_id"):
            params["threadId"] = session["remote_id"]
        result = proc.rpc("thread/resume" if session.get("remote_id") else "thread/start", params, run)
        thread_id = result["thread"]["id"]
        run.remote(thread_id)
        turn = {"threadId": thread_id, "input": [{"type": "text", "text": prompt}]}
        if profile.get("model"):
            turn["model"] = profile["model"]
        if profile.get("effort"):
            turn["effort"] = profile["effort"]
        proc.rpc("turn/start", turn, run)
        run.context_sent()
        deadline = time.monotonic() + 1800
        while True:
            event = proc.next(run.cancelled, deadline)
            run.event(proc, event)
            if event.get("method") == "turn/completed":
                turn = event.get("params", {}).get("turn", {})
                if turn.get("status") != "completed":
                    raise WorkspaceError(str(turn.get("error") or turn.get("status", "Agent 未完成")))
                break
    finally:
        proc.close()


def replay_prompt(session, prompt):
    """Fallback for transports without durable remote sessions, without truncation."""
    previous = session["messages"][:-2]
    if not previous:
        return prompt
    history = [{"role": m["role"], "content": m["text"]} for m in previous if m["text"]]
    return session["context"] + "\n\nPrevious conversation (JSON):\n" + json.dumps(history, ensure_ascii=False) + "\n\nUser question:\n" + session["messages"][-2]["text"]


def run_acp(profile, session, prompt, run):
    proc = Process(profile["resolved"] + profile.get("args", []), run.cwd)
    run.process = proc
    try:
        init = proc.rpc("initialize", {"protocolVersion": 1, "clientCapabilities": {},
                                      "clientInfo": {"name": "qprint", "version": "0.1.0"}}, run)
        params = {"cwd": str(run.cwd), "mcpServers": []}
        if session.get("remote_id") and init.get("agentCapabilities", {}).get("loadSession"):
            params["sessionId"] = session["remote_id"]
            # Loading replays old messages; do not duplicate them in the new answer.
            run.replaying = True
            info = proc.rpc("session/load", params, run)
            run.replaying = False
            session_id = session["remote_id"]
        else:
            info = proc.rpc("session/new", params, run)
            session_id = info["sessionId"]
            prompt = replay_prompt(session, prompt)
        run.remote(session_id)
        if profile.get("model") or profile.get("effort"):
            from .chat_models import acp_apply_selection
            acp_apply_selection(proc, run, session_id, info, profile)
        result = proc.rpc("session/prompt", {"sessionId": session_id, "prompt": [{"type": "text", "text": prompt}]}, run, timeout=1800)
        run.context_sent()
        if result.get("stopReason") == "cancelled":
            raise InterruptedError("已停止")
    finally:
        proc.close()


def run_claude(profile, session, prompt, run):
    args = ["-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk"]
    if session.get("remote_id"):
        args += ["--resume", session["remote_id"]]
    if profile.get("model"):
        args += ["--model", profile["model"]]
    if profile.get("effort"):
        args += ["--effort", profile["effort"]]
    proc = Process(profile["resolved"] + args, run.cwd)
    run.process = proc
    try:
        proc.proc.stdin.write(prompt)
        proc.proc.stdin.close()
        deadline = time.monotonic() + 1800
        while True:
            event = proc.next(run.cancelled, deadline)
            if event.get("session_id"):
                run.remote(event["session_id"])
            if event.get("type") == "assistant":
                run.context_sent()
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        run.append(block["text"])
                    elif block.get("type") == "tool_use":
                        run.status("工具：" + block.get("name", ""))
            if event.get("type") == "result":
                if event.get("is_error"):
                    raise WorkspaceError(str(event.get("result") or event.get("errors") or "Claude 请求失败"))
                run.final_text(event.get("result", ""))
                break
    finally:
        proc.close()


def validate_base_url(value):
    url = urlsplit(value)
    if (url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password
            or url.query or url.fragment or (url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"})):
        raise WorkspaceError("API 地址必须是 HTTPS；本机服务可使用 HTTP，不可包含密钥或查询参数")
    return value.rstrip("/")


def run_api(profile, session, prompt, run):
    url = validate_base_url(profile["base_url"]) + "/chat/completions"
    messages = [{"role": "user", "content": session["context"]}]
    messages += [{"role": m["role"], "content": m["text"]} for m in session["messages"][:-1] if m["text"]]
    body = {"model": profile["model"], "messages": messages, "stream": True}
    if profile.get("effort"):
        body["reasoning_effort"] = profile["effort"]
    async def consume():
        async with httpx.AsyncClient(timeout=httpx.Timeout(180, connect=20), follow_redirects=False) as client:
            async with client.stream("POST", url, headers={"Authorization": "Bearer " + profile["key"]},
                                     json=body) as response:
                if response.status_code >= 300:
                    raise WorkspaceError(f"API 返回 HTTP {response.status_code}，请检查地址、模型、密钥和额度")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    if event.get("error"):
                        raise WorkspaceError("API 流返回错误，请检查模型和额度")
                    choices = event.get("choices", [])
                    if choices:
                        run.append(choices[0].get("delta", {}).get("content") or "")

    async def cancellable():
        task = asyncio.create_task(consume())
        try:
            while not task.done():
                if run.cancelled.is_set():
                    raise InterruptedError("已停止")
                await asyncio.wait({task}, timeout=.2)
            return await task
        finally:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
    asyncio.run(cancellable())


RUNNERS = {"codex": run_codex, "claude": run_claude, "acp": run_acp, "api": run_api}
