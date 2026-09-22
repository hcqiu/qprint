"""Replay a report's source selection after an explicitly scoped config repair."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qprint.formal_service import formal_project


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--home", type=Path, required=True)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.report.read_text(encoding="utf-8-sig"))
    request = data["request"]
    project, home = args.project.resolve(), args.home.resolve()
    if Path(request["project"]).resolve() != project:
        parser.error("Report project does not match the explicitly supplied project")
    if request.get("toolchain_home") and Path(request["toolchain_home"]).resolve() != home:
        parser.error("Report toolchain store does not match --home")
    options = {"toolchain_home": home, "offline": args.offline or request.get("offline", False),
               "timeout": args.timeout if args.timeout is not None else request.get("timeout", 600),
               "safe": request.get("safe"), "entry_strategy": request.get("entry_strategy", "all"),
               "allow_system": request.get("allow_system", False)}
    resolution = formal_project(project, request["language"], action="resolve", **options)
    print(json.dumps({"resolve": resolution["status"], "report": resolution["report_path"]}), flush=True)
    if resolution["status"] != "resolved":
        return 1
    verified = formal_project(project, request["language"], action="audit" if request.get("action") == "audit" else "verify", entries=request.get("entries"),
                              declaration=request.get("declaration"), **options)
    print(json.dumps({"verify": verified["status"], "report": verified["report_path"]}), flush=True)
    return 0 if verified["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
