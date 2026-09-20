# 工作区与文件模块

[中文](workspace.md) | [English](workspace.en.md) · [文档目录](index.md)

实现：[workspace.py](../qprint/workspace.py)、[paths.py](../qprint/paths.py)。测试：[test_workspace_api.py](../tests/test_workspace_api.py)。

## 文件布局与路径

```text
my-math/
  blueprint/Topology/Notes.md
  tex/Topology/Notes.tex
  pdf/Topology/Notes.pdf
  lean/Topology/Notes.lean
  agda/Topology/Notes.agda
  coq/Topology/Notes.v
```

这些目录允许缺失或为空，节点不必绑定论文或代码。服务加载指定工作区，默认是当前目录下的 `examples/demo`。Markdown 与 TeX 使用相同相对路径时可用标签简写；不同位置应显式填写绑定路径。

Blueprint 文件路径相对 `blueprint/`，TeX 路径相对 `tex/`，代码路径相对其语言目录。API 和元数据使用 `/`，不使用 Windows 反斜杠；本地 CLI 的工作区根路径可用 `D:/my-math`。

`safe_path(root, relative)` 拒绝空路径、绝对路径、`.` / `..` 段、反斜杠、Windows drive/ADS、保留名、非法字符和末尾点/空格，并检查解析符号链接后的路径仍在指定根目录内。`read_text` 读取 UTF-8（允许 BOM），单文件上限 5 MiB。

## 索引与诊断

`Workspace(root)` 初始化时调用 `reload()`。重建时扫描 Markdown 和 TeX，解析节点，建立关系、TeX 位置与论文内阅读顺序，再生成[分级图谱索引](graph.md)。空文件也保留在文件图中。

`project()` 返回节点、边、论文目录、分级图谱、诊断和统计；`detail(id)` 返回正文 HTML、代码切片、TeX 渲染/源文、前后节点、关系和反向引用。未绑定论文的节点仍可阅读，但不参与论文内前后导航。

不存在或歧义的节点引用产生 warning；非法节点、读文件失败、重复 TeX 标签或缺失 TeX 绑定产生 error。代码定位问题在节点详情中报告。CLI `check` 有 error 时退出 1，仅 warning 时退出 0；它不是形式化编译或所有详情渲染的全面检查。

## 保存协议

1. `document(path)` 返回当前文本和 SHA-256 `revision`，只接受既有 `.md` 文件。
2. `save_document(path, text, expected)` 比较磁盘当前版本；不一致返回冲突。
3. 检查 UTF-8 字节数和节点解析 error；通过后写同目录临时文件。
4. 再检查版本，使用 `os.replace` 替换目标，清理临时文件并重建索引。

保存返回新的文本和版本。它校验语法，但不会禁止所有未解析链接或缺失 TeX 绑定；这些会在重建后显示诊断。API 对冲突使用 409，其他工作区校验错误使用 400。

进程内 `RLock` 串行保护工作区操作；外部编辑器不持有该锁。因此版本比较可检测已发生的外部修改，但最后比较与替换之间仍不是跨进程原子比较交换。

## 缓存与维护

TeX 渲染按节点惰性缓存，每次 reload 全部失效。文件没有自动监听；外部修改后点击刷新或调用 reload。新建、删除、移动文件使用外部工具。索引全部存内存，重启后从文件恢复，无需数据库迁移。
