# Tools

## Formal Blueprint Project to QPrint

将已有的 LaTeX Blueprint 与 Lean 工程转换为独立的 Qprint 工作区。

在 Qprint 根目录运行，两个必填参数依次为**源工程地址**与**输出文件夹名字**：

```powershell
.\.conda\python.exe tools/formal_blueprint_project_to_qprint.py https://github.com/frenzymath/Poincare-Conjecture Poincare-QPrint
```

支持本地目录、zip/tar、GitHub 仓库根地址。目标文件夹必须不存在。
工具保留 `\label`、`\uses` 和 Lean 源码，添加同名 `\bpnode`，从 `\lean` 生成声明、文件和行号绑定；没有 `\bpdesc` 就不生成描述。

用法、输出结构及限制见 [工具说明](../docs/formal-blueprint-project-to-qprint.md)。
