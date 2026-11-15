"""Discover model capabilities without sending a user prompt or running tools."""
import threading
import time

import httpx

from .chat_agents import Process, discover, validate_base_url
from .paths import WorkspaceError


def efforts(values):
    result = []
    for value in values or []:
        if isinstance(value, str):
            identifier, label = value, value
        else:
            identifier = value.get("reasoningEffort") or value.get("value") or value.get("id")
            label = value.get("name") or identifier
        if identifier and identifier not in {row["id"] for row in result}:
            result.append({"id": identifier, "name": label})
    return result


def model(identifier, name=None, levels=None, default="", loaded=True):
    return {"id": identifier, "name": name or identifier, "efforts": efforts(levels),
            "default_effort": default or "", "efforts_loaded": loaded}


class Probe:
    def __init__(self):
        self.cancelled = threading.Event()

    def event(self, proc, event):
        if "id" in event and "method" in event:
            proc.send({"jsonrpc": "2.0", "id": event["id"], "error": {
                "code": -32601, "message": "Model discovery does not execute client tools"}})


def codex_models(profile, cwd):
    proc = Process(profile["resolved"] + ["app-server"], cwd)
    probe = Probe()
    try:
        proc.rpc("initialize", {"clientInfo": {"name": "qprint", "version": "0.1.0"}}, probe, timeout=20)
        proc.send({"method": "initialized", "params": {}})
        entries, cursor, seen = [], None, set()
        for _ in range(20):
            result = proc.rpc("model/list", {"limit": 100, "includeHidden": False, "cursor": cursor}, probe, timeout=20)
            entries.extend(result.get("data", []))
            cursor = result.get("nextCursor")
            if not cursor or cursor in seen:
                break
            seen.add(cursor)
        models = [model(m.get("model") or m["id"], m.get("displayName"), m.get("supportedReasoningEfforts"),
                        m.get("defaultReasoningEffort")) for m in entries if not m.get("hidden")]
        default = next((m.get("model") or m["id"] for m in entries if m.get("isDefault")), "")
        configured_effort = ""
        try:
            config = proc.rpc("config/read", {"includeLayers": False, "cwd": str(cwd)}, probe, timeout=10).get("config", {})
            default = config.get("model") or default
            configured_effort = config.get("model_reasoning_effort") or ""
        except WorkspaceError:
            pass  # Older Codex releases may not expose config/read.
        return {"models": models, "default_model": profile.get("model") or default,
                "default_effort": configured_effort if not profile.get("model") or profile["model"] == default else ""}
    finally:
        proc.close()


def flatten_options(options):
    result = []
    for option in options or []:
        if "options" in option:
            result.extend(flatten_options(option["options"]))
        elif isinstance(option.get("value"), str):
            result.append(option)
    return result


def config_option(info, category):
    return next((o for o in info.get("configOptions", [])
                 if o.get("type") == "select" and (o.get("category") == category
                     or (not o.get("category") and o.get("id") == category))), None)


def acp_set_model(proc, probe, session_id, info, selected):
    if not selected:
        return info
    option = config_option(info, "model")
    if option:
        if selected not in {o["value"] for o in flatten_options(option.get("options"))}:
            raise WorkspaceError("Agent 已不再提供所选模型，请刷新模型列表")
        # Apply even on resume: the selection belongs to this turn.
        return {**info, **proc.rpc("session/set_config_option", {
            "sessionId": session_id, "configId": option["id"], "value": selected}, probe, timeout=30)}
    models = info.get("models") or {}
    if selected not in {m["modelId"] for m in models.get("availableModels", [])}:
        raise WorkspaceError("此 ACP Agent 没有提供所选模型的切换接口")
    result = proc.rpc("session/set_model", {"sessionId": session_id, "modelId": selected}, probe, timeout=30)
    return {**info, **result}


def acp_apply_selection(proc, run, session_id, info, profile):
    info = acp_set_model(proc, run, session_id, info, profile.get("model"))
    selected = profile.get("effort")
    if selected:
        option = config_option(info, "thought_level")
        if not option or selected not in {o["value"] for o in flatten_options(option.get("options"))}:
            raise WorkspaceError("当前模型不支持所选推理强度，请刷新模型列表")
        proc.rpc("session/set_config_option", {"sessionId": session_id, "configId": option["id"], "value": selected}, run, timeout=30)


