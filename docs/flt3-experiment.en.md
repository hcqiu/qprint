# FLT3 verification and missing report investigation

[中文](flt3-experiment.md) | [English](flt3-experiment.en.md) · [Documentation](index.en.md)

On 2026-09-22 the production `import_code` downloader reproduced [pitmonticone/FLT3](https://github.com/pitmonticone/FLT3) at the user's commit `a199fa0467f86504a9d2f6164b0456608e586821`, source ZIP SHA-256 `3dc3258df0a95c9f24961932cca0b970c8e94d136586520faee0fba40ba1af76`. The separate reproduction is `.qprint/flt3-repro/lean/FLT3`.

## Report visibility

The original report existed at `examples/demo/lean/Topology/FLT3/.qprint/reports/20260921T175633.467479Z-e1cb9e0c.json`. Its path was buried in raw JSON with no report link, and in-memory jobs disappear on restart. Separately, the importer's outer exception handler returned empty reports without saving evidence.

The UI now shows per-project errors, readable report links, JSON downloads and persistent workspace report history. The API accepts only workspace-contained timestamped reports. Unexpected per-project exceptions produce reports without discarding other results; storage failures explicitly expose `report_error`.

## General compatibility fixes

- Official Lean `4.7.0-rc2` ZIP metadata has `digest: null`. Discovery now pins the official URL, asset ID `155141827`, size `249401814` and first-acquisition SHA-256 `f6ed14925e4edab147add6010690963e9440ca86b85bdaf3b4fb50bfb3a13fef`. Later acquisitions still check that hash. Receipts/reports label `official-release-https-first-use-sha256`, without claiming a publisher digest/signature.
- Legacy quoted package names such as `«doc-gen4»` map to native directory names, retaining path validation.
- Lake 4.7 lacks package overrides. `formal_legacy_lake.py` acquires real Git metadata for exact locked commits and verifies FETCH_HEAD without checkout/reset or lock changes. Release tags must peel to the locked commit.
- Old mathlib reads `XDG_CACHE_HOME/mathlib` rather than `MATHLIB_CACHE_DIR`; child processes now use the project's `.qprint/preparation/legacy-cache`.

## Results

Initial reproduction took about 1.9 seconds and wrote `20260921T180357.081218Z-b5ec532e.json`. Compiler installation took about 255 seconds; the next package-name error wrote `20260921T180956.130006Z-f973602a.json`.

After repair, fixed dependency preparation took about 50 seconds, mathlib cache preparation 263 seconds and `lake build` 117 seconds. Report `20260921T181949.001180Z-ced1e87f.json` records `outcomes.typecheck: passed` for native default targets, without an additional safety audit. The early cache probe revealed the old global-cache behavior. Final verification copies 4356 existing hash-named objects into the project cache for native revalidation; the user's cache is preserved. This is not a cold-cache benchmark.

All observed compatibility issues belonged to general preparation. Hash comparison confirmed identical native configuration and all 10 Lean files (including Lake configuration) in the user's original import and test copy. Final native tag acquisition encountered a GitHub connection timeout, reported as `20260921T182154.173860Z-71fc5981.json`. After adding bounded transient Git-fetch retries, a fresh agent was given only the [runtime helper skill](../skills/formalization-runtime-helper/SKILL.md) and case paths to replay `inspect/recover`, with no source-editing scope.

The helper stopped after three attempts. Its last report, `20260921T183157.426455Z-2866838c.json`, exposed native curl connection failures and the same pre-digest restriction for old ProofWidgets assets. The main task then fixed general preparation: `formal_release_assets.py` acquires/pins auxiliary releases, old Lake records verified assets using its native `BuildTrace` API, and upstream-pinned leantar `0.1.11` is version-checked and installed in the project cache. The helper budget was not reset.

Final report `.qprint/flt3-repro/lean/FLT3/.qprint/reports/20260921T183613.297179Z-e802365b.json` records `status: passed`, `typecheck: passed`, `safe_audit: not_run`. Reusing existing caches, preparation and native default-target checking completed in about 13.3 seconds. Source/native-configuration hashes remained unchanged on final comparison.

Browser verification opened the actual failure report from import history and displayed its error/diagnosis. Full Python suite: 216 passed; Node suite: 12 passed, with two existing Python dependency deprecations. The user's server was not restarted; restart it and refresh the page to load the changes.
