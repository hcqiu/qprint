import argparse
import json
from pathlib import Path
import sys

from .importers import import_code, import_paper
from .workspace import Workspace


def main():
    parser = argparse.ArgumentParser(prog="qprint", description="Markdown-first proof navigation IDE")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("serve", "check", "import-code", "import-paper"):
        command = commands.add_parser(name)
        command.add_argument("--workspace", type=Path, default=Path("examples/demo"))
        if name == "serve":
            command.add_argument("--port", type=int, default=8765)
        if name.startswith("import"):
            command.add_argument("source")
            command.add_argument("--dest", required=True)
        if name == "import-code":
            command.add_argument("--language", choices=["lean", "agda", "coq"], required=True)
            command.add_argument("--ref")
        if name == "import-paper":
            command.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        from .server import create_app
        if not args.workspace.is_dir():
            parser.error(f"工作区不存在: {args.workspace}")
        uvicorn.run(create_app(args.workspace), host="127.0.0.1", port=args.port)
        return
    try:
        if args.command == "check":
            if not args.workspace.is_dir():
                raise ValueError(f"工作区不存在: {args.workspace}")
            workspace = Workspace(args.workspace)
            print(json.dumps(workspace.project()["diagnostics"], ensure_ascii=False, indent=2))
            return int(any(d["severity"] == "error" for d in workspace.diagnostics))
        if args.command == "import-code":
            result = import_code(args.workspace.resolve(), args.source, args.language, args.dest, args.ref)
        else:
            result = import_paper(args.workspace.resolve(), args.source, args.dest, args.name)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
