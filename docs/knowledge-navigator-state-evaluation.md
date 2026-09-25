# Knowledge Navigator 当前状态与修复后重测

> 历史运行记录；机器路径已去标识化。当前命令与自动 runtime 约定见 [使用说明](knowledge-navigator.md)。

本轮在原有双论文测试题面和评分点不变的基础上，增加宿主页面状态输入。
原始首轮及四项重测结果保留在[上一轮报告](knowledge-navigator-agent-evaluation.md)。

**结果：八题首测 7 题完整通过、1 题部分覆盖；补充 skill 的通用证明表述规则后，
该题由第九个干净代理复测通过。** 没有覆盖原来的部分覆盖记录，也不把不同 skill 版本
合并称作同一轮 8/8。九次均调用了 `state`，实际调用审计全部合规，查询进程失败和
Conda 临时文件冲突均为 0。39 份数学源文件的 SHA-256 与第一轮一致。

完整证据：[最终回答](evaluations/knowledge-navigator-2026-09-24-v2/answers.md)、
[逐例指标与调用审计](evaluations/knowledge-navigator-2026-09-24-v2/results.json)、
[初始页面快照](evaluations/knowledge-navigator-2026-09-24-v2/initial-states.json)。
两版 skill：[八题首测版](evaluations/knowledge-navigator-2026-09-24-v2/skill.snapshot.md)、
[补充复测版](evaluations/knowledge-navigator-2026-09-24-v2/skill-refined.snapshot.md)。

## 修复与行为

- `kb_state` / `agent state` 返回当前节点、项目、来源、页面模式、选中文本、更新时间、
  最近访问记录和索引信息。空状态与已删除的焦点节点都有明确结果。
- 网页经受保护的 `/api/navigator/focus` 上报状态；API、CLI 共用 session。
  agent 查阅依赖只更新历史，不覆盖宿主当前节点。不同 session 不混用记录。
- 普通查询只读数学索引；索引迁移至 rollback journal，会话库独立存储。
  demo 目录下的读取不再依赖创建 WAL/SHM 文件。
- 沙箱拒绝会话写入时仍交付有效查询结果并附 `state_warning`，不会因保存历史失败中断答案。
  这是明确的降级行为，不表示当前运行环境获得了历史写权限。
- 新增单进程 `agent batch`；skill 指导顺序启动 Conda、使用状态、核查证明依据，
  并在受限任务中避免越界工具及反复提权。

## 验证方法

自动测试覆盖焦点与历史分离、跨会话隔离、删除/清空焦点、只读索引、跨启动目录查询、
并发首次创建会话库、历史写入失败降级、网页 API 的 token/同源检查，以及批量查询部分失败。
网页 JavaScript 测试覆盖按顺序发送快照、发送失败后恢复。没有执行真实浏览器的端到端点击测试。

Python 全量测试：**296 passed，1 skipped**。跳过项为当前环境不支持的符号链接测试。
JavaScript：**20 passed**。skill frontmatter 校验通过。
首次 pytest 默认临时目录被 Windows 权限拒绝；改用仓库内专用 basetemp 后运行上述测试。

独立 agent 测试使用[八个状态场景](../tests/scenarios/knowledge_navigator_state.json)。
主持端通过真实服务的 TestClient 调用 `/api/navigator/focus`，模拟用户正在看的节点和所复制文本；
agent prompt 不提供节点 ID、项目名、评分点或其他 agent 的结果。
每例都是 `fork_turns=none`、新 session，启动目录统一为 `examples/demo`。
各例使用独立 Conda TEMP/TMP 目录，单例内依 skill 顺序执行查询。
数学语料未修改；Navigator/skill 在八题独立重测开始前完成修复。
八题完成后，仅对 skill 增加三行通用要求：最终解释应保留关键步骤的成立依据，
并区分同伦、同痕及相对边界等限定。随后使用第九个干净代理只重测 K2，
题面、评分点、宿主焦点和查询实现不变。两版 skill 分别存档，不覆盖 K2 的部分覆盖记录。

当前平台没有裁剪 subagent 的底层工具列表，因此通过实际调用记录审核范围，
不宣称强制隔离。禁止直接读取 skill 以外的文件、代码、SQL、内部 Python API、
网络、浏览器、其他 agent/协调工具及维护写操作；`exec/wait` 只作为命令执行通道。

## 实测结果

模型均为运行环境继承的 `gpt-6-astra`，reasoning effort 为 `high`。
九次共出现 50 次历史写入降级提示；数学查询和宿主焦点仍可读取。
当前沙箱的历史写权限限制仍然存在，修复的是它阻断读取的行为。

