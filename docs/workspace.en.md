# Workspace and file module

[中文](workspace.md) | [English](workspace.en.md) · [Documentation](index.en.md)

Implementation: [workspace.py](../qprint/workspace.py), [paths.py](../qprint/paths.py). Tests: [test_workspace_api.py](../tests/test_workspace_api.py).

## Layout and paths

```text
my-math/
  blueprint/Topology/Notes.md
  tex/Topology/Notes.tex
  pdf/Topology/Notes.pdf
  lean/Topology/Notes.lean
  agda/Topology/Notes.agda
  coq/Topology/Notes.v
```

Directories may be absent or empty, and nodes need not bind papers or code. The server loads the specified workspace, defaulting to `examples/demo` relative to the current directory. Matching Markdown/TeX paths support a label-only binding; other locations require explicit paths.

Blueprint paths are relative to `blueprint/`, TeX paths to `tex/`, and code paths to the corresponding language directory. API and metadata paths use `/`, not Windows backslashes. A CLI workspace root may use `D:/my-math`.

`safe_path(root, relative)` rejects empty or absolute paths, `.` / `..` segments, backslashes, Windows drive/ADS syntax, reserved names, invalid characters, and trailing dots/spaces. It checks that the resolved path, including symlinks, stays inside the specified root. `read_text` reads UTF-8 with optional BOM and a 5 MiB per-file limit.

## Indexing and diagnostics

`Workspace(root)` calls `reload()` during initialization. Reload scans Markdown and TeX, parses nodes, builds relations, TeX locations, and reading order within each paper, then produces [grouped graph indexes](graph.en.md). Empty files remain in the file graph.

`project()` returns nodes, edges, paper outlines, grouped graphs, diagnostics, and statistics. `detail(id)` returns body HTML, code slices, rendered/raw TeX, previous/next nodes, relations, and backlinks. Nodes without paper bindings remain readable but do not participate in navigation within a paper.

Missing or ambiguous node references produce warnings. Invalid nodes, file read failures, duplicate TeX labels, or missing TeX bindings produce errors. Code lookup issues appear in node details. CLI `check` exits with 1 for errors and 0 for warnings only; it does not compile formal code or render every node detail.

## Save protocol

1. `document(path)` returns current text and its SHA-256 `revision`; it accepts existing `.md` files.
2. `save_document(path, text, expected)` compares the current disk revision and reports a conflict on mismatch.
3. Validate UTF-8 byte length and node parser errors, then write a sibling temporary file.
4. Recheck the revision, replace the target using `os.replace`, clean the temporary file, and rebuild indexes.

The save returns new text and revision. Syntax validation does not reject every unresolved link or missing TeX binding; those appear as diagnostics after rebuilding. The API uses 409 for conflicts and 400 for other workspace validation errors.

An in-process `RLock` protects workspace operations. External editors do not hold this lock. Revision comparisons detect external changes already present, but the final comparison and replacement are not a cross-process atomic compare-and-swap.

## Caching and maintenance

TeX output is cached lazily per node and invalidated on every reload. There is no file watcher; refresh or call reload after external edits. Use external tools to create, delete, or move files. Indexes live in memory and rebuild from files on restart, with no database migration.
