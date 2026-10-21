# Formal Blueprint Project to QPrint：Poincare 实测

日期：2026-10-14。

来源：[frenzymath/Poincare-Conjecture](https://github.com/frenzymath/Poincare-Conjecture)，含主证明工程与参考书 Blueprint。使用 GitHub 下载的 `main` 源码 zip；归档注释中的 revision 为 `432c38f2aa5a30efb13871292d17b4a3309a496a`，归档 SHA-256 为 `8fd95eaacda9c089c9059feed002d06b8dd6747bffbfd440a075b6b14367129f`。

本地命令（均从 Qprint 根目录执行）：

```powershell
.\.conda\python.exe -X utf8 tools/formal_blueprint_project_to_qprint.py .qprint/import-sources/Poincare-Conjecture.zip Poincare-QPrint
.\.conda\python.exe -X utf8 tools/smoke_formal_blueprint.py .qprint/import-sources/Poincare-Conjecture.zip Poincare-QPrint
```

也可直接从仓库地址固定同一 revision，使用新的输出目录：

```powershell
.\.conda\python.exe tools/formal_blueprint_project_to_qprint.py https://github.com/frenzymath/Poincare-Conjecture Poincare-Review --ref 432c38f2aa5a30efb13871292d17b4a3309a496a
```

## 结果

| 检查 | 结果 |
| --- | --- |
| Blueprint TeX | 252 个文件 |
| 保留 `\label` | 9,948 次，参数和命令原文未变 |
| 保留 `\uses` | 6,380 次，命令原文未变 |
| 保留 `\lean` | 346 次，命令原文未变；含多声明绑定 |
| 新增 `\bpnode` / Markdown 节点 | 9,947 个 |
| Blueprint 节点文件 | 223 份 Markdown；另有各项目索引 |
| 主工程章节 | 原有 18 章全部保留 |
| Markdown 依赖 | 10,643 条，其中 10,625 条解析成功 |
| Lean 绑定 | 388 个，其中 387 个生成文件和行号，均可由 Qprint 读取 |
| Lean 源码完整性 | 23,563 个文件逐字节相同 |
| 描述 | 原文无 `\bpdesc`，生成节点正文全部留空 |
| Qprint Workspace | 无 error，18 条 warning 为未解析的源依赖 |
| 逐文件核对脚本 | 成功，`errors: []` |
| 相关自动化测试 | 71 passed |

测试覆盖转换器、归档导入、Blueprint 解析、TeX/形式化代码定位及原有 TeX 转 Blueprint 流程。生成工作区保存在 `Poincare-QPrint/`，已加入 Git 忽略规则；下载缓存保存在 `.qprint/`。这两个目录不作为源码提交内容。

## 保留的源数据问题

`Poincare-QPrint/conversion-report.json` 中共 30 项诊断：

- 1 个 Lean 声明存在两个候选文件：`PoincareMT.m65Projection_tangentNorm_le`，分别位于 `Deformation/Limit/Projection/Speed.lean` 和 `Deformation/Transfer/ProjectedLength.lean`。保留声明名及候选位置，未任意选择其一。
- 1 个 Morgan–Tian 参考 Blueprint label 中含换行，无法原样成为 Qprint 节点；原 `\label` 保留，不更名。因此节点数比 label 数少 1。
- 10 处 Lee 参考书的 `\uses` 中写的是 `\cite` / `\dcref` 宏，不是节点名。TeX 原文保留，未生成非法 wikilink。
- 18 个依赖目标无法解析，主要是源文件已有的 `UNRESOLVED:` / `REF:` 占位引用。Markdown 保留未解析链接。

逐文件核对报告为 `Poincare-QPrint/validation-report.json`。测试没有执行 Lean 编译器，也没有运行仓库脚本；这里的成功指文件转换、源码保留和 Qprint 导航通过检查。
