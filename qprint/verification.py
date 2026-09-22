"""Blueprint binding verification orchestration; public compatibility exports."""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import math
from pathlib import Path
from .formal_sources import SOURCE_SUFFIXES, source_suffix
from .paths import WorkspaceError, safe_path
from .formal_environment import FormalExecutionContext, ToolchainResolver
from .toolchains import EnvironmentUnavailable
from .formal_runner import Check, Runner, run_command
from .formal_workspace import Project, load_projects, CONFIG
from .formal_adapters import LeanAdapter, AgdaAdapter, ADAPTERS
from .formal_reports import save_report
from .formal_policy import policy_summary, check_outcomes
from .formal_preparation import prepare_environment, config_fingerprints, config_changed, record_preparation, preparation_summary
from .formal_downloads import EVENTS
import httpx

def _source(root: Path, binding: dict) -> Path:
    language = binding["language"]
    base = safe_path(root, language)
    filename = binding.get("file")
    if filename:
        source = safe_path(base, filename)
    else:
        parts = binding["declaration"].split(".")
        candidates = [safe_path(base, "/".join(parts[:i]) + suffix)
                      for i in range(len(parts), 0, -1) for suffix in SOURCE_SUFFIXES[language]]
        source = next((p for p in candidates if p.is_file()), None)
    if source is None or not source.is_file():
        raise WorkspaceError("没有本地形式化文件；请导入源码并填写 file")
    if not source_suffix(source, language):
        raise WorkspaceError("验证文件扩展名与语言不匹配")
    return source


@record_preparation
def verify_bindings(root: Path, bindings: list[dict], *, timeout: float = 120,
                    runner: Runner | None = None, resolver: ToolchainResolver | None = None,
                    toolchain_home: Path | None = None, allow_system: bool = False, auto_install: bool = True) -> dict:
    """Return a fresh point-in-time report; never modify blueprint status or cache success."""
    if isinstance(timeout, bool) or not math.isfinite(timeout) or not 1 <= timeout <= 3600:
        raise WorkspaceError("验证超时必须在 1 到 3600 秒之间")
    root = root.resolve()
    projects = load_projects(root)
    resolver = resolver or ToolchainResolver(toolchain_home, allow_system=allow_system, auto_install=auto_install)
    results = []
    for binding in bindings:
        EVENTS.get().clear()
        result = {"binding": dict(binding), "status": "not_run", "checks": [],
                  "source_sha256": None, "message": "", "project": None, "policy": None, "environment": None}
        results.append(result)
        error = None
        project = None
        adapter = ADAPTERS.get(binding["language"])
        if adapter is None:
            result.update(status="unsupported", message="尚未实现该语言的验证适配器")
            continue
        try:
            source = _source(root, binding)
            candidates = [p for p in projects if p.language == binding["language"] and source.is_relative_to(p.source_root)]
            if not candidates:
                raise WorkspaceError("绑定文件不属于任何已配置的验证项目")
            project = max(candidates, key=lambda p: len(p.source_root.parts))
            result["project"] = project.root.relative_to(root).as_posix()
            context = resolver.resolve(project)
            result["configuration_sha256"] = config_fingerprints(project.root)
            result["environment"] = context.public()
            result["policy"] = policy_summary(context)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            result["sources"] = {source.relative_to(project.root).as_posix(): before}
            if runner is None:
                context = prepare_environment(context, timeout=timeout, offline=not auto_install)
            result["environment"] = context.public()
            result["policy"] = policy_summary(context)
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            result["source_sha256"] = before
            def execute(stage, command, cwd, limit):
                return run_command(stage, command, cwd, limit, env=context.environment)
            checks = adapter.verify(context, source, binding["declaration"], runner or execute, timeout)
            result["checks"] = [asdict(check) for check in checks]
            result["outcomes"] = check_outcomes(checks, context)
            result["status"] = checks[-1].status if checks else "not_run"
            result["configuration_after_sha256"] = config_fingerprints(project.root)
            if hashlib.sha256(source.read_bytes()).hexdigest() != before or config_changed(result["configuration_sha256"], result["configuration_after_sha256"]):
                result.update(status="stale", message="验证期间源文件改变，请重新验证")
                result["outcomes"] = {"typecheck": "stale", "safe_audit": "stale" if context.safe == "require" else "not_run"}
            elif result["status"] == "passed":
                result["message"] = "工具链检查及声明解析通过；不等于无公理证明或与正文语义一致"
            else:
                result["message"] = "工具链检查未通过，详见 checks 中的阶段、状态与输出"
        except EnvironmentUnavailable as exc:
            error = exc
            result.update(status="unavailable", message=str(exc))
        except (OSError, UnicodeError, WorkspaceError, httpx.HTTPError) as exc:
            error = exc
            result.update(status="error", message=str(exc))
        result["preparation"] = preparation_summary("failed" if error else None)
        if result["status"] not in {"passed", "not_run", "unsupported"}:
            report_root = project.root if project else root
            result["request"] = {"action": "verify", "project": str(report_root), "language": binding["language"],
                                 "entries": [source.relative_to(report_root).as_posix()] if project else None,
                                 "declaration": binding["declaration"], "timeout": timeout,
                                 "toolchain_home": str(toolchain_home) if toolchain_home else None,
                                 "offline": not auto_install, "safe": context.safe if result.get("environment") else None,
                                 "entry_strategy": "all", "allow_system": allow_system}
            save_report(report_root, result, home=toolchain_home, error=error)
    status = "not_run" if not results else ("passed" if all(r["status"] == "passed" for r in results) else "incomplete")
    return {"schema_version": 1, "checked_at": datetime.now(timezone.utc).isoformat(),
            "status": status, "results": results}
