"""Workspace project boundaries, independent of environment resolution."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
from .paths import WorkspaceError, read_text, safe_path
from .formal_policy import safe_policy

CONFIG = "qprint-verification.json"

@dataclass(frozen=True)
class Project:
    language: str
    root: Path
    source_root: Path
    include_paths: tuple[Path, ...] = ()
    safe: str | bool = "inherit"
    mode: str = "standard"


def _directory(root: Path, relative: str) -> Path:
    path = root if relative == "." else safe_path(root, relative)
    if not path.is_dir():
        raise WorkspaceError(f"验证目录不存在: {relative}")
    return path


def load_projects(root: Path) -> list[Project]:
    path = safe_path(root, CONFIG)
    if not path.exists():
        projects = []
        for lang in ("lean", "agda"):
            base = safe_path(root, lang)
            if not base.is_dir():
                continue
            found = []
            for directory, folders, files in os.walk(base, followlinks=False):
                folders[:] = [name for name in folders if not name.startswith(".")
                              and name not in {"vendor", "packages", "toolchains", "_build"}
                              and not (Path(directory) / name).is_symlink()
                              and not (Path(directory) / name).is_junction()]
                if ("project.yaml" in files or ".qprint-formal.yaml" in files
                        or (lang == "agda" and any(f.endswith(".agda-lib") for f in files))
                        or (lang == "lean" and "lean-toolchain" in files)):
                    project_root = Path(directory).resolve()
                    if not project_root.is_relative_to(base):
                        raise WorkspaceError("验证项目不能离开语言目录")
                    found.append(Project(lang, project_root, project_root))
                    folders[:] = []
            projects.extend(found or [Project(lang, base, base)])
        return projects
    try:
        data = json.loads(read_text(path))
    except (OSError, UnicodeError, ValueError) as exc:
        raise WorkspaceError(f"无法读取 {CONFIG}: {exc}") from exc
    if (not isinstance(data, dict) or set(data) != {"version", "projects"}
            or type(data["version"]) is not int or data["version"] != 1
            or not isinstance(data["projects"], list)):
        raise WorkspaceError("验证配置需要 version: 1 和 projects 数组")
    projects = []
    for item in data["projects"]:
        if not isinstance(item, dict) or set(item) - {"language", "root", "source_root", "include_paths", "safe", "mode"}:
            raise WorkspaceError("验证项目含不支持的配置字段")
        lang = item.get("language")
        if lang not in ("lean", "agda"):
            raise WorkspaceError("验证项目 language 必须为 lean 或 agda")
        base = _directory(safe_path(root, lang), item.get("root", "."))
        source = _directory(base, item.get("source_root", "."))
        includes = item.get("include_paths", [])
        if not isinstance(includes, list):
            raise WorkspaceError("include_paths 必须是项目相对路径数组")
        policy = safe_policy(item.get("safe", "inherit"))
        if item.get("mode", "standard") not in ("standard", "cubical", "erased-cubical"):
            raise WorkspaceError("mode 必须是 standard/cubical/erased-cubical")
        if lang == "lean" and set(item) & {"include_paths", "safe", "mode"}:
            raise WorkspaceError("include_paths、safe、mode 只用于 Agda")
        if any(p.language == lang and p.source_root == source for p in projects):
            raise WorkspaceError("验证项目 source_root 重复")
        projects.append(Project(lang, base, source, tuple(_directory(base, p) for p in includes),
                                policy, item.get("mode", "standard")))
    return projects


