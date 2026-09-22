"""A narrow tool surface: bounded inspection or identical-request recovery."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from qprint.formal_recovery import inspect_case, recover_case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "recover"])
    parser.add_argument("report")
    parser.add_argument("--project", required=True)
    parser.add_argument("--home", required=True)
    args = parser.parse_args()
    try:
        result = (inspect_case if args.action == "inspect" else recover_case)(args.report, args.project, args.home)
    except (OSError, ValueError) as exc:
        result = {"status": "stopped", "message": str(exc)}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if args.action == "inspect" or result.get("status") in {"passed", "resolved"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
