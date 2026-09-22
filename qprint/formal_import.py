"""Post-download project discovery and verification, independent of transport/UI."""
import os
from pathlib import Path

from .formal_service import formal_project
from .formal_reports import failure_report


def projects(root, language):
    found = []
    for directory, folders, files in os.walk(root):
        folders[:] = [name for name in folders if not name.startswith(".") and name not in {"vendor", "packages", "toolchains", "_build"}
                      and not (Path(directory) / name).is_symlink() and not (Path(directory) / name).is_junction()]
        native = "lean-toolchain" in files if language == "lean" else any(name.endswith(".agda-lib") for name in files)
        if native or language == "agda" and (".qprint-formal.yaml" in files or "project.yaml" in files):
            found.append(Path(directory))
            folders[:] = []
    return sorted(found) or [root]


def verify_download(root, language, *, timeout=600, toolchain_home=None, offline=False):
    if language not in {"lean", "agda"}:
        return {"status": "unsupported", "message": f"No {language} verification adapter", "reports": []}
    reports = []
    for project in projects(root, language):
        try:
            report = formal_project(project, language, timeout=timeout, toolchain_home=toolchain_home,
                                    offline=offline, entry_strategy="auto")
        except Exception as exc:
            try:
                report = failure_report(project, language, exc, home=toolchain_home, timeout=timeout, offline=offline)
            except Exception as storage_error:
                report = {"project": str(project), "status": "error", "message": str(exc),
                          "report_error": f"无法保存验证报告：{storage_error}"}
        reports.append(report)
    return {"status": "passed" if all(r["status"] == "passed" for r in reports) else "incomplete",
            "reports": [{key: report[key] for key in ("project", "status", "message", "report_path", "report_error", "policy", "scope", "diagnosis", "outcomes", "preparation") if key in report}
                        for report in reports]}
