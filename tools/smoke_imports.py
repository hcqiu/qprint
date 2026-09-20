"""Optional live network smoke test; downloads public fixtures into .qprint only."""
import json
from pathlib import Path
import tempfile

from qprint.importers import import_code, import_paper


def main():
    project = Path(__file__).resolve().parents[1]
    scratch = project / ".qprint"
    scratch.mkdir(exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="network-smoke-", dir=scratch))
    results = {}
    for name, action in {
        "github": lambda: import_code(root, "https://github.com/CMU-HoTT/serre-finiteness", "agda", "serre-finiteness"),
        "arxiv": lambda: import_paper(root, "1603.04246", "Geometry", "Via16SpherePacking"),
    }.items():
        try:
            results[name] = {"status": "passed", "result": action()}
        except Exception as exc:
            results[name] = {"status": "failed", "error": str(exc)}
        print(json.dumps({name: results[name]}, ensure_ascii=True), flush=True)
    (scratch / "network-smoke.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return int(any(result["status"] == "failed" for result in results.values()))


if __name__ == "__main__":
    raise SystemExit(main())
