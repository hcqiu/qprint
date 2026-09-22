"""Project-level resolve/verify API, also usable without a Blueprint workspace."""
from dataclasses import asdict, replace
import hashlib
import math
import os
from pathlib import Path
import tempfile
import time

import httpx

from .formal_adapters import ADAPTERS, _lean_name
from .formal_environment import ToolchainResolver
from .formal_projects import ResolutionError
from .formal_reports import save_report
from .formal_runner import run_command
from .formal_sources import module_name, source_suffix
from .formal_policy import safe_policy, policy_summary, check_outcomes
from .formal_agda import command as agda_command, write_registry
from .formal_runner import Check
from .formal_preparation import (prepare_environment, record_preparation, preparation_summary,
                                 config_fingerprints, config_changed)
from .formal_workspace import Project
from .paths import WorkspaceError, safe_path
from .toolchains import EnvironmentUnavailable, managed_home
from .formal_progress import update, with_progress


def source_files(context):
    files = []
    for directory, folders, names in os.walk(context.source_root):
        folders[:] = [f for f in folders if not f.startswith(".") and f not in {"_build", "vendor", "packages", "toolchains"}
                      and not (Path(directory) / f).is_symlink() and not (Path(directory) / f).is_junction()]
        for name in names:
            path = Path(directory) / name
            if context.language == "lean" and path == context.project_root / "lakefile.lean":
                continue
            if source_suffix(path, context.language) and not path.is_symlink():
                files.append(path)
    return sorted(files)


def fingerprints(files, root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def check_project(context, files, runner, timeout, *, native_lean=False):
    """Run native entry files so each Agda module retains its own OPTIONS."""
    with tempfile.TemporaryDirectory(prefix="qprint-project-", dir=context.project_root) as temporary:
        directory = Path(temporary)
        if context.language == "lean":
            modules = [_lean_name(module_name(p, context.source_root, "lean")) for p in files]
            targets = [] if native_lean else ["+" + m for m in modules]
            return [runner("build", [str(context.driver), "build", *targets], context.project_root, timeout)]
        registry = write_registry(context, directory)
        command = agda_command(context, registry)
        checks, deadline = [], time.monotonic() + timeout
        for source in files:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                checks.append(Check("typecheck-project", "timeout", output="Project checking deadline exhausted"))
                break
            check = runner("typecheck-project", command + [str(source)], context.project_root, remaining)
            checks.append(check)
            if check.status != "passed":
                break
        return checks


def select_entries(context, strategy):
    files = source_files(context)
    if strategy == "auto" and context.language == "agda":
        for name in ("AllModulesIndex", "Everything", "index", "Index", "Main"):
            candidates = [p for p in files if p.parent == context.source_root and module_name(p, context.source_root, "agda") == name]
            if len(candidates) == 1:
                return candidates, "native_entry"
    return files, "native_targets" if strategy == "auto" and context.language == "lean" else "all_files"


@with_progress
@record_preparation
def formal_project(project_root, language, *, action="verify", entries=None, declaration=None,
                   timeout=600, toolchain_home=None, offline=False, allow_system=False, resolver=None, runner=None,
                   safe=None, entry_strategy="all", preparer=None, on_progress=None):
    """Resolve pins, acquire missing artifacts, run checks, and always save evidence."""
    root, home = Path(project_root).resolve(), managed_home(toolchain_home)
    if not root.is_dir():
        raise WorkspaceError(f"Project directory does not exist: {root}")
    report = {"schema_version": 1, "status": "error", "project": str(root), "language": language,
              "checks": [], "environment": None, "message": "",
              "outcomes": {"typecheck": "not_run", "safe_audit": "not_run"},
              "request": {"action": action, "project": str(root), "language": language, "entries": entries,
                          "declaration": declaration, "timeout": timeout, "toolchain_home": str(home), "offline": offline,
                          "safe": safe, "entry_strategy": entry_strategy, "allow_system": allow_system}}
    error = None
    try:
        if language not in ADAPTERS:
            raise ResolutionError("unsupported_language", f"No verification adapter for {language}")
        if action not in {"verify", "resolve", "audit"}:
            raise WorkspaceError("action must be resolve, verify or audit")
        if entry_strategy not in {"auto", "all"}:
            raise WorkspaceError("entry_strategy must be auto or all")
        if action == "audit" and (language != "agda" or safe not in (None, "require", True)):
            raise WorkspaceError("Safe audit requires Agda and safe=require")
        if isinstance(timeout, bool) or not math.isfinite(timeout) or not 1 <= timeout <= 3600:
            raise WorkspaceError("timeout must be between 1 and 3600 seconds")
        project = Project(language, root, root)
        update("resolve", f"正在解析 {root.name} 的 {language} 环境")
        context = (resolver or ToolchainResolver(home, allow_system=allow_system, auto_install=not offline)).resolve(project)
        if safe is not None or action == "audit":
            context = replace(context, safe="require" if action == "audit" else safe_policy(safe))
        report["environment"] = context.public()
        report["policy"] = policy_summary(context)
        report["configuration_sha256"] = config_fingerprints(root)
        if action == "resolve":
            report.update(status="resolved", message="Project requirements and execution environment resolved")
        else:
            files, selection = ([safe_path(root, entry) for entry in entries], "explicit") if entries else select_entries(context, entry_strategy)
            report["scope"] = {"selection": selection, "entries": [p.relative_to(root).as_posix() for p in files]}
            if not files or any(not p.is_file() or not p.is_relative_to(context.source_root) or not source_suffix(p, language) for p in files):
                raise WorkspaceError("No valid source files selected inside the source root")
            if declaration and len(files) != 1:
                raise WorkspaceError("Declaration verification requires exactly one --entry")
            report["sources"] = fingerprints(files, root)
            if preparer is not None or runner is None:
                update("prepare", "正在准备固定版本依赖")
                context = (preparer or prepare_environment)(context, timeout=timeout, offline=offline)
                report["environment"] = context.public()
            execute = runner or (lambda stage, command, cwd, limit: run_command(stage, command, cwd, limit, env=context.environment))
            update("verify", f"正在验证 {root.name}")
            checks = (ADAPTERS[language].verify(context, files[0], declaration, execute, timeout) if declaration
                      else check_project(context, files, execute, timeout, native_lean=selection == "native_targets"))
            report["checks"] = [asdict(check) for check in checks]
            report["status"] = checks[-1].status
            report["outcomes"] = check_outcomes(checks, context)
            if fingerprints(files, root) != report["sources"] or not entries and select_entries(context, entry_strategy)[0] != files:
                report["status"] = "stale"
            report["configuration_after_sha256"] = config_fingerprints(root)
            if config_changed(report["configuration_sha256"], report["configuration_after_sha256"]):
                report["status"] = "stale"
            if report["status"] == "stale":
                report["outcomes"] = {"typecheck": "stale", "safe_audit": "stale" if context.safe == "require" else "not_run"}
            scope_label = "Native Lake default targets" if selection == "native_targets" else f"{len(files)} selected source files"
            report["message"] = f"{scope_label}: {report['status']}"
    except (OSError, ValueError, httpx.HTTPError) as exc:
        error = exc
        report.update(status="unavailable" if isinstance(exc, EnvironmentUnavailable) else "error", message=str(exc))
    report["preparation"] = preparation_summary("failed" if error else None)
    update("report", "正在保存验证报告")
    return save_report(root, report, home=home, error=error)
