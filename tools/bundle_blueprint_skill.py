"""Maintainer-only: refresh the skill's portable runtime from application modules."""
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("blueprint.py", "paths.py", "graph_index.py", "tex.py", "_tex_worker.py", "tex_to_blueprint.py")


def bundle():
    target = ROOT / "skills/tex-to-blueprint/scripts/qprint_blueprint"
    target.mkdir(parents=True, exist_ok=True)
    (target / "__init__.py").write_text('"""Portable Blueprint runtime bundled with the skill."""\n', encoding="utf-8")
    for name in MODULES:
        shutil.copyfile(ROOT / "qprint" / name, target / name)
    print(f"Bundled {len(MODULES)} modules in {target}")


if __name__ == "__main__":
    bundle()
