# Unified formal verification adapters

[中文](formal-verification.md) | [English](formal-verification.en.md) · [Documentation](index.en.md)

Implementation: [verification.py](../qprint/verification.py). Tests: [test_verification.py](../tests/test_verification.py). This module invokes installed toolchains; [formal.py](../qprint/formal.py) continues to provide source navigation. Reading, refreshing and saving never trigger verification; GitHub imports have a default-on verification switch. Node `status`, graph colors, and completion counts remain author-assigned progress.

See [modular project resolution](formal-resolution.en.md) for all-module project checks, native requirements, automatic acquisition and version repair. Explicit verification can acquire missing supported versions; CLI `--offline` disables downloads. Language adapters live in `formal_adapters.py`.

## What is checked

| Adapter | First stage | Declaration stage | Meaning of success |
| --- | --- | --- | --- |
| Lean 4 / Lake | `lake build +Module` builds the bound module and dependencies explicitly | A temporary file imports `Lean` and the target module, then queries the exact name through `Lean.getEnv` / `contains`, using `lake env lean` | The build succeeds and the declaration exists in the imported environment |
| Agda | Agda checks the bound file using upstream OPTIONS; default `safe: inherit` adds no safety policy | A temporary module imports the target and resolves an exported name through `open Scope using (name)`; enabled warnings are errors | The file typechecks and the exported name resolves |
| Coq | Not implemented | Not implemented | Returns `unsupported`, even when source navigation succeeds |

Explicit line ranges cannot substitute for declaration checks. A Lean declaration may come from an imported dependency; existence does not establish that it was defined in the bound file. Lean axiom, `sorry`, and unsafe dependency auditing is not implemented. Agda defaults to native checking with upstream OPTIONS preserved. Use `safe: require` or `formal audit` for an explicit safe audit. `off` also preserves source-level `--safe`. Neither adapter establishes that the formal statement matches the Markdown/TeX prose.

Agda performs typechecking, without generating Haskell/JavaScript executables. The initial probe supports exported names, qualified submodule names, and ordinary mixfix names. Parameterized top-level modules, modules requiring instantiation, and special syntax may fail. Lean accepts ordinary dotted identifiers, not expressions or `«escaped names»`. Private Agda declarations cannot be reached through the public import probe.

## Configuration

[Toolchain resolution](toolchains.en.md) precedes execution. Lean requires `lean-toolchain`; Agda requires project-local `project.yaml`. Adapters receive a resolved `FormalExecutionContext`, and reports add `environment`. Agda mode configures probe module options; source retains native OPTIONS/.agda-lib settings, with isolated library registries.

Without configuration, language subprojects are discovered through lean-toolchain/project.yaml. With no declarations, language directories remain candidates but execution reports missing versions. Lean requires a `lakefile.lean` or `lakefile.toml`. The navigation demo is not a complete Lake project.

For multiple imported repositories or custom source layouts, create `qprint-verification.json` at the **workspace root**:

```json
{
  "version": 1,
  "projects": [
    {"language": "lean", "root": "my-lean-repo", "source_root": "."},
    {
      "language": "agda",
      "root": "my-agda-repo",
      "source_root": "src",
      "include_paths": ["vendor/library"],
      "safe": "inherit",
      "mode": "cubical"
    }
  ]
}
```

| Field | Contract |
| --- | --- |
| `version` | Integer `1` |
| `projects` | Array replacing default inference entirely; may be empty |
| `language` | `lean` or `agda` |
| `root` | Relative to the language directory; default `.` |
| `source_root` | Relative to the project root; default `.`; must match the module root, such as Lake's `srcDir` |
| `include_paths` | Agda only; directories inside the project, default empty; the source root is always included |
| `safe` | Agda only; `inherit` (default), `require`, `off`; legacy `true/false` map to `require/off` |
| `mode` | Agda probe module options: `standard` (default), `cubical`, or `erased-cubical`; source retains native OPTIONS/.agda-lib |

Directories must exist and remain inside their designated roots after resolving symlinks. Absolute paths, traversal, Windows special paths, and arbitrary command configuration are rejected. See [managed toolchains](toolchains.en.md) for explicit installation and exact resolution. Lean retains native Lake dependencies; Agda uses declared packages and a temporary registry; toolchains themselves may download dependencies, create build files, and execute macros or project configuration code.

Binding syntax is unchanged. For example, `file: my-agda-repo/src/Topology/Maps.agda` is still relative to `agda/`, and `source_root` yields the module `Topology.Maps`. Verification resolves files independently of heuristic source slicing and ignores `lines`. Without `file`, dotted declaration names supply candidate file paths. The deepest matching source root wins; duplicate source roots for a language are rejected. Invalid global configuration fails the request.

## CLI

