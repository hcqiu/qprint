# Knowledge Navigator 双论文盲测

> 历史运行记录；机器路径已去标识化。当前命令与自动 runtime 约定见 [使用说明](knowledge-navigator.md)。

后续的当前状态接口、运行问题修复和全新代理重测见[第二轮报告](knowledge-navigator-state-evaluation.md)。

本轮按 [knowledge_navigator 测试指南](../产品经理prompt/knowledge_navigator测试.md) 编写并执行。
使用 `examples/demo` 中的 `Topology/Lin20K3` 和 `Topology/KPT25TwoStabilizations`，
每篇 4 个问题。完整题面、隐藏来源节点、原文行号和评分点保存在
[测试清单](../tests/scenarios/knowledge_navigator.json)。

2026-09-24 共执行 **12 次独立 agent 运行：8 个首轮用例、4 个全新 agent 重测**。
首轮严格通过 **4/8**；另有 1 例答案完整但违反工具白名单、3 例因环境错误未完成原文核实。
将启动目录从 `examples/demo` 改为仓库根目录后，对这 4 例保持题面不变重测，
结果为 **3 例完整通过、1 例部分覆盖**。部分覆盖的 K2R 答对主要机制，
但漏解释“附着位置无关”所依赖的 boundary twist 延拓，因此没有按完整通过统计。

12 次均未直接读取 skill 以外的源文件或代码。40 份语料/skill 文件的前后 SHA-256 相同。
本次只新增测试用例、采集器和报告，没有为提高通过率修改 Navigator、skill 或数学语料。
这是小样本探索性测试，重测条件发生了变化，不能将其合并宣称为同一条件下 8/8 通过。

逐例证据：[完整答案](evaluations/knowledge-navigator-2026-09-24/answers.md)、
[指标与调用审计 JSON](evaluations/knowledge-navigator-2026-09-24/results.json)、
[语料哈希](evaluations/knowledge-navigator-2026-09-24/source-hashes.json)。

## 实测结果

所有 agent 的运行日志均记录模型 `gpt-6-astra`、reasoning effort `high`，未单独覆盖模型配置。
表中的总 tokens 包含累计缓存输入；完整的 input/output/reasoning 分项保存在 JSON。

### 首轮

| 用例 | 严格结果 | 总耗时 / 工具阶段（秒） | Navigator 次数 | 总 tokens | 缓存输入 | 非缓存输入＋输出 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| L1 | 通过 | 253.7 / 129.1 | 4 | 197,250 | 155,008 | 42,242 |
| L2 | 通过 | 280.7 / 160.8 | 6 | 301,170 | 274,560 | 26,610 |
| L3 | 失败 | 361.4 / 239.9 | 14 | 416,442 | 363,392 | 53,050 |
| L4 | 失败 | 193.3 / 71.0 | 3 | 194,691 | 183,552 | 11,139 |
| K1 | 通过 | 264.1 / 145.9 | 7 | 232,768 | 214,016 | 18,752 |
| K2 | 失败 | 162.2 / 43.6 | 2 | 133,227 | 125,440 | 7,787 |
| K3 | 失败 | 188.0 / 68.0 | 3 | 194,458 | 183,296 | 11,162 |
| K4 | 通过 | 306.1 / 184.9 | 9 | 359,909 | 335,872 | 24,037 |

### 调整启动目录后的独立重测

| 用例 | 严格结果 | 总耗时 / 工具阶段（秒） | Navigator 次数 | 总 tokens | 缓存输入 | 非缓存输入＋输出 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| L4R | 通过 | 223.3 / 103.9 | 10 | 290,740 | 261,376 | 29,364 |
| K2R | 部分覆盖 | 212.6 / 86.3 | 6 | 233,809 | 213,120 | 20,689 |
| K3R | 通过 | 209.9 / 91.6 | 9 | 226,555 | 209,408 | 17,147 |
| L3R | 通过 | 252.2 / 133.6 | 14 | 318,961 | 293,120 | 25,841 |

### 逐例评分说明

