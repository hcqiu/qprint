"""CLI adapters; query commands never implicitly rescan the workspace."""
import json
from pathlib import Path
import time

from ..paths import WorkspaceError
from ..agent_paths import relative_output
from .index import KnowledgeIndexer
from .navigator import KnowledgeNavigator
from .tools import call_tool, tool_definitions
from .runtime import query_target


def add_commands(commands):
    for name in ("index", "watch"):
        command = commands.add_parser(name, help="Build/update the knowledge navigator index")
        command.add_argument("--workspace", help="Workspace relative to the Qprint folder; defaults to active UI workspace")
        command.add_argument("--verify-hashes", action="store_true", help="Hash even files with unchanged size/mtime")
        if name == "watch":
            command.add_argument("--interval", type=float, default=1.0)
            command.add_argument("--once", action="store_true")
    agent = commands.add_parser("agent", help="Query the persistent knowledge navigator (JSON)")
    actions = agent.add_subparsers(dest="action", required=True)
    for action in ("state", "batch", "search", "resolve", "open", "source", "dependencies", "backlinks", "refs", "path", "context", "explain-edge", "annotate-edge", "tools", "call"):
        command = actions.add_parser(action)
        command.add_argument("--workspace", help="Relative workspace override; normally discovered from runtime")
        command.add_argument("--session", help="Optional session override; normally discovered from runtime")
        if action == "state":
            command.add_argument("--limit", type=int, default=8)
        if action == "batch":
            command.add_argument("--calls", required=True, help='JSON array of {"tool":"kb_state","arguments":{}}; up to 32 sequential queries')
        if action in {"search", "resolve"}:
            command.add_argument("query")
            command.add_argument("--scope")
        if action == "search":
            command.add_argument("--kind", action="append", dest="kinds")
            command.add_argument("--limit", type=int, default=20)
            command.add_argument("--radius", type=int, default=1)
        if action in {"open", "source", "dependencies", "backlinks", "refs", "context"}:
            command.add_argument("node")
        if action == "source":
            command.add_argument("--source", choices=["tex", "md", "agda", "lean", "coq"], default="tex")
            command.add_argument("--lines", type=int, nargs=2)
            command.add_argument("--max-lines", type=int, default=120)
            command.add_argument("--max-chars", type=int, default=20000)
        if action in {"dependencies", "backlinks", "refs"}:
            command.add_argument("--depth", type=int, default=1)
            command.add_argument("--limit", type=int, default=200)
            command.add_argument("--type", action="append", dest="types")
        if action in {"dependencies", "path"}:
            command.add_argument("--direction", choices=["out", "in", "both"], default="out" if action == "dependencies" else "both")
        if action == "path":
            command.add_argument("start")
            command.add_argument("end")
            command.add_argument("--max-depth", type=int, default=12)
            command.add_argument("--type", action="append", dest="types")
            command.add_argument("--limit", type=int, default=2000)
        if action == "context":
            command.add_argument("--token-budget", type=int, default=6000)
        if action in {"explain-edge", "annotate-edge"}:
            command.add_argument("source")
            command.add_argument("target")
            command.add_argument("--type", default="uses")
            if action == "annotate-edge":
                command.add_argument("--reason", required=True)
        if action == "call":
            command.add_argument("tool")
            command.add_argument("--args", default="{}", help="JSON argument object")


def run(args):
    def emit(value):
        print(json.dumps(relative_output(value), ensure_ascii=True, indent=2), flush=True)
    if args.command in {"index", "watch"}:
        args.workspace, _ = query_target(Path.cwd(), args.workspace)
        if args.command == "watch" and not 0.1 <= args.interval <= 3600:
            raise WorkspaceError("interval must be between 0.1 and 3600 seconds")
        indexer = KnowledgeIndexer(args.workspace)
        try:
            first = True
            while True:
                try:
                    result = indexer.update(verify_hashes=args.verify_hashes)
                except (ValueError, OSError) as exc:
                    if args.command == "index" or args.once:
                        raise
                    emit({"error": str(exc), "previous_index_preserved": True})
                    time.sleep(args.interval)
                    continue
                if first or result["changed_files"] or result["deleted_files"]:
                    emit(result)
                if args.command == "index" or args.once:
                    return 0
                first = False
                time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0
    if args.action == "tools":
        emit(tool_definitions())
        return 0
    root, session = query_target(Path.cwd(), args.workspace, args.session)
    with KnowledgeNavigator(root, session=session, runtime_root=Path.cwd()) as navigator:
        arguments = {k: v for k, v in vars(args).items() if k not in {"command", "action", "workspace", "session"}}
        if args.action == "call":
            result = call_tool(navigator, args.tool, json.loads(args.args))
        elif args.action == "batch":
            calls = json.loads(args.calls)
            if not isinstance(calls, list) or not 1 <= len(calls) <= 32:
                raise WorkspaceError("calls must be an array of 1..32 queries")
            if any(not isinstance(c, dict) or set(c) != {"tool", "arguments"} or not isinstance(c["tool"], str) for c in calls):
                raise WorkspaceError("Each call must contain tool and arguments")
            results = []
            for c in calls:
                try:
                    results.append({"tool": c["tool"], "result": call_tool(navigator, c["tool"], c["arguments"])})
                except WorkspaceError as exc:
                    results.append({"tool": c["tool"], "error": str(exc)})
            emit({"results": results})
            return int(any("error" in r for r in results))
        elif args.action == "annotate-edge":
            result = navigator.explain_link(**arguments)
        else:
            action = args.action.replace("-", "_")
            if action == "refs":
                action = "dependencies"
                arguments["types"] = args.types or ["ref", "cites", "mentions"]
            result = call_tool(navigator, "kb_" + action, arguments)
        emit(result)
    return 0
