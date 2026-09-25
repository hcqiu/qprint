import argparse
import json
from pathlib import Path
import sys

from .importers import import_code, import_paper
from .workspace import Workspace
from .agent_paths import relative_output


def main():
    parser = argparse.ArgumentParser(prog="qprint", description="Markdown-first proof navigation IDE")
    commands = parser.add_subparsers(dest="command", required=True)
    from .knowledge.cli import add_commands
    add_commands(commands)
    formal = commands.add_parser("formal", help="解析或验证独立形式化项目，自动补齐固定版本依赖")
    formal.add_argument("action", choices=["resolve", "verify", "audit"])
    formal.add_argument("--project", type=Path, required=True)
    formal.add_argument("--language", choices=["lean", "agda"], required=True)
    formal.add_argument("--entry", action="append", help="相对项目路径；可重复，默认选择上游入口或 Lake 默认目标")
    formal.add_argument("--declaration", help="额外检查单个入口的声明")
    formal.add_argument("--timeout", type=float, default=600)
    formal.add_argument("--toolchain-home", type=Path)
    formal.add_argument("--offline", action="store_true", help="只使用已安装环境，不下载")
    formal.add_argument("--allow-system-toolchains", action="store_true")
    formal.add_argument("--safe", choices=["inherit", "require", "off"])
    formal.add_argument("--entry-strategy", choices=["auto", "all"], default="auto")
    manager_command = commands.add_parser("toolchain", help="管理本地工具链与依赖库")
    manager_command.add_argument("action", choices=["list", "install", "remove"])
    manager_command.add_argument("artifact", nargs="?")
    manager_command.add_argument("--home", type=Path)
    manager_command.add_argument("--archive", type=Path, help="使用已下载、仍需校验 SHA-256 的归档")
    for name in ("serve", "check", "verify", "import-code", "import-paper"):
        command = commands.add_parser(name)
        default_workspace = Path("examples/demo") if Path("examples/demo").is_dir() else Path("examples/verification")
        command.add_argument("--workspace", type=Path, default=default_workspace)
        if name in {"serve", "verify"}:
            command.add_argument("--toolchain-home", type=Path, help="Qprint 安装根目录；默认 QPRINT_HOME 或程序所在目录")
            command.add_argument("--allow-system-toolchains", action="store_true", help="显式允许匹配版本的 PATH 工具链回退")
        if name == "serve":
            command.add_argument("--port", type=int, default=8765)
            command.add_argument("--allow-verification", action="store_true",
                                 help="允许 API 显式运行此可信工作区的形式化工具链")
        if name == "verify":
            command.add_argument("--offline", action="store_true", help="不自动安装缺失环境")
            command.add_argument("--node", help="仅验证指定节点 ID")
            command.add_argument("--language", choices=["lean", "agda", "coq"])
            command.add_argument("--timeout", type=float, default=120, help="每个工具链阶段超时秒数（1–3600）")
        if name.startswith("import"):
            command.add_argument("source")
            command.add_argument("--dest", required=True)
        if name == "import-code":
            command.add_argument("--language", choices=["lean", "agda", "coq"], required=True)
            command.add_argument("--ref")
            command.add_argument("--verify-after-download", action=argparse.BooleanOptionalAction, default=True)
            command.add_argument("--timeout", type=float, default=600)
            command.add_argument("--toolchain-home", type=Path)
            command.add_argument("--offline", action="store_true", help="验证仅使用已安装环境；源码下载仍需网络")
        if name == "import-paper":
            command.add_argument("--name", required=True)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        from .server import create_app
        from .knowledge.runtime import relative_workspace
        args.workspace = relative_workspace(Path.cwd(), args.workspace)
        if not args.workspace.is_dir():
            parser.error(f"工作区不存在: {args.workspace}")
        uvicorn.run(create_app(args.workspace, runtime_root=Path.cwd(), allow_verification=args.allow_verification,
                              toolchain_home=args.toolchain_home, allow_system_toolchains=args.allow_system_toolchains),
                    host="127.0.0.1", port=args.port)
        return
    try:
        if args.command in {"index", "watch", "agent"}:
            from .knowledge.cli import run
            return run(args)
        if args.command == "formal":
            from .formal_service import formal_project
            report = formal_project(args.project, args.language, action=args.action, entries=args.entry,
                                    declaration=args.declaration, timeout=args.timeout, toolchain_home=args.toolchain_home,
                                    offline=args.offline, allow_system=args.allow_system_toolchains,
                                    safe=args.safe, entry_strategy=args.entry_strategy)
            print(json.dumps(report, ensure_ascii=True, indent=2))
            return 0 if report["status"] in {"passed", "resolved"} else 1
        if args.command == "toolchain":
            from .toolchains import ToolchainManager
            manager = ToolchainManager(args.home)
            if args.action == "list":
                if args.artifact or args.archive:
                    raise ValueError("list does not accept an artifact or archive")
                result = manager.list()
            else:
                if not args.artifact:
                    raise ValueError("install/remove requires an artifact ID from toolchain list")
                if args.action == "remove" and args.archive:
                    raise ValueError("remove does not accept --archive")
                result = manager.install(args.artifact, archive=args.archive) if args.action == "install" else manager.remove(args.artifact)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0
        if args.command == "verify":
            from .verification import verify_bindings
            if not args.workspace.is_dir():
                raise ValueError(f"工作区不存在: {args.workspace}")
            workspace = Workspace(args.workspace)
            report = verify_bindings(workspace.root, workspace.verification_bindings(args.node, args.language), timeout=args.timeout,
                                     toolchain_home=args.toolchain_home, allow_system=args.allow_system_toolchains,
                                     auto_install=not args.offline)
            report["diagnostics"] = workspace.diagnostics
            if any(d["severity"] == "error" for d in workspace.diagnostics):
                report["status"] = "incomplete"
            # ASCII JSON also survives Conda's captured output on GBK Windows consoles.
            print(json.dumps(report, ensure_ascii=True, indent=2))
            return 0 if report["status"] == "passed" else 1
        if args.command == "check":
            if not args.workspace.is_dir():
                raise ValueError(f"工作区不存在: {args.workspace}")
            workspace = Workspace(args.workspace)
            print(json.dumps(workspace.project()["diagnostics"], ensure_ascii=False, indent=2))
            return int(any(d["severity"] == "error" for d in workspace.diagnostics))
        if args.command == "import-code":
            result = import_code(args.workspace.resolve(), args.source, args.language, args.dest, args.ref,
                                 verify_after_download=args.verify_after_download, timeout=args.timeout,
                                 toolchain_home=args.toolchain_home, offline=args.offline)
        else:
            result = import_paper(args.workspace.resolve(), args.source, args.dest, args.name)
        print(json.dumps(result, ensure_ascii=True, indent=2))
        if args.command == "import-code" and args.verify_after_download:
            return 0 if result["verification"]["status"] == "passed" else 1
    except Exception as exc:
        print(relative_output(str(exc)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
