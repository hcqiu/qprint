"""Pinned GitHub package acquisition; never rewrite native version authorities."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zlib

from .formal_archives import extract
from .formal_downloads import download_file, event, github_json
from .paths import WorkspaceError, safe_path

PACKAGE_RECEIPT = ".qprint-package.json"


def package_name(value):
    # Legacy Lake serializes escaped Lean identifiers, but uses unescaped directories.
    if isinstance(value, str) and value.startswith("«") and value.endswith("»"):
        value = value[1:-1]
    if not isinstance(value, str) or not re.fullmatch(r"[\w-]+", value):
        raise WorkspaceError("Invalid locked Lake package name")
    return value


def uses_cloud_release(target):
    """Older ProofWidgets opts into Lake release archives; newer pins do not."""
    configuration = safe_path(target, "lakefile.lean")
    return configuration.is_file() and bool(re.search(
        r"(?m)^\s*preferReleaseBuild\s*:=\s*true\b", configuration.read_text(encoding="utf-8")))


def github_repo(url):
    if not isinstance(url, str):
        return None
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?/?", url or "")
    return match[1] if match else None


def pinned_package(root, entry, *, offline=False, downloader=download_file):
    repo, revision, name = github_repo(entry.get("url")), entry.get("rev"), entry.get("name")
    if not repo or not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        return None  # Let Lake handle other supported native dependency kinds.
    name = package_name(name)
    target = safe_path(root, ".lake/packages/" + name)
    receipt_path = safe_path(target, PACKAGE_RECEIPT)
    if target.exists():
        if not receipt_path.is_file():
            return None  # Existing user checkouts are never adopted or overwritten.
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("revision") != revision or receipt.get("repository") != repo:
            raise WorkspaceError(f"Managed package {name} conflicts with the current lock; preserve it and resolve explicitly")
        return target
    if offline:
        raise WorkspaceError(f"Offline: missing locked package {name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".qprint-package-", dir=target.parent) as temporary:
        directory = Path(temporary)
        archive, stage = directory / "source.zip", directory / "source"
        url = f"https://codeload.github.com/{repo}/zip/{revision}"
        info = downloader(url, archive, limit=300 * 1024**2)
        stage.mkdir()
        count = extract(archive, stage, strip_root=True, internal_aliases=True)
        # Source archives must not impersonate a previously managed installation.
        if (stage / PACKAGE_RECEIPT).exists() or (stage / ".git").exists():
            raise WorkspaceError("Source archive contains reserved preparation metadata")
        config = entry.get("configFile", "lakefile.lean")
        if not safe_path(stage, config).is_file():
            raise WorkspaceError(f"Pinned package {name} is missing {config}")
        (stage / PACKAGE_RECEIPT).write_text(json.dumps({"repository": repo, "revision": revision,
            "url": url, "sha256": info["sha256"], "files": count}, indent=2), encoding="utf-8")
        stage.rename(target)
    event("package_prepared", package=name, revision=revision, transport="fixed-commit-archive")
    return target


def release_metadata(target, entry, *, query=github_json):
    """Restore authentic signed commit/tag objects solely for Lake release lookup.

    This is explicitly not a full Git checkout. Never manufacture a commit ID.
    """
    repo, revision, tag = github_repo(entry.get("url")), entry.get("rev"), entry.get("inputRev")
    if not repo or not isinstance(tag, str) or not re.fullmatch(r"v\d+(?:\.\d+)+(?:-[\w.]+)?", tag):
        raise WorkspaceError("Release preparation requires an exact upstream tag in the native lock")
    receipt = safe_path(target, PACKAGE_RECEIPT)
    if not receipt.is_file():
        return  # Do not modify the Git metadata of a user checkout.
    git = safe_path(target, ".git")
    marker = safe_path(git, "qprint-release.json")
    expected = {"repository": repo, "revision": revision, "tag": tag}
    if marker.is_file() and json.loads(marker.read_text()) == expected:
        return
    if git.exists():
        raise WorkspaceError("Existing Git metadata is not owned by this preparation step")
    remote_tag = query(f"repos/{repo}/git/ref/tags/{tag}")["object"]
    if remote_tag["type"] == "tag":
        remote_tag = query(f"repos/{repo}/git/tags/{remote_tag['sha']}")["object"]
    if remote_tag.get("sha") != revision or remote_tag.get("type") != "commit":
        raise WorkspaceError("Release tag does not match the locked commit")
    commit = query(f"repos/{repo}/git/commits/{revision}")
    proof = commit.get("verification", {})
    if not proof.get("payload") or not proof.get("signature"):
        raise WorkspaceError("Cannot reconstruct authentic release metadata from this GitHub response")
    header, body = proof["payload"].split("\n\n", 1)
    signature = proof["signature"].replace("\n", "\n ")
    data = (header + "\ngpgsig " + signature + "\n\n" + body).encode()
    content = b"commit " + str(len(data)).encode() + b"\0" + data
    if hashlib.sha1(content).hexdigest() != revision:
        raise WorkspaceError("Reconstructed release commit SHA does not match the native lock")
    with tempfile.TemporaryDirectory(prefix=".qprint-git-", dir=target) as temporary:
        stage = Path(temporary) / "git"
        obj = stage / "objects" / revision[:2] / revision[2:]
        obj.parent.mkdir(parents=True)
        obj.write_bytes(zlib.compress(content))
        (stage / "HEAD").write_text(revision + "\n")
        tag_path = stage / "refs/tags" / tag
        tag_path.parent.mkdir(parents=True)
        tag_path.write_text(revision + "\n")
        (stage / "config").write_text('[core]\n\trepositoryformatversion = 0\n\tbare = false\n')
        (stage / "qprint-release.json").write_text(json.dumps(expected))
        stage.rename(git)
    event("release_metadata_restored", **expected)
