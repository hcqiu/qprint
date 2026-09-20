# Material import module

[中文](importers.md) | [English](importers.en.md) · [Documentation](index.en.md)

Implementation: [importers.py](../qprint/importers.py). Tests: [test_importers.py](../tests/test_importers.py). CLI and UI share the same importers; HTTP jobs are described in the [API document](server-api.en.md).

## GitHub repositories

Imports accept public GitHub repository root URLs, optionally ending in `.git`, not blob/tree pages. Pass a branch, tag, or SHA separately as `ref`; omission resolves the default branch through GitHub. There is no account login or private-repository credential flow.

```powershell
conda run -n qprint python -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace D:/my-math
```

The archive is extracted into `agda/serre-finiteness/`; `language` can also be lean or coq. The entire repository is retained, including code, licenses, configuration, and other files, without filtering by language extension. The result contains `path`, `files`, and `ref`. A `.qprint-source.json` file records type, URL, ref, and UTC download time.

## arXiv papers

Imports accept modern/legacy arXiv IDs, optional version suffixes, and HTTPS abs/pdf/src/e-print URLs. Both PDF and source are downloaded. Source formats include zip, tar/tar.gz, a single gzipped TeX file, and UTF-8 TeX.

```powershell
conda run -n qprint python -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace D:/my-math
```

Outputs are `pdf/Geometry/Via16SpherePacking.pdf` and `tex/Geometry/Via16SpherePacking/`. Multi-file source retains internal relative paths and includes provenance. The result contains `pdf`, `tex`, `files`, and `id`. Supply a basename for `name`, without directories or a `.pdf` suffix. An empty `dest` selects the root category.

A valid PDF and source containing `.tex` are both required. Error pages, unavailable source, and unsupported content fail the import. Imports do not create Markdown, insert `\bpnode`, execute code, or install dependencies. Nodes and bindings must be authored afterward.

## Downloads, archives, and publication

| Limit | Current rule |
| --- | --- |
| Network | HTTPS, no URL user credentials, default port/443 only; validate each redirect |
| Download hosts | api.github.com, codeload.github.com, github.com, arxiv.org, export.arxiv.org |
| HTTP | httpx timeout configured at 60 seconds with bounded redirects; not a total 60-second job deadline |
| Download size | At most 100 MiB per response |
| Expanded size | At most 300 MiB and 10,000 entries per archive, including directories |
| Archive paths | Reject traversal, Windows special paths, case collisions, and duplicate paths |
| Archive types | Reject symlinks, hard links, devices, and other special files |
| Destination | Reject existing targets; `.qprint-source.json` is reserved for provenance |

Content is staged in `.qprint-import-*` inside the workspace and published after validation. GitHub imports remove one archive root directory; paper imports preserve internal structure. After validating both paper resources, TeX is published first and PDF second. If the latter fails, the newly published TeX is moved back. Normal exit cleans staging.

This is application-level staging and rollback, not crash-safe atomic publication across multiple files. Downloads and archives are handled in memory. Per-operation limits are not cumulative workspace or process quotas.

## Failures and verification

Choose another directory or paper name if a destination exists. Check connectivity and manually retry network failures. Missing source requires another legitimate source. Read job `error` on failure; 202 does not mean the import finished. There is no unbounded automatic retry.

Unit tests inject a downloader and require no real network. `tools/smoke_imports.py` is a separate network smoke tool that downloads public examples into `.qprint/`. Historical results appear in [verification](verification.en.md). Provenance records identify the download source, not correctness or compilability.
