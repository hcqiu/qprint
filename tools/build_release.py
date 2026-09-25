r"""Run with .\.conda\python.exe tools/build_release.py [--full]."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qprint.release import build_release
from qprint.agent_paths import relative_output

parser = argparse.ArgumentParser()
parser.add_argument("--full", action="store_true")
parser.add_argument("--output", type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
flavor = "full" if args.full else "light"
output = args.output or root / "dist" / f"Qprint-0.1.0-windows-x64-{flavor}.zip"
try:
    print(json.dumps(relative_output(build_release(root, output, full=args.full), root), indent=2))
except Exception as exc:
    print(relative_output(str(exc), root), file=sys.stderr)
    raise SystemExit(1)
