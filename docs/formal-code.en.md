# Formal code lookup module

[中文](formal-code.md) | [English](formal-code.en.md) · [Documentation](index.en.md)

Implementation: [formal.py](../qprint/formal.py). Tests: [test_tex_formal.py](../tests/test_tex_formal.py). This module reads source slices; it does not compile or execute proofs.

The separate [unified verification layer](formal-verification.en.md) provides CLI and opt-in background API checks for Lean / Agda, independent of source slicing and author progress.

## Binding syntax

Use language fields in a node's `qprint` metadata, for example:

```yaml
lean:
  - declaration: Topology.identity_continuous
    file: Topology/Continuity.lean
    lines: [5, 9]
  - declaration: External.some_theorem
    url: https://github.com/owner/repo/blob/main/SomeFile.lean
agda: Topology.Maps.identity
coq:
  declaration: identity_continuous
  file: Topology/Maps.v
```

These paths and line numbers illustrate syntax. `file` is relative to the workspace's `lean/`, `agda/`, or `coq/`, not to the blueprint file. A node may bind multiple languages and declarations. Line ranges are one-based and inclusive.

## Lookup order

`locate_code(root, binding)` returns the binding plus `code` and `error`, filling `file` and `lines` on success.

1. Use an explicit `file`; otherwise split the declaration on dots and try module paths from longest to shortest with the language extension.
2. If explicit `lines` exist, slice directly and check bounds. Line ranges take precedence; the text is not revalidated against the declaration name.
3. Without line numbers, scan declarations. Prefer an exact qualified name, then a unique final name component. Missing or multiple candidates produce an error.
4. Slice from the declaration to the next declaration or a language-specific boundary, trimming trailing blank lines.

| Language | Extension | Heuristic support |
| --- | --- | --- |
| Lean | `.lean` | Namespaces and common def/theorem/lemma/structure/inductive/class declarations; end/namespace/section boundaries |
| Agda | `.agda` | Top-level `name : type` signatures |
| Coq | `.v` | Definition/Theorem/Lemma/Fixpoint/Inductive and similar declarations; Qed/Defined/Admitted endings |

These are line-based rules, not full syntax trees. Complex indentation, multiline declarations, generated syntax, nested scopes, or overloads should use explicit files and line ranges.

## Remote bindings and errors

A binding may contain only `declaration` and an HTTPS `url`. When no local file is found, the result indicates that remote code has not been downloaded. The UI provides the source link without fetching the web page or individual declaration. Use [repository import](importers.en.md) for local source.

Missing files, read failures, out-of-range lines, and ambiguity return `code: null` with an explanation. A whole file is not substituted as a falsely located declaration. Paths are checked against workspace boundaries. Finding a source slice does not mean it compiles under Lean / Agda / Coq, and it never changes node `status` automatically.
