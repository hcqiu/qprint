"""Formal Blueprint Project to QPrint — run from the Qprint root."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from qprint.formal_blueprint import main


if __name__ == "__main__":
    raise SystemExit(main())
