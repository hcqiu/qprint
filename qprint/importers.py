"""Bounded downloads, validated archives and non-overwriting publication."""
from datetime import datetime, timezone
import gzip
import hashlib
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
from .formal_progress import with_progress, update
from .formal_downloads import fetch_bytes, recording
from .formal_preparation import record_preparation, preparation_summary

MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_EXPANDED = 300 * 1024 * 1024
MAX_FILES = 10_000
HOSTS = {"api.github.com", "codeload.github.com", "github.com", "arxiv.org", "export.arxiv.org"}


def fetch(url: str) -> bytes:
    return fetch_bytes(url, limit=MAX_DOWNLOAD, hosts=HOSTS)


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


@with_progress
@record_preparation
def import_code(root: Path, url: str, language: str, dest: str, ref: str | None = None, downloader=fetch,
                *, verify_after_download=True, timeout=600, toolchain_home=None, offline=False,
                verifier=None, on_phase=None, on_progress=None):
    if language not in {"lean", "agda", "coq"}:
        raise WorkspaceError("语言必须是 lean、agda 或 coq")
    if type(verify_after_download) is not bool:
        raise WorkspaceError("verify_after_download must be boolean")
    if on_phase:
        on_phase("downloading")
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
    commit = json.loads(downloader(f"https://api.github.com/repos/{owner}/{repo}/commits/{quote(ref, safe='')}" )).get("sha")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise WorkspaceError("GitHub did not resolve the ref to a fixed commit")
    data = downloader(f"https://codeload.github.com/{owner}/{repo}/zip/{commit}")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".qprint-import-", dir=root) as temp:
        stage = Path(temp) / "code"
        stage.mkdir()
        update("extract-source", "正在解压项目源码")
        files = extract_archive(data, stage, strip_root=True)
        if not files:
            raise WorkspaceError("仓库归档没有文件")
        provenance(stage, {"type": "github", "url": url, "ref": ref, "revision": commit,
                           "sha256": hashlib.sha256(data).hexdigest()})
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise WorkspaceError("目标已存在")
        stage.rename(target)
    result = {"path": target.relative_to(root).as_posix(), "files": len(files), "ref": ref, "revision": commit,
              "verification": {"status": "not_run", "reason": "disabled", "reports": []}}
    if verify_after_download:
        from .formal_import import verify_download
        if on_phase:
            on_phase("verifying")
        update("resolve", "正在识别项目与解析固定环境")
        try:
            result["verification"] = (verifier or verify_download)(target, language, timeout=timeout,
                                                                  toolchain_home=toolchain_home, offline=offline)
        except Exception as exc:
            # Import publication is retained even if compiler preparation fails.
            from .formal_reports import failure_report
            verification = {"status": "error", "message": str(exc), "reports": []}
            try:
                report = failure_report(target, language, exc, home=toolchain_home, timeout=timeout, offline=offline)
                verification["reports"] = [{key: report[key] for key in ("project", "status", "message", "report_path", "diagnosis")}]
            except Exception as report_error:
                verification["report_error"] = f"无法保存验证报告：{report_error}"
            result["verification"] = verification
    result["download_preparation"] = preparation_summary(None)
    return result


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
