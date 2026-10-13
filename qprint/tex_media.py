"""Bounded local TeX graphics, cached as browser-safe raster images."""
from hashlib import sha256
from html import escape
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import tempfile
from uuid import uuid4

from .tex import mask_comments, tex_graphics
from .tex_support import simple_definitions


class MediaError(ValueError):
    pass


def compiler_path():
    local = Path(sys.prefix) / "Library/bin/tectonic.exe"
    return str(local) if local.is_file() else shutil.which("tectonic")


def drawing_document(source: str, preamble: str) -> str:
    # Import only simple command definitions needed by this picture. A paper's
    # complete preamble can contain document I/O and unrelated package effects.
    definitions = {}
    pattern = re.compile(r"\\(?:newcommand|renewcommand|providecommand)\*?\s*\{(\\[A-Za-z]+)\}\s*(?:\[(\d)\])?\s*\{")
    masked = mask_comments(preamble)
    masked += '\n' + '\n'.join(simple_definitions(masked))
    for match in pattern.finditer(masked):
        depth, end = 1, match.end()
        while end < len(masked) and depth:
            if masked[end] == "\\":
                end += 2
                continue
            depth += (masked[end] == "{") - (masked[end] == "}")
            end += 1
        if not depth:
            definitions[match[1]] = (match[2], masked[match.end():end - 1])
    selected = {}
    pending = [source]
    while pending:
        for name in re.findall(r"\\[A-Za-z]+", pending.pop()):
            if name in definitions and name not in selected:
                count, body = definitions[name]
                selected[name] = rf"\providecommand{{{name}}}" + (f"[{count}]" if count else "") + "{" + body + "}"
                pending.append(body)
    libraries = {"matrix", "arrows", "arrows.meta", "calc", "positioning"}
    for value in re.findall(r"\\usetikzlibrary\s*\{([^{}]*)\}", masked):
        for library in value.split(","):
            library = library.strip()
            if re.fullmatch(r"[a-zA-Z][a-zA-Z0-9.-]*", library):
                libraries.add(library)
    content = "\n".join(selected.values()) + "\n" + mask_comments(source)
    # No TeX file/process access, dynamic command names, category changes, or
    # encoded control sequences in supplied content. Tectonic also runs untrusted.
    forbidden = r"\\(?:input|include\w*|openin|openout|read\w*|write\w*|immediate|special|catcode|csname|endcsname|def|edef|gdef|xdef|let|futurelet|directlua|usepackage|documentclass|loop|repeat|every\w*|scantokens|expandafter|newread|newwrite|file\w*|pdf\w*|shipout)\b|\^\^"
    if len(content) > 100_000 or re.search(forbidden, content, re.I):
        raise MediaError("TikZ 含不支持的文件操作或动态 TeX 命令")
    extra_packages = ''
    if re.search(r'\\xymatrix\b|\\begin\{CD\}', source):
        extra_packages = r'\usepackage[all]{xy}' + '\n' + r'\usepackage{amscd}' + '\n'
        source = re.sub(r'^\s*(?:\\\[|\$\$|\\begin\{(?:equation\*?|align\*?|gather\*?)\})', '', source)
        source = re.sub(r'(?:\\\]|\$\$|\\end\{(?:equation\*?|align\*?|gather\*?)\})\s*$', '', source)
        source = re.sub(r'\\label\s*\{[^{}]*\}', '', source)
        source = '$\\displaystyle ' + source + '$'
    return (r"\documentclass[border=4pt]{standalone}" + "\n"
            + r"\usepackage{amsmath,amssymb,tikz,tikz-cd}" + "\n"
            + extra_packages
            + r"\usetikzlibrary{" + ",".join(sorted(libraries)) + "}\n"
            + "\n".join(selected.values()) + "\n"
            + r"\begin{document}" + "\n" + mask_comments(source) + "\n" + r"\end{document}")


