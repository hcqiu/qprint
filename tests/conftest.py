import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.fixture
def local_python_shell(tmp_path):
    """An isolated Qprint root using the real local Python, without Conda on PATH."""
    shell = shutil.which("pwsh") or shutil.which("powershell")
    prefix = Path(__file__).resolve().parents[1] / ".conda"
    if os.name != "nt" or not shell or not (prefix / "python.exe").is_file():
        pytest.skip("Windows PowerShell and the project .conda environment required")
    root = tmp_path / "Qprint local's folder"
    root.mkdir()
    env = {key: value for key, value in os.environ.items()
           if not key.upper().startswith("CONDA") and key.upper() not in {"PYTHONHOME", "PYTHONPATH"}}
    env.update(PATH=str(Path(os.environ["SystemRoot"]) / "System32"),
               QPRINT_TEST_ROOT=str(root), QPRINT_TEST_PREFIX=str(prefix), PYTHONIOENCODING="utf-8")

    def run(script, *, cwd=None):
        return subprocess.run([shell, "-NoProfile", "-NonInteractive", "-Command", script],
                              cwd=cwd or root, env=env, capture_output=True, text=True,
                              encoding="utf-8", timeout=30)

    # A junction avoids copying or installing an environment for each fixture.
    # Only the test workspace/runtime is isolated; product startup still uses .\.conda.
    result = run("$null = New-Item -ItemType Junction -Path .conda -Target $env:QPRINT_TEST_PREFIX")
    assert result.returncode == 0, result.stderr
    try:
        yield root, run
    finally:
        # Remove only the junction itself, never its environment target.
        (root / ".conda").rmdir()
