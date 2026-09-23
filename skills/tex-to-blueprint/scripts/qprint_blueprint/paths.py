from pathlib import Path, PurePosixPath
import re


class WorkspaceError(ValueError):
    pass


def safe_path(root: Path, relative: str) -> Path:
    """Validate portable paths, including Windows quirks, before resolving symlinks."""
    if not isinstance(relative, str) or not relative or "\\" in relative:
        raise WorkspaceError("路径必须是非空的相对路径，分隔符请使用 /")
    parts = relative.split("/")
    if PurePosixPath(relative).is_absolute() or any(
        p in {"", ".", ".."} or p.endswith((" ", "."))
        or re.search(r'[<>:"|?*\x00-\x1f]', p)
        or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p)
        for p in parts
    ):
        raise WorkspaceError(f"不安全的路径: {relative}")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise WorkspaceError("路径不能离开工作区")
    return target


def read_text(path: Path) -> str:
    if path.stat().st_size > 5 * 1024 * 1024:
        raise WorkspaceError(f"文本超过 5 MiB: {path.name}")
    return path.read_text(encoding="utf-8-sig")
