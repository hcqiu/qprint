# TeX to Blueprint

[中文](tex-to-blueprint.md) · [Rendering](tex-rendering.en.md)

The workflow follows the product prompt: agent annotation, deterministic generation, then mathematical review. Projects, milestones and nodes remain folders, Markdown files and first-level headings; no hierarchy fields are added to the node schema.

Use the [skill](../skills/tex-to-blueprint/SKILL.md) to read the paper, identify shared definitions outside environments and implicit dependencies, and add `\bpnode`, `\bpdesc` and `\uses` without changing existing references or citations. Repeated labels within a file collect statement and proof fragments into one node.

```powershell
conda run -n qprint python -m qprint.tex_to_blueprint search --workspace WORKSPACE --query KEYWORD
conda run -n qprint python -m qprint.tex_to_blueprint generate --workspace WORKSPACE --tex Paper/main.tex --dest Topology/Paper --title TITLE --author AUTHOR --year 2025 --keyword topology --dry-run
```

Remove `--dry-run` to write. Source paths are relative to `tex/`; destinations are relative to `blueprint/`. Repeat `--tex`, `--author` and `--keyword` as needed. `--dependency-map MAP.json` maps ambiguous labels to complete node IDs. Search reads only existing Blueprint Markdown.

The generator creates one file per subsection, including empty ones, and separate drafts for annotated section content outside subsections. Repeated nodes belong to their first occurrence and collect all descriptions and dependencies. Declared theorem aliases determine existing kind values; propositions and corollaries use `theorem`.

`index.md` records title, authors, year, keywords, file links and resolved external project dependencies, using frontmatter and second-level headings to avoid fake nodes. `generation-report.json` records unresolved dependencies and `review_required: true`. Existing destinations are never overwritten; all files are prepared before publishing the directory.

Review drafts against the paper, reorganize them into mathematical milestones, complete implicit dependencies, and update links after moving nodes. The script does not execute TeX or expand includes; pass related body files explicitly. It does not infer mathematical semantics. Complex macros, packages and images remain subject to renderer limitations.

## Validation

```powershell
conda run -n qprint pytest tests/test_tex_formal.py tests/test_tex_to_blueprint.py tests/test_workspace_api.py
conda run -n qprint python tools/smoke_tex_to_blueprint.py SOURCE_ARCHIVE --output NEW_TEST_WORKSPACE --title TITLE --author AUTHOR --year YEAR --render-limit 12
```

Unit and integration tests cover repeated anchors, nested descriptions, empty subsections, multiple files, external dependency disambiguation, inline/math links, HTML escaping, source fallback, path validation, dry runs and overwrite prevention.

The offline smoke script mechanically marks outer mathematical environments, proof repetitions and resolvable explicit references in disposable extracted copies. **It does not perform complete mathematical annotation or semantic review.** Original archives are preserved; papers are not distributed with the repository.

Measured on 2026-09-22 in Conda `qprint`:

| Source | Environment markers | Nodes | Markdown files including index | Edges | Conversion | Rendering |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| [2003.03925v6](https://arxiv.org/abs/2003.03925v6) | 44 | 32 | 6 | 20 | 0.055 s | All 32, no fallbacks |
| [2510.12394v2](https://arxiv.org/abs/2510.12394v2) | 311 | 216 | 34 | 234 | 0.444 s | All 216, two fallbacks (47.274 s total) |

Both workspaces had no parsing or dependency-index diagnostics. The stress fallbacks contain external resources or unsupported commands, and some other fragments report complex typesetting warnings. This is not a claim of full LaTeX fidelity. Local reports under `.qprint/tex-to-blueprint-tests/{basic-smoke,stress-full}/smoke-report.json` include archive hashes, warnings, link counts and timings.

Initial full Python regression: 227 tests passed, with two existing FastAPI/Starlette deprecation warnings. The skill passed `quick_validate.py`, was installed in the local default skills directory, and its installed search entry point was exercised successfully.

## Portable skill

The skill now contains its own `references/blueprint-format.md`, `scripts/convert.py` and `scripts/qprint_blueprint/` runtime. It does not read product prompts, repository documentation or application modules at runtime. Python dependencies come from Conda `qprint`. Run the script by its absolute path from any directory. The additional `validate --workspace WORKSPACE --project PROJECT --render-limit 5` command checks bindings, annotation coverage and dependency links, then returns rendered HTML and warnings.

For maintainers only, `tools/bundle_blueprint_skill.py` refreshes the bundled runtime from application modules; regression tests check that these copies stay identical and that a relocated skill can generate and render without the checkout. This maintainer script is not an agent input.

For the portable skill and real downloader evaluation with two clean agents, see [independent paper evaluation](tex-to-blueprint-agent-evaluation.en.md).
