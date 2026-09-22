# 原生配置解析、自动安装与版本修复

Qprint 使用语言生态的原生配置。阅读源码不会触发编译或下载；显式验证会为固定版本补齐缺失环境。`--offline` 禁止联网安装。尚未支持 Coq 编译适配器，因此不解析 `_CoqProject`/opam/dune 为可执行验证环境。

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `formal_workspace.py` | 工作区内的项目发现与源目录边界 |
| `formal_projects.py` | 原生配置、元数据、recipe/lock、README 证据解析；不运行程序、不下载 |
| `formal_artifacts.py` | 查询官方发行物、固定提交包，持久化本地 artifact 目录 |
| `toolchains.py` | SHA-256 校验、安全解包、安装收据、原子安装和库存 |
| `formal_environment.py` | 将 requirements 与库存组装为隔离的执行环境 |
| `formal_sources.py` | 普通/文学化源码后缀与模块名转换，供项目检查和声明检查共用 |
| `formal_adapters.py` | Lean/Agda 语言相关的构建与声明探针 |
| `formal_runner.py` | 子进程、超时、进程树终止与受限日志 |
| `formal_reports.py` | 带 UTC 时间和唯一 ID 的报告、版本修复交接信息 |
| `formal_service.py` | 独立项目 resolve/verify 流程；原生入口、逐文件检查与显式安全审计 |
| `verification.py` | Blueprint 绑定编排，兼容原公共 Python 导入 |

## 解析规则

Lean 必须提供精确的 `lean-toolchain`；缺失或 stable/nightly 等浮动值立即生成错误报告。读取 `lake-manifest.json` 并交由 Lake 使用，不另外复制 Lean 版本到 YAML。Lake 负责原生依赖构建。

Agda 优先使用 `.agda-lib` 的 include、depend 和模块选项。它通常不提供编译器/依赖提交，因此按顺序补充：

1. `.qprint-formal.yaml`，兼容旧 `project.yaml`。
2. `.qprint-formal.lock.yaml`、`.qprint-formal.recipe.yaml`。
3. README 中唯一、明确的 Agda 版本与 Cubical 完整提交号。

较低优先级仅填空，不替换已固定版本。多个候选、缺少 pin 或不支持的配置返回错误，不猜测。README 只作为数据读取，绝不执行其中命令。解析成功且尚无 `.qprint-formal.yaml` 时，生成此文件并记录证据；不会覆写已存在的配置。

```yaml
toolchain:
  agda: "2.8.0"
dependencies:
  cubical:
    revision: d0b9c7b0e9e4f816422c3447d7983b03274dd829
policy:
  safe: inherit
  mode: cubical
```

lock/recipe 使用相同结构。依赖需 `revision`（完整 40 字符 Git 提交）或精确 `version`，二选一。额外 `provenance` 字段用于保存来源。原生 cubical/erased-cubical 选项优先；flags 保持 `.agda-lib` 原本的作用域，不向内置 primitive 模块全局强加 `--cubical`。

## 使用

```powershell
conda run -n qprint python -m qprint formal resolve --project PROJECT --language agda
conda run -n qprint python -m qprint formal verify --project PROJECT --language agda --timeout 600
conda run -n qprint python -m qprint formal verify --project PROJECT --language agda --entry Summary.agda --offline
conda run -n qprint python -m qprint formal verify --project PROJECT --language agda --entry Maps.agda --declaration identity
```

