"""Installation and inventory for the portable, versioned Qprint stores.

Acquisition policy lives in formal_artifacts; this module validates and installs.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import tempfile
from urllib.parse import urljoin, urlparse
import zipfile

import httpx

from .paths import WorkspaceError, read_text, safe_path
from .formal_progress import update

RECEIPT = ".qprint-install.json"
CATALOG = Path(__file__).with_name("toolchain-catalog.json")
DOWNLOAD_LIMIT = 2 * 1024**3
EXPANDED_LIMIT = 8 * 1024**3
DOWNLOAD_HOSTS = {"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com", "codeload.github.com"}


class EnvironmentUnavailable(WorkspaceError):
    pass


def managed_home(home: Path | None = None) -> Path:
    return Path(home or os.environ.get("QPRINT_HOME") or Path(__file__).resolve().parents[1]).resolve()


def host_platform() -> str:
    machine = platform.machine().lower()
    arch = "x64" if machine in {"amd64", "x86_64"} else machine
    return f"{platform.system().lower()}-{arch}"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, destination: Path, *, expected_sha256=None):
    from .formal_downloads import download_file
    return download_file(url, destination, expected_sha256=expected_sha256, limit=DOWNLOAD_LIMIT, hosts=DOWNLOAD_HOSTS)


def extract_zip(archive: Path, destination: Path, prefix: str = "", subdir: str = ""):
    """Validate every member before writing; reject aliases, links and collisions."""
    with zipfile.ZipFile(archive) as source:
        infos = source.infolist()
        if len(infos) > 100_000 or sum(i.file_size for i in infos) > EXPANDED_LIMIT:
            raise WorkspaceError("Toolchain archive exceeds extraction limits")
        update("validate-archive", "正在校验工具链归档目录", total_files=len(infos))
        records, seen = [], set()
        for info in infos:
            name = info.filename.rstrip("/")
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
                raise WorkspaceError("Toolchain archive contains a link or special file")
            safe_path(destination, name)
            if prefix:
                if name == prefix and info.is_dir():
                    continue
                if not name.startswith(prefix + "/"):
                    raise WorkspaceError("Unexpected archive root")
                name = name[len(prefix) + 1:]
            if subdir:
                name = subdir + "/" + name
            target = safe_path(destination, name)
            key = str(target).casefold()
            if key in seen or target.name == RECEIPT:
                raise WorkspaceError("Duplicate or reserved archive member")
            seen.add(key)
            records.append((info, target))
        for index, (info, target) in enumerate(records, 1):
            update("extract-toolchain", "正在解压工具链", completed_files=index, total_files=len(records))
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.open(info) as content, target.open("xb") as output:
                shutil.copyfileobj(content, output, length=1024 * 1024)


class ToolchainManager:
    def __init__(self, home: Path | None = None, *, catalog: dict | None = None):
        self.home = managed_home(home)
        self.catalog = catalog if catalog is not None else json.loads(read_text(CATALOG))
        if catalog is None:
            local = safe_path(self.home, "toolchains/.qprint-catalog.json")
            if local.is_file():
                extra = json.loads(read_text(local))
                if extra.get("schema_version") != 1 or not isinstance(extra.get("artifacts"), dict):
                    raise WorkspaceError("Invalid local toolchain catalog")
                for key, item in extra["artifacts"].items():
                    if key in self.catalog["artifacts"] and self.catalog["artifacts"][key] != item:
                        raise WorkspaceError(f"Local catalog cannot override bundled artifact: {key}")
                    self.catalog["artifacts"][key] = item
        if self.catalog.get("schema_version") != 1:
            raise WorkspaceError("Unsupported toolchain catalog schema")

    def artifact(self, artifact_id: str) -> dict:
        try:
            artifact = self.catalog["artifacts"][artifact_id]
        except KeyError as exc:
            raise WorkspaceError(f"Unknown catalog artifact: {artifact_id}") from exc
        if artifact["kind"] not in {"toolchain", "package"}:
            raise WorkspaceError("Invalid artifact kind")
        self.target(artifact)
        return artifact

    def target(self, artifact: dict) -> Path:
        directory = "toolchains" if artifact["kind"] == "toolchain" else "packages"
        return safe_path(safe_path(self.home, directory), artifact["path"])

    def installed(self, artifact_id: str) -> dict | None:
        artifact = self.artifact(artifact_id)
        target = self.target(artifact)
        if not target.exists():
            return None
        receipt_path = safe_path(target, RECEIPT)
        if not receipt_path.is_file():
            raise WorkspaceError(f"Unmanaged installation at {target}")
        receipt = json.loads(read_text(receipt_path))
        if receipt.get("id") != artifact_id or receipt.get("sha256") != artifact["sha256"]:
            raise WorkspaceError(f"Installation receipt does not match catalog: {artifact_id}")
        for relative in artifact.get("executables", {}).values():
            if not safe_path(target, relative).is_file():
                raise EnvironmentUnavailable(f"Incomplete toolchain: {artifact_id}")
        if artifact["kind"] == "toolchain" and artifact["language"] == "agda" and not safe_path(target, "data").is_dir():
            raise EnvironmentUnavailable(f"Missing managed Agda data directory: {artifact_id}")
        return receipt

    def list(self) -> list[dict]:
        output = []
        for key, item in self.catalog["artifacts"].items():
            try:
                state = "installed" if self.installed(key) else "missing"
                error = None
            except (OSError, ValueError) as exc:
                state, error = "invalid", str(exc)
            output.append({"id": key, "kind": item["kind"], "language": item["language"],
                           "version": item["version"], "platform": item.get("platform", "any"),
                           "path": str(self.target(item)), "status": state, "error": error})
        return output

    @contextmanager
    def mutation(self):
        directory = safe_path(self.home, ".qprint")
        directory.mkdir(parents=True, exist_ok=True)
        lock = safe_path(directory, "toolchain-manager.lock")
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise WorkspaceError("Another store operation is active (toolchain-manager.lock)") from exc
        try:
            os.close(fd)
            yield
        finally:
            lock.unlink(missing_ok=True)

    def install(self, artifact_id: str, *, archive: Path | None = None, downloader=download) -> dict:
        artifact = self.artifact(artifact_id)
        if artifact.get("platform", "any") not in {"any", host_platform()}:
            raise EnvironmentUnavailable(f"Artifact does not support {host_platform()}: {artifact_id}")
        with self.mutation():
            if receipt := self.installed(artifact_id):
                return receipt
            update("install", f"正在安装 {artifact_id}")
            target = self.target(artifact)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".install-", dir=target.parent) as temporary:
                stage = Path(temporary) / "payload"
                stage.mkdir()
                local = Path(archive).resolve() if archive else Path(temporary) / "archive.zip"
                if archive is None:
                    if downloader is download:
                        downloader(artifact["url"], local, expected_sha256=artifact["sha256"])
                    else:
                        downloader(artifact["url"], local)
                update("checksum", f"正在校验 {artifact_id}")
                if local.stat().st_size > DOWNLOAD_LIMIT or sha256(local) != artifact["sha256"]:
                    raise WorkspaceError(f"Archive SHA-256 mismatch: {artifact_id}")
                extract_zip(local, stage, artifact.get("strip_prefix", ""), artifact.get("subdir", ""))
                if license_file := artifact.get("bundled_license"):
                    license_path = safe_path(Path(__file__).parent, license_file)
                    shutil.copyfile(license_path, stage / "LICENSE.Qprint-bundle.txt")
                for relative in artifact.get("executables", {}).values():
                    if not safe_path(stage, relative).is_file():
                        raise WorkspaceError(f"Archive is missing executable: {relative}")
                if artifact["kind"] == "toolchain":
                    self._prepare(artifact, stage)
                receipt = {"schema_version": 1, "id": artifact_id, "sha256": artifact["sha256"],
                           "url": artifact["url"], "version": artifact["version"],
                           "platform": artifact.get("platform", "any"),
                           "installed_at": datetime.now(timezone.utc).isoformat()}
                receipt.update({key: artifact[key] for key in ("integrity", "release_api", "asset_id", "asset_size") if key in artifact})
                (stage / RECEIPT).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
                # Atomic publication; never overwrite existing installations.
                stage.rename(target)
            return receipt

    def _prepare(self, artifact, stage):
        from .verification import run_command
        env = dict(os.environ)
        compiler = safe_path(stage, artifact["executables"][artifact["language"]])
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        if artifact["language"] == "agda":
            (stage / "data").mkdir()
            env["AGDA_DIR"] = str(stage / "data")
            env["Agda_datadir"] = str(stage / "data")
            result = run_command("setup", [str(compiler), "--setup"], stage, 120, env=env)
            if result.status != "passed":
                raise WorkspaceError(f"Agda setup failed: {result.output}")
        result = run_command("version", [str(compiler), "--version"], stage, 30, env=env)
        if result.status != "passed" or not re.search(rf"(?<![\w.-]){re.escape(artifact['version'])}(?![\w.-])", result.output):
            raise WorkspaceError(f"Installed compiler version check failed: {result.output}")

    def remove(self, artifact_id: str) -> dict:
        artifact = self.artifact(artifact_id)
        with self.mutation():
            if not self.installed(artifact_id):
                raise WorkspaceError(f"Artifact is not installed: {artifact_id}")
            target = self.target(artifact)
            store = safe_path(self.home, "toolchains" if artifact["kind"] == "toolchain" else "packages")
            # Validate the final absolute path and reject reparse points before recursion.
            if not target.is_relative_to(store) or target == store:
                raise WorkspaceError("Refusing to remove a store root or outside path")
            for directory, folders, files in os.walk(target, followlinks=False):
                for path in [Path(directory), *(Path(directory) / p for p in folders + files)]:
                    if path.is_symlink() or path.is_junction():
                        raise WorkspaceError("Refusing to remove an installation containing links")
            shutil.rmtree(target)
        return {"id": artifact_id, "status": "removed"}
