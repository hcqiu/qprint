# Knowledge Navigator

Start every agent in the opened Qprint folder. The UI publishes a relative
workspace and its automatically assigned tab session to `.qprint/runtime/navigation.json`.
Run `.\.conda\python.exe -m qprint agent state` with no flags: all subsequent queries follow this runtime.
There is no workspace scan or guessed session. Explicit `--workspace` overrides
must stay relative to and inside Qprint. Without runtime, the current folder is used.
Use the exact same Qprint folder that launched the UI. An installed Conda CLI
does not switch to its source or server directory. `runtime_status: not_published`
means this folder has no UI runtime; check the working directory first.
`published` means a persisted pointer exists, not that the browser is still open.

State includes `workspace`, `current_node`, `current_document`, `selection`,
`session` and `path_base: qprint`. Every returned file location is relative to
the opened Qprint folder, including files in nested workspaces. Opening a
prerequisite never replaces UI focus. Non-node document pages retain their
document with a null node. Deleted focus is marked stale. Latest active-tab
publication wins; this is a last-reported snapshot, not proof a tab remains open.

The UI writes through token-protected `POST /api/navigator/focus`; the CLI and
`GET /api/navigator/state` share the result. Embedded hosts supply the Qprint
folder as `create_app(..., runtime_root=...)`. Moving the entire folder needs
no state edits. Internal resolved filesystem paths are not returned to agents.

The UI host prepares its index and publishes the workspace on startup, before
the first browser click. A fresh PowerShell can run `.\.conda\python.exe -m qprint agent state`
without activation or inherited UI terminal variables. Without an index, state
still succeeds with `index_status: unavailable` and a startup hint. A persisted
focus retains its node ID, document and selection, with `focus_verified: false`;
mathematical queries continue to require an index. No query implicitly builds one.

For first-time setup, run `conda init powershell` and
`conda env create -p .\.conda -f environment.yml` in Anaconda Prompt / Miniconda
Prompt from the Qprint root. Thereafter use `.\.conda\python.exe -m qprint`;
no activation, PATH lookup, or profile initialization is needed. When Conda is
available, `conda run -p .\.conda python -m qprint` is equivalent.
If the environment is missing, report the setup command instead of discovering
installation-specific interpreter paths or using a named/global environment.

Queries use a read-only index and separate session storage. UI startup also
migrates legacy WAL storage; offline maintenance can use `.\.conda\python.exe -m qprint index`. History write failures produce `state_warning`
without blocking valid source results. `agent batch --calls` runs up to 32
registered query tools sequentially with per-call results/errors.

[中文](knowledge-navigator.md) | [English](knowledge-navigator.en.md)

This module implements sections 1–13, 16 and 17 of the referenced design.
UI index sharing (section 14) and the project-wide four-layer restructuring
(section 15) are outside its scope. Existing UI rendering is unchanged.

## Usage

```text
.\.conda\python.exe -m qprint index
.\.conda\python.exe -m qprint agent state
.\.conda\python.exe -m qprint agent search "Ganea construction"
.\.conda\python.exe -m qprint agent resolve GaneaIso
.\.conda\python.exe -m qprint agent open NODE_ID
.\.conda\python.exe -m qprint agent source NODE_ID --source tex --max-lines 100
.\.conda\python.exe -m qprint agent dependencies NODE_ID --depth 2
.\.conda\python.exe -m qprint agent backlinks NODE_ID --depth 2
.\.conda\python.exe -m qprint agent path A B --type uses --direction out
.\.conda\python.exe -m qprint agent context NODE_ID --token-budget 6000
.\.conda\python.exe -m qprint agent refs NODE_ID
.\.conda\python.exe -m qprint agent explain-edge A B --type uses
```

The examples include the local interpreter prefix and run from the Qprint root.
All results are JSON. Query commands use the existing index without rescanning
the workspace. `.\.conda\python.exe -m qprint watch --interval 1` runs a foreground
polling indexer; `--once` exits after one update. Failed updates preserve the
previous index, and watch retries after the next polling interval.

## Design mapping

| Reference sections | Implementation |
| --- | --- |
| 1–2 | `KnowledgeNavigator`, canonical node identities and aliases |
| 3 | `.qprint/index/knowledge.sqlite`: nodes, edges, aliases, chunks plus file caches, embeddings, sessions and review notes |
| 4 | Symbol/graph, SQLite FTS5, optional embedding provider |
| 5–6 | Eight core tools; resolve metadata → open summary → source fragments |
| 7–8 | Markdown navigation layer, TeX mathematical source, legacy fences and single-node front matter |
| 9 | Search graph expansion, default radius 1 |
| 10 | Persistent session working set, capped at 32 recently opened nodes |
| 11 | mtime/size checks, SHA-256 hashes, differential database updates and embedding cache |
| 12 | Deterministic indexing plus `skills/knowledge-navigator/SKILL.md` |
| 13 | Python API, CLI, JSON tool schemas and shared dispatcher |
| 16 | Formal symbol resolution, transitive backlinks and bounded source access |
| 17 | Reviewed edge explanations, provenance and `annotate-edge` |

## Identity and metadata

