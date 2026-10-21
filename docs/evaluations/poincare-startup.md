# Poincare-QPrint 启动性能优化

日期：2026-10-14。工作区为已转换的 `Poincare-QPrint/`，含 9,947 个节点、10,625 条已解析依赖和 23,563 个 Lean 文件。

## 本机对比

使用项目 `.conda`，在普通 Windows 环境、已有 Navigator 索引且源文件未改变的条件下比较。计时范围是 `Workspace` 初始化和 `KnowledgeIndexer.update()`，对应 `serve` 在提供服务前执行的主要工作；不包含解释器导入时间、浏览器渲染或首次创建索引。

| 阶段 | 优化前 | 优化后 |
| --- | ---: | ---: |
| 工作区、图谱、复制上下文 | 23.16 秒 | 3.81 秒 |
| Navigator 增量检查 | 5.24 秒 | 0.81 秒 |
| 合计 | **28.40 秒** | **4.61 秒** |

本次测量约加速 **6.2 倍**。两次的 `parsed_files` 均为 0。不同机器、磁盘缓存、源文件变更及首次建立索引会影响耗时。

沙箱内另一次对比为 64.81 秒 → 6.41 秒；Windows 沙箱显著放大了旧实现的路径解析开销，因此用户侧参考上表的普通本机结果。

## 改动

- 每个 Workspace 快照建立 `NodeLookup`，按标题、TeX 标签和文件简称索引候选节点。TeX 依赖解析不再逐条遍历全部节点；同论文优先、已声明依赖优先和歧义处理顺序保持不变。每次 reload 重新建立索引。
- Navigator 使用 `os.scandir` 遍历已经校验的目录，普通文件继承父目录的路径边界检查。仍校验文件名；符号链接文件和目录 junction 额外解析真实路径，拒绝越界或 junction 循环。继续扫描所有支持的源文件，不跳过未绑定的 Lean 文件。
- 无变更时复用序列化的源缓存，只在实际重建索引贡献时解码。文件变更、删除、显式哈希校验和索引版本更新仍按原规则触发更新。

## 验证

优化前后逐项比较整个工作区的 `project()`、全部复制上下文、TeX 定位和导航顺序，结果完全相同。现有索引检查报告 `parsed_files: 0`、`updated_nodes: 0`、`updated_chunks: 0`。

```powershell
.\.conda\python.exe -X utf8 -m pytest tests/test_startup_performance.py tests/test_clipboard_context.py tests/test_blueprint.py tests/test_knowledge.py tests/test_knowledge_runtime.py tests/test_workspace_api.py tests/test_tex_to_blueprint.py -q
```

结果：**73 passed，1 skipped**。跳过项为本机不支持创建符号链接的既有测试；新增 Windows junction 的内部路径和越界检查均通过。测试还覆盖解析结果等价、查找不再全量扫描、缓存更新、API 刷新和技能便携运行时同步。

## 使用

停止原服务后重新运行相同命令即可，无需删除或重建工作区：

```powershell
.\.conda\python.exe -m qprint serve --workspace Poincare-QPrint --port 8765
```