| 用例 | 说明 |
| --- | --- |
| L1 | 完整解释 complete 定义、采用 May 结果的便利，以及脚注允许的 incomplete universe。 |
| L2 | 准确限定非等变公式、两种 signature 情形；没有把期待的等变推广当成已证结果。 |
| L3 | 数学回答完整；调用一次 send_message 报告环境错误，违反本轮明确禁止协调工具的约束。 |
| L4 | 数据库错误后未取得原文，未回答数学问题；调用两次 send_message。 |
| K1 | 说明固定点侧 rank 差、符号表示商，以及经纤维同伦等价对应包含映射。 |
| K2 | 数据库错误后只解释符号并请求上下文，没有给出受原文支持的机制；调用一次 send_message。 |
| K3 | 给出条件性的投影推断，但未通过 Navigator 核实原文，不计通过；调用两次 send_message。 |
| K4 | 完整区分两份、三份代数障碍和拓扑要求偶数份；解释四份与两次稳定化不是同一数量。 |
| L4R | 完整说明 S¹ 限制下 Euler class 消失，以及 Pin(2) 关键命题和 η³ 非零的反证链。 |
| K2R | 核心机制正确：同一 Z 改变附着位置逐项消去，偶数份消除修正；指出允许的 Z 和附着位置无关，但没有解释该无关性来自 punctured summand 的 boundary twists 可延拓，第二评分点仅部分覆盖。 |
| K3R | 给出 level 0 投影及具体生成元取值，后合成保持 level 2，从而与三份不存在定理矛盾。 |
| L3R | 完整说明连通和乘积、S²×S² 的固定点计算及 Euler class，并解释 twisted/product spin families 同构。 |


## 发现的问题

1. **从 demo 目录启动时出现数据库打开失败。** 八个首轮用例首次查询均出现
   `unable to open database file`。主代理诊断定位到
   `qprint/knowledge/index.py` 的 `PRAGMA journal_mode=WAL`；相同 workspace 参数在仓库根目录可运行，
   部分 agent 在 demo 目录通过权限提升重试也能继续。四个根目录重测均没有数据库打开错误。
   这是当前 Windows/sandbox 环境下的观测，尚不能确定操作系统层面的根因。
   建议检查查询连接为什么需要 WAL/schema 写入，并补充启动环境诊断或只读索引连接。
2. **并发 Conda 启动有临时文件冲突。** L3、K4、L4R、K2R、K3R、L3R 共记录 9 次
   `__conda_tmp_*.txt` 访问/缺失错误；顺序重试后恢复。该成本包含在耗时和命令次数中。
   建议查询入口复用已启动进程，或在此 Windows 环境中串行启动 Conda。
3. **文字约束没有阻止全部越界工具调用。** L3、L4、K2、K3 使用 `send_message`
   向主代理报告错误。主代理未回传答案或导航提示，但这仍违反了本轮额外规定的协调工具禁令。
   严格评测宜在运行时只暴露 skill 读取和 Navigator 查询能力；本轮没有这样的物理隔离。
4. **答案完整性仍需核查。** K2R 找到了正确的复制引理，解释了同一个 Z 的逐项复用，
   但没有展开附着位置无关的依据。检索到正确节点不保证所有评分细节都会出现在回答中。
5. **端到端耗时不能当作检索性能。** 每例初始化至首 token 约两分钟，工具阶段仍有
   43.6–239.9 秒的跨度，包含模型、进程启动及失败重试。本轮未设置 `rg` 或无 skill 对照组，
   因此不能据此声称 token 节省比例或速度提升。

## 测试方法

每次执行都创建 `fork_turns=none` 的新 subagent，不沿用其他案例的历史。
提供给 agent 的数学输入只有复制的词句和一句短问；环境说明仅指定工作目录、
skill 路径、Conda 入口、Navigator workspace/session 和读取边界。
不提供论文名、当前节点 ID、参考答案、评分点或其他 agent 的发现。

这里模拟“用户已在浏览器打开某节点，再复制一句话提问”。来源节点仅用于主代理核对，
没有实际驱动浏览器或测试 TeX 渲染。数学符号题面采用可读的文本写法。
每例使用新的 Navigator session；不预先把来源节点加入 working set。

agent 只能直接读取 `skills/knowledge-navigator/SKILL.md`，其余资料只能经
`qprint agent` 查询获得。禁止直接读取/搜索 TeX、Markdown、源码、测试清单，
禁止 SQL、内部 Python API、网络、浏览器、索引重建和边注释写入。
Navigator 自身维护该例 working set 属于正常查询行为。
工具能力并未在平台层裁剪，因此边界合规通过实际调用记录审计，不宣称物理隔离。

为落实指南中的“配备 skill、指定文件夹”，本轮显式提供了一段相同的环境及权限说明，
没有把这段说明当作数学提示。其模板存于测试清单的 `agent_environment_template`；
实际用户问题仅取每例的 `question` 字段。首轮失败与目录调整都计入结果，不静默预热重跑。

