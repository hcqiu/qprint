"""Restricted report inspection/retry API for the non-version helper."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from .formal_preparation import config_fingerprints
from .formal_reports import diagnose
from .formal_service import formal_project
from .formal_sources import source_suffix
from .paths import WorkspaceError, safe_path

REPAIRABLE = {"preparation_failure", "timeout", "filesystem_access", "environment_unavailable"}


def load_case(report_path, project, home):
    root, store = Path(project).resolve(), Path(home).resolve()
    report_path = Path(report_path).absolute()
    directory = safe_path(root, ".qprint/reports")
    if report_path.parent != directory or not re.fullmatch(r"\d{8}T\d{6}\.\d+Z-[0-9a-f]{8}\.json", report_path.name):
        raise WorkspaceError("Use a timestamped report directly inside the authorized project's .qprint/reports")
    report_path = safe_path(directory, report_path.name)
    if report_path.stat().st_size > 2 * 1024**2:
        raise WorkspaceError("Report exceeds helper input limit")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    request = report.get("request", {})
    if Path(request.get("project", "")).resolve() != root or Path(request.get("toolchain_home") or store).resolve() != store:
        raise WorkspaceError("Report project/toolchain home does not match the authorized scope")
    if request.get("language") not in {"lean", "agda"} or request.get("action") not in {"resolve", "verify", "audit"}:
        raise WorkspaceError("Unsupported replay request")
    return report, root, store


def inspect_case(report_path, project, home):
    report, root, store = load_case(report_path, project, home)
    diagnosis = report.get("diagnosis") or diagnose(report)
    route = "version_helper" if diagnosis.get("version_helper_candidate") else "runtime_recovery" if diagnosis.get("code") in REPAIRABLE else "report_only"
    events = report.get("preparation", {}).get("events", [])
    request = {k: v for k, v in report["request"].items() if k in {
        "action", "language", "timeout", "offline", "safe", "entry_strategy", "allow_system"}}
    request["entry_count"] = len(report["request"].get("entries") or [])
    diagnosis = {k: str(v)[:300] if isinstance(v, str) else v for k, v in diagnosis.items()
                 if k in {"code", "certainty", "note", "version_helper_candidate"}}
    return {"report": str(report_path), "project": str(root), "toolchain_home": str(store),
            "status": report["status"], "diagnosis": diagnosis, "route": route,
            "request": request, "policy": report.get("policy"),
            "source_count": len(report.get("sources", {})),
            "events": [{key: str(value)[-600:] for key, value in event.items() if key in {"kind", "stage", "status", "attempt", "reason", "package", "object"}}
                       for event in events[-8:]],
            "message": report.get("message", "")[-1000:] if route == "runtime_recovery" else "See diagnosis; no proof source is exposed to this helper.",
            "allowed_operations": ["inspect", "recover"] if route == "runtime_recovery" else ["inspect"],
            "scope_notice": "Python tools constrain operations; host filesystem/tool restrictions are still required for enforcement."}


def _proof_snapshot(root, language):
    result = {}
    for directory, folders, names in os.walk(root):
        folders[:] = [name for name in folders if not name.startswith(".") and name not in {"vendor", "packages", "toolchains", "_build"}
                      and not (Path(directory) / name).is_symlink() and not (Path(directory) / name).is_junction()]
        for name in names:
            path = Path(directory) / name
            if source_suffix(path, language) and not path.is_symlink():
                result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _recover_case(report_path, project, home, *, verify):
    case = inspect_case(report_path, project, home)
    if case["route"] != "runtime_recovery":
        return {"status": "stopped", "route": case["route"], "diagnosis": case["diagnosis"]}
    report, root, store = load_case(report_path, project, home)
    before_config = config_fingerprints(root)
    if report.get("configuration_sha256") != before_config:
        raise WorkspaceError("Configuration changed or original fingerprints are absent; do not replay an uncertain environment")
    sources = report.get("sources", {})
    snapshot = _proof_snapshot(root, report["request"]["language"])
    before_sources = {}
    for name, expected in sources.items():
        source = safe_path(root, name)
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != expected:
            raise WorkspaceError("Proof source changed since the report; helper cannot repair it")
        before_sources[name] = actual
    attempts_path = safe_path(root, ".qprint/preparation/helper-attempts.json")
    attempts_path.parent.mkdir(parents=True, exist_ok=True)
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else {}
    key = report["report_id"]
    if attempts.get(key, 0) >= 3:
        return {"status": "stopped", "message": "Three attempts exhausted for this case"}
    attempts[key] = attempts.get(key, 0) + 1
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=attempts_path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(attempts, stream)
    try:
        temporary.replace(attempts_path)
    finally:
        temporary.unlink(missing_ok=True)
    request = report["request"]
    result = verify(root, request["language"], action=request["action"], entries=request.get("entries"),
                    declaration=request.get("declaration"), timeout=request.get("timeout", 600),
                    toolchain_home=store, offline=request.get("offline", False),
                    allow_system=request.get("allow_system", False), safe=request.get("safe"),
                    entry_strategy=request.get("entry_strategy", "all"))
    unchanged = config_fingerprints(root) == before_config and snapshot == _proof_snapshot(root, request["language"]) and all(
        hashlib.sha256(safe_path(root, name).read_bytes()).hexdigest() == value for name, value in before_sources.items())
    return {"status": result["status"] if unchanged else "stale", "report_path": result["report_path"],
            "diagnosis": result.get("diagnosis"), "outcomes": result.get("outcomes"),
            "preparation_status": result.get("preparation", {}).get("status"), "attempt": attempts[key],
            "configuration_and_selected_sources_unchanged": unchanged}


def recover_case(report_path, project, home, *, verify=formal_project):
    case = inspect_case(report_path, project, home)
    if case["route"] != "runtime_recovery":
        return {"status": "stopped", "route": case["route"], "diagnosis": case["diagnosis"]}
    guard = safe_path(Path(project).resolve(), ".qprint/preparation/helper.lock")
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock = guard.open("x")
    except FileExistsError as exc:
        raise WorkspaceError("Another helper recovery is active for this project") from exc
    try:
        with lock:
            lock.write(str(os.getpid()))
        return _recover_case(report_path, project, home, verify=verify)
    finally:
        guard.unlink(missing_ok=True)
