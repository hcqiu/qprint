"""Fetch pinned KaTeX package with npm integrity verification; never run npm scripts."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
from urllib.request import urlopen

VERSION = "0.16.22"
ROOT = Path(__file__).resolve().parents[1] / "qprint" / "static" / "vendor" / "katex"


def main():
    with urlopen(f"https://registry.npmjs.org/katex/{VERSION}", timeout=60) as response:
        metadata = json.load(response)
    with urlopen(metadata["dist"]["tarball"], timeout=60) as response:
        data = response.read(10 * 1024 * 1024)
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
    if integrity != metadata["dist"]["integrity"]:
        raise RuntimeError("KaTeX integrity mismatch")
    wanted = {"package/dist/katex.min.js": "katex.min.js", "package/dist/katex.min.css": "katex.min.css", "package/dist/contrib/auto-render.min.js": "auto-render.min.js", "package/LICENSE": "LICENSE"}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            name = wanted.get(member.name)
            if member.name.startswith("package/dist/fonts/") and member.name.endswith((".woff2", ".woff", ".ttf")):
                name = "fonts/" + Path(member.name).name
            if name and member.isfile():
                target = ROOT / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())
    (ROOT / "provenance.json").write_text(json.dumps({"name": "katex", "version": VERSION, "integrity": integrity, "source": metadata["dist"]["tarball"]}, indent=2), encoding="utf-8")
    print(f"Vendored KaTeX {VERSION} to {ROOT}")


if __name__ == "__main__":
    main()
