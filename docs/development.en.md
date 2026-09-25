# Development and verification

[中文](development.md) | [English](development.en.md) · [Documentation](index.en.md)

See [pyproject.toml](../pyproject.toml) for dependencies and [AGENTS.md](../AGENTS.md) for repository rules. Python 3.12+ runs in the project-local `.conda` prefix. The frontend has no build dependencies; JS tests need a Node.js installation supporting `node --test`.

## Installation and startup

For first-time setup, open **Anaconda Prompt / Miniconda Prompt**, change to the Qprint root folder, and run:

```text
conda init powershell
conda env create -p .\.conda -f environment.yml
```

`environment.yml` installs Python 3.12+, Qprint, and development dependencies. After setup, open PowerShell or your agent in the Qprint root and run:

```powershell
.\.conda\python.exe -m qprint serve --workspace examples/demo --port 8765
```

Alternatively, run `.\start.ps1`. Open <http://127.0.0.1:8765>; the server listens locally by default. The script uses the project's `.conda` and reports the setup command if it is missing.

Agents do not run `conda activate`; Conda need not be on PATH and PowerShell profiles need not load. When Conda is available, `conda run -p .\.conda python -m qprint agent state` is equivalent. Commands and paths are relative to the Qprint root. Recreate `.conda` after relocating an installation rather than copying the old environment.

To reproduce the recorded dependency versions:

```powershell
.\.conda\python.exe -m pip install -r requirements-lock.txt
.\.conda\python.exe -m pip install -e . --no-deps
```

## CLI

`toolchain list|install|remove [artifact-id] [--home PATH]` manages local artifacts; installation accepts `--archive ZIP`. `verify`/`serve` add `--toolchain-home` and explicit `--allow-system-toolchains`. Startup script equivalents are `-ToolchainHome`, `-AllowVerification`, and `-AllowSystemToolchains`. Releases without the navigation demo default to `examples/verification`. Installation and `scripts/build-release.ps1 [-Full]` are documented under [toolchains](toolchains.en.md).

`verify --workspace PATH [--node ID] [--language LANG] [--timeout SECONDS]` explicitly runs installed toolchains and exits 0 only when all selected checks pass. `serve --allow-verification` enables the background API for trusted workspaces. See [formal verification](formal-verification.en.md) for configuration and result boundaries. `test_verification.py` covers adapters, the runner, and API; real toolchain checks skip explicitly when tools are missing.

| Command | Arguments and behavior |
| --- | --- |
| `serve` | `--workspace PATH`, `--port 8765`; requires an existing workspace and binds 127.0.0.1 |
| `check` | `--workspace PATH`; prints JSON diagnostics, exits 1 for errors and 0 otherwise |
| `import-code URL` | Required `--language`, `--dest`; optional `--ref`, `--workspace` |
| `import-paper ID` | Required `--dest`, `--name`; optional `--workspace` |

Use the prefix `.\.conda\python.exe -m qprint`. The default workspace is `examples/demo` relative to the current directory. Imports synchronously print JSON or errors; `serve` runs continuously. Installation also provides a `qprint` entry point, but repository examples consistently use module invocation.

## Automated checks

```powershell
.\.conda\python.exe -m pytest -q
node --test tests/graph_view.test.mjs
node --check qprint/static/app.js
node --check qprint/static/graph.js
.\.conda\python.exe -m qprint check --workspace examples/demo
```

| File | Main coverage |
| --- | --- |
| `test_blueprint.py` | Nodes, metadata, links, ambiguity, diagnostics |
| `test_tex_formal.py` | Anchors, rendering fallbacks, lookup in three languages |
| `test_workspace_api.py` | Saves, conflicts, APIs, paths, local request protections |
| `test_importers.py` | Download formats, limits, archives, publication failures |
| `test_graph_index.py` | Project ownership, reference extraction, aggregation |
| `graph_view.test.mjs` | Frontend scope, projections, both drill-down states |

If Windows restricts the system temporary directory, use a **test-only** directory inside the workspace:

```powershell
New-Item -ItemType Directory .qprint -Force
.\.conda\python.exe -m pytest -q --basetemp .qprint/test-local
```

pytest cleans `--basetemp`; never point it at user material. Run relevant regressions for parser/business changes. Layout and interaction changes require browser checks, not merely JS syntax validation. Historical results are in [verification](verification.en.md); their counts are not results from a new run.

## Assets and network tools

KaTeX `0.16.22` JS, CSS, fonts, LICENSE, and provenance live in `qprint/static/vendor/katex/` and ship as Python package data. Read [vendor_assets.py](../tools/vendor_assets.py) before refreshing assets. It downloads the pinned version and verifies npm SHA-512 integrity:

```powershell
.\.conda\python.exe tools/vendor_assets.py
```

[smoke_imports.py](../tools/smoke_imports.py) downloads public examples into `.qprint/network-smoke-*` and records results. It is separate from offline tests and depends on source sites and network availability.

## Troubleshooting and change conventions

- No nodes: check `--workspace`, `blueprint/`, and level-one headings, then run `check`.
- External edits are missing: refresh; there is no file watcher.
- Save returns 409: reload and merge manually. For 403, refresh the token and keep requests on the same origin.
- TeX only shows source: inspect warnings and [rendering limits](tex-rendering.en.md).
- Code lookup fails: provide the actual file and line range; see [formal code](formal-code.en.md).
- Imports fail: inspect job errors and [import limits](importers.en.md); failed jobs are not completed material.

Update the specification, module documentation, and both languages with functional changes. Track unfinished capabilities in TODO. Acceptance records should state dates, commands, results, samples, and untested scope. Documentation updates must not claim business tests that were not run.