CLI 与下载后验证默认使用 `--entry-strategy auto`：Lean 执行 `lake build` 的默认目标；Agda 在源根依次查找唯一的 `AllModulesIndex`、`Everything`、`index`、`Index`、`Main`，无此入口则逐文件检查。`--entry-strategy all` 显式选择所有源文件，Python `formal_project()` 为兼容旧调用仍默认 `all`。支持的源码后缀包括 `.agda`、`.lagda`、`.lagda.tex`、`.lagda.md`、`.lagda.rst`、`.lagda.org`、`.lagda.typ` 和 `.lean`。文学化源码的整个后缀会从模块名中移除，不会误把 `Compact.lagda.md` 导入为 `Compact.lagda`。[Agda 文学化编程格式](https://agda.readthedocs.io/en/v2.8.0/tools/literate-programming.html)。

`--entry` 可重复，路径相对项目；`--declaration` 要求只选一个文件。Agda 直接检查各入口，保留各模块及 `.agda-lib` 的 OPTIONS，不生成混合策略的聚合模块。默认 `safe: inherit` 不添加 `--safe`，不全局把警告升级为错误；声明探针仍把名称缺失警告升级为错误。`safe: require` 添加 `--safe --ignore-all-interfaces`，失败不会自动降级；`safe: off` 也不会取消源码自身的 `--safe`。旧布尔值 `true/false` 分别兼容为 `require/off`。`formal audit --project PROJECT --language agda` 显式要求安全审计。检查范围写入 `scope`，原生默认目标通过不表示逐一检查了仓库所有文件。准备和检查各有默认 600 秒预算（参数上限 3600），逐文件 Agda 检查共享检查预算。Blueprint `verify`/API 仍只检查选中的绑定。

低层 `ToolchainResolver(auto_install=False)` 适合只读库存检查；CLI/验证服务显式采用 `auto_install=True`。阅读与索引操作不会调用它。网络失败、平台不支持、没有精确发行物或发行元数据无效均报告失败。

## 自动安装与证据

已有目录命中时复用安装；缺失的已知 artifact 通过原安装器下载。目录外的 Lean/Agda 版本由官方 GitHub release API 查询，当前自动发现支持 Windows x64，要求精确资产名，优先验证官方 SHA-256 digest；旧发行物没有 digest 时使用下文明确标注的首次下载策略。固定 Cubical 提交从官方 `agda/cubical` codeload 下载，首次获得的归档 SHA-256 与固定来源一并记录；这不是独立的发布者签名。未知库需要受支持的目录定义，不执行任意 recipe 脚本。

编译器保存在 `toolchains/<language>/<version>/`，库保存在 `packages/agda/cubical/<commit>/`。自动发现记录保存在 `toolchains/.qprint-catalog.json`，不会覆盖内置目录。所有目录均忽略 Git。全局 PATH、Conda 和用户 Agda library 配置不变。

依据：[Agda 库配置](https://agda.readthedocs.io/en/v2.8.0/tools/package-system.html)、[GitHub release asset digest](https://docs.github.com/en/rest/releases/assets)。

## 报告与 agent 交接

每次独立项目 resolve/verify 保存 `.qprint/reports/<UTC时间>-<唯一ID>.json` 和 `.md`；Blueprint 失败也持久化报告。JSON 包含请求参数、项目、环境、pin 来源、源文件哈希、阶段、命令、退出码、日志尾部及截断标记。报告不包含进程环境变量。`policy` 记录实际策略，`outcomes.typecheck` 与 `outcomes.safe_audit` 分开记录；安全审计失败时原生检查结果为 `unknown`，不能推断失败或成功。`preparation` 记录准备事件及 `ready/recovered/failed`，恢复后通过与一次通过可以区分。源码与已有配置改变会使检查结果变为 `stale`；首次由 Lake 创建的锁文件单独记录，不误判为修改已有 pin。配置缺失、依赖错误、超时与普通编译错误分别分类；缺少模块只标记为“疑似依赖问题”，不能自动断言证明错误或版本错误。

Qprint 后端不内置或自动启动 AI 服务。用户/宿主可将错误报告与项目交给无历史上下文的 agent，使用 [formalization-version-helper](../skills/formalization-version-helper/SKILL.md)。其权限限于该项目的版本配置与管理的 stores，保留证明源码和安全策略，修复后通过 `retry.py` 重新 resolve，再 verification。每次重试保存新报告，不覆盖先前证据。


## 自动准备与非版本故障恢复

`formal_policy.py` 定义策略和结果；`formal_agda.py` 构造原生命令与声明探针。`formal_downloads.py` 提供有限 HTTPS 重试、经 ETag 确认的断点续传和 SHA-256 校验；`formal_archives.py` 校验准备归档。`formal_git.py` 按原生 Lake 锁下载 GitHub 精确提交、记录收据，通过 Lake path overrides 使用固定依赖，不改写原锁。已有非托管 checkout 保留。准备源码时可将归档内部文档链接展开为普通文件；编译器安装器和公共导入器仍拒绝链接。

`formal_preparation.py` 准备 mathlib 原生缓存，对停滞下载有限重试，每次恢复最多补齐 64 个缺失/损坏对象，并支持 Windows 下校验后的 ProofWidgets release 解包。缓存对象仍由原生缓存工具校验。精确 tag、commit ID 和官方发布物 digest 必须匹配；恢复不伪造提交、不关闭哈希、不改证明 OPTIONS。自动发现编译器仍限 Windows x64，不支持的依赖来源或构建故障会报告。准备产物在项目 `.qprint/preparation`、`.lake` 中，编译器/库仍在 Qprint home 的 stores；不修改全局 Git 配置。

`formal_import.py` 负责下载后的项目发现并调用同一验证服务。传输、准备、验证与界面编排分别实现。[下载开关](importers.md) 默认开启。

无法确定性恢复的非版本问题交给 [formalization-runtime-helper](../skills/formalization-runtime-helper/SKILL.md)，通过 `formal_recovery.py` 只暴露 Python `inspect`、`recover` 两个操作。给干净 agent 的输入仅为 skill、报告路径、项目根和 toolchain home；检查返回受限摘要，不包含证明正文或对话历史。重试保持入口、pin、safe 策略及 offline 设置；输入变化、策略冲突和证明错误立即停止，每个原始报告最多重试三次。版本问题路由到已有 version helper。Qprint 不自动启动 LLM。脚本限制操作不等于 OS 沙箱，实际工具和文件权限仍需宿主执行隔离。


## 原生发布策略与实时进度

ProofWidgets 只有在锁定源码的 `lakefile.lean` 声明 `preferReleaseBuild := true` 时才进入旧式 cloud release 准备流程，并继续验证精确 tag、commit 与发布物摘要。新版未声明该策略时遵循原生源码/mathlib 缓存流程，不要求不存在的 release tag，不修改上游锁。见 [sphere-eversion 实测](sphere-eversion-experiment.md)。

`formal_progress.py` 使用请求局部上下文和节流回调，串联导入、工具链安装、依赖准备与检查；进度与持久报告分离。子进程输出仍写临时文件，仅报告字节数，不并发读取共享日志指针。观察进度不改变超时及进程树终止逻辑；展示回调故障不会中断检查。


## 旧版工具链和 Lake

官方 Lean/Agda 旧发布物可能没有 GitHub `digest`。解析器仍要求唯一的精确文件名、官方 HTTPS URL、正整数 asset ID 和长度；首次完整下载检查长度后计算 SHA-256，固定到本地 catalog，再按该哈希安装。`integrity: official-release-https-first-use-sha256` 明确表示首次信任官方 HTTPS 来源，不是发布者签名/摘要。后续安装复用固定哈希，不因摘要不匹配重新接受新值。已有官方 digest 时仍优先验证；格式错误的 digest 不降级。报告准备事件和安装收据记录来源、asset ID、长度及完整性类型。

`formal_legacy_lake.py` 检查已安装 Lake 是否支持 package overrides。旧版通过精确提交的浅 Git fetch 补齐 Qprint 管理依赖的真实 Git 元数据，检查 FETCH_HEAD，不执行 checkout/reset、不重写原生锁。发布 tag 先验证 peeled commit 等于锁定提交，再发布本地引用。支持旧锁中的 `«doc-gen4»` 引号名称，保留路径验证。旧 mathlib 使用 `XDG_CACHE_HOME/mathlib`，准备器为子进程设置项目内 `.qprint/preparation/legacy-cache`，不修改父进程或全局配置。

对于官方 API 确认直接指向锁定提交的轻量标签，复用已有真实提交对象；带注释标签通过 Git 获取后核对 peeled commit。Git fetch 的瞬态网络失败最多重试三次，仍共享原准备期限，不对仓库不存在或提交不匹配等确定错误重试。

`formal_release_assets.py` 将同样的官方来源/首次哈希策略用于旧辅助发布物（ProofWidgets、上游固定版本的 leantar），保存独立收据并复用已校验归档，避免这些下载绕过 Qprint 的网络重试。已提供的官方摘要始终验证，缺失时明确标记首次 HTTPS 信任；后续摘要或 asset ID 不匹配不接受新值。旧 Lake 使用原生 `BuildTrace`，新版使用 `BuildMetadata`，只记录已获取发布物的依赖，不伪造证明构建成功。