def acp_models(profile, cwd, selected):
    proc = Process(profile["resolved"] + profile.get("args", []), cwd)
    probe = Probe()
    try:
        proc.rpc("initialize", {"protocolVersion": 1, "clientCapabilities": {},
                                "clientInfo": {"name": "qprint", "version": "0.1.0"}}, probe, timeout=20)
        info = proc.rpc("session/new", {"cwd": str(cwd), "mcpServers": []}, probe, timeout=30)
        option = config_option(info, "model")
        legacy = info.get("models") or {}
        default = (option.get("currentValue") if option else legacy.get("currentModelId")) or ""
        selected = selected or profile.get("model") or default
        choices = flatten_options(option.get("options")) if option else [
            {"value": m["modelId"], "name": m.get("name")} for m in legacy.get("availableModels", [])]
        if selected and selected != default:
            info = acp_set_model(proc, probe, info["sessionId"], info, selected)
        thought = config_option(info, "thought_level")
        levels = flatten_options(thought.get("options")) if thought else []
        default_effort = thought.get("currentValue", "") if thought else ""
        models = [model(o["value"], o.get("name"), levels if o["value"] == selected else [],
                        default_effort if o["value"] == selected else "", loaded=o["value"] == selected) for o in choices]
        return {"models": models, "default_model": profile.get("model") or default, "default_effort": ""}
    finally:
        proc.close()


def claude_models(profile, cwd):
    proc = Process(profile["resolved"] + ["-p", "--input-format", "stream-json", "--output-format", "stream-json",
                                          "--verbose", "--permission-mode", "dontAsk"], cwd)
    probe = Probe()
    try:
        identifier = "qprint-model-discovery"
        proc.send({"type": "control_request", "request_id": identifier,
                   "request": {"subtype": "initialize", "hooks": None}})
        deadline = time.monotonic() + 30
        while True:
            event = proc.next(probe.cancelled, deadline)
            response = event.get("response", {})
            if event.get("type") == "control_response" and response.get("request_id") == identifier:
                if response.get("subtype") == "error":
                    raise WorkspaceError(str(response.get("error", "Claude 模型发现失败")))
                info = response.get("response", {})
                return {"models": [model(m["value"], m.get("displayName"), m.get("supportedEffortLevels"))
                                   for m in info.get("models", [])],
                        "default_model": profile.get("model") or info.get("model", ""), "default_effort": ""}
            if event.get("type") == "control_request":
                proc.send({"type": "control_response", "response": {"subtype": "error",
                           "request_id": event["request_id"], "error": "No tools during model discovery"}})
    finally:
        proc.close()


def api_models(profile):
    if not profile.get("key"):
        raise WorkspaceError("请先配置 API key")
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        response = client.get(validate_base_url(profile["base_url"]) + "/models",
                              headers={"Authorization": "Bearer " + profile["key"]})
        if response.status_code != 200:
            raise WorkspaceError(f"模型列表返回 HTTP {response.status_code}；可在 Agent 设置中指定模型")
        entries = response.json().get("data", [])
    return {"models": [model(m["id"], m.get("name"), m.get("supported_reasoning_efforts"), m.get("default_reasoning_effort"))
                       for m in entries if isinstance(m, dict) and isinstance(m.get("id"), str)],
            "default_model": profile.get("model", ""), "default_effort": ""}


def discover_models(profile, cwd, selected=""):
    if profile["kind"] == "api":
        return api_models(profile)
    profile = {**profile, "resolved": discover(profile)}
    if not profile["resolved"]:
        raise WorkspaceError("未找到 Agent，请先在设置中查找定位")
    if profile["kind"] == "codex":
        return codex_models(profile, cwd)
    if profile["kind"] == "claude":
        return claude_models(profile, cwd)
    return acp_models(profile, cwd, selected)


def resolve_selection(catalog, selected, effort):
    effective = selected or catalog.get("default_model", "")
    entry = next((m for m in catalog["models"] if m["id"] == effective), None)
    if selected and not entry:
        raise WorkspaceError("模型已不可用，请刷新模型列表后重新选择")
    if effort and (not entry or effort not in {e["id"] for e in entry["efforts"]}):
        raise WorkspaceError("所选模型不支持这个推理强度")
    default = (catalog.get("default_effort", "") if effective == catalog.get("default_model") else "") or (entry or {}).get("default_effort", "")
    return effective, effort or default
