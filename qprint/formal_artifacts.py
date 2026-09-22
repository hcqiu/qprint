"""Acquire exact official artifacts; never resolve a floating branch/tag as a pin."""
import json
from pathlib import Path
import re
import tempfile

import httpx

from .paths import WorkspaceError, safe_path
from .toolchains import EnvironmentUnavailable, RECEIPT, download, host_platform, sha256

LOCAL_CATALOG = "toolchains/.qprint-catalog.json"


def release_asset(language, version):
    if host_platform() != "windows-x64":
        raise EnvironmentUnavailable("Automatic compiler discovery currently supports windows-x64")
    repo = {"lean": "leanprover/lean4", "agda": "agda/agda"}[language]
    name = f"lean-{version}-windows.zip" if language == "lean" else f"Agda-v{version}-win64.zip"
    url = f"https://api.github.com/repos/{repo}/releases/tags/v{version}"
    with httpx.Client(timeout=30, follow_redirects=False) as client:
        response = client.get(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "Qprint/1"})
        response.raise_for_status()
        assets = response.json().get("assets", [])
    matches = [a for a in assets if a.get("name") == name]
    if len(matches) != 1:
        raise EnvironmentUnavailable(f"No unique official asset for {language} {version}")
    asset = matches[0]
    expected = f"https://github.com/{repo}/releases/download/v{version}/{name}"
    if asset.get("browser_download_url") != expected:
        raise WorkspaceError("Unexpected compiler release asset URL")
    item = {"kind": "toolchain", "language": language, "version": version, "platform": host_platform(),
            "path": f"{language}/{version}", "url": expected,
            "executables": {language: f"bin/{language}.exe"}}
    digest = asset.get("digest")
    if digest is not None:
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            raise WorkspaceError("Invalid official compiler asset digest")
        item.update(sha256=digest[7:], integrity="github-release-digest")
    else:
        # Older GitHub assets have no publisher digest. Pin their HTTPS identity
        # and first acquired bytes explicitly; never label this publisher verification.
        if type(asset.get("id")) is not int or asset["id"] <= 0 or type(asset.get("size")) is not int or asset["size"] <= 0:
            raise EnvironmentUnavailable("Legacy official asset lacks an exact identity or size")
        item.update(integrity="official-release-https-first-use-sha256",
                    release_api=url, asset_id=asset["id"], asset_size=asset["size"])
    if language == "lean":
        item.update(strip_prefix=f"lean-{version}-windows")
        item["executables"]["lake"] = "bin/lake.exe"
    else:
        item["subdir"] = "bin"
    return f"{language}-{version}-{host_platform()}", item


class ArtifactProvider:
    def __init__(self, manager, *, downloader=download, release_lookup=release_asset):
        self.manager, self.downloader, self.release_lookup = manager, downloader, release_lookup

    def _remember(self, key, item):
        path = safe_path(self.manager.home, LOCAL_CATALOG)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.manager.mutation():
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema_version": 1, "artifacts": {}}
            existing = data["artifacts"].get(key)
            if existing is not None and existing != item:
                raise WorkspaceError(f"Conflicting local artifact: {key}")
            data["artifacts"][key] = item
            # Same-directory replacement also works on Windows, without partial JSON.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(data, stream, indent=2)
            try:
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        self.manager.catalog["artifacts"][key] = item
        return key, item

    def discover(self, *, kind, language, version=None, name=None, revision=None):
        if kind == "toolchain":
            if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+|-rc\d+)?", version):
                raise EnvironmentUnavailable("Automatic installation requires an exact compiler version")
            key, item = self.release_lookup(language, version)
            if "sha256" in item:
                return self._remember(key, item)
            cache = safe_path(self.manager.home, ".qprint/downloads")
            cache.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="compiler-", dir=cache) as directory:
                archive = Path(directory) / "compiler.zip"
                self.downloader(item["url"], archive)
                if archive.stat().st_size != item["asset_size"]:
                    raise WorkspaceError("Official compiler asset size mismatch")
                item["sha256"] = sha256(archive)
                self._remember(key, item)
                self.manager.install(key, archive=archive)
            return key, item
        if language != "agda" or name != "cubical" or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise EnvironmentUnavailable("Automatic package discovery requires supported library cubical and a full commit; add other libraries to the catalog")
        item = {"kind": "package", "language": "agda", "name": "cubical", "version": f"git-{revision}",
                "revision": revision, "path": f"agda/cubical/{revision}",
                "url": f"https://codeload.github.com/agda/cubical/zip/{revision}",
                "strip_prefix": f"cubical-{revision}", "include_paths": ["."],
                "library_file": "cubical.agda-lib", "flags": ["--guardedness"],
                "integrity": "fixed-commit-https-first-use-sha256"}
        key = f"cubical-{revision}"
        target = self.manager.target(item)
        receipt_path = safe_path(target, RECEIPT)
        # Adopt a previous managed installation only when its immutable source matches.
        if receipt_path.is_file():
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            if receipt.get("url") != item["url"] or not re.fullmatch(r"[0-9a-f]{64}", receipt.get("sha256", "")):
                raise WorkspaceError("Existing package receipt does not match requested immutable source")
            item["sha256"] = receipt["sha256"]
            item["version"] = receipt["version"]
            return self._remember(receipt["id"], item)
        cache = safe_path(self.manager.home, ".qprint/downloads")
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="resolve-", dir=cache) as directory:
            archive = Path(directory) / "package.zip"
            self.downloader(item["url"], archive)
            item["sha256"] = sha256(archive)
            self._remember(key, item)
            self.manager.install(key, archive=archive)
        return key, item