class TexMedia:
    def __init__(self, root: Path, *, allow_download: bool = False):
        self.root = root.resolve()
        self.tex_root = (self.root / "tex").resolve()
        self.cache = self.root / ".qprint/cache/tex-media"
        self.allow_download = allow_download

    def cached_file(self, key: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", key):
            raise FileNotFoundError("无效的图片缓存编号")
        target = (self.cache / (key + ".png")).resolve()
        if not target.is_relative_to(self.cache.resolve()) or not target.is_file():
            raise FileNotFoundError("图片缓存不存在")
        return target

    def resolve_image(self, name: str, path: str, preamble: str) -> Path:
        if re.search(r"[\\:{}\x00]", name) or Path(name).is_absolute():
            raise MediaError("图片路径必须是 TeX 目录内的相对路径")
        parent = (self.tex_root / path).parent
        folders = [parent]
        for match in re.finditer(r"\\graphicspath\s*\{((?:\s*\{[^{}]*\}\s*)+)\}", mask_comments(preamble)):
            folders.extend(parent / item for item in re.findall(r"\{([^{}]*)\}", match[1]))
        for folder in folders:
            candidate = folder / name
            for suffix in ([""] if candidate.suffix else [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"]):
                target = Path(str(candidate) + suffix).resolve()
                if target.is_relative_to(self.tex_root) and target.is_file():
                    if target.suffix.lower() not in {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}:
                        raise MediaError("不支持的图片格式（支持 PDF、PNG、JPEG、WebP、GIF）")
                    if target.stat().st_size > 32 * 1024 * 1024:
                        raise MediaError("图片超过 32 MiB 限制")
                    return target
        raise MediaError(f"找不到图片: {name}")

    @staticmethod
    def rasterize(source: Path, target: Path, page: int = 1):
        from PIL import Image, ImageOps
        if source.suffix.lower() == ".pdf":
            import pypdfium2 as pdfium
            with pdfium.PdfDocument(source) as document:
                if not 1 <= page <= len(document):
                    raise MediaError("PDF 图片页码超出范围")
                pdf_page = document[page - 1]
                try:
                    width, height = pdf_page.get_size()
                    if min(width, height) <= 0:
                        raise MediaError("PDF 图片尺寸无效")
                    bitmap = pdf_page.render(scale=min(2.5, 2400 / max(width, height)))
                    try:
                        image = bitmap.to_pil().copy()
                    finally:
                        bitmap.close()
                finally:
                    pdf_page.close()
        else:
            try:
                with Image.open(source) as original:
                    if original.width * original.height > 24_000_000:
                        raise MediaError("图片超过 2400 万像素限制")
                    image = ImageOps.exif_transpose(original).convert("RGBA")
            except Image.DecompressionBombError as exc:
                raise MediaError("图片像素尺寸过大") from exc
        image.thumbnail((2400, 2400))
        image.save(target, "PNG")

    def render(self, graphic: dict, path: str, preamble: str) -> str:
        options = graphic.get("options", "")
        page_match = re.search(r"(?:^|,)\s*page\s*=\s*(\d+)\s*(?:,|$)", options)
        page = int(page_match[1]) if page_match else 1
        if graphic["kind"] != "image":
            document = drawing_document(graphic["source"], preamble)
            payload = document.encode()
            alt = "TikZ 图" if graphic['kind'] == 'tikz' else '交换图'
        else:
            source = self.resolve_image(graphic["value"], path, preamble)
            payload = source.suffix.lower().encode() + source.read_bytes() + str(page).encode()
            alt = Path(graphic["value"]).name
        key = sha256(b"qprint-tex-media-v1\0" + payload).hexdigest()
        target = self.cache / (key + ".png")
        self.cache.mkdir(parents=True, exist_ok=True)
        if not target.is_file():
            with tempfile.TemporaryDirectory(prefix="render-", dir=self.cache) as folder:
                folder = Path(folder)
                if graphic["kind"] != "image":
                    compiler = compiler_path()
                    if not compiler:
                        raise MediaError("TikZ 需要本地 Tectonic；请更新 .conda 环境并运行图形预热命令")
                    (folder / "picture.tex").write_text(document, encoding="utf-8")
                    try:
                        result = subprocess.run([compiler, "-X", "compile", "--untrusted", *([] if self.allow_download else ["--only-cached"]),
                                                 "--reruns", "0", "picture.tex"], cwd=folder,
                                                capture_output=True, timeout=600 if self.allow_download else 30,
                                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                                                env={**os.environ, "TECTONIC_UNTRUSTED_MODE": "1"})
                    except subprocess.TimeoutExpired as exc:
                        raise MediaError(f"TikZ 编译超过 {600 if self.allow_download else 30} 秒，已停止") from exc
                    source = folder / "picture.pdf"
                    if result.returncode or not source.is_file():
                        if self.allow_download:
                            print((result.stdout + result.stderr).decode("utf-8", errors="replace")[-6000:], file=sys.stderr)
                        raise MediaError("TikZ 编译失败或缺少缓存的 TeX 宏包；请运行图形预热命令")
                output = folder / "image.png"
                self.rasterize(source, output, page)
                # Publish a new file inheriting the cache directory's ACL, not
                # the private TemporaryDirectory ACL (notably on Windows).
                staged = self.cache / f"{key}-{uuid4().hex}.tmp"
                try:
                    shutil.copyfile(output, staged)
                    staged.replace(target)
                finally:
                    staged.unlink(missing_ok=True)
        style = ""
        width = re.search(r"(?:^|,)\s*width\s*=\s*(\d*\.?\d+)\s*\\(?:line|text|column)width", options)
        if width:
            style = f' style="width:{min(100, max(1, float(width[1]) * 100)):g}%"'
        return f'<img class="tex-image" src="/api/tex-media/{key}.png" alt="{escape(alt, quote=True)}"{style} loading="lazy">'

    def prepare(self, source: str, path: str, preamble: str):
        html, warnings = [], []
        try:
            graphics = tex_graphics(source)
        except ValueError as exc:
            return source, [], [f"图形源码不完整: {exc}"]
        for graphic in graphics:
            try:
                html.append(self.render(graphic, path, preamble))
            except (OSError, ValueError, RuntimeError, ImportError) as exc:
                message = f"图形未渲染: {exc}"
                warnings.append(message)
                html.append(f'<details class="tex-media-fallback"><summary>{escape(message)}</summary><pre>{escape(graphic["source"])}</pre></details>')
        for index, graphic in reversed(list(enumerate(graphics))):
            labels = ''.join(re.findall(r'\\label\s*\{[^{}]*\}', graphic['source']))
            source = source[:graphic["start"]] + rf"\qprintmedia{{{index}}}" + labels + source[graphic["end"]:]
        return source, html, warnings


if __name__ == "__main__":
    import argparse
    from .tex import TexDocument
    parser = argparse.ArgumentParser(description="预热论文图形与 Tectonic 宏包缓存（允许下载 TeX 宏包）")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--paper", required=True, help="相对于工作区 tex/ 的论文路径")
    args = parser.parse_args()
    media = TexMedia(args.workspace, allow_download=True)
    path = (media.tex_root / args.paper).resolve()
    if not path.is_relative_to(media.tex_root):
        parser.error("论文必须位于工作区 tex/ 内")
    doc = TexDocument(args.paper, path.read_text(encoding="utf-8"))
    failures = 0
    graphics = tex_graphics(doc.source)
    for index, graphic in enumerate(graphics, 1):
        try:
            media.render(graphic, args.paper, doc.preamble)
            print(f"{index}/{len(graphics)} {graphic['kind']}: OK", flush=True)
        except (OSError, ValueError, RuntimeError, ImportError) as exc:
            failures += 1
            print(f"{index}/{len(graphics)} {graphic['kind']}: {exc}", flush=True)
    sys.exit(bool(failures))
