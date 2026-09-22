"""Bounded HTTPS retry/resume with integrity checks and preparation evidence."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urljoin, urlparse

import httpx

from .paths import WorkspaceError
from .formal_progress import update

EVENTS = ContextVar("qprint_preparation_events", default=None)
HOSTS = {"api.github.com", "github.com", "codeload.github.com", "release-assets.githubusercontent.com",
         "objects.githubusercontent.com", "lakecache.blob.core.windows.net"}


def event(kind, **details):
    events = EVENTS.get()
    if events is not None and len(events) < 200:
        events.append({"kind": kind, **details})


@contextmanager
def recording(events):
    token = EVENTS.set(events)
    try:
        yield
    finally:
        EVENTS.reset(token)


def validated_url(url, hosts):
    parsed = urlparse(url)
    if (parsed.scheme != "https" or parsed.hostname not in hosts or parsed.username or parsed.password
            or parsed.port not in {None, 443}):
        raise WorkspaceError("Download requires an approved HTTPS source")
    return url


def download_file(url, destination, *, expected_sha256=None, limit=2 * 1024**3,
                  hosts=HOSTS, attempts=3, client=None, sleep=time.sleep):
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(destination)
    if expected_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
        raise WorkspaceError("Expected SHA-256 must be a complete lowercase digest")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # A private staging directory prevents unrelated partial files being reused.
    with tempfile.TemporaryDirectory(prefix=".qprint-download-", dir=destination.parent) as temporary:
        partial = Path(temporary) / "partial"
        etag = None
        own_client = client is None
        transport = client or httpx.Client(timeout=httpx.Timeout(30, read=20), follow_redirects=False,
                                          headers={"User-Agent": "Qprint/1", "Accept-Encoding": "identity"})
        try:
            for attempt in range(1, attempts + 1):
                message = "正在下载 " + urlparse(url).path.rsplit("/", 1)[-1]
                update("download", message, force=True, attempt=attempt, bytes=0)
                current, offset = url, partial.stat().st_size if partial.exists() and etag else 0
                headers = {"Accept-Encoding": "identity"}
                if offset:
                    headers.update({"Range": f"bytes={offset}-", "If-Range": etag})
                try:
                    for _ in range(6):
                        validated_url(current, hosts)
                        with transport.stream("GET", current, headers=headers) as response:
                            if response.is_redirect:
                                current = urljoin(current, response.headers["location"])
                                continue
                            if response.status_code == 416 and offset:
                                etag = None
                                raise httpx.ReadError("Range no longer valid; restart download")
                            response.raise_for_status()
                            if response.headers.get("content-encoding", "identity") != "identity":
                                raise WorkspaceError("Download server ignored identity encoding")
                            append = bool(offset and response.status_code == 206)
                            if response.status_code == 206:
                                content_range = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", response.headers.get("content-range", ""))
                                if (not append or not content_range or int(content_range[1]) != offset
                                        or int(content_range[2]) < offset or int(content_range[2]) + 1 != int(content_range[3])
                                        or response.headers.get("etag") != etag):
                                    etag = None
                                    raise httpx.ReadError("Unverifiable resumed response; restart download")
                            new_etag = response.headers.get("etag")
                            etag = new_etag if new_etag and not new_etag.startswith("W/") else None
                            size = offset if append else 0
                            expected_size = response.headers.get("content-length")
                            received = 0
                            total = int(content_range[3]) if append else int(expected_size) if expected_size else None
                            update("download", message, force=True, attempt=attempt, bytes=size, total_bytes=total)
                            with partial.open("ab" if append else "wb") as output:
                                chunks = (response.content,) if response.is_stream_consumed else response.iter_raw()
                                for chunk in chunks:
                                    size += len(chunk)
                                    received += len(chunk)
                                    if size > limit:
                                        raise WorkspaceError(f"Download exceeds {limit} byte limit")
                                    output.write(chunk)
                                    update("download", message, attempt=attempt, bytes=size, total_bytes=total)
                            if expected_size and received != int(expected_size):
                                raise httpx.ReadError("Incomplete response body")
                            if append and size != int(content_range[3]):
                                raise httpx.ReadError("Incomplete resumed response body")
                            update("checksum", "正在校验 " + urlparse(url).path.rsplit("/", 1)[-1], bytes=size, total_bytes=size)
                            digest = hashlib.sha256(partial.read_bytes()).hexdigest() if size < 1024**2 else _digest(partial)
                            if expected_sha256 and digest != expected_sha256:
                                event("checksum_mismatch", url=url, attempt=attempt)
                                etag = None
                                raise httpx.ReadError("Archive SHA-256 mismatch")
                            partial.replace(destination)
                            event("download_completed", url=url, sha256=digest, bytes=size, attempts=attempt, resumed=append)
                            return {"url": url, "sha256": digest, "bytes": size, "attempts": attempt}
                    raise WorkspaceError("Too many download redirects")
                except (httpx.TransportError, httpx.HTTPStatusError) as exc:
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in {408, 429, 500, 502, 503, 504}:
                        raise
                    event("download_retry", url=url, attempt=attempt, reason=type(exc).__name__)
                    if attempt == attempts:
                        update("download-failed", "下载重试次数已用尽", attempt=attempt)
                        raise
                    update("download-retry", f"下载中断，准备第 {attempt + 1} 次尝试", attempt=attempt)
                    sleep(min(2 ** (attempt - 1), 4))
        finally:
            if own_client:
                transport.close()


def _digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def fetch_bytes(url, *, limit=100 * 1024**2, hosts=HOSTS):
    with tempfile.TemporaryDirectory(prefix="qprint-fetch-") as temporary:
        path = Path(temporary) / "response"
        download_file(url, path, limit=limit, hosts=hosts)
        return path.read_bytes()


def github_json(path):
    return json.loads(fetch_bytes("https://api.github.com/" + path, limit=8 * 1024**2))
