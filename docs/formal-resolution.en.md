# Native project resolution and version repair

Qprint prefers ecosystem configuration. Reading does not compile or acquire environments. GitHub imports verify after download by default, with an opt-out. Explicit verification acquires supported missing exact versions; `--offline` disables acquisition. Coq execution and `_CoqProject`/opam/dune resolution remain unsupported.

## Responsibilities

| Module | Responsibility |
| --- | --- |
| `formal_workspace.py` | Workspace discovery and project boundaries |
| `formal_projects.py` | Native configuration, metadata, lock/recipe and README evidence; no processes or downloads |
| `formal_artifacts.py` | Official release discovery and immutable package acquisition |
| `toolchains.py` | Hash/archive validation, atomic installation, receipts and inventory |
| `formal_environment.py` | Requirements and inventory into an isolated execution context |
| `formal_sources.py` | Source suffixes and module names shared by project and declaration checks |
| `formal_adapters.py` | Language-specific build and declaration probes |
| `formal_runner.py` | Subprocesses, timeout, process-tree termination and bounded output |
| `formal_reports.py` | Timestamped evidence and agent handoff information |
| `formal_service.py` | Native entries, individual file checks and explicit safe audit |
| `verification.py` | Blueprint binding orchestration with compatible public imports |

## Resolution

Lean requires an exact `lean-toolchain`; missing files and floating stable/nightly pins produce an error report. `lake-manifest.json` is read and retained as native dependency information used by Lake. No duplicate Lean version is put into YAML.

Agda uses `.agda-lib` for includes, dependencies and scoped options. Missing compiler and package pins are filled in this order:

1. `.qprint-formal.yaml`, with legacy `project.yaml` compatibility.
2. `.qprint-formal.lock.yaml`, then `.qprint-formal.recipe.yaml`.
3. A unique explicit Agda version and full Cubical commit from README.

Lower-priority evidence only fills gaps. Missing or ambiguous evidence fails instead of guessing. README content is data, never executable instructions. Successful resolution creates `.qprint-formal.yaml` with provenance if absent; existing metadata is preserved.

```yaml
toolchain:
  agda: "2.8.0"
dependencies:
  cubical:
    revision: d0b9c7b0e9e4f816422c3447d7983b03274dd829
policy:
  safe: inherit
  mode: cubical
```

Lock/recipe files share this schema. Each dependency supplies one full 40-character `revision` or exact `version`; `provenance` records evidence. Native cubical/erased-cubical options take precedence. Options stay scoped to native library modules, avoiding a global `--cubical` flag on Agda primitives.

## Commands

```powershell
.\.conda\python.exe -m qprint formal resolve --project PROJECT --language agda
.\.conda\python.exe -m qprint formal verify --project PROJECT --language agda --timeout 600
.\.conda\python.exe -m qprint formal verify --project PROJECT --language agda --entry Summary.agda --offline
```

