"""Workspace-scoped report discovery and browser links; no arbitrary file serving."""
import json
import os
from pathlib import Path
import re
from urllib.parse import urlencode

from .paths import WorkspaceError, read_text, safe_path

REPORT_NAME = re.compile(r"\d{8}T\d{6}\.\d{6}Z-[0-9a-f]{8}\.json")


def report_file(root, relative):
    path = safe_path(root, relative)
    if not REPORT_NAME.fullmatch(path.name) or path.parent.name != "reports" or path.parent.parent.name != ".qprint":
        raise WorkspaceError("Only timestamped Qprint verification reports can be opened")
    return path


def report_links(root, report):
    result = dict(report)
    if report.get("report_path"):
        try:
            relative = Path(report["report_path"]).resolve().relative_to(root.resolve()).as_posix()
            report_file(root, relative)
        except (ValueError, OSError):
            return result
        result["report_url"] = "/api/formal-report?" + urlencode({"path": relative})
        result["download_url"] = result["report_url"] + "&download=true"
    return result


def recent_reports(root, limit=30):
    candidates = []
    for directory, folders, files in os.walk(root):
        base = Path(directory)
        if ".qprint" in folders:
            try:
                reports = safe_path(base, ".qprint/reports")
                for path in reports.glob("*.json"):
                    if REPORT_NAME.fullmatch(path.name):
                        report_file(root, path.relative_to(root).as_posix())
                        candidates.append(path)
            except (OSError, ValueError):
                pass
        folders[:] = [name for name in folders if not name.startswith(".") and name not in
                      {"vendor", "packages", "toolchains", "_build", "node_modules"}
                      and not (base / name).is_symlink() and not (base / name).is_junction()]
    results = []
    for path in sorted(candidates, key=lambda p: p.name, reverse=True)[:limit]:
        try:
            data = json.loads(read_text(path))
            if not isinstance(data, dict):
                continue
            summary = {key: data[key] for key in ("project", "status", "message", "diagnosis", "checked_at") if key in data}
            summary["report_path"] = str(path)
            results.append(report_links(root, summary))
        except (OSError, ValueError, TypeError):
            continue
    return results


def report_text(data):
    lines = ["Qprint 形式化验证报告", f"项目：{data.get('project', '')}",
             f"状态：{data.get('status', '')}", f"时间：{data.get('checked_at', '')}",
             f"原因：{data.get('message', '')}",
             f"诊断：{(data.get('diagnosis') or {}).get('code', '')}"]
    for check in [*data.get("preparation", {}).get("events", []), *data.get("checks", [])]:
        if check.get("output"):
            lines.extend(["", f"{check.get('stage', check.get('kind', ''))}: {check.get('status', '')}", check['output']])
    return "\n".join(lines)