```powershell
.\.conda\python.exe -m qprint verify --workspace my-math
.\.conda\python.exe -m qprint verify --workspace my-math --language lean
.\.conda\python.exe -m qprint verify --workspace my-math --node "Topology/Notes#My theorem" --timeout 180
```

Combine `--node` and `--language` as needed. JSON goes to stdout. Exit `0` requires every selected binding to pass and no index errors. Failed checks, missing tools, unsupported adapters, empty selections, and errors exit `1`. Request-level errors, including invalid configuration and unknown nodes, go to stderr. `check` still checks indexes only. Timeout is 1–3600 seconds, default 120, **per toolchain stage**, not per batch.

## API

CLI JSON escapes non-ASCII characters as `\u...` to survive Windows/Conda capture encoding differences. JSON decoding restores original names and diagnostics.

HTTP execution is disabled by default because verification executes toolchain code from the workspace. Enable it for a trusted workspace:

```powershell
.\.conda\python.exe -m qprint serve --workspace my-math --allow-verification
```

`GET /api/project` includes `verification_enabled`. Submit explicitly with the same-origin write token:

```javascript
const project = await fetch('/api/project').then(r => r.json());
const response = await fetch('/api/verify', {
  method: 'POST',
  headers: {'Content-Type': 'application/json', 'x-qprint-token': project.token},
  body: JSON.stringify({node_id: 'Topology/Notes#My theorem', language: 'lean', timeout: 120})
});
const job = await response.json();
if (!response.ok) throw new Error(JSON.stringify(job.detail));
// Poll until status is no longer queued/running.
const progress = await fetch('/api/jobs/' + job.id).then(r => r.json());
```

Omitted or null `node_id`/`language` selects all nodes/languages. HTTP 202 means queued; 403 means execution is disabled or credentials are invalid; 404 means unknown node; 422 means invalid parameters; 429 means a full verification queue. An independent single worker accepts up to five queued/running jobs and runs outside the workspace lock. Bindings and index diagnostics are captured at submission; configuration and source are read during execution. Imports keep their separate queue.

Jobs have `kind: verification` and transition `queued → running → succeeded | failed`. Job success means a report was produced: inspect `result.status` to determine whether checks passed. Exceptions preventing report generation, such as invalid configuration, fail the job. Records live in memory and disappear on restart; there is no cancellation endpoint. The existing browser code panel remains source navigation; this extension adds no verification button or automatic historical-result display.

## Results and lifecycle

Reports contain `schema_version: 1`, UTC `checked_at` (completion time), overall `status`, and `results`. CLI/API also attach index `diagnostics`. Overall status is `passed`, `incomplete`, or `not_run` for an empty selection; index errors force `incomplete`.

Each result contains the original `binding` (with `node_id` from CLI/API), workspace-relative `project`, `policy`, `source_sha256`, `status`, `message`, and `checks`. Each check includes `stage`, `status`, a `command` argument array, `returncode`, combined stdout/stderr `output`, `truncated`, and `duration_ms`. Missing tools and timeouts may have no return code.

Binding/stage states are `passed`, `failed` (nonzero tool exit), `unavailable` (missing executable), `timeout`, `error` (input/path/environment), `unsupported`, `stale` (bound source changed during verification), and `not_run`. A failed first stage prevents the declaration probe; unexecuted stages are omitted. Logs return only their final 32 KiB of bytes, decoded as UTF-8 with replacement; truncation is explicit.

Reports are historical evidence, not live status or reusable success caches. Binding failures persist timestamped reports; independent project commands save every resolve/verify result. See [project resolution and version repair](formal-resolution.en.md). Each request executes again. Binding hashes cover the bound file; project reports hash every selected file. Neither fully detects changes in external dependencies, configuration or toolchains. Rerun after edits and never update author progress from an old report.

The runner uses no shell, closes stdin, hides Windows windows, attempts process-tree termination on timeout, and cleans temporary probes on normal exit. Disk logs and compiler artifacts have no total quota. This layer is not an operating-system sandbox for hostile projects; execute explicitly on trusted workspaces.

## Extension and tests

Implement `VerificationAdapter.verify(context, source, declaration, runner, timeout)` and register it in `ADAPTERS`, returning unified `Check` stages. Extend project/language validation, path rules, and tests together. The injectable `Runner` enables deterministic command and failure tests without installed compilers. Real Lake/Agda tests run automatically when the tools are available and otherwise skip explicitly.

Implementation references: [Lake documentation](https://lean-lang.org/doc/reference/latest/Build-Tools-and-Distribution/Lake/), [Agda command-line options](https://agda.readthedocs.io/en/latest/tools/command-line-options.html), and [Agda modules](https://agda.readthedocs.io/en/latest/language/module-system.html). Executed local checks and limitations are recorded in [acceptance history](verification.en.md).