CLI and post-download verification default to `--entry-strategy auto`: native Lake default targets, or the first unique Agda source-root entry named `AllModulesIndex`, `Everything`, `index`, `Index`, or `Main`. Without an Agda entry, all files are checked individually. Use `--entry-strategy all` for explicit all-file checking; the Python service retains its `all` default for compatibility. Supported suffixes are `.agda`, `.lagda`, `.lagda.tex`, `.lagda.md`, `.lagda.rst`, `.lagda.org`, `.lagda.typ`, and `.lean`. The complete literate suffix is removed when deriving module names: `Compact.lagda.md` imports `Compact`, not `Compact.lagda`. See [Agda literate formats](https://agda.readthedocs.io/en/v2.8.0/tools/literate-programming.html).

Repeat `--entry` for project-relative files; `--declaration` requires one entry. Agda directly checks entries, preserving source and library OPTIONS. Default `safe: inherit` adds no safe flag and retains native warning policy. Declaration probes still promote missing-name warnings to errors. `require` adds `--safe --ignore-all-interfaces` and never downgrades after failure. `off` also preserves any source-level `--safe`. Legacy `true/false` map to `require/off`. Run `formal audit --project PROJECT --language agda` for an explicit required safe audit. Reports identify actual scope; native default targets do not establish every repository file passed. Preparation and checking each default to 600 seconds (maximum 3600); individual Agda entries share the checking budget. Blueprint commands still select bindings.

Low-level `ToolchainResolver` defaults to acquisition disabled. CLI/verification services opt into `auto_install=True`. Network failure, unsupported platform, missing exact assets or invalid release metadata are reported, not replaced with a different version.

## Installation

Existing exact installations are reused. Known missing artifacts use the installer. Automatic compiler discovery currently supports Windows x64 Lean/Agda releases with exact asset names, preferring SHA-256 digests supplied by GitHub's release API; older assets use the explicitly recorded first-use policy below. Cubical source archives use a fixed full commit from official `agda/cubical`; the first HTTPS archive hash is recorded for subsequent consistency checks, not presented as an independent publisher signature. Other libraries require supported catalog entries; recipes do not execute arbitrary scripts.

Stores remain `toolchains/<language>/<version>/` and `packages/agda/cubical/<commit>/`. Dynamic artifact entries are persisted at `toolchains/.qprint-catalog.json` without overriding bundled entries. These stores are ignored by Git. Parent PATH, Conda and global Agda library settings are unchanged.

References: [Agda library management](https://agda.readthedocs.io/en/v2.8.0/tools/package-system.html), [GitHub release asset digests](https://docs.github.com/en/rest/releases/assets).

## Reports and the helper skill

Independent project commands save JSON/Markdown at `.qprint/reports/<UTC timestamp>-<unique ID>`. Failed Blueprint bindings also persist reports. Evidence includes request arguments, environment, pins and provenance, selected source hashes, stages, commands, exit codes, output tails and truncation flags. Process environment variables are excluded. Reports separate `outcomes.typecheck` from `outcomes.safe_audit`; failed required audits leave native checking `unknown`. `preparation` records events and `ready/recovered/failed`, distinguishing recovery from first-pass success. Source or existing configuration changes produce `stale`; a lock first generated by Lake is recorded separately. Missing modules are a suspected dependency problem, not proof of a version mismatch. Timeouts and access errors are distinct diagnostics.

Qprint does not embed or automatically start an AI service. A user/host can hand the error report and project to a fresh agent using [formalization-version-helper](../skills/formalization-version-helper/SKILL.md). It may repair version configuration and managed stores, preserving proof sources and safety policy, then run `retry.py` to resolve and verify again. New reports retain the earlier evidence.


## Automatic preparation and non-version recovery

`formal_policy.py` defines policy/outcomes; `formal_agda.py` constructs native commands and declaration probes. `formal_downloads.py` provides bounded HTTPS retries, ETag-validated resume and SHA-256 checks. `formal_archives.py` validates preparation archives. `formal_git.py` acquires exact GitHub commits from the native Lake lock, records receipts, and uses Lake path overrides without rewriting the lock. Existing unmanaged checkouts are preserved. Internal source-document aliases can be materialized as regular files; compiler installers and the public importer retain their stricter link rejection.

`formal_preparation.py` prepares native mathlib caches, retries stalled downloads, repairs at most 64 missing/corrupt objects per recovery step and supports verified ProofWidgets release extraction on Windows. Native cache tooling still validates downloaded cache objects. Exact upstream tags/commit IDs and official release digests are checked; recovery never fabricates commits, disables hashes or changes proof OPTIONS. Automatic compiler discovery remains Windows x64; unsupported dependency sources/build failures are reported. Preparation state lives under the project's `.qprint/preparation` and `.lake`; compiler/library stores remain under Qprint home. No global Git configuration is changed.

`formal_import.py` discovers projects and invokes the same verification service after import. Transport, preparation, verification and UI orchestration have separate modules. See [import switches](importers.en.md).

For unresolved non-version failures, [formalization-runtime-helper](../skills/formalization-runtime-helper/SKILL.md) exposes only Python `inspect` and `recover` operations through `formal_recovery.py`. Supply a fresh agent only the skill, report path, project root and toolchain home. Inspection returns a bounded summary, without proof text or conversation history. Recovery preserves source selection, pins, safe policy and offline settings; changed inputs, policy conflicts and proof errors stop recovery. A case permits at most three replays. Version issues route to the existing version helper. Qprint does not automatically launch an LLM. The scripts limit operations but are not an OS sandbox; the host must enforce actual tool/filesystem restrictions.


## Native release strategy and live progress

ProofWidgets enters legacy cloud-release preparation only when the pinned source's `lakefile.lean` declares `preferReleaseBuild := true`; exact tags, commits and release digests remain validated there. Newer configurations without that strategy use native sources/mathlib caches without demanding a nonexistent release tag or modifying the upstream lock. See the [sphere-eversion experiment](sphere-eversion-experiment.en.md).

`formal_progress.py` uses request-local context and throttled callbacks across import, compiler installation, dependency preparation and checking, separate from persisted reports. Subprocess output remains file-spooled; progress reports byte counts without concurrently reading the shared log pointer. Observation preserves timeout/process-tree termination behavior, and presentation callback failures do not interrupt checking.


## Legacy compiler releases and Lake

Old official Lean/Agda assets can lack GitHub's `digest`. Discovery still requires one exact filename, the official HTTPS URL, positive asset ID and size. The first complete acquisition checks size, pins its computed SHA-256 in the local catalog and installs against that hash. `integrity: official-release-https-first-use-sha256` explicitly identifies first-use trust in official HTTPS, not a publisher signature/digest. Later installations retain the pinned hash rather than accepting changed bytes. Official digests remain preferred; malformed digests never fall back. Preparation events and installation receipts record identity, size and integrity type.

`formal_legacy_lake.py` detects package-override support in the installed Lake. Older versions acquire real Git metadata for managed dependencies via shallow fetch of the exact locked commit and check FETCH_HEAD, without checkout/reset or rewriting native locks. Release tags are published locally only after their peeled commit matches the lock. Legacy quoted names such as `«doc-gen4»` are supported while retaining path validation. Old mathlib's `XDG_CACHE_HOME/mathlib` is scoped to the project's `.qprint/preparation/legacy-cache` in child processes; parent/global configuration stays unchanged.

Lightweight tags confirmed by the official API to point directly to the lock reuse the existing real commit object. Annotated tags are fetched and their peeled commits checked. Transient Git fetch failures receive at most three attempts within the original preparation deadline; missing repositories and mismatching commits are not retried.

`formal_release_assets.py` applies the same official-source/first-use hash policy to old auxiliary assets (ProofWidgets and upstream-pinned leantar), retaining separate receipts and reusing checked archives through Qprint's network retry path. Available publisher digests are verified; absent digests explicitly retain first-use HTTPS provenance. Later identity/hash changes are rejected. Old Lake uses native `BuildTrace`, newer Lake uses `BuildMetadata`, recording only acquired release dependencies rather than fabricating proof-build success.
