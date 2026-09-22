# Qprint TODO

[中文](TODO.md) | [English](TODO.en.md) · [Documentation](docs/index.en.md)

Baseline date: 2026-09-20. Checked items are implemented capabilities. Unchecked items are proposed follow-up work without committed delivery dates. Historical validation is recorded in [verification](docs/verification.en.md).

## Implemented baseline

- [x] [Managed toolchains](docs/toolchains.en.md): local Lean/Agda, pinned Cubical, requirements, resolver/context, install/list/remove, light/full ZIPs.

- [x] Multiple Markdown nodes, metadata, relations, diagnostics, and a demo workspace.
- [x] TeX anchor fragments, bounded plasTeX rendering, and local KaTeX.
- [x] Lean / Agda / Coq bindings and source lookup.
- [x] [Unified verification adapters](docs/formal-verification.en.md): Lean / Agda, independent results, CLI, opt-in background API, timeouts, and diagnostics.
- [x] [Native project resolution and version repair](docs/formal-resolution.en.md): modular resolver, exact artifact acquisition, timestamped reports, project checks and an independent helper skill.
- [x] Reading, search, Markdown saves, revision conflicts, and node deep links.
- [x] Three graph granularities, scope selection, project ownership, and two drill-down highlight steps.
- [x] GitHub / arXiv imports, provenance, background jobs, and archive protections.
- [x] Python regression tests, graph state tests, and browser acceptance on the demo.

## Priority: reliability and maintenance

| Status | Work | Acceptance condition |
| --- | --- | --- |
| [ ] | CI and browser regression | Run Python/JS tests automatically; cover save conflicts, deep links, both drill-down steps, narrow screens, and failed imports without real network dependencies |
| [ ] | Reduce workspace locking during TeX rendering | Slow fragments do not block unrelated reads; refresh prevents stale render results from entering new caches; add concurrency regressions |
| [ ] | File watching and incremental indexing | External saves update indexes; coalesce consecutive writes; preserve valid selection and handle deletion/renaming |
| [ ] | Large-graph benchmarks and budgets | Record indexing, transfer, first-frame, layout, and interaction timings for fixed 100 / 1,000 / 10,000-node samples before defining supported scale |
| [ ] | Dependency upgrades and deprecations | Resolve existing third-party warnings, update the lock file, and pass regressions instead of merely hiding warnings |
| [ ] | Documentation maintenance checks | Include language pairing, internal links, and API/example consistency in the update workflow |

## Next: reading, organization, and imports

| Status | Work | Acceptance condition |
| --- | --- | --- |
| [ ] | Multi-file TeX and broader macro support | Define workspace-contained include rules, cycle handling, and resource limits; support multiline macros with source locations and fallbacks for unsupported syntax |
| [ ] | More accurate formal declaration lookup | Add language-aware parsing or optional indexes; cover multiline declarations, nested scopes, overloads, and ambiguity while preserving explicit line-range precedence |
| [ ] | File management and rename assistance | Create/rename Markdown files; preview affected links and handle conflicts without silently breaking references |
| [ ] | Restore and share graph state | Define URL/local state formats for level, scope, and focus, with fallback for old links and deleted objects |
| [ ] | Accessibility improvements | Check keyboard traversal, focus restoration, and screen-reader descriptions; avoid color-only progress and membership signals |
| [ ] | Persistent and cancellable imports | Explain job state after restart; cancellation cleans staging without affecting completed imports; repeated submissions behave predictably |
| [ ] | Crash recovery and import quotas | Detect abandoned staging and partial publication; define cumulative disk/memory limits and test recovery after interruption |
| [ ] | Paper PDF navigation | Define the source of node-to-page mappings and indicate unavailable mappings instead of guessing page numbers |

## Extensions requiring separate design

- [ ] Standalone Python runtime/offline wheels, more platforms/versions, Coq installation, shared Lean caches, and complete dependencies for arbitrary projects.

- [ ] Verification extensions: Coq adapter, Lean axiom/sorry auditing, special names and parameterized Agda modules, real-toolchain CI, cancellable jobs, full dependency fingerprints, and UI results; design LSP separately.
- [ ] Legacy leanblueprint migration: provide read-only analysis and conversion previews while retaining originals; this item remains deferred from the original requirements.
- [ ] AI assistance or bidirectional generation: define context, diff previews, user confirmation, and provenance; generated content must not automatically be marked proven.
- [ ] Remote and multi-user deployment: design authentication, authorization, isolation, concurrent editing, and persistent jobs first; the local token does not provide these facilities.

## Maintenance convention

When completing work, update the corresponding Chinese and English module documents and specification. Record only tests actually executed. Update the [product overview](PRODUCT.en.md) and [architecture](ARCHITECTURE.en.md) when scope changes so planned features remain distinct from implemented ones.
