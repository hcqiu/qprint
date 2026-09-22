"""Build an explicit source/runtime ZIP; ignored stores are opt-in, not git archive."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import zipfile

from .paths import WorkspaceError, read_text, safe_path
from .toolchains import ToolchainManager


def build_release(root: Path, output: Path, *, full: bool = False, manifest: dict | None = None) -> dict:
    root, output = root.resolve(), output.resolve()
    manifest = manifest or json.loads(read_text(safe_path(root, "release-manifest.json")))
    if manifest.get("schema_version") != 1:
        raise WorkspaceError("Unsupported release manifest schema")
    paths = list(manifest["source_paths"])
    # Source manifests must never accidentally scoop up private workspaces or caches.
    forbidden = {".git", ".qprint", ".codex", ".agents", "toolchains", "packages", "dist"}
    if any(p.split("/")[0] in forbidden for p in paths):
        raise WorkspaceError("Runtime stores and private directories cannot be source_paths")
    receipts = []
    if full:
        manager = ToolchainManager(root)
        for artifact_id in manifest["full_artifacts"]:
            receipt = manager.installed(artifact_id)
            if receipt is None:
                raise WorkspaceError(f"Full release requires installed artifact: {artifact_id}")
            receipts.append(receipt)
            paths.append(manager.target(manager.artifact(artifact_id)).relative_to(root).as_posix())
    records, seen = [], set()
    for relative in paths:
        path = safe_path(root, relative)
        lexical = root / relative
        if path != lexical or lexical.is_symlink() or lexical.is_junction():
            raise WorkspaceError(f"Release input must not traverse links: {relative}")
        if not path.exists():
            raise WorkspaceError(f"Missing release input: {relative}")
        def append(file):
            if file == output or file.is_symlink() or file.is_junction() or not file.resolve().is_relative_to(root):
                raise WorkspaceError(f"Unsafe release input: {file}")
            name = file.relative_to(root).as_posix()
            if name.casefold() in seen:
                raise WorkspaceError(f"Duplicate release input: {name}")
            seen.add(name.casefold())
            records.append((file, name))
        if path.is_file():
            append(path)
        else:
            for directory, folders, files in os.walk(path, followlinks=False):
                for name in folders + files:
                    candidate = Path(directory) / name
                    if candidate.is_symlink() or candidate.is_junction():
                        raise WorkspaceError(f"Release input contains a link: {candidate}")
                folders[:] = [name for name in folders if name not in {".git", "__pycache__", ".lake", "_build", "config"}
                              and not name.startswith((".install-", "qprint-verify-"))]
                for name in sorted(files):
                    if not name.endswith((".pyc", ".agdai")):
                        append(Path(directory) / name)
    info = {"schema_version": 1, "version": manifest["version"], "flavor": "full" if full else "light",
            "created_at": datetime.now(timezone.utc).isoformat(), "artifacts": receipts,
            "python_runtime_bundled": False, "files": len(records)}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects previous releases; remove only this incomplete file.
    stream = output.open("xb")
    try:
        with stream, zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for file, name in records:
                archive.write(file, "Qprint/" + name)
            archive.writestr("Qprint/release-info.json", json.dumps(info, indent=2))
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return {**info, "output": str(output), "bytes": output.stat().st_size}
