# Serre finiteness: verification and version repair experiment

> Command examples now use the project-local `.conda` convention. Historical results and timings are unchanged; this command migration does not imply those experiments were rerun.

Executed on 2026-09-21, Windows x64, Conda `qprint`, Agda 2.8.0. The isolated project at `.qprint/formal-experiment/serre-finiteness` contains 35 Agda files whose hashes match the original demo project. Original proof sources were preserved.

Native `.agda-lib` and README evidence produced `.qprint-formal.yaml`, selecting Agda 2.8.0 and Cubical commit `d0b9c7b0e9e4f816422c3447d7983b03274dd829`. The artifact provider registered a matching existing installation without downloading again.

An initial receipt access error generated a report. A fresh agent (`fork_turns=none`) applied the [helper skill](../skills/formalization-version-helper/SKILL.md), found matching versions, preserved configuration and retried successfully: all 35 modules passed. The access error did not recur; its cause remains undetermined.

For the negative control, only the experimental copy's Cubical pin was changed to release `0.9`. Aggregate verification failed after 71.265 seconds, exit 42, at `FiberOrCofiberSequences/Base.agda:148`: `[NoParseForLHS]` for `Iso.sec (IsoFiberSeqs A B C) F`.

A second fresh agent received only this failure report, project, store paths and skill. It independently compared README and both library interfaces: 0.9 uses `rightInv/leftInv`, whereas the required commit uses `sec/ret`. Its only repair was:

```diff
-    version: "0.9"
+    revision: d0b9c7b0e9e4f816422c3447d7983b03274dd829
```

The skill's `retry.py` resolved and verified again: **35 modules passed**, exit **0**, **221.359 seconds**, with safe mode, warnings as errors and full interface rechecking retained. Hashes match across the failure report, pre/post-repair snapshots and success report. The control error was intentionally introduced, not a newly discovered proof defect.

Evidence under the experimental project's `.qprint/reports/`:

| Evidence | File |
| --- | --- |
| Access error | `20260921T101211.715022Z-57983a0b.json` |
| First agent's success | `20260921T101906.287166Z-8e4ecab4.json` |
| Negative control | `20260921T102130.850626Z-014a62bb.json` |
| Repaired resolution | `20260921T102628.976657Z-ab5acfea.json` |
| Repaired verification | `20260921T103010.351934Z-53c42647.json` |
| Configuration diff, interface evidence and hashes | `version-helper-control-evidence.json` |

Reports are gitignored historical evidence; output tails are capped at 32 KiB with truncation flags. Reproduce with:

```powershell
.\.conda\python.exe -m qprint formal verify --project .qprint/formal-experiment/serre-finiteness --language agda --timeout 600 --offline
```

Final regression: **136 passed, 2 existing dependency deprecation warnings, no skips, 6.93 seconds**, using `.qprint/tests-formal-modular-final`. Skill validation passed; both agents exercised the helper script. Related documentation had 126 valid local links. Acquisition, hashes, official asset validation and offline behavior have automated tests; this live experiment reused installations. Historical Release ZIPs were not rebuilt. See [project resolution](formal-resolution.en.md) for supported boundaries.
