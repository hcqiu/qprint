# Server and API module

[中文](server-api.md) | [English](server-api.en.md) · [Documentation](index.en.md)

Implementation: [server.py](../qprint/server.py). `create_app(root)` creates the workspace, session write token, and import executor. APIs use JSON. The runtime schema is available at `/openapi.json`; Swagger/ReDoc pages are disabled.

## Paths and writes

The example server address is `http://127.0.0.1:8765`. URL-encode node IDs in query parameters, especially `#`, which otherwise becomes a browser fragment and is not sent to the server. Document paths are relative to `blueprint/`; TeX paths are relative to `tex/`. Both use `/`.

First GET `/api/project` to obtain `token`. Every non-GET/HEAD/OPTIONS request requires `x-qprint-token`. When `Origin` is supplied, it must exactly match the request server's origin. Retrieve a new token after restarting the server. This token is not remote user authentication.

## Endpoints

| Method and path | Input | Successful response |
| --- | --- | --- |
| GET `/api/project` | None | `name`, `nodes`, `edges`, `graph`, `papers`, `diagnostics`, `stats`, `token` |
| GET `/api/node` | Query `id` | Node fields plus `body_html`, `formal`, `tex_content`, `previous`, `next`, `relations`, `backlinks` |
| GET `/api/document` | Query `path` | `path`, `text`, `revision` |
| PUT `/api/document` | JSON `path`, `text`, `revision` | Saved `path`, `text`, `revision` |
| GET `/api/tex` | Query `path` | `path`, `source`, `sections` |
| POST `/api/reload` | No body | Rebuilt project data, without token |
| POST `/api/import` | Body below | HTTP 202, `id`, `status: queued` |
| GET `/api/jobs/{id}` | Job ID in path | `id`, `status`, `result`, `error` |

See the [graph module](graph.en.md) for `graph`. `stats` contains node, complete, edge, and TeX file counts. `tex_content` is null without a paper binding; unavailable previous/next nodes are null. Code results carry individual `error` fields.

Import request:

| Field | Rule |
| --- | --- |
| `kind` | Required: `code` or `paper` |
| `source` | Required repository URL or arXiv ID/URL; at most 2,048 characters |
| `dest` | Required relative destination directory; at most 512 characters; papers allow an empty string |
| `language` | Defaults to `lean`; code supports `lean` / `agda` / `coq` |
| `ref` | Optional code branch/tag/SHA; omitted means resolve the default branch |
| `name` | Defaults to empty; papers require a valid paper basename |

Some business validation happens in the background job. HTTP 202 means accepted, not successfully downloaded.

## Request example

Verification adds `POST /api/verify` with optional `node_id`, `language`, and `timeout`, returning HTTP 202 with `id` and `status: queued`. It requires `serve --allow-verification` and the existing write protections. `/api/project` adds `verification_enabled`; jobs add `kind: import | verification`. Verification has a separate single worker/five-job queue. Job success means report generation; inspect `result.status` for check success. See [formal verification](formal-verification.en.md) for full contracts.

This browser example runs on the same origin. Saving the original text illustrates the revision protocol; replace `text` for a real edit.

```javascript
const project = await fetch('/api/project').then(r => r.json());
const path = 'Topology/Maps.md';
const doc = await fetch('/api/document?path=' + encodeURIComponent(path))
  .then(r => r.json());
const response = await fetch('/api/document', {
  method: 'PUT',
  headers: {'Content-Type': 'application/json', 'x-qprint-token': project.token},
  body: JSON.stringify({path, text: doc.text, revision: doc.revision})
});
const result = await response.json();
if (!response.ok) throw new Error(JSON.stringify(result.detail));
```

## Jobs and errors

Startup `--toolchain-home` and `--allow-system-toolchains` apply to verification jobs. HTTP requests cannot select installation paths, arbitrary compilers, or install/remove commands. Explicit jobs acquire supported missing exact versions from project requirements. Binding results add `environment`; failures persist timestamped reports with `report_path`. See [project resolution](formal-resolution.en.md).

Jobs move through `queued → running → succeeded | failed`; clients poll results or errors. One import worker runs at a time. Five queued/running jobs fill the queue. The job table is in memory, so IDs disappear on restart. No cancellation or automatic retry endpoint exists.

| Status | Meaning |
| --- | --- |
| 400 | Workspace path, format, or other business validation failure; Host validation may also return 400 |
| 403 | Invalid token or Origin |
| 404 | Missing node, file, TeX document, or job |
| 409 | Markdown revision conflict |
| 413 | Declared write Content-Length exceeds 6 MiB |
| 422 | Request model/parameter validation failure |
| 429 | Import queue is full |

Business JSON errors use `detail`; request model errors may use an array for that field. The Markdown model limits text to 5 MiB characters; the save layer additionally enforces 5 MiB of UTF-8 bytes. The 6 MiB check uses a request header and is not a comprehensive streaming body limit.

Responses include CSP, nosniff, and no-referrer; API responses use `Cache-Control: no-store`. The server binds locally by default and allows Host values localhost, 127.0.0.1, [::1], and testserver for tests. Remote deployment requires separate design; see [architecture](../ARCHITECTURE.en.md).


Code import requests additionally accept `verify_after_download: true` (default) and `timeout: 600` (1–3600 seconds). Running jobs include `phase: downloading` or `verifying`. A completed import returns `result.verification.status` and compact `reports` with timestamped evidence paths; inspect these even when job status is `succeeded`. Set the switch to false for download only. The import option selects toolchain execution independently of the manual Blueprint verification gate. Paper imports ignore this option.


## Import job progress fields

Running import jobs expose `started_at` (Unix seconds) and `elapsed_seconds`; completion adds `finished_at` and freezes elapsed time. Code imports also expose a `progress` snapshot with `stage`, `message`, `elapsed_seconds`, `stage_seconds`, and optional stage-specific `bytes/total_bytes`, `completed_files/total_files`, `attempt`, `output_bytes`, `quiet_seconds`, and `timeout_seconds`. Progress elapsed time belongs to the last event; top-level elapsed time updates on each read. This is a latest snapshot, not an event log or guaranteed heartbeat: network reads may wait for their timeout. Existing `phase` and final `result.verification` contracts remain available.


## Persisted verification reports

`GET /api/formal-reports` returns up to 30 recent readable report summaries from the workspace. `GET /api/formal-report?path=PROJECT/.qprint/reports/TIMESTAMP-ID.json` displays plain-text errors/stage output; `download=true` downloads full JSON. Only workspace-contained timestamped report paths are accepted, not arbitrary files. Import job `result.verification.reports[]` adds `report_url` and `download_url`; reports outside the workspace retain their path without a URL. In-memory jobs disappear on restart, while report history remains on disk.
