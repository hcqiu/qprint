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
