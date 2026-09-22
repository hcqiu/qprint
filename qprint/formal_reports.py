"""Timestamped verification evidence and a narrow handoff contract for agents."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from .paths import safe_path


def failure_report(project, language, error, *, home=None, timeout=600, offline=False):
    """Persist orchestration errors as evidence, even before a compiler starts."""
    return save_report(Path(project), {
        "schema_version": 1, "status": "error", "project": str(project), "language": language,
        "message": str(error), "checks": [], "environment": None,
        "outcomes": {"typecheck": "not_run", "safe_audit": "not_run"},
        "request": {"action": "verify", "project": str(project), "language": language,
                    "timeout": timeout, "toolchain_home": str(home) if home else None,
                    "offline": offline, "entry_strategy": "auto"},
    }, home=Path(home) if home else None, error=error)


def diagnose(report, error=None):
    if isinstance(error, PermissionError):
        return {"code": "filesystem_access", "version_helper_candidate": False, "certainty": "observed"}
    code = getattr(error, "code", None)
    if code:
        return {"code": code, "version_helper_candidate": code in {
            "missing_version", "invalid_version", "ambiguous_version", "missing_dependency_pin", "ambiguous_native_config"},
            "certainty": "configuration"}
    checks = report.get("checks", [])
    if any(c["status"] == "timeout" for c in checks):
        return {"code": "timeout", "version_helper_candidate": False, "certainty": "observed"}
    output = "\n".join(c.get("output", "") for c in checks)
    combined = output + "\n" + report.get("message", "")
    if "SafeFlag" in combined or "Cannot set OPTIONS pragma" in combined and "safe" in combined.lower():
        return {"code": "policy_conflict", "version_helper_candidate": False, "certainty": "observed",
                "note": "Preserve the requested safe policy and source OPTIONS; native typecheck may be unknown."}
    if any(term in combined.lower() for term in ("connection", "timed out", "http", "download", "checksum", "sha-256", "non utf-8", "non-utf-8", "archive", "cache")):
        return {"code": "preparation_failure", "version_helper_candidate": False, "certainty": "suspected"}
    if "[FileNotFound]" in output or "Unknown library" in output or "Library '" in output and "not found" in output:
        return {"code": "dependency_resolution", "version_helper_candidate": True,
                "certainty": "suspected", "note": "Missing module/library can indicate a version mismatch; inspect evidence before editing pins."}
    if report.get("status") in {"unavailable", "error"}:
        return {"code": "environment_unavailable", "version_helper_candidate": False, "certainty": "needs_review"}
    return {"code": "verification_failed", "version_helper_candidate": False, "certainty": "observed"}


def save_report(project: Path, report: dict, *, home: Path | None = None, error=None):
    now = datetime.now(timezone.utc)
    identifier = now.strftime("%Y%m%dT%H%M%S.%fZ") + "-" + uuid.uuid4().hex[:8]
    directory = safe_path(project, ".qprint/reports")
    directory.mkdir(parents=True, exist_ok=True)
    path = safe_path(directory, identifier + ".json")
    report.update(report_id=identifier, checked_at=now.isoformat(), report_path=str(path))
    if report.get("status") not in {"passed", "resolved", "not_run"}:
        report["diagnosis"] = diagnose(report, error)
        report["version_helper"] = {
            "skill": "skills/formalization-version-helper/SKILL.md",
            "project": str(project), "report": str(path),
            "toolchain_home": str(home) if home else None,
            "allowed_changes": ["project version/configuration files", "toolchains", "packages"],
            "retry": report.get("request"),
        }
        report["runtime_helper"] = {
            "skill": "skills/formalization-runtime-helper/SKILL.md",
            "report": str(path), "project": str(project), "toolchain_home": str(home) if home else None,
            "candidate": report["diagnosis"]["code"] in {"preparation_failure", "timeout", "filesystem_access", "environment_unavailable"},
            "context": "fresh agent; script inspect output only; do not pass repository or conversation history",
            "allowed_changes": ["managed preparation artifacts and new reports via the supplied Python tool"],
        }
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    summary = (f"# Formal verification {identifier}\n\n"
               f"- Project: `{project}`\n- Status: `{report['status']}`\n"
               f"- Message: {report.get('message', '')}\n"
               f"- Evidence: [{path.name}]({path.name})\n")
    if "diagnosis" in report:
        summary += f"- Diagnosis: `{report['diagnosis']['code']}` ({report['diagnosis']['certainty']})\n"
    path.with_suffix(".md").write_text(summary, encoding="utf-8")
    return report
