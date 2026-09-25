# Qprint runtime 与相对路径回归验证

本次入口约定：在 Qprint 文件夹启动或打开 agent，执行 `qprint agent state`。
UI 发布当前 workspace、节点、文档、selection、session；查询无需 agent 猜测或手动拼接参数。
当前使用说明见 [Knowledge Navigator](knowledge-navigator.md)。

实现包括根目录 runtime 指针、自动页签 session、Qprint 相对路径输出、文档页上下文、
相对 workspace 参数校验和异常中的机器路径去标识化。操作系统内部仍可解析真实路径，
但它们不作为 agent 的命令参数或返回文件位置。

回归测试通过真实 CLI 子进程读取由服务 API 发布的状态，覆盖：

- 根目录中的无参数 state/source/open 跟随当前 UI workspace 与 session。
- 切换节点、页签、workspace 时状态随之更新；阅读依赖不覆盖 UI 焦点。
- TeX、Markdown 编辑页和非节点文档页报告正确的 current_document。
- 整个 Qprint 文件夹复制到新位置后，原命令与状态无需修改。
- 显式 workspace 只接受文件夹内的相对路径；无 runtime 时不扫描或猜测其他工作区。
- 已损坏或试图越界的 runtime 不被采用；输出不泄漏安装路径。
- 页签 session 自动生成和复用；存储不可用时可降级生成。

验证结果：Python 全量 **300 passed，1 skipped**；JavaScript **21 passed**。
Python 跳过项为环境不支持的符号链接测试。首次相关测试出现一次并发路径检查失败，
随后单独诊断与完整测试均通过；没有为绕过该检查放宽目录边界。
本次验证没有重新运行八道数学问答，也没有执行真实浏览器的端到端点击测试。

历史问答报告继续保留原有分数和耗时；其中机器专用路径已去标识化，
原始本地运行日志仍保留。旧记录不作为当前 agent 的启动模板。
`tests/scenarios` 的题面与评分点不变，启动约定已改为根目录、相对路径和自动 runtime。

宿主首次准备本地环境可执行 `conda env create -p ./.conda -f environment.yml`。
已运行的 Qprint 服务需要重启以加载新的 runtime 同步接口。

## 新 PowerShell 启动回归

发现首次运行存在启动依赖：UI 只在索引已存在时同步状态，根目录 runtime
也要等首次节点上报才出现；`state` 本身又强制要求索引。现改为 UI 服务启动时
自动增量准备索引并发布工作区，agent 查询不负责建索引。
`start.ps1` 的 workspace 和 toolchain-home 默认参数也改为相对路径。

`state`、`call kb_state` 和 batch 中的 `kb_state` 在无索引时均返回有效 JSON：
没有页面快照则节点为 null；已有快照则保留节点 ID、文档、selection 和 session，
同时报告 `index_status=unavailable`、`focus_verified=false` 和恢复提示。
索引恢复后继续返回完整节点信息；数学查询仍要求有效索引。

本轮全量 Python 测试 **302 passed，1 skipped**。新增测试实际创建
`powershell -NoProfile -NonInteractive` 进程并执行
`conda run -n qprint qprint agent state`，验证未启动 UI、首次无索引启动、
两次节点/session 切换。另覆盖索引丢失时仍可读快照、重启后自动恢复索引，
以及新进程无需 workspace/session 参数即可读取 source。PowerShell 启动脚本语法检查通过。
页面状态由服务 API 发布，未进行真实浏览器点击测试。
