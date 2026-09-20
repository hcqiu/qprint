# 资料导入模块

[中文](importers.md) | [English](importers.en.md) · [文档目录](index.md)

实现：[importers.py](../qprint/importers.py)。测试：[test_importers.py](../tests/test_importers.py)。CLI 与界面调用同一套导入器；HTTP 任务机制见 [API](server-api.md)。

## GitHub 仓库

接受公共 GitHub 仓库根地址，可带 `.git`，不接受 blob/tree 页面。branch、tag 或 SHA 使用独立 `ref`；省略时查询 GitHub 默认分支。无账户登录和私有仓库凭据流程。

```powershell
conda run -n qprint python -m qprint import-code https://github.com/CMU-HoTT/serre-finiteness --language agda --dest serre-finiteness --workspace D:/my-math
```

归档展开到 `agda/serre-finiteness/`；`language` 也可为 lean 或 coq。保留整个仓库中的代码、许可证、配置及其他文件，不只筛选语言扩展名。返回 `path`、`files`、`ref`，并在目标目录写 `.qprint-source.json`，记录类型、URL、ref 和 UTC 下载时间。

## arXiv 论文

接受新版/旧版 arXiv ID、可选版本后缀，以及 HTTPS abs/pdf/src/e-print URL。下载 PDF 与源码，源码支持 zip、tar/tar.gz、单个 gzip TeX 或 UTF-8 TeX。

```powershell
conda run -n qprint python -m qprint import-paper 1603.04246 --dest Geometry --name Via16SpherePacking --workspace D:/my-math
```

结果为 `pdf/Geometry/Via16SpherePacking.pdf` 和 `tex/Geometry/Via16SpherePacking/`。多文件源码保留内部相对目录；源码目录含来源记录。返回 `pdf`、`tex`、`files`、`id`。`name` 只填 basename，不含目录或 `.pdf` 后缀；`dest` 可为空字符串以使用根分类。

必须同时得到有效 PDF 和含 `.tex` 的源码，错误页面、缺失源码或不支持内容会失败。导入不生成 Markdown、不插入 `\bpnode`，也不执行代码或安装依赖；之后需要人工建立节点和绑定。

## 下载、归档与发布

| 限制 | 当前规则 |
| --- | --- |
| 网络 | HTTPS、无 URL 用户凭据、仅默认端口/443；每次跳转校验来源 |
| 下载域 | api.github.com、codeload.github.com、github.com、arxiv.org、export.arxiv.org |
| HTTP | httpx 超时配置 60 秒；重定向有次数上限，不是整个任务的统一 60 秒期限 |
| 下载量 | 每次响应最多 100 MiB |
| 解压量 | 每份归档最多 300 MiB、10,000 个条目（含目录） |
| 归档路径 | 拒绝越界、Windows 特殊路径、大小写冲突和重复路径 |
| 归档类型 | 拒绝符号链接、硬链接、设备及其他特殊文件 |
| 目标 | 已存在则拒绝覆盖；`.qprint-source.json` 是保留来源文件名 |

下载内容先进入工作区内 `.qprint-import-*` 暂存目录，经校验后发布。GitHub 去掉单一归档顶层目录；论文保留内部结构。论文两种资料都验证后先发布 TeX，再发布 PDF；后一步失败时回退本次 TeX，正常退出清理暂存。

这是应用级暂存与回退，不保证进程崩溃时的跨文件原子提交。下载与归档在内存中处理，单次限额不等于整个工作区或进程的累计配额。

## 故障处理与验证

目标已存在时选择新目录或论文名；网络错误时检查连接并手动重试；源站没有源码时需另找合法来源。任务失败查看 job 的 `error`，202 不代表导入完成。不会在失败后自动无限重试。

单元测试使用注入的下载器，不依赖真实网络。`tools/smoke_imports.py` 是另外的网络冒烟工具，会实际下载公开样例并写入 `.qprint/`；历史结果见[验收记录](verification.md)。来源记录只记录下载来源，不证明仓库内容正确或可编译。
