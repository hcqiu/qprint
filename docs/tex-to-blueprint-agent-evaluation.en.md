# Independent two-paper skill evaluation

## Clean inputs

Both agents were created with `fork_turns=none`. Each initial request contained only the installed skill path, workspace, paper source directory and Blueprint destination. They received no conversation history, product prompt, expected node counts, answer key or previous mechanical annotations. The fixed format reference, entry point and supporting runtime are all inside the skill.

Fresh PDF and TeX downloads used the actual Qprint `import-paper` command, pinned to 2003.03925v6 and 2510.12394v2. Supplying both a project destination and a matching paper name now produces `tex/Topology/Lin20K3` and `tex/Topology/KPT25TwoStabilizations` without duplicate directories. Source archive wrappers are removed while internal relative paths are retained. Workspaces under `.qprint/blueprint-skill-evaluation/basic` and `stress` are isolated; this run does not test links between the two papers.

## First paper

The agent read the complete TeX and bibliography, annotated 41 nodes, and reorganized five generated section files into seven mathematical milestones with 80 prerequisite edges. Nine Markdown files include the index and review. External Blueprint searches found no matching projects; external mathematical inputs remain ordinary citations with a review record.

Initial full validation had no structural diagnostics and produced 95 inline links. The final repeated theorem segment inadvertently included bibliography directives, causing one fallback. The independent run exposed this boundary bug. After fixing it without changing the paper, all 41 nodes were revalidated: 109 inline links, zero fallbacks, and no structural diagnostics. Complex typesetting commands still produce warnings. Initial and refreshed reports are both retained.

## Stress paper

The agent reports reading all 9,599 original lines, including three appendices, in recorded consecutive ranges. It produced 218 marked segments representing 216 unique nodes, reorganized 33 subsection drafts into 26 mathematical milestones, and recorded 468 prerequisite edges. There are 28 Markdown files including index and review. Proof-local statements nested in a long proof were explicitly aggregated to preserve the enclosing environment.

Initial generation and structural validation had no diagnostics. All 216 nodes were rendered: 83 without warnings, 133 with warnings, and two fallbacks; 550 inline links appeared across 209 nodes. The fallbacks involved a PDF figure and trailing bibliography directives. The review records unresolved orientation, example-name, localization, module-basis and appendix-formula issues while preserving the TeX. This is a semantic Blueprint review, not proof certification; all formalization statuses remain `not_started`.

## Independent checks and evidence

The parent compared both annotated sources with the original downloads after removing annotation commands/no-op definitions and ignoring whitespace/comments. Both comparisons passed. Neither project has empty descriptions, unbound nodes or mechanical-test placeholder descriptions. Evidence is under `.qprint/blueprint-skill-evaluation/evidence/`: initial and final skill hashes, original source copies, and the independent output audit. Project indexes, review logs, generation records and validation reports remain in each project's Blueprint folder. Generation file lists are historical; current organization is defined by the reviewed index.

The portable-runtime test copies the skill outside the checkout, clears `PYTHONPATH`, and generates and renders with no Qprint repository dependency. It also verifies that a working-directory package cannot shadow the bundled worker. Release checks verify that all skill resources are included. Maintainers refresh the bundled modules using `tools/bundle_blueprint_skill.py`; this maintenance tool was not supplied to the paper-processing agents.

The final regression suite has 245 passing tests and two existing FastAPI/Starlette deprecation warnings. It covers path normalization, archive wrappers and multiple roots, rollback, relative extraction paths, portable execution, renderer worker resolution and bibliography boundaries.

## Revalidation by the original agents

Both original agents used the updated skill to revalidate their own projects, preserving initial reports and mathematical annotations. The first paper has 41 nodes, 80 edges, no structural diagnostics, 109 inline links and zero fallbacks; two nodes still report eight typesetting warnings. The stress paper has 216 nodes, 468 edges, no structural diagnostics and 555 links across 210 nodes. Of all 216 renderings, 83 have no warnings and 133 have warnings; one fallback remains because the main theorem segment contains the Mazur PDF figure. The final appendix theorem now renders as HTML. Each agent updated its review and validation summary from these results.
