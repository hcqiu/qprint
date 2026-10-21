# Lean 文件格式

[返回格式总索引](index.md)

## 源码与项目结构

Lean 文件使用原生 Lean 4 语法，扩展名为 `.lean`，默认保存于工作区的 `lean/` 下。Qprint 不要求在 Lean 源码内添加 Blueprint 标记；节点与声明的关系写在 Blueprint 元数据中。

阅读源码和执行验证需要区分：源码文件及绑定足以尝试导航；通过 Qprint 构建则需要固定版本的 `lean-toolchain` 和 `lakefile.toml` 或 `lakefile.lean`。示例项目结构为：

```text
examples/format-demo/lean/Identity/
  lean-toolchain
  lakefile.toml
  Identity.lean
```

## 完整源码示例

保存为 `examples/format-demo/lean/Identity/Identity.lean`：

```lean
namespace Identity

def idNat (n : Nat) : Nat := n

theorem identity (n : Nat) : idNat n = n := by
  rfl

end Identity
```

`def` 定义函数，`theorem` 给出命题与证明；命名空间使两个声明的完整名称分别成为 `Identity.idNat` 和 `Identity.identity`。此例只使用 Lean 自带基础定义，不需要 mathlib。

## 项目配置示例

保存为 `examples/format-demo/lean/Identity/lean-toolchain`，内容只有一行：

```text
leanprover/lean4:v4.19.0
```

保存为 `examples/format-demo/lean/Identity/lakefile.toml`：

```toml
name = "identity_example"
version = "0.1.0"
defaultTargets = ["Identity"]

[[lean_lib]]
name = "Identity"
```

这里固定版本供示例使用。现有项目应保留自身精确版本与 Lake 依赖配置，不直接替换为本文版本。Qprint 不接受缺失或 `stable` / `nightly` 等浮动版本作为可复现验证配置；有外部依赖时保留 Lake 生成的 `lake-manifest.json`，不手写伪造的锁文件。

## Blueprint 绑定

将下列字段放入节点的 `qprint` 围栏：

```yaml
lean:
  - declaration: Identity.identity
    file: Identity/Identity.lean
```

`file` 相对工作区的 `lean/`；`declaration` 是 Lean 环境中的完整声明名，不是磁盘路径，也不必等于模块名。本例文件对应模块 `Identity`，声明则由源码中的 namespace 决定。

省略 `lines` 时，Qprint 通过逐行规则定位声明。复杂宏、多行声明头或歧义场景可添加 `lines: [5, 6]`，对应本例定理的两行；行号为从 1 开始的闭区间，编辑源码后应更新。行号只控制展示片段，不改变编译器中的声明查找。

## 验证入口

从 Qprint 根目录执行：

```powershell
.\.conda\python.exe -m qprint formal verify --project examples/format-demo/lean/Identity --language lean --offline
```

本例 `defaultTargets` 明确指定 `Identity` 库为默认构建目标。工作区内的 Blueprint 绑定验证使用总索引中的 `qprint verify`，会构建绑定模块并检查声明存在性。工具链未准备好时，离线命令报告缺失环境。

`sorry`、公理或不安全依赖的审计并不包含在当前声明存在性检查中；不要将“源码可定位”或“声明存在”写成完整的数学证明验收结论。自定义 Lake `srcDir` 或多项目配置见 [形式化验证](../formal-verification.md)。
