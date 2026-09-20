"""Bounded downloads, validated archives and non-overwriting publication."""
from datetime import datetime, timezone
import gzip
import io
import json
from pathlib import Path
import re
import shutil
import stat
import tarfile
import tempfile
from urllib.parse import quote, urljoin, urlparse
import zipfile

import httpx

from .paths import WorkspaceError, safe_path

MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_EXPANDED = 300 * 1024 * 1024
MAX_FILES = 10_000
HOSTS = {"api.github.com", "codeload.github.com", "github.com", "arxiv.org", "export.arxiv.org"}


def fetch(url: str) -> bytes:
    with httpx.Client(timeout=60, follow_redirects=False, headers={"User-Agent": "Qprint/0.1 (local research workspace)"}) as client:
        for _ in range(6):
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in HOSTS or parsed.username or parsed.port not in {None, 443}:
                raise WorkspaceError("下载地址或重定向不在允许的 HTTPS 来源范围内")
            with client.stream("GET", url) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers["location"])
                    continue
                response.raise_for_status()
                output = bytearray()
                for chunk in response.iter_bytes():
                    output.extend(chunk)
                    if len(output) > MAX_DOWNLOAD:
                        raise WorkspaceError("下载超过 100 MiB 限制")
                return bytes(output)
        raise WorkspaceError("下载重定向次数过多")