An explicit front-matter `id` wins. Otherwise a TeX-bound node uses
`<TeX relative path without extension>/<bpnode>`. Old Markdown addresses,
titles, bpnode names, TeX labels and bound formal declarations remain aliases.
A Markdown binding to a label inside a bpnode merges into that bpnode, too.
Repeated statement/proof anchors retain separate source ranges. Unbound legacy
nodes retain their original `file#heading` ID. Ordinary Markdown documents also
have document nodes, connected to folder indexes where available.
Use explicit IDs when identity must survive moving a TeX file.

```yaml
---
id: Topology/EM/loop-em
kind: theorem
aliases: [LoopEM, ΩEM]
description: Loop space of an Eilenberg–Mac Lane space.
proof_summary: Apply the suspension-loop adjunction.
milestone: EM induction
status: in_progress
source:
  tex: Topology/EM/main.tex
  label: thm:loop-em
formal:
  agda:
    declaration: loopEM
    file: Cubical/EM.agda
    lines: [20, 35]
uses:
  - target: Topology/EM/definition
    reason: Supplies the representing space.
---
```

Follow with a heading and navigation prose. Formal bindings also accept
`Cubical/EM.agda#loopEM`. TeX paths are relative to `tex/`; formal paths are
relative to the language directory. Legacy multi-node qprint fences remain
supported. Front matter extends only the navigator, not the current UI parser.
Prose wikilinks under `Uses:` become uses edges; other prose links become
mentions. Code blocks, inline code and HTML comments do not create edges.

Supported edge types are uses, ref, defines, proves, proof_of, same_node,
formalizes, cites, mentions and parent. Declare additional typed relationships
through the matching front-matter keys; no mathematical relationships are
inferred. Citations are external entities scoped by the TeX directory, without
invented bibliographic details.

Edges point from the dependent to its prerequisite: A → B means A uses B.
This differs from the existing UI graph's display convention. Dependencies
default to uses; backlinks additionally include references, mentions,
proof_of and formalizes. Paths default to bidirectional traversal and retain
the original directed edges; use `--direction out` for dependency chains.
Ambiguous names return candidates, not guesses. Unresolved edges preserve
`target_ref` with a null target and are repaired when new sources resolve them.

## Retrieval and updates

Search uses the fixed order: exact symbol, alias, lexical FTS, graph neighbors,
then optional semantics. Multiword lexical queries use OR matching with BM25
ranking. Query text is escaped rather than treated as raw FTS syntax. Scope
and kind filters apply before limiting results. Scores are local to retrieval
stages, not calibrated probabilities. FTS5 uses unicode61; embeddings can
provide paraphrase matching and better Chinese natural-language retrieval.

Open returns bounded navigation prose, dependencies, locations and formal
bindings without reading source files. Source reads only indexed ranges,
defaulting to 120 lines/20000 characters, and rejects stale hashes. Use
`--lines START END` to intersect source ranges. Context includes the current
node, direct dependencies, required definitions at depth two and recent
session nodes. Its compact JSON UTF-8 byte count conservatively bounds
byte-level tokenizer tokens; it is not a model-specific token count.
Check `token_upper_bound` and `truncated` in the result.

Only changed files are read and parsed. Relationship projections use cached
contributions; only changed database rows and embeddings are written. File
enumeration and graph assembly still scale with workspace size. There is no
OS event watcher. `index --verify-hashes` detects changes with preserved
mtime and size. Transactions keep previous data intact on parsing failures.

Formal location support uses explicit bindings and simple declaration scans.
For complex syntax provide file and lines. Ambiguous or missing declarations
have `location_status=unresolved`. This is not a full language parser or a
formal-verification result.

## Python and tools

```python
from qprint.knowledge import KnowledgeIndexer, KnowledgeNavigator
from qprint.knowledge.tools import call_tool, tool_definitions

KnowledgeIndexer("my-math").update()
with KnowledgeNavigator("my-math", session="em-review") as kb:
    result = call_tool(kb, "kb_resolve", {"query": "LoopEM"})
    if result["status"] == "resolved":
        summary = kb.kb_open(result["node"]["id"])
```

`tool_definitions()` exposes JSON schemas for eight core tools plus
`kb_explain_edge`; `call_tool` provides a transport-independent dispatcher for
agent or MCP hosts. This module does not start a standalone MCP server or
install client configuration. CLI equivalents are `agent tools` and
`agent call TOOL --args JSON`.

An optional provider implements `model_id` and
`embed(list[str]) -> list[list[float]]`. Pass it as `embedding_provider` to both
the indexer and navigator. Vectors are cached in SQLite by chunk hash and
model ID and searched with cosine similarity. Change model_id when updating
the model. Without a provider, operation is fully offline: no model download
or remote API call. The default CLI does not enable embeddings. Semantic
search currently scans vectors linearly rather than using an ANN service.

Record reviewed edge explanations using front-matter reasons or:

```text
.\.conda\python.exe -m qprint agent annotate-edge A B --type uses --reason "B identifies the fiber of p_n."
```

Notes survive incremental indexing. Edge explanations include source evidence;
missing reasons return `unexplained`. Review notes and working sets live in
SQLite rather than source files; back up `.qprint/index` before deleting it.
