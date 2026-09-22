"""Deterministic preparation and recovery before any proof verification."""
from dataclasses import replace
from functools import wraps
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
import time

from .formal_archives import extract
from .formal_downloads import EVENTS, download_file, event, github_json, recording
from .formal_git import PACKAGE_RECEIPT, github_repo, pinned_package, release_metadata, uses_cloud_release
from .formal_runner import run_command
from .paths import WorkspaceError, safe_path
from .formal_progress import update
from .formal_legacy_lake import needs_native_git, prepare_native_git, prepare_native_tag
from .formal_release_assets import acquire_asset, prepare_legacy_leantar


class PreparationError(WorkspaceError):
    code = "preparation_failure"


def record_preparation(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with recording([]):
            return function(*args, **kwargs)
    return wrapped


def preparation_summary(status):
    events = EVENTS.get() or []
    recovered = any(e["kind"] in {"download_retry", "checksum_mismatch", "archive_fallback", "cache_repair", "cache_retry"} for e in events)
    return {"status": "failed" if status in {"failed", "preparation_failure"} else "recovered" if recovered else "ready", "events": list(events)}


def config_fingerprints(root):
    names = {"lean-toolchain", "lake-manifest.json", "lakefile.toml", "lakefile.lean", "project.yaml",
             ".qprint-formal.yaml", ".qprint-formal.lock.yaml", ".qprint-formal.recipe.yaml"}
    names.update(path.name for path in root.glob("*.agda-lib"))
    return {name: hashlib.sha256(safe_path(root, name).read_bytes()).hexdigest()
            for name in sorted(names) if safe_path(root, name).is_file()}


def config_changed(before, after):
    # A first native Lake build may create its lock; existing pins must not change.
    current = dict(after)
    if "lake-manifest.json" not in before:
        current.pop("lake-manifest.json", None)
    return current != before


def _overrides(root, entries):
    path = safe_path(root, ".lake/package-overrides.json")
    data = json.loads(path.read_text()) if path.exists() else {"version": "1.1.0", "packages": []}
    if not isinstance(data, dict) or not isinstance(data.get("packages"), list) or any(not isinstance(p, dict) for p in data["packages"]):
        raise PreparationError("Invalid Lake package overrides")
    existing = {p.get("name"): p for p in data["packages"]}
    for entry, directory in entries:
        item = {k: entry[k] for k in ("name", "scope", "inherited", "configFile", "manifestFile") if k in entry}
        item.update(type="path", dir=directory.as_posix(), inherited=entry.get("inherited", False))
        if entry["name"] in existing:
            # Preserve explicit native overrides, never silently replace user intent.
            if existing[entry["name"]].get("type") != "path" or (root / existing[entry["name"]].get("dir", "")).resolve() != directory.resolve():
                raise PreparationError(f"Existing override conflicts with managed package {entry['name']}")
        else:
            data["packages"].append(item)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        json.dump(data, stream, indent=2)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _release_fallback(root, entry, *, downloader=download_file, query=github_json):
    package = safe_path(root, ".lake/packages/" + entry["name"])
    if not safe_path(package, PACKAGE_RECEIPT).is_file():
        raise PreparationError("Automatic release extraction requires a Qprint-managed package")
    repo, tag = github_repo(entry["url"]), entry["inputRev"]
    release = query(f"repos/{repo}/releases/tags/{tag}")
    assets = [a for a in release.get("assets", []) if a.get("name") == "ProofWidgets4.tar.gz"]
    expected = f"https://github.com/{repo}/releases/download/{tag}/ProofWidgets4.tar.gz"
    if len(assets) != 1 or assets[0].get("browser_download_url") != expected:
        raise PreparationError("No exact official ProofWidgets release")
    lake = safe_path(package, ".lake")
    lake.mkdir(exist_ok=True)
    archive = safe_path(lake, "ProofWidgets4.tar.gz")
    receipt = safe_path(lake, "qprint-release-asset.json")
    with tempfile.TemporaryDirectory(prefix=".qprint-extract-", dir=lake) as temporary:
        stage = Path(temporary)
        download = stage / "release.tar.gz"
        digest = acquire_asset(assets[0], expected, download, receipt, downloader=downloader, cached=archive)
        payload = stage / "payload"
        payload.mkdir()
        extract(download, payload)
        build = safe_path(lake, "build")
        for source in payload.rglob("*"):
            destination = safe_path(build, source.relative_to(payload).as_posix())
            if source.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        if not (build / "js").is_dir():
            raise PreparationError("Verified release is missing expected JavaScript artifacts")
        shutil.copyfile(download, archive)
    event("archive_fallback", package=entry["name"], backend="python", sha256=digest)
    return archive, expected


def _record_release_trace(context, archive, url, timeout, runner):
    """Let native Lake record acquisition of the verified, extracted release.

    A curl failure can leave no trace even after Python repairs the archive.
    This records only the release URL dependency, never a proof/build result.
    """
    with tempfile.TemporaryDirectory(prefix=".qprint-release-", dir=context.project_root) as temporary:
        program = Path(temporary) / "ReleaseTrace.lean"
        trace = archive.with_name(archive.name + ".trace")
        expression = (f'BuildTrace.writeToFile {json.dumps(str(trace), ensure_ascii=False)} '
                      f'(BuildTrace.ofHash (Hash.ofString {json.dumps(url, ensure_ascii=False)}))'
                      if needs_native_git(context) else
                      f'BuildMetadata.writeFile {json.dumps(str(trace), ensure_ascii=False)} '
                      f'(BuildMetadata.ofStub (Hash.ofString {json.dumps(url, ensure_ascii=False)}))')
        program.write_text('import Lake\nopen Lake\ndef main : IO Unit := do\n  ' + expression + '\n', encoding="utf-8")
        result = runner("release-trace", [str(context.driver), "env", str(context.compiler), "--run", str(program)],
                        context.project_root, timeout, env=context.environment)
        if result.status != "passed":
            raise PreparationError(f"Native Lake release receipt failed: {result.output[-2000:]}")
    event("release_trace_recorded", backend="native-lake", archive=archive.name)


def repair_cache_objects(cache, output, *, downloader=download_file, limit=64):
    """Repair only reported/missing objects from the native cache manifest."""
    config = safe_path(cache, "curl.cfg")
    if not config.is_file() or config.stat().st_size > 8 * 1024**2:
        return 0
    damaged = set(re.findall(r"([0-9a-f]{16})\.ltar: removing corrupted file", output))
    urls = dict((match[1], match[0]) for match in re.finditer(
        r"https://lakecache\.blob\.core\.windows\.net/mathlib4/f/([0-9a-f]{16})\.ltar", config.read_text(encoding="utf-8")))
    targets = [(key, url) for key, url in urls.items() if key in damaged or not safe_path(cache, key + ".ltar").is_file()]
    if len(targets) > limit:
        return 0  # The next native attempt resumes a substantially incomplete fetch.
    for key, url in targets:
        with tempfile.TemporaryDirectory(prefix=".qprint-object-", dir=cache) as temporary:
            downloaded = Path(temporary) / "object"
            downloader(url, downloaded, limit=100 * 1024**2)
            downloaded.replace(safe_path(cache, key + ".ltar"))
        event("cache_repair", object=key, source=url)
    return len(targets)


def prepare_environment(context, *, timeout=600, offline=False, runner=run_command):
    if context.language != "lean":
        return context
    manifest = context.requirements.get("native", {}).get("lake-manifest.json", {})
    entries = manifest.get("packages", [])
    if not isinstance(entries, list) or any(not isinstance(p, dict) for p in entries):
        raise PreparationError("Invalid locked Lake dependency entries")
    if not entries:
        return context
    if len(entries) > 128:
        raise PreparationError("Lake dependency preparation exceeds 128 locked packages")
    root, deadline = context.project_root, time.monotonic() + timeout
    guard = safe_path(root, ".qprint/preparation/lock")
    guard.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock = guard.open("x")
    except FileExistsError as exc:
        raise PreparationError("Another preparation operation is active for this project") from exc
    try:
        with lock:
            lock.write(str(os.getpid()))
        managed = []
        for index, entry in enumerate(entries, 1):
            update("dependency", f"正在准备依赖 {entry.get('name', '?')}", completed_files=index, total_files=len(entries))
            if time.monotonic() >= deadline:
                raise PreparationError("Dependency preparation deadline exhausted")
            if entry.get("type") == "git":
                target = pinned_package(root, entry, offline=offline)
                if target is not None:
                    managed.append((entry, target))
        legacy = needs_native_git(context)
        if managed and not legacy:
            _overrides(root, managed)
        env = dict(context.environment)
        for entry, target in managed:
            if legacy:
                prepare_native_git(target, entry, env=env, deadline=deadline, offline=offline, runner=runner)
                count = int(env.get("GIT_CONFIG_COUNT", "0"))
                if not 0 <= count < 128:
                    raise PreparationError("Too many inherited Git configuration overrides")
                env.update({"GIT_CONFIG_COUNT": str(count + 1), f"GIT_CONFIG_KEY_{count}": "safe.directory",
                            f"GIT_CONFIG_VALUE_{count}": target.as_posix()})
            if github_repo(entry.get("url")) == "leanprover-community/ProofWidgets4":
                if not uses_cloud_release(target):
                    event("release_strategy", package=entry["name"], strategy="upstream-source-and-cache")
                    continue
                if not offline and not legacy:
                    release_metadata(target, entry)
                if legacy:
                    prepare_native_tag(target, entry, env=env, deadline=deadline, offline=offline, runner=runner)
                count = int(env.get("GIT_CONFIG_COUNT", "0"))
                if not 0 <= count < 32:
                    raise PreparationError("Too many inherited Git configuration overrides")
                env.update({"GIT_CONFIG_COUNT": str(count + 1), f"GIT_CONFIG_KEY_{count}": "safe.directory",
                            f"GIT_CONFIG_VALUE_{count}": target.as_posix()})
        context = replace(context, environment=env)
        if legacy and not offline:
            for entry, target in managed:
                if github_repo(entry.get("url")) == "leanprover-community/ProofWidgets4" and uses_cloud_release(target):
                    archive, url = _release_fallback(root, entry)
                    _record_release_trace(context, archive, url, max(.1, deadline-time.monotonic()), runner)
        mathlib = next((p for p in entries if github_repo(p.get("url")) == "leanprover-community/mathlib4"), None)
        if not mathlib or offline:
            return context
        cache = safe_path(root, ".qprint/preparation/mathlib-cache")
        cache.mkdir(parents=True, exist_ok=True)
        env["MATHLIB_CACHE_DIR"] = str(cache)
        command = [str(context.driver), "exe", "cache", "get"]
        source = safe_path(root, ".lake/packages/" + mathlib["name"] + "/Cache/Main.lean")
        cache_io = source.with_name("IO.lean")
        if cache_io.is_file() and "MATHLIB_CACHE_DIR" not in cache_io.read_text(encoding="utf-8"):
            # Old mathlib reads XDG_CACHE_HOME/mathlib, ignoring MATHLIB_CACHE_DIR.
            cache = safe_path(root, ".qprint/preparation/legacy-cache/mathlib")
            cache.mkdir(parents=True, exist_ok=True)
            env["XDG_CACHE_HOME"] = str(cache.parent)
            prepare_legacy_leantar(cache_io, cache, context, max(.1, deadline-time.monotonic()), runner)
        if source.is_file() and "--repo=" in source.read_text(encoding="utf-8"):
            command = [str(context.driver), "exe", "cache", "--repo=leanprover-community/mathlib4", "get"]
        for attempt in range(1, 4):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise PreparationError("Mathlib preparation deadline exhausted")
            result = runner("mathlib-cache", command, root, remaining, env=env, idle_timeout=90)
            event("preparation_command", stage=result.stage, status=result.status, attempt=attempt,
                  duration_ms=result.duration_ms, output=result.output[-6000:])
            corrupt = "removing corrupted file" in result.output
            if result.status == "passed" and not corrupt:
                return context
            if attempt == 3:
                break
            if "ProofWidgets" in result.output and "release" in result.output:
                widget = next((p for p in entries if github_repo(p.get("url")) == "leanprover-community/ProofWidgets4"), None)
                if widget and uses_cloud_release(safe_path(root, ".lake/packages/" + widget["name"])):
                    archive, url = _release_fallback(root, widget)
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise PreparationError("Release preparation deadline exhausted")
                    _record_release_trace(context, archive, url, remaining, runner)
            repaired = repair_cache_objects(cache, result.output)
            recoverable = result.status == "timeout" or corrupt or repaired or any(t in result.output.lower() for t in ("curl", "download", "proofwidgets", "non utf-8", "non-utf-8"))
            if not recoverable:
                break
            event("cache_retry", attempt=attempt, repaired=repaired)
        raise PreparationError(f"Mathlib cache preparation failed: {result.output[-5000:]}")
    finally:
        guard.unlink(missing_ok=True)
