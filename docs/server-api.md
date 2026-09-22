# 服务与 API 模块

[中文](server-api.md) | [English](server-api.en.md) · [文档目录](index.md)

实现：[server.py](../qprint/server.py)。入口 `create_app(root)` 创建工作区、会话写入 token 和导入执行器。API 使用 JSON；运行时 schema 位于 `/openapi.json`，未启用 Swagger/ReDoc 页面。

## 路径与写入约定

示例服务地址为 `http://127.0.0.1:8765`。查询参数中的节点 ID 必须 URL 编码，尤其是 `#`，否则它会被浏览器当作片段而不发给服务器。文档路径相对 `blueprint/`，TeX 路径相对 `tex/`，均用 `/`。

先 GET `/api/project` 获取 `token`。所有非 GET/HEAD/OPTIONS 请求都需携带 `x-qprint-token`；提供 `Origin` 时必须与请求服务的 origin 完全一致。服务重启后需重新获取 token。该 token 不是远程用户认证。

## 接口表

| 方法与路径 | 输入 | 成功响应 |
| --- | --- | --- |
| GET `/api/project` | 无 | `name`, `nodes`, `edges`, `graph`, `papers`, `diagnostics`, `stats`, `token` |
| GET `/api/node` | query `id` | Node 字段及 `body_html`, `formal`, `tex_content`, `previous`, `next`, `relations`, `backlinks` |
| GET `/api/document` | query `path` | `path`, `text`, `revision` |
| PUT `/api/document` | JSON `path`, `text`, `revision` | 保存后的 `path`, `text`, `revision` |
| GET `/api/tex` | query `path` | `path`, `source`, `sections` |
| POST `/api/reload` | 无 body | 重建后的 project 数据，不含 token |
| POST `/api/import` | 下表请求体 | HTTP 202，`id`, `status: queued` |
| POST `/api/verify` | 可选 `node_id`, `language`, `timeout` | HTTP 202，`id`, `status: queued`；要求启用验证执行 |
| GET `/api/jobs/{id}` | 路径 job ID | `id`, `status`, `result`, `error` |

`graph` 结构见[图谱模块](graph.md)。`stats` 含节点数、complete 数、边数和 TeX 文件数。未绑定论文时 `tex_content` 为 null，无法前后导航时对应字段为 null。代码结果独立携带 `error`。

导入请求：

| 字段 | 规则 |
| --- | --- |
| `kind` | 必填，`code` 或 `paper` |
| `source` | 必填，仓库 URL 或 arXiv ID/URL，最多 2,048 字符 |
| `dest` | 必填，目标相对目录，最多 512 字符；论文可传空字符串 |
| `language` | 默认 `lean`；code 可用 `lean` / `agda` / `coq` |
| `ref` | 可选，代码分支/tag/SHA；不填则读取默认分支 |
| `name` | 默认空；paper 需要有效论文 basename |

部分业务校验在后台导入时进行，HTTP 202 只表示任务已接收，不表示下载成功。

## 请求示例

`/api/project` 另含 `verification_enabled`；`/api/jobs/{id}` 另含 `kind: import | verification`。验证需使用 `serve --allow-verification` 启用，使用独立单线程/五任务队列；报告位于 job.result，任务 succeeded 不等于检查 passed。配置、请求和结果契约见[形式化验证](formal-verification.md)。

下面是浏览器同源环境中的调用顺序；保存原文用于说明版本协议，实际编辑应替换 `text`。

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

## 任务和错误

服务启动时的 `--toolchain-home` 和 `--allow-system-toolchains` 控制所有验证任务；HTTP 请求不能指定安装路径、任意编译器或安装/删除命令。显式验证任务会按项目声明补齐支持的固定版本。结果另含 `environment`；失败时持久化带时间的报告并返回 `report_path`。见[项目解析](formal-resolution.md)。

任务状态为 `queued → running → succeeded | failed`，结果或错误由客户端轮询读取。只有一个导入工作线程，排队和运行总数达到 5 时拒绝新任务。任务表仅存内存，重启后 job ID 不再有效；没有取消或自动重试接口。

| 状态码 | 含义 |
| --- | --- |
| 400 | 工作区路径、格式或其他业务校验失败；Host 校验也可能返回 400 |
| 403 | token 或 Origin 不合法 |
| 404 | 节点、文件、TeX 或任务不存在 |
| 409 | Markdown revision 冲突 |
| 413 | 声明的写入 Content-Length 超过 6 MiB |
| 422 | 请求模型/参数校验失败 |
| 429 | 导入队列已满 |

业务 JSON 错误使用 `detail`；请求模型错误的 `detail` 可能是数组。Markdown 文本模型限制 5 MiB 字符数，保存层另检查 UTF-8 字节数不超过 5 MiB；6 MiB 是请求头检查，不能当作完整流式请求体限额。

响应带 CSP、nosniff、no-referrer，API 带 `Cache-Control: no-store`。默认绑定本机，允许 Host 为 localhost、127.0.0.1、[::1] 和测试使用的 testserver。远程部署需要另行设计，见 [架构](../ARCHITECTURE.md)。


代码导入请求新增 `verify_after_download: true`（默认）与 `timeout: 600`（1–3600 秒）。运行任务返回 `phase: downloading/verifying`；完成后读取 `result.verification.status` 与含时间戳报告路径的 `reports`，即使 job 为 `succeeded` 也需看检查结果。开关设为 false 则只下载。此开关在导入流程中选择执行工具链，与手动 Blueprint 验证的启用开关独立；论文导入不使用此项。


## 导入任务进度字段

运行中的导入 job 返回 `started_at`（Unix 秒）、`elapsed_seconds`；完成后增加 `finished_at`，耗时固定。代码导入另有 `progress`，包括 `stage`、`message`、`elapsed_seconds`、`stage_seconds`，按阶段可选 `bytes/total_bytes`、`completed_files/total_files`、`attempt`、`output_bytes`、`quiet_seconds`、`timeout_seconds`。`progress.elapsed_seconds` 是最后一次事件时的耗时；顶层耗时在每次读取时更新。进度是最近快照，不是完整事件日志或心跳保证；下载读取期间可能等待网络超时。现有 `phase` 和最终 `result.verification` 契约保留。


## 持久验证报告

`GET /api/formal-reports` 返回当前工作区最近 30 份可读报告摘要；`GET /api/formal-report?path=项目/.qprint/reports/时间戳-ID.json` 返回纯文本错误与阶段输出，增加 `download=true` 下载完整 JSON。路径必须在工作区内，文件名必须符合 Qprint 时间戳格式，不提供任意文件读取。导入 job 的 `result.verification.reports[]` 增加 `report_url`、`download_url`；路径在工作区外时保留原路径而不生成链接。进程内 job 会在重启后消失，磁盘报告历史不受影响。
