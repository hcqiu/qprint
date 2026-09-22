# 资料导入模块

[中文](importers.md) | [English](importers.en.md) · [文档目录](index.md)

实现：[importers.py](../qprint/importers.py)。测试：[test_importers.py](../tests/test_importers.py)。CLI 与界面调用同一套导入器；HTTP 任务机制见 [API](server-api.md)。

## GitHub 仓库

接受公共 GitHub 仓库根地址，可带 `.git`，不接受 blob/tree 页面。branch、tag 或 SHA 使用独立 `ref`；省略时查询 GitHub 默认分支。无账户登录和私有仓库凭据流程。

```powershell
conda run -n qprint python -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace D:/my-math
```

归档展开到 `agda/serre-finiteness/`；`language` 也可为 lean 或 coq。保留整个仓库中的代码、许可证、配置及其他文件，不只筛选语言扩展名。返回 `path`、`files`、`ref`，并在目标目录写 `.qprint-source.json`，记录类型、URL、ref、解析出的完整 commit、归档 SHA-256 和 UTC 下载时间。

## arXiv 论文

接受新版/旧版 arXiv ID、可选版本后缀，以及 HTTPS abs/pdf/src/e-print URL。下载 PDF 与源码，源码支持 zip、tar/tar.gz、单个 gzip TeX 或 UTF-8 TeX。

```powershell
conda run -n qprint python -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace D:/my-math
```

结果为 `pdf/Geometry/Via16SpherePacking.pdf` 和 `tex/Geometry/Via16SpherePacking/`。多文件源码保留内部相对目录；源码目录含来源记录。返回 `pdf`、`tex`、`files`、`id`。`name` 只填 basename，不含目录或 `.pdf` 后缀；`dest` 可为空字符串以使用根分类。

必须同时得到有效 PDF 和含 `.tex` 的源码，错误页面、缺失源码或不支持内容会失败。导入不生成 Markdown、不插入 `\bpnode`，论文导入也不执行代码或安装依赖；之后需要人工建立节点和绑定。

## 下载、归档与发布

| 限制 | 当前规则 |
| --- | --- |
| 网络 | HTTPS、无 URL 用户凭据、仅默认端口/443；每次跳转校验来源 |
| 下载域 | api.github.com、codeload.github.com、github.com、arxiv.org、export.arxiv.org |
| HTTP | 连接超时 30 秒、读取闲置超时 20 秒；最多三次尝试、有限重定向；有强 ETag 时验证后续传，不是总任务期限 |
| 下载量 | 每次响应最多 100 MiB |
| 解压量 | 每份归档最多 300 MiB、10,000 个条目（含目录） |
| 归档路径 | 拒绝越界、Windows 特殊路径、大小写冲突和重复路径 |
| 归档类型 | 拒绝符号链接、硬链接、设备及其他特殊文件 |
| 目标 | 已存在则拒绝覆盖；`.qprint-source.json` 是保留来源文件名 |

下载内容先进入工作区内 `.qprint-import-*` 暂存目录，经校验后发布。GitHub 去掉单一归档顶层目录；论文保留内部结构。论文两种资料都验证后先发布 TeX，再发布 PDF；后一步失败时回退本次 TeX，正常退出清理暂存。

这是应用级暂存与回退，不保证进程崩溃时的跨文件原子提交。下载先流式暂存，导入归档随后读入内存，单次限额不等于整个工作区或进程的累计配额。

## 故障处理与验证

目标已存在时选择新目录或论文名；瞬时网络错误自动有限重试，仍失败时检查连接后再重试；源站没有源码时需另找合法来源。任务失败查看 job 的 `error`，202 不代表导入完成。不会在失败后自动无限重试。

单元测试使用注入的下载器，不依赖真实网络。`tools/smoke_imports.py` 是另外的网络冒烟工具，会实际下载公开样例并写入 `.qprint/`；历史结果见[验收记录](verification.md)。来源记录只记录下载来源，不证明仓库内容正确或可编译。


## 下载后验证（默认开启）

界面复选框和 API `verify_after_download` 默认 `true`；CLI 提供 `--verify-after-download` / `--no-verify-after-download`。发布源码后发现原生 Lean/Agda 项目，补齐受支持的固定环境并检查上游入口。启用此项会执行下载项目的工具链与构建配置。`--timeout` 默认 600 秒，`--toolchain-home` 指定 store；`--offline` 禁止验证阶段下载环境，但源码下载仍使用网络。Coq 返回 `unsupported`。

下载成功和验证状态分开：返回 `verification.status`、`verification.reports`。检查失败仍保留源码和带时间戳的报告。启用验证时 CLI 仅在验证通过后返回 0，否则返回 1；关闭验证且导入成功则返回 0、`not_run`。导入 job 以 `phase: downloading/verifying` 显示阶段，`succeeded` 表示导入完成、结果可用，不能据此认定证明检查通过。独立的手动 Blueprint 验证 API 仍需 `--allow-verification`；下载开关在导入请求中单独选择执行。


## 等待期间的进度

导入任务提供 `progress`：当前下载文件、已接收/总字节（服务器提供长度时）、解压项数、依赖序号，以及 mathlib 缓存或 Lake 构建阶段。工具链运行期间提供输出字节数；界面显示任务总耗时。未知总量时不显示百分比。阶段切换立即更新，其余更新最多每秒一次；客户端仍通过 job API 轮询。

源码下载完成后可能还需首次安装数百 MiB 的编译器、获取依赖和编译缓存。`timeout` 是准备命令和检查的阶段预算，不是整个下载任务的总期限；工具链获取使用独立网络超时。默认 600 秒不表示整个任务必定在十分钟内结束。参见 [sphere-eversion 实测](sphere-eversion-experiment.md)。


## 查看失败报告

导入结果直接显示每个项目的状态、错误原因、“查看错误/验证报告”和“下载完整 JSON”。“查看历史验证报告”从磁盘读取当前工作区最近 30 份报告，服务重启后仍可查看。报告路径也以文本保留，便于交给 helper。导入、发现或单个验证流程意外抛错时尽量保存独立失败报告；报告写入失败会明确显示 `report_error`，不再只提示“见报告”。多项目仓库的单个失败不会丢掉其他项目的结果。