def extract_archive(data: bytes, destination: Path, strip_root: bool = False) -> list[str]:
    records = []
    expanded_size = 0
    if zipfile.is_zipfile(io.BytesIO(data)):
        archive = zipfile.ZipFile(io.BytesIO(data))
        for info in archive.infolist():
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}):
                archive.close()
                raise WorkspaceError("归档包含链接或特殊文件")
            records.append((info.filename, info.file_size, info.is_dir(), lambda info=info: archive.open(info)))
    else:
        try:
            archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
        except tarfile.TarError as exc:
            raise WorkspaceError("不是支持的 zip/tar 归档") from exc
        for info in archive:
            if not (info.isfile() or info.isdir()):
                archive.close()
                raise WorkspaceError("归档包含链接或特殊文件")
            records.append((info.name, info.size, info.isdir(), lambda info=info: archive.extractfile(info)))
            expanded_size += info.size
            if len(records) > MAX_FILES or expanded_size > MAX_EXPANDED:
                archive.close()
                raise WorkspaceError("解压内容超过文件数或 300 MiB 限制")
    try:
        if len(records) > MAX_FILES or sum(size for _, size, _, _ in records) > MAX_EXPANDED:
            raise WorkspaceError("解压内容超过文件数或 300 MiB 限制")
        validated, seen, roots = [], set(), set()
        for name, size, is_dir, opener in records:
            name = name.rstrip("/")
            while name.startswith("./"):
                name = name[2:]
            if name in {"", "."} and is_dir:
                continue
            safe_path(destination, name)
            roots.add(name.split("/")[0])
            if strip_root:
                if "/" not in name:
                    if is_dir:
                        continue
                    raise WorkspaceError("仓库归档缺少根目录")
                name = name.split("/", 1)[1]
            path = safe_path(destination, name)
            if str(path).casefold() in seen:
                raise WorkspaceError("归档包含重复路径（含大小写冲突）")
            seen.add(str(path).casefold())
            validated.append((path, size, is_dir, opener))
        if strip_root and len(roots) != 1:
            raise WorkspaceError("仓库归档有多个根目录")
        written = []
        for path, size, is_dir, opener in validated:
            if is_dir:
                path.mkdir(parents=True, exist_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with opener() as source, path.open("xb") as target:
                remaining = size
                while chunk := source.read(min(1024 * 1024, remaining + 1)):
                    remaining -= len(chunk)
                    if remaining < 0:
                        raise WorkspaceError("归档文件大小与声明不符")
                    target.write(chunk)
            written.append(path.relative_to(destination).as_posix())
        return written
    finally:
        archive.close()


def provenance(folder: Path, info: dict):
    target = folder / ".qprint-source.json"
    if target.exists():
        raise WorkspaceError("来源归档使用了保留文件名 .qprint-source.json")
    target.write_text(json.dumps({**info, "downloaded_at": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")


def import_code(root: Path, url: str, language: str, dest: str, ref: str | None = None, downloader=fetch):
    if language not in {"lean", "agda", "coq"}:
        raise WorkspaceError("语言必须是 lean、agda 或 coq")
    match = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+?)(?:\.git)?/?", url.strip())
    if not match:
        raise WorkspaceError("请输入 GitHub 仓库根地址，分支请填写在 ref 中")
    target = safe_path(root, f"{language}/{dest}")
    if target.exists():
        raise WorkspaceError("目标已存在，导入不会覆盖原有内容")
    owner, repo = match.groups()
    if not ref:
        info = json.loads(downloader(f"https://api.github.com/repos/{owner}/{repo}"))
        ref = info.get("default_branch")
    if not isinstance(ref, str) or not re.fullmatch(r"[\w./-]+", ref) or ".." in ref:
        raise WorkspaceError("无效的仓库 ref")
    data = downloader(f"https://codeload.github.com/{owner}/{repo}/zip/{quote(ref, safe='')}")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".qprint-import-", dir=root) as temp:
        stage = Path(temp) / "code"
        stage.mkdir()
        files = extract_archive(data, stage, strip_root=True)
        if not files:
            raise WorkspaceError("仓库归档没有文件")
        provenance(stage, {"type": "github", "url": url, "ref": ref})
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise WorkspaceError("目标已存在")
        stage.rename(target)
    return {"path": target.relative_to(root).as_posix(), "files": len(files), "ref": ref}


def arxiv_id(value: str) -> str:
    value = value.strip()
    if value.startswith("https://"):
        parsed = urlparse(value)
        if parsed.hostname not in {"arxiv.org", "www.arxiv.org", "export.arxiv.org"}:
            raise WorkspaceError("论文 URL 必须来自 arxiv.org")
        value = re.sub(r"^/(?:abs|pdf|src|e-print)/", "", parsed.path).removesuffix(".pdf")
    value = value.removeprefix("arXiv:")
    if not re.fullmatch(r"(?:\d{4}\.\d{4,5}|[a-zA-Z][\w.-]*/\d{7})(?:v[1-9]\d*)?", value):
        raise WorkspaceError("无效的 arXiv 编号")
    return value


def extract_source(data: bytes, stage: Path, name: str):
    try:
        return extract_archive(data, stage)
    except WorkspaceError as exc:
        if str(exc) != "不是支持的 zip/tar 归档":
            raise
    if data.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            data = stream.read(MAX_EXPANDED + 1)
    if len(data) > MAX_EXPANDED:
        raise WorkspaceError("源码解压超过限制")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError as exc:
        raise WorkspaceError("源文件既不是归档也不是 UTF-8 TeX") from exc
    if not re.search(r"\\(?:documentclass\b|begin\{document\}|section\b)", text) or re.search(r"<(?:!doctype|html)\b", text, re.I):
        raise WorkspaceError("arXiv 未提供可识别的 TeX 源码")
    (stage / f"{name}.tex").write_text(text, encoding="utf-8")
    return [f"{name}.tex"]


def import_paper(root: Path, source: str, dest: str, name: str, downloader=fetch):
    identifier = arxiv_id(source)
    if "/" in name or not name:
        raise WorkspaceError("论文名必须是不含目录的 basename")
    prefix = f"{dest}/" if dest else ""
    pdf_target = safe_path(root, f"pdf/{prefix}{name}.pdf")
    tex_target = safe_path(root, f"tex/{prefix}{name}")
    if pdf_target.exists() or tex_target.exists():
        raise WorkspaceError("PDF 或 TeX 目标已存在，导入不会覆盖")
    pdf = downloader(f"https://arxiv.org/pdf/{identifier}")
    if not pdf.startswith(b"%PDF-"):
        raise WorkspaceError("arXiv 返回内容不是 PDF")
    source_data = downloader(f"https://arxiv.org/src/{identifier}")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".qprint-import-", dir=root) as temp:
        stage = Path(temp)
        tex_stage = stage / "tex"
        tex_stage.mkdir()
        files = extract_source(source_data, tex_stage, name)
        if not any(p.lower().endswith(".tex") for p in files):
            raise WorkspaceError("arXiv 源码归档中没有 TeX 文件")
        provenance(tex_stage, {"type": "arxiv", "id": identifier})
        pdf_stage = stage / "paper.pdf"
        pdf_stage.write_bytes(pdf)
        tex_target.parent.mkdir(parents=True, exist_ok=True)
        pdf_target.parent.mkdir(parents=True, exist_ok=True)
        if pdf_target.exists() or tex_target.exists():
            raise WorkspaceError("导入期间目标已被创建")
        tex_stage.rename(tex_target)
        try:
            pdf_stage.rename(pdf_target)
        except Exception:
            # Roll back only the directory that this operation just published.
            tex_target.rename(tex_stage)
            raise
    return {"pdf": pdf_target.relative_to(root).as_posix(), "tex": tex_target.relative_to(root).as_posix(), "files": len(files), "id": identifier}
