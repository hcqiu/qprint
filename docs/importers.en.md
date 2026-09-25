# Material import module

[中文](importers.md) | [English](importers.en.md) · [Documentation](index.en.md)

Implementation: [importers.py](../qprint/importers.py). Tests: [test_importers.py](../tests/test_importers.py). CLI and UI share the same importers; HTTP jobs are described in the [API document](server-api.en.md).

## GitHub repositories

Imports accept public GitHub repository root URLs, optionally ending in `.git`, not blob/tree pages. Pass a branch, tag, or SHA separately as `ref`; omission resolves the default branch through GitHub. There is no account login or private-repository credential flow.

```powershell
.\.conda\python.exe -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace my-math
```

The archive is extracted into `agda/serre-finiteness/`; `language` can also be lean or coq. The entire repository is retained, including code, licenses, configuration, and other files, without filtering by language extension. The result contains `path`, `files`, and `ref`. A `.qprint-source.json` file records type, URL, ref, resolved full commit, archive SHA-256, and UTC download time.

## arXiv papers

Imports accept modern/legacy arXiv IDs, optional version suffixes, and HTTPS abs/pdf/src/e-print URLs. Both PDF and source are downloaded. Source formats include zip, tar/tar.gz, a single gzipped TeX file, and UTF-8 TeX.

```powershell
.\.conda\python.exe -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace my-math
```

Outputs are `pdf/Geometry/Via16SpherePacking.pdf` and `tex/Geometry/Via16SpherePacking/`. Multi-file source retains internal relative paths and includes provenance. The result contains `pdf`, `tex`, `files`, and `id`. Supply a basename for `name`, without directories or a `.pdf` suffix. An empty `dest` selects the root category.

A valid PDF and source containing `.tex` are both required. Error pages, unavailable source, and unsupported content fail the import. Paper imports do not create Markdown, insert `\bpnode`, execute code, or install dependencies. Nodes and bindings must be authored afterward.

## Downloads, archives, and publication

| Limit | Current rule |
| --- | --- |
| Network | HTTPS, no URL user credentials, default port/443 only; validate each redirect |
| Download hosts | api.github.com, codeload.github.com, github.com, arxiv.org, export.arxiv.org |
| HTTP | 30-second connect and 20-second idle-read timeout; three bounded attempts, validated ETag resume and bounded redirects; not a total job deadline |
| Download size | At most 100 MiB per response |
| Expanded size | At most 300 MiB and 10,000 entries per archive, including directories |
| Archive paths | Reject traversal, Windows special paths, case collisions, and duplicate paths |
| Archive types | Reject symlinks, hard links, devices, and other special files |
| Destination | Reject existing targets; `.qprint-source.json` is reserved for provenance |

Content is staged in `.qprint-import-*` inside the workspace and published after validation. GitHub imports remove one archive root directory; paper imports preserve internal structure. After validating both paper resources, TeX is published first and PDF second. If the latter fails, the newly published TeX is moved back. Normal exit cleans staging.

This is application-level staging and rollback, not crash-safe atomic publication across multiple files. Downloads stream to staging before the importer loads archive bytes into memory. Per-operation limits are not cumulative workspace or process quotas.

## Failures and verification

Choose another directory or paper name if a destination exists. Transient network failures retry automatically within a fixed budget; check connectivity if recovery fails. Missing source requires another legitimate source. Read job `error` on failure; 202 does not mean the import finished. There is no unbounded automatic retry.

Unit tests inject a downloader and require no real network. `tools/smoke_imports.py` is a separate network smoke tool that downloads public examples into `.qprint/`. Historical results appear in [verification](verification.en.md). Provenance records identify the download source, not correctness or compilability.


## Verify after download (default ON)

The UI checkbox and API `verify_after_download` default to true. The CLI accepts `--verify-after-download` / `--no-verify-after-download`. Once code is published, verification discovers native Lean/Agda projects, acquires supported pinned environments and runs upstream entry checks. Enabling this option runs the downloaded project's toolchain and build configuration. `--timeout` defaults to 600 seconds; `--toolchain-home` selects the store; `--offline` prevents verification acquisition but source download still uses the network. Coq returns `unsupported`.

Download success and verification status are separate. The result contains `verification.status` and `verification.reports`; failed checks keep downloaded files and timestamped reports. With verification enabled, the CLI returns 1 unless verification passes; an opted-out successful import returns 0 with `not_run`. Import jobs expose phase `downloading` or `verifying`. Job `succeeded` means the import completed and results are available, not that proof checking passed. The separate manual Blueprint API still requires `--allow-verification`; this import option independently selects execution as part of the import request.


## Progress while waiting

Import jobs expose `progress`: the current archive, received/total bytes when supplied by the server, extraction counts, dependency position, and the mathlib cache or Lake build stage. Running tools report output byte counts; the UI displays total elapsed time. Unknown totals do not produce percentages. Stage changes publish immediately; other updates are throttled to one per second and delivered through existing job polling.

After source download, a first run may still acquire a compiler of several hundred MiB, dependencies and build caches. `timeout` budgets preparation commands and checking stages, not the entire import. Toolchain acquisition uses separate network timeouts, so the default 600 seconds is not a ten-minute end-to-end deadline. See the [sphere-eversion experiment](sphere-eversion-experiment.en.md).


## Opening failure reports

Import results show each project's status, error, readable report link and full JSON download. “查看历史验证报告” reads the latest 30 reports from the current workspace on disk, including after server restart. Plain report paths remain available for helper handoff. Unexpected discovery/verification exceptions produce failure reports where possible; storage failures expose `report_error` instead of referring to a nonexistent report. One project's exception does not discard other results in a multi-project repository.

## Paper destination normalization

A destination may name the parent category (`Topology`) or the paper project (`Topology/Lin20K3`) with `--name Lin20K3`; both publish to `tex/Topology/Lin20K3/` and `pdf/Topology/Lin20K3.pdf`. A matching final directory component is not appended twice (case-insensitive). A source archive containing only an enclosing directory has that wrapper removed; relative paths inside the paper are preserved, and archives with multiple root entries remain intact. Existing targets are still never overwritten.