判定需要同时满足：回答覆盖该例的三个评分点、通过原文核实、没有越界资料访问。
数据库错误后仅给出条件性的数学推断不计通过。初次失败和重测分开保存，不覆盖记录。
额外的协调工具调用也单独登记，区别于文件/代码访问合规。本轮运行约束明确禁止 agent
协调调用，因此即使只是向主代理报告环境错误、没有获取额外知识，严格工具白名单判定仍失败。
`functions.exec`/`wait` 作为允许命令的执行与等待通道不作额外知识工具计算。

## 八个问题

| ID | 论文 | 用户短问 | 主要考察 |
| --- | --- | --- | --- |
| L1 | Lin20K3 | “complete”：这里的 universe 为什么要假设 complete？ | 定义与脚注限定，避免把便利假设说成必要条件 |
| L2 | Lin20K3 | “twisted spin structure”：这里的 η·BF(M) 公式也适用于 Pin(2) 等变情形吗？ | 非等变公式与未证明的推广 |
| L3 | Lin20K3 | “BFᴳ(N,s) · e_R̃”：为什么稳定化后多出的是这个 Euler class？ | 连通和公式、S²×S² 的 BF 计算、两种 spin family |
| L4 | Lin20K3 | “not smoothly isotopic … even after a single stabilization”：为什么这里一定要用 Pin(2)，只用 S¹ 不行吗？ | 主定理的证明链与限制映射 |
| K1 | KPT25 | “local of level k”：这个 k 具体量的是什么？ | 固定点侧余维和符号表示 |
| K2 | KPT25 | “X^{#2n} # Z”：为什么复制了 2n 份 X，却不需要复制 2n 份 Z？ | 同一个稳定化因子的移位与逐个消去 |
| K3 | KPT25 | “There does not exist a local map … of level 2.”：三份的结论怎么推出这里四份的结论？ | level-zero 投影、后合成与矛盾 |
| K4 | KPT25 | “at least three copies of M”：既然三份就能给出代数障碍，最后为什么用了四份？ | 代数最小值与拓扑偶数条件的区别 |

## 指标口径

耗时使用运行日志 `task_complete.duration_ms`，包含 agent 初始化、模型响应和工具等待。
另列首次工具调用至最终回答的时间，便于看到初始化影响；它仍包含重试和权限等待，
不等同于 Navigator 查询延迟。

token 使用来自 `token_usage_record.turn_token_usage`。累计 input 包含每次模型请求中
重复输入的历史与缓存命中；cached input 是 input 的子集。记录 total、input、cached input、
output 和 reasoning output，reasoning output 已包含在 output 中，不重复相加。
另列 `input - cached_input + output`，仅作为非缓存输入加输出量，不能解释为价格或纯检索成本。
干净 subagent 指无对话历史继承，不代表底层公共提示缓存被清除。

Navigator 命令次数按实际 shell 返回计数，包含失败重试及 `agent tools`，
排除 skill 读取。循环或并发执行按实际命令数统计，不能只数外层工具调用。

## 复现与证据

原始工具输出、源文件/skill 哈希和未评分的测量结果保存在：

```text
.qprint/knowledge-navigator-evaluation/2026-09-24/
  source-hashes.json
  results.raw.json
  tool-outputs/<RUN_ID>.json
```

主代理读取 skill 以外的文件仅用于编题、评分和环境诊断；这些动作不在测试 agent 的输入中。
测试期间不修改 Navigator 或 skill，以免首轮与重测混入不同实现。

采集器 [collect_knowledge_navigator_eval.py](../tools/collect_knowledge_navigator_eval.py)
只抽取与指定测试 agent recipient 匹配的日志。它不读取加密任务内容，也不自动给数学答案打分。

```powershell
conda run -n qprint python tools/collect_knowledge_navigator_eval.py `
  --logs HOST_PATH `
  --output .qprint/knowledge-navigator-evaluation/2026-09-24/results.raw.json `
  --evidence .qprint/knowledge-navigator-evaluation/2026-09-24/tool-outputs `
  --rerun L4R=L4 --rerun K2R=K2 --rerun K3R=K3 --rerun L3R=L3
```

重放时，应由测试主持人读取测试清单，单独把短问与通用环境说明交给新 agent；
不要把包含评分点的清单直接交给受测 agent。
