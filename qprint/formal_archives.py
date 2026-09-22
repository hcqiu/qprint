"""Validated ZIP/tar extraction for pinned source and release preparation."""
import posixpath
from pathlib import Path
import shutil
import stat
import tarfile
import zipfile

from .paths import WorkspaceError, safe_path
from .formal_progress import update


def extract(archive, destination, *, strip_root=False, internal_aliases=False, limit=8 * 1024**3):
    destination = Path(destination)
    zipped = zipfile.is_zipfile(archive)
    try:
        source = zipfile.ZipFile(archive) if zipped else tarfile.open(archive, "r:*")
    except (zipfile.BadZipFile, tarfile.TarError) as exc:
        raise WorkspaceError("Invalid preparation archive") from exc
    try:
        items = source.infolist() if zipped else source.getmembers()
        if len(items) > 100_000:
            raise WorkspaceError("Archive exceeds file count limit")
        records, seen, expanded = {}, set(), 0
        for item in items:
            name = (item.filename if zipped else item.name).rstrip("/")
            while name.startswith("./"):
                name = name[2:]
            directory = item.is_dir() if zipped else item.isdir()
            if name in {"", "."} and directory:
                continue
            safe_path(destination, name)
            if zipped:
                mode = stat.S_IFMT(item.external_attr >> 16)
                link = mode == stat.S_IFLNK
                regular = mode in {0, stat.S_IFREG}
                size = item.file_size
            else:
                link = item.issym()
                regular = item.isfile()
                size = item.size
            if not (directory or regular or internal_aliases and link):
                raise WorkspaceError("Archive contains an unsupported link or special file")
            if name.casefold() in seen:
                raise WorkspaceError("Archive contains duplicate paths")
            seen.add(name.casefold())
            records[name] = (item, directory, link, size)
            expanded += size
        if expanded > limit:
            raise WorkspaceError("Archive exceeds expanded size limit")
        roots = {name.split("/")[0] for name in records}
        if strip_root and len(roots) != 1:
            raise WorkspaceError("Expected one archive root")
        validated = []
        for name, (item, directory, link, size) in records.items():
            relative = name.split("/", 1)[1] if strip_root and "/" in name else "" if strip_root else name
            if not relative and directory:
                continue
            target = safe_path(destination, relative)
            payload = item
            if link:
                alias = source.read(item).decode("utf-8") if zipped else item.linkname
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(name), alias))
                if alias.startswith(("/", "\\")) or "\\" in alias or ":" in alias or resolved not in records:
                    raise WorkspaceError("Archive alias leaves its source root")
                if strip_root and resolved.split("/")[0] != name.split("/")[0]:
                    raise WorkspaceError("Archive alias leaves its source root")
                payload, is_directory, another_link, size = records[resolved]
                if is_directory or another_link:
                    raise WorkspaceError("Only aliases to regular archive files can be materialized")
                expanded += size
                if expanded > limit:
                    raise WorkspaceError("Expanded aliases exceed archive size limit")
            validated.append((target, payload, directory))
        # Validate the whole archive before publishing even the first member.
        for index, (target, payload, directory) in enumerate(validated, 1):
            update("extract-dependency", "正在解压依赖归档", completed_files=index, total_files=len(validated))
            if directory:
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                stream = source.open(payload) if zipped else source.extractfile(payload)
                with stream, target.open("xb") as output:
                    shutil.copyfileobj(stream, output, 1024**2)
        return len(validated)
    finally:
        source.close()