| 用例 | 判定 | 总耗时 / 工具阶段（秒） | 进程 / 逻辑查询 | 总 tokens | 缓存输入 | 非缓存输入＋输出 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V2L1 | 通过 | 168.4 / 47.6 | 3 / 3 | 140,147 | 127,232 | 12,915 |
| V2L2 | 通过 | 199.8 / 79.6 | 6 / 6 | 249,065 | 228,736 | 20,329 |
| V2L3 | 通过 | 285.9 / 167.2 | 13 / 13 | 511,881 | 476,672 | 35,209 |
| V2L4 | 通过 | 257.0 / 138.8 | 10 / 10 | 460,437 | 408,192 | 52,245 |
| V2K1 | 通过 | 163.6 / 43.3 | 3 / 3 | 140,771 | 132,480 | 8,291 |
| V2K2 | 部分覆盖 | 214.2 / 93.8 | 6 / 6 | 260,247 | 242,048 | 18,199 |
| V2K3 | 通过 | 220.5 / 101.5 | 7 / 7 | 285,732 | 260,608 | 25,124 |
| V2K4 | 通过 | 277.8 / 157.1 | 12 / 12 | 527,577 | 491,136 | 36,441 |
| V2K2R | 通过 | 196.5 / 75.3 | 5 / 5 | 221,513 | 198,272 | 23,241 |

| 用例 | 原文核实与评分说明 |
| --- | --- |
| V2L1 | 完整解释 complete 定义、May 理论的便利性，以及原文脚注允许的 incomplete universe。 |
| V2L2 | 明确非等变公式、signature 两种情况和未证明的等变推广；额外核实忘却群作用的限制关系。 |
| V2L3 | 完整覆盖连通和乘积、固定点包含决定 Euler class，以及旋转 S² 交换两种 spin family。 |
| V2L4 | 正确解释 S¹ 限制后 Euler class 消失、特征度条件与关键命题、稳定化前 η³ 非零的矛盾；没有夸大为所有 S¹ 方法都无用。 |
| V2K1 | 完整给出固定点侧 rank 差、符号表示商、纤维同伦等价后的包含映射；k=0 的说明也正确。 |
| V2K2 | 同一 Z 重定位逐项消去、允许的 Z、偶数性和 Ruberman 修正均正确；但仅概括为稳定化块消除歧义，未明确说明边界扭转可光滑延拓到内部，第二评分点仍部分覆盖；还将此处 isotopy 写成同伦，措辞不够准确。 |
| V2K3 | 给出 level 0 投影的生成元公式，后合成保留 level 2；核实三份不存在定理和 level 相加依据。 |
| V2K4 | 完整区分两份的 level 2 映射、三份代数障碍和几何偶数约束，并用 level 0 投影说明四份仍有障碍。 |
| V2K2R | 完整说明穿孔稳定化块的边界扭转可向内部延拓、Ruberman 引理与连接位置无关性；同一 Z 逐项消去及偶数修正均正确，并准确使用固定外边界的同痕。 |


耗时和 token 从真实 `task_complete` / `token_usage_record` 日志采集，未用回答长度估算。
总耗时包含初始化；工具阶段为第一次工具调用至最终回答，也包含模型响应和进程等待。
总 token 为累计输入加输出，缓存输入是累计输入的子集；非缓存输入加输出不等于费用。
批量查询另计内部逻辑调用次数，不能只统计 shell 进程数。

本轮提供了工具可读取的当前页面，且隔离了 Conda 临时目录；
与上一轮无当前页面状态的条件不同。因此结果只能说明修复后的任务表现，
不能把时间/token 差异单独归因于某一改动或宣称受控性能提升。

## 复现与证据

保持当前节点发布在宿主侧：网页使用 `?navigator_session=TASK`，查询使用 `--session TASK`。
若重放测试，应创建新 session 并按清单的隐藏 node 发布焦点，单独把 `question` 交给新 agent。
不得把完整测试清单交给受测 agent。对旧 WAL 索引，主持端先运行一次 `qprint index`。

```powershell
conda run -n qprint python tools/collect_knowledge_navigator_eval.py `
  --cases tests/scenarios/knowledge_navigator_state.json `
  --logs HOST_PATH `
  --output .qprint/knowledge-navigator-evaluation/2026-09-24-v2/results.raw.json `
  --evidence .qprint/knowledge-navigator-evaluation/2026-09-24-v2/tool-outputs `
  --rerun V2K2R=V2K2
```

原始工具输出和初始状态快照保存在上述 `.qprint` 目录。
逐例回答、指标和人工审计结论随报告保存在 `docs/evaluations/knowledge-navigator-2026-09-24-v2/`。
