# 形式化代码定位模块

[中文](formal-code.md) | [English](formal-code.en.md) · [文档目录](index.md)

实现：[formal.py](../qprint/formal.py)。测试：[test_tex_formal.py](../tests/test_tex_formal.py)。本模块读取源码片段，不编译或执行证明。

## 绑定写法

在节点 `qprint` 元数据中填写语言字段，例如：

```yaml
lean:
  - declaration: Topology.identity_continuous
    file: Topology/Continuity.lean
    lines: [5, 9]
  - declaration: External.some_theorem
    url: https://github.com/owner/repo/blob/main/SomeFile.lean
agda: Topology.Maps.identity
coq:
  declaration: identity_continuous
  file: Topology/Maps.v
```

以上路径和行号仅说明格式。`file` 分别相对工作区 `lean/`、`agda/`、`coq/`；并非相对 blueprint 文件。允许一个节点绑定多个语言和多个声明。`lines` 为一基闭区间。

## 定位顺序

`locate_code(root, binding)` 返回原绑定字段以及 `code`、`error`；成功时补全 `file` 和 `lines`。

1. 有 `file` 时直接使用；否则按声明名的点分段，从长到短尝试模块路径和语言扩展名。
2. 有显式 `lines` 时直接切片，并检查是否超出文件范围。行号优先，不再次验证这段文本是否匹配声明名。
3. 没有行号时扫描声明，先找精确限定名，再尝试唯一的末段名称；多个候选或无候选都报错。
4. 从声明起点截取到下一个声明或语言特定结束边界，清除末尾空行。

| 语言 | 扩展名 | 启发式支持 |
| --- | --- | --- |
| Lean | `.lean` | namespace 及常见 def/theorem/lemma/structure/inductive/class 等声明；end/namespace/section 边界 |
| Agda | `.agda` | 顶层 `名称 : 类型` 签名 |
| Coq | `.v` | Definition/Theorem/Lemma/Fixpoint/Inductive 等；Qed/Defined/Admitted 结束 |

这些是逐行规则，不是完整语法树。复杂缩进、多行声明、宏生成、嵌套作用域或重载应填写明确的文件与行号。

## 远程与错误

绑定可以只含 `declaration` 和 HTTPS `url`；本地无法找到文件时返回远程未下载提示，界面提供来源链接，不自动抓取网页或单个声明。需要本地源码时可使用[仓库导入](importers.md)。

文件缺失、读取失败、越界行号和歧义都返回 `code: null` 与错误说明，不将整个文件冒充已定位声明。路径经过工作区边界校验。即使找到片段，也不意味着声明通过 Lean / Agda / Coq 编译；节点 `status` 不会因此自动变化。
