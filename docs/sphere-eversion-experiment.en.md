# sphere-eversion import wait investigation

[中文](sphere-eversion-experiment.md) | [English](sphere-eversion-experiment.en.md) · [Documentation](index.en.md)

On 2026-09-22, the production `import_code` downloader reproduced the reported wait for [sphere-eversion](https://github.com/leanprover-community/sphere-eversion), with post-download verification enabled. The user's commit was pinned to `e03dfec32debbef8736185d6778bf3aa2f1d0572`; source archive SHA-256 was `3f411ff4fc71735f4709b8c7b94c60e550690e6cefec628e1ef0e3e7e6db5b44`. The separate reproduction lives at `.qprint/sphere-repro/lean/sphere-eversion`.

## Causes

The project requires Lean `4.34.0-rc2`, initially absent locally. Its official Windows ZIP is 850,663,032 bytes (about 811 MiB). Local records show acquisition starting around 01:14:03, archive completion at 01:21:47, and installation publication at 01:22:15, Beijing time. The UI displayed only a generic environment/verification message throughout installation.

After installation, preparation also failed: upstream pins ProofWidgets commit `a8acbfd87375ff4abe14ce09db5b7664d383bc7f` with `inputRev: main`. Its newer native configuration no longer requests a cloud release, but Qprint unconditionally required an exact release tag. `Release preparation requires an exact upstream tag in the native lock` stopped execution before checking. The user's original error report was `20260921T172249.058690Z-c0aa096e`.

## Fix and results

Preparation now selects the release strategy from pinned native Lake configuration. Newer packages follow source/mathlib cache preparation; legacy packages retain exact tag, commit and artifact digest validation. A request-local progress module exposes download bytes, extraction counts, dependency preparation, cache/build stages and elapsed time in the UI.

| Stage | Observed result |
| --- | --- |
| Separate downloader reproduction | Source download took about 4 seconds; the same tag error reproduced in about 45 seconds, reusing the installed compiler |
| Preparation after fix | Native mathlib cache completed in 257.781 seconds, downloading/decompressing 8893 objects |
| Native default targets | `lake build` passed in 124.032 seconds, completing 2967 build jobs |
| Final report | `status: passed`, `outcomes.typecheck: passed`, `safe_audit: not_run` |

Initial report: `.qprint/sphere-repro/lean/sphere-eversion/.qprint/reports/20260921T172353.595119Z-c1e594fa.json`. Successful report in the same directory: `20260921T173455.861358Z-08ae92e0.json`.

A fresh agent received only the [runtime helper skill](../skills/formalization-runtime-helper/SKILL.md), report, project and toolchain paths. It used Python `inspect` / `recover` and passed on the first replay, with selected sources and configuration unchanged. Scope is native Lake default targets, not an additional safety audit or individual checking of every repository file. Compiler installation and cache measurements came from different runs, not one end-to-end benchmark.

Existing server processes require restart to load the Python fix; refresh the page for new frontend code. Failed imports preserve source and reports, so existing destinations need no second download. Import `timeout: 600` is not an end-to-end ten-minute deadline.
