"""Workspace-scoped agent settings, durable conversations and running turns."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field

from .chat_agents import BUILTINS, RUNNERS, discover, validate_base_url
from .chat_models import discover_models, model as model_entry, resolve_selection
from .paths import WorkspaceError, safe_path


class AgentSettings(BaseModel):
    selected: str
    command: str = Field(default="", max_length=4096)
    args: list[str] = Field(default_factory=list, max_length=20)
    model: str = Field(default="", max_length=300)
    base_url: str = Field(default="https://api.openai.com/v1", max_length=2048)
    api_key: str | None = Field(default=None, max_length=8192)


class Anchor(BaseModel):
    node: str = Field(min_length=1, max_length=2048)
    view: str = Field(pattern="^(rendered|tex)$")
    quote: str = Field(min_length=1, max_length=20000)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    prefix: str = Field(default="", max_length=80)
    suffix: str = Field(default="", max_length=80)


class NewSession(BaseModel):
    anchor: Anchor
    context: str = Field(min_length=1, max_length=4 * 1024 * 1024)


class Message(BaseModel):
    text: str = Field(min_length=1, max_length=40000)
    request_id: str = Field(min_length=1, max_length=100)
    model: str | None = Field(default=None, max_length=300)
    effort: str | None = Field(default=None, max_length=100)


class ModelQuery(BaseModel):
    model: str = Field(default="", max_length=300)
    refresh: bool = False


class Answer(BaseModel):
    request_id: str
    option: str = ""
    answers: dict[str, str] = Field(default_factory=dict)


class ChatService:
    def __init__(self, workspace, runtime_root):
        self.workspace = workspace
        self.cwd = runtime_root
        self.path = safe_path(workspace.root, ".qprint/chat.sqlite")
        self.lock = threading.RLock()
        self.runs = {}
        self.keys = {}
        self.resolved = {}
        self.catalogs = {}
        self.catalog_lock = threading.Lock()
        self.settings_generation = 0
        self.closed = False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, data TEXT, PRIMARY KEY(kind,id))")
            # Never silently re-send a turn after a server restart.
            for row in db.execute("SELECT id,data FROM records WHERE kind='session'").fetchall():
                session = json.loads(row[1])
                if session["status"] in {"running", "waiting"}:
                    session.update(status="interrupted", error="服务已重启，上次回答中断；可继续提问", pending=None)
                    db.execute("UPDATE records SET data=? WHERE kind='session' AND id=?", (json.dumps(session, ensure_ascii=False), row[0]))

    def db(self):
        # Context manager below explicitly closes connections on Windows.
        from contextlib import contextmanager

        @contextmanager
        def connection():
            db = sqlite3.connect(self.path, timeout=10)
            try:
                with db:
                    yield db
            finally:
                db.close()
        return connection()

    def read(self, kind, identifier):
        with self.db() as db:
            row = db.execute("SELECT data FROM records WHERE kind=? AND id=?", (kind, identifier)).fetchone()
        return json.loads(row[0]) if row else None

    def write(self, kind, identifier, value):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (kind, identifier, json.dumps(value, ensure_ascii=False)))

    def config(self):
        return self.read("settings", "main") or {"selected": "codex", "profiles": {}}

    def profile(self, name):
        if name not in BUILTINS:
            raise WorkspaceError("未知 Agent")
        return {**BUILTINS[name], **self.config()["profiles"].get(name, {})}

    def settings(self, refresh=False):
        with self.lock:
            config = self.config()
            profiles = []
            for name in BUILTINS:
                profile = self.profile(name)
                if profile["kind"] == "api":
                    available = bool(self.keys.get(name) or os.getenv("OPENAI_API_KEY"))
                    path = ""
                else:
                    if refresh or name not in self.resolved:
                        self.resolved[name] = discover(profile)
                    available = bool(self.resolved[name])
                    path = self.resolved[name][-1] if available else ""
                profiles.append({**profile, "id": name, "available": available, "path": path,
                                 "has_key": bool(self.keys.get(name) or (name == "api" and os.getenv("OPENAI_API_KEY")))})
            return {"selected": config["selected"], "profiles": profiles}

    def configure(self, payload):
        with self.lock:
            self.profile(payload.selected)
            if any(len(arg) > 2048 for arg in payload.args):
                raise WorkspaceError("Agent 参数过长")
            config = self.config()
            values = {"model": payload.model.strip()}
            if payload.selected == "api":
                values["base_url"] = validate_base_url(payload.base_url.strip())
                if payload.api_key is not None:
                    self.keys[payload.selected] = payload.api_key.strip()
            else:
                values["command"] = payload.command.strip() or BUILTINS[payload.selected]["command"]
                values["args"] = payload.args if payload.selected == "custom" else BUILTINS[payload.selected]["args"]
            config["profiles"][payload.selected] = values
            config["selected"] = payload.selected
            self.write("settings", "main", config)
            self.settings_generation += 1
            self.catalogs.clear()
            return self.settings(refresh=True)

    def models(self, identifier, payload):
        # Discovery can start a local protocol process; never hold the chat lock
        # while waiting, otherwise stop/poll would hang behind model discovery.
        with self.lock:
            session = self.get(identifier)
            name = session["agent"]
            profile = deepcopy(self.profile(name))
            profile["key"] = (self.keys.get(name) or os.getenv("OPENAI_API_KEY", "")) if name == "api" else ""
            generation = self.settings_generation
            key = (name, generation, payload.model if profile["kind"] == "acp" else "")
        with self.catalog_lock:
            cached = self.catalogs.get(key)
            if cached and not payload.refresh and time.monotonic() < cached[0]:
                result = deepcopy(cached[1])
            else:
                try:
                    result = discover_models(profile, self.cwd, payload.model)
                    result["error"] = ""
                except Exception as exc:
                    error = str(exc)
                    if profile.get("key"):
                        error = error.replace(profile["key"], "[redacted]")
                    result = {"models": [], "default_model": profile.get("model", ""),
                              "default_effort": "", "error": error[:1000]}
                default = result.get("default_model", "")
                if default and not any(m["id"] == default for m in result["models"]):
                    result["models"].insert(0, model_entry(default, default + "（已配置）"))
                if generation == self.settings_generation:
                    self.catalogs[key] = (time.monotonic() + (10 if result["error"] else 300), deepcopy(result))
            if result["error"]:
                saved = session.get("selection", {}).get("model", "")
                if saved and not any(m["id"] == saved for m in result["models"]):
                    result["models"].append(model_entry(saved, saved + "（上次选择，未验证）"))
            return {**result, "requires_model": profile["kind"] == "api"}

    def get(self, identifier):
        with self.lock:
            result = self.read("session", identifier)
            if result is None:
                raise HTTPException(404, "会话不存在")
            return result

    def listing(self):
        with self.lock, self.db() as db:
            sessions = [json.loads(row[0]) for row in db.execute("SELECT data FROM records WHERE kind='session'")]
        return sorted([{k: s[k] for k in ("id", "anchor", "agent", "status", "created_at")} for s in sessions], key=lambda s: s["created_at"])

    def create(self, payload):
        with self.lock:
            if payload.anchor.node not in self.workspace.nodes:
                raise HTTPException(404, "节点不存在")
            if not payload.anchor.quote.strip() or payload.anchor.end <= payload.anchor.start:
                raise WorkspaceError("请选择正文中的文字")
            selected = self.config()["selected"]
            identifier = uuid.uuid4().hex
            session = {"id": identifier, "agent": selected, "anchor": payload.anchor.model_dump(),
                       "context": payload.context, "messages": [], "remote_id": None, "context_sent": False,
                       "status": "idle", "pending": None, "error": "", "activity": "",
                       "created_at": time.time()}
            self.write("session", identifier, session)
            return session

    def send(self, identifier, payload):
        previous = self.get(identifier)
        if any(m.get("request_id") == payload.request_id for m in previous["messages"]):
            return previous
        choice, resolved_choice = None, None
        if payload.model is not None or payload.effort is not None or "selection" in previous:
            saved = previous.get("selection", {})
            choice = {"model": saved.get("model", "") if payload.model is None else payload.model,
                      "effort": saved.get("effort", "") if payload.effort is None else payload.effort}
            if payload.model is not None and payload.model != saved.get("model", "") and payload.effort is None:
                choice["effort"] = ""
            catalog = self.models(identifier, ModelQuery(model=choice["model"]))
            resolved_choice = resolve_selection(catalog, choice["model"], choice["effort"])
        with self.lock:
            session = self.get(identifier)
            if any(m.get("request_id") == payload.request_id for m in session["messages"]):
                return session
            if identifier in self.runs:
                raise HTTPException(409, "请等待当前回答完成或停止后再发送")
            if self.closed or len(self.runs) >= 3:
                raise HTTPException(409, "当前任务较多，请稍后再试")
            if not payload.text.strip():
                raise WorkspaceError("请输入问题")
            name = session["agent"]
            profile = deepcopy(self.profile(name))
            if resolved_choice:
                profile["model"], profile["effort"] = resolved_choice
            if profile["kind"] == "api":
                profile["key"] = self.keys.get(name) or os.getenv("OPENAI_API_KEY", "")
                if not profile["key"]:
                    raise WorkspaceError("请在 Agent 设置中填写 API 密钥")
                if not profile.get("model"):
                    raise WorkspaceError("请在对话框选择模型，或在 Agent 设置中填写模型")
            else:
                profile["resolved"] = discover(profile)
                if not profile["resolved"]:
                    raise WorkspaceError("未找到此会话使用的 Agent，请在设置中查找定位")
            if choice is not None:
                session["selection"] = choice
            session["messages"] += [{"role": "user", "text": payload.text, "request_id": payload.request_id},
                                    {"role": "assistant", "text": "", "model": profile.get("model", ""),
                                     "effort": profile.get("effort", "")}]
            session.update(status="running", error="", activity="正在连接 " + profile["name"], pending=None)
            self.write("session", identifier, session)
            run = Run(self, session, profile)
            self.runs[identifier] = run
            threading.Thread(target=run.execute, name="qprint-chat", daemon=True).start()
            return session

    def stop(self, identifier):
        with self.lock:
            self.get(identifier)
            run = self.runs.get(identifier)
            if run:
                run.cancelled.set()
            return {"ok": True}

    def answer(self, identifier, payload):
        with self.lock:
            run = self.runs.get(identifier)
            if not run or not run.pending or run.pending["id"] != payload.request_id:
                raise HTTPException(409, "此请求已结束，请刷新会话")
            if run.pending.get("questions"):
                if not all(payload.answers.get(q["id"], "").strip() for q in run.pending["questions"]):
                    raise WorkspaceError("请回答每个问题")
            elif payload.option not in {o["id"] for o in run.pending["options"]}:
                raise WorkspaceError("无效选项")
            run.answer_value = payload
            run.answered.set()
            return {"ok": True}

    def close(self):
        with self.lock:
            self.closed = True
            for run in self.runs.values():
                run.cancelled.set()


class Run:
    def __init__(self, service, session, profile):
        self.service, self.session, self.profile = service, session, profile
        self.cwd = service.cwd
        self.cancelled, self.answered = threading.Event(), threading.Event()
        self.pending, self.answer_value, self.process = None, None, None
        self.replaying = False
        self.items = {}
        self.last_save = 0

    def save(self, force=False):
        if force or time.monotonic() - self.last_save > .15:
            with self.service.lock:
                self.service.write("session", self.session["id"], self.session)
                self.last_save = time.monotonic()

    def append(self, text):
        if self.replaying:
            return
        message = self.session["messages"][-1]
        if len(message["text"]) + len(text) > 2_000_000:
            raise WorkspaceError("回答过长，已停止")
        message["text"] += text
        self.save()

    def final_text(self, text):
        if text:
            self.session["messages"][-1]["text"] = text[:2_000_000]
            self.save()

    def remote(self, identifier):
        self.session["remote_id"] = identifier
        self.save(True)

    def context_sent(self):
        self.session["context_sent"] = True
        self.save(True)

    def status(self, value):
        self.session["activity"] = value[:500]
        self.save()

    def ask(self, method, params, options=None, questions=None):
        self.pending = {"id": uuid.uuid4().hex, "method": method, "detail": json.dumps(params, ensure_ascii=False)[:12000],
                        "options": options or [], "questions": questions or []}
        self.session.update(status="waiting", pending=self.pending)
        self.answered.clear()
        self.save(True)
        deadline = time.monotonic() + 1800
        while not self.answered.wait(.2):
            if self.cancelled.is_set():
                raise InterruptedError("已停止")
            if time.monotonic() > deadline:
                raise TimeoutError("等待回复超时")
        answer = self.answer_value
        self.pending = None
        self.session.update(status="running", pending=None)
        self.save(True)
        return answer

    def event(self, proc, event):
        method, params = event.get("method", ""), event.get("params", {})
        if "id" in event and method:
            if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
                answer = self.ask(method, params, [{"id": "accept", "label": "允许一次"}, {"id": "decline", "label": "拒绝"}])
                result = {"decision": answer.option}
            elif method == "item/tool/requestUserInput":
                answer = self.ask(method, params, questions=params.get("questions", []))
                result = {"answers": {key: {"answers": [value]} for key, value in answer.answers.items()}}
            elif method == "session/request_permission":
                options = [{"id": o["optionId"], "label": o["name"]} for o in params["options"]
                           if o["kind"] in {"allow_once", "reject_once"}]
                if not options:
                    result = {"outcome": {"outcome": "cancelled"}}
                else:
                    answer = self.ask(method, params.get("toolCall", {}), options)
                    result = {"outcome": {"outcome": "selected", "optionId": answer.option}}
            else:
                proc.send({"jsonrpc": "2.0", "id": event["id"], "error": {"code": -32601, "message": "Qprint does not support this client method"}})
                return
            proc.send({"jsonrpc": "2.0", "id": event["id"], "result": result})
        elif method == "item/agentMessage/delta":
            identifier = params.get("itemId", "answer")
            self.items[identifier] = self.items.get(identifier, "") + params.get("delta", "")
            self.final_text("\n\n".join(self.items.values()))
        elif method == "item/completed" and params.get("item", {}).get("type") == "agentMessage":
            item = params["item"]
            self.items[item["id"]] = item.get("text", "")
            self.final_text("\n\n".join(self.items.values()))
        elif method == "item/started":
            self.status("正在处理：" + params.get("item", {}).get("type", ""))
        elif method == "error":
            error = params.get("error", {})
            message = error.get("message", str(error)) if isinstance(error, dict) else str(error)
            if params.get("willRetry"):
                self.status("Agent 正在重试：" + message)
            else:
                raise WorkspaceError(message or "Agent 请求失败")
        elif method == "session/update":
            update = params.get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                self.append(update.get("content", {}).get("text", ""))
            elif update.get("sessionUpdate") in {"tool_call", "tool_call_update"}:
                self.status(update.get("title") or update.get("status", "工具执行中"))

    def execute(self):
        try:
            message = self.session["messages"][-2]["text"]
            prompt = message if self.session.get("remote_id") and self.session.get("context_sent") else self.session["context"] + "\n\nFollow-up question:\n" + message
            RUNNERS[self.profile["kind"]](self.profile, self.session, prompt, self)
            if self.cancelled.is_set():
                raise InterruptedError("已停止")
            if not self.session["messages"][-1]["text"].strip():
                raise WorkspaceError("Agent 未返回文本回答，请检查登录、模型及权限")
            self.session.update(status="idle", activity="回答完成")
        except InterruptedError:
            self.session.update(status="interrupted", error="已停止，可继续提问")
        except Exception as exc:
            error = str(exc)
            for key in [*self.service.keys.values(), self.profile.get("key")]:
                if key:
                    error = error.replace(key, "[redacted]")
            self.session.update(status="failed", error=error[:4000])
        finally:
            self.session["pending"] = None
            with self.service.lock:
                self.save(True)
                self.service.runs.pop(self.session["id"], None)


def install_chat_routes(app, service):
    @app.get("/api/chat/settings")
    def settings():
        return service.settings()

    @app.post("/api/chat/discover")
    def discover_agents():
        return service.settings(refresh=True)

    @app.put("/api/chat/settings")
    def configure(payload: AgentSettings):
        return service.configure(payload)

    @app.get("/api/chat/sessions")
    def sessions():
        return {"sessions": service.listing()}

    @app.post("/api/chat/sessions")
    def create(payload: NewSession):
        return service.create(payload)

    @app.get("/api/chat/sessions/{identifier}")
    def session(identifier: str):
        return service.get(identifier)

    @app.post("/api/chat/sessions/{identifier}/messages")
    def send(identifier: str, payload: Message):
        return service.send(identifier, payload)

    @app.post("/api/chat/sessions/{identifier}/models")
    def models(identifier: str, payload: ModelQuery):
        return service.models(identifier, payload)

    @app.post("/api/chat/sessions/{identifier}/stop")
    def stop(identifier: str):
        return service.stop(identifier)

    @app.post("/api/chat/sessions/{identifier}/answer")
    def answer(identifier: str, payload: Answer):
        return service.answer(identifier, payload)
