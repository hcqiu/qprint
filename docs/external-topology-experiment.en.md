# External topology experiment (2026-09-21)

[中文](external-topology-experiment.md) | [English](external-topology-experiment.en.md)

Two new public projects were downloaded at fixed commits and tested on Windows x64 using Conda `qprint`. Projects and evidence live under the ignored `.qprint/external-topology/` directory. `downloads.json` records official archive URLs, commits, download times and SHA-256 hashes; `source-audit.json` compares source files directly against the downloaded archives.

| Language | Upstream | Commit | Compiler |
| --- | --- | --- | --- |
| Lean | [CounterExamplesInTopology](https://github.com/dleijnse/CounterExamplesInTopology) | `f7710027fa73fa2c16fa08929037d8c96283c564` | `4.26.0-rc2` |
| Agda | [TypeTopology](https://github.com/martinescardo/TypeTopology) | `19b7895d644def0dbbced98a097f7e4e3a46f633` | `2.8.0` |

## Agda results

Initial resolution returned `missing_version`. A fresh subagent used the [version helper skill](../skills/formalization-version-helper/SKILL.md), locating explicit released Agda 2.8.0 evidence in the pinned `Makefile:11`, `source/AllModulesIndex.lagda:13`, and `source/index.lagda:14`. Its only configuration edit was `.qprint-formal.yaml` with the version and provenance; the compiler was already installed.

Retrying the original whole-project request selected 995 files under `source/` and **failed**, exit code 42: `--safe` rejects `--rewriting` in `AllModulesIndex.lagda:31`. Upstream deliberately provides separate safe and unsafe entry points. This is not a version mismatch, so the helper stopped without weakening policy.

A separate check of upstream's safe topology entry, `source/TypeTopology/index.lagda`, **passed** with its transitive dependencies in **112.656 seconds**, retaining `--safe`, `--warning=error`, and `--ignore-all-interfaces`. This does not claim that all repository modules pass safe checking. All 996 proof source files, including one outside `source/`, match the downloaded archive.

Evidence under `agda/.qprint/reports/`:

- Missing version: `20260921T112547.878085Z-3045a5d6.json`.
- Helper resolution: `20260921T113331.828808Z-2b853776.json`.
- Whole-project safe failure: `20260921T113335.954315Z-e358c8f2.json`.
- Safe topology entry pass: `20260921T113631.098568Z-c0a66f28.json`.
- Configuration and source audit: `typetopology-version-helper-audit.json`.

```powershell
conda run -n qprint python -m qprint formal verify --project .qprint/external-topology/agda --language agda --entry source/TypeTopology/index.lagda --timeout 600 --offline
```

## Lean results and preparation

All **five project sources compiled successfully**, exit code 0, in **26.250 seconds** after cache preparation. Report: `lean/.qprint/reports/20260921T120936.371315Z-02f4ec47.json`. Every module was explicitly selected, including `DiscreteTopology`, which the root module does not import.

Upstream linter warnings remain in `DiscreteTopology.lean`: unused section variables, long lines, spacing and flexible tactics. In particular, `discr_top_finest` does not use the discrete-topology assumption; successful compilation does not establish that its statement matches the author's intention. No third-party theorems were changed. Lean retained upstream warning policy, did not promote all warnings to errors, and did not run an axiom audit.

No Lean version helper was used. `lean-toolchain` supplies the exact compiler version, and the native `lake-manifest.json` pins mathlib to `790901a8c97c730ae7af9bd44fe60c733a21d9ba`. Qprint automatically discovered, downloaded and verified the official Windows compiler archive with SHA-256 `f142276ea81a3761624d6218bb792714789e3349a462a02a007b77ea0106c153`.

Git transport repeatedly failed on this machine. The initial native verification report, `lean/.qprint/reports/20260921T114339.593559Z-5a2c43d8.json`, records exit code 1 and underlying Git exit code 128. The same nine locked commits were then downloaded from official codeload URLs, recorded in `lean-dependencies/downloads.json`, and selected through Lake's native `.lake/package-overrides.json` using the standard `.lake/packages/` layout. The original `lean-toolchain`, `lakefile.toml`, `lake-manifest.json`, and five project sources remain unchanged.

This was an experimental network fallback, not an implemented automatic Qprint fallback for Lake dependencies. Batteries' internal documentation alias `docs/README.md → ../README.md` was materialized as identical documentation text; no Lean sources changed.

Mathlib's official `lake exe cache get` also needs the ProofWidgets release tag. GitHub API data restored its authentic signed commit object only after its computed Git SHA matched the locked `2aaad968dd10a168b644b6a5afd4b92496af4710`; upstream tag `v0.0.82` was verified to point to that commit. This is metadata for release lookup, not a complete Git checkout. Windows `tar` output then triggered a non-UTF-8 decoding error in Lake. The release archive was checked against official SHA-256 `bc998b1516f8527b8dc29116972bfe55d1382e0025d3b96872cbd8704d175614` and completely extracted. Preparation scripts and caches remain in the experiment directory; global Git and PATH settings were not changed.

Three initial cache connections stalled, and decompression identified one additional corrupt download. After retrying the same official sources, the cache tool successfully unpacked all **7,740 entries**. Final cache evidence is `lean-cache-20260921T120817Z.json`, without truncation or corruption messages; earlier failures and the long initial log remain available. Initial environment preparation took substantially longer than the final 26-second project build.

Reproduce after preparation:

```powershell
conda run -n qprint python -m qprint formal verify --project .qprint/external-topology/lean --language lean --timeout 600 --offline
```

The local `verify_lean.ps1` additionally sets process-local Git ownership trust for the test directory and a local cache path, accommodating ownership differences between the sandbox and user accounts.

This sample's native pins were sufficient: **no version helper was needed to infer or change Lean versions**. Download transport, package layout and Windows tool behavior still required work. These experimental network fallbacks are not yet product features, so this was not an unattended one-command success.

## Module changes exposed by the experiment

TypeTopology exposed missing literate Agda support. `formal_sources.py` now centralizes Lean, Agda and literate Agda suffixes and module names for source discovery, explicit entries, Blueprint file inference and declaration probes. See [project resolution](formal-resolution.en.md). The helper did not edit Qprint implementation.

Regression result: **144 passed, no skips**, with two existing dependency deprecation warnings from FastAPI/Starlette. The real bundled-example test checks only its required artifacts, so an unrelated extra compiler being downloaded or inaccessible under another execution account no longer skips that test.


## Automation follow-up (2026-09-22; historical results above retained)

With the new default `safe: inherit`, the same TypeTopology commit and Agda 2.8.0 passed native `source/AllModulesIndex.lagda`, which upstream describes as recursively importing all modules. No additional safe audit ran. Report: `.qprint/external-topology/agda/.qprint/reports/20260921T155821.155101Z-298459e7.json`. The earlier forced-safe failure remains a valid experiment under a different policy.

Real Agda boundary cases also behaved correctly: rewriting/postulates pass native checking, explicit require fails with native checking unknown, and off still preserves a source-level safe pragma. Small-case reports are under `.qprint/automation-experiment/agda/.qprint/reports/`.

A fresh GitHub import of the same CounterExamplesInTopology commit kept post-download verification enabled and automatically acquired all nine locked dependency sources. It reused 7740 previously acquired official mathlib cache objects, so this was not a cold-cache performance test. The first run exposed missing native release receipts after Windows ProofWidgets acquisition failure; report `20260921T155504.923390Z-a613d84e.json` is retained. After fixing preparation, native Lake recorded acquisition of the verified release and `--no-build` confirmed reuse. A fresh agent then used only the runtime helper inspect/recover operations on the original report; the first replay passed native Lake default targets. Final report: `.qprint/automation-download/lean/topology/.qprint/reports/20260921T160633.874691Z-27957600.json`.

A separate small-case helper test also passed real Lean checking. No version helper changed Lean pins; the runtime helper handled preparation failures. Configuration/source hashes remained unchanged. Archive comparisons confirmed unchanged fresh Lean sources/native configuration and all original 5 Lean / 996 Agda sources. UI checks confirmed default-on, opt-out and hiding the option for paper imports. See [acceptance](verification.en.md) and [module contracts](formal-resolution.en.md). Success is not an axiom audit or a guarantee of universal upstream compatibility.
