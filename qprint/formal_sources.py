"""Source suffixes and module paths shared by verification entry points."""
from pathlib import Path

from .paths import WorkspaceError


SOURCE_SUFFIXES = {
    "lean": (".lean",),
    "agda": (".agda", ".lagda", ".lagda.tex", ".lagda.md", ".lagda.rst", ".lagda.org", ".lagda.typ"),
}


def source_suffix(path: Path, language: str) -> str | None:
    return next((suffix for suffix in SOURCE_SUFFIXES.get(language, ()) if path.name.endswith(suffix)), None)


def module_name(path: Path, root: Path, language: str) -> str:
    """Strip the entire literate suffix, retaining dots in the module path."""
    suffix = source_suffix(path, language)
    if suffix is None:
        raise WorkspaceError(f"Unsupported {language} source: {path.name}")
    relative = path.relative_to(root)
    return ".".join((*relative.parts[:-1], relative.name[:-len(suffix)]))
