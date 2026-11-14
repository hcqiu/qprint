# 在阅读页面与 Agent 对话

启动 Qprint 后，点击顶部 qprint 同一行的 **⚙ Agent**：

1. 选择 Codex、Claude Code、Hermes、OpenCode，或其他支持 ACP 的 Agent。
2. 点击 **重新查找**，或填写 Agent 可执行文件的完整路径。Windows 支持原生 `.exe` 和 Node `.js`；常见 Codex / Claude npm 启动器会解析为 Node 入口，不通过 shell 拼接提示词。
3. 保存选择，在节点的阅读或 TeX 页面选中文字，点击 **Ask agent**。
4. 在右侧面板输入问题。选区旁的圆形气泡可以再次打开同一会话；顶部 **会话** 和面板下拉列表也能找回它。

新会话直接复用 `clipboard-context.js` 的 `formatContext`，内容与选中文字后复制到剪贴板的上下文一致。第一条提问附在该上下文之后；后续对话保留历史。面板中可以展开查看实际上下文。

会话和选区锚点保存在各工作区 `.qprint/chat.sqlite`，刷新页面或重启服务后保留。选区用节点、视图、文字、偏移和前后文定位；原文消失或重复内容无法区分时不显示猜测位置的气泡，仍可从会话列表打开。服务重启会将未完成的回答标为中断，不自动重发。

## Agent 连接

| 方式 | 接口 | 登录与权限 |
| --- | --- | --- |
| Codex | 本机 `codex app-server`，原生 thread 恢复 | 使用 Codex 自身登录；默认只读、按需审批；审批和追问显示在面板 |
| Claude Code | `claude -p`，结构化输出和原生 session 恢复 | 使用 CLI 自身登录；`dontAsk` 拒绝需要人工批准的工具，不自动扩大权限 |
| Hermes / OpenCode | `hermes acp` / `opencode acp` | 使用 Agent 自身配置；ACP 一次性权限请求显示在面板 |
| 其他 Agent | 用户指定可执行文件及 ACP 参数数组 | 必须实现 ACP v1 stdio；不支持任意交互式终端程序 |
| API | OpenAI-compatible `/chat/completions` 流式接口 | 设置 Base URL、模型和 API key；仅文本问答，没有本地工具 |

CLI 发现结果只表明文件存在，首次提问时才验证协议、登录和网络。如未登录，在终端完成对应 Agent 的正常登录或 setup，然后重试。Qprint 不复制 Agent 的凭据。Windows 和 WSL 的 Agent 是独立环境，此面板的自动发现面向运行 Qprint 的环境。

ACP Agent 支持加载会话时使用其原生会话，否则将完整上下文和已有对话重放到新 ACP session。自定义 ACP 参数使用 JSON 字符串数组，如 `["acp"]`。不提供客户端文件写入和终端扩展能力；Agent 仍可能使用自身工具。

API key 仅保存在当前 Qprint 服务的内存中，重启服务后需重新填写；也可在启动服务的环境中提供 `OPENAI_API_KEY`。地址和模型会保存，密钥不会写入会话数据库或返回浏览器。API 地址必须使用 HTTPS，本机服务允许 HTTP。配置和开始提问是两个独立动作，保存设置不会发送论文内容。

所有 Agent 从 Qprint 根目录启动，便于使用本地 `.conda` 与 Knowledge Navigator。CLI 的登录、可用模型、网络和额度由各 Agent 自身管理。遇到错误会在面板保留原因和已收到的部分回答；可停止当前任务后继续提问。
