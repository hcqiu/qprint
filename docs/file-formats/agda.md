# Agda 文件格式

[返回格式总索引](index.md)

## 源码与模块

Agda 文件使用原生语法，常规扩展名为 `.agda`，默认保存于工作区的 `agda/` 下。模块名与相对于源码搜索根目录的路径对应：`Identity.agda` 声明 `module Identity where`；若文件为 `Algebra/Identity.agda`，则声明 `module Algebra.Identity where`。

Qprint 不要求在 Agda 源码内插入 Blueprint 标记。推荐使用清晰的顶层类型签名和定义，便于导航器定位声明。

```text
examples/format-demo/agda/Identity/
  identity.agda-lib
  .qprint-formal.yaml
  Identity.agda
```

## 完整源码示例

保存为 `examples/format-demo/agda/Identity/Identity.agda`：

```agda
{-# OPTIONS --safe #-}
module Identity where

open import Agda.Builtin.Nat using (Nat)
open import Agda.Builtin.Equality using (_≡_; refl)

idNat : Nat → Nat
idNat n = n

identity : (n : Nat) → idNat n ≡ n
identity n = refl
```

签名 `identity : ...` 给出命题，`identity n = refl` 给出证明；`idNat n` 归约为 `n`，因此可使用自反性。本例只导入编译器内置模块，不需要 Agda 标准库或 Cubical 库。Unicode 数学符号保存在 UTF-8 文件中，文件名和目录名仍为英文。

## 项目配置示例

保存为 `examples/format-demo/agda/Identity/identity.agda-lib`：

```text
name: identity-example
include: .
```

`include: .` 表示模块从当前项目根目录查找。若采用 `src/`，模块路径应相对该源码根，并在 Qprint 工作区验证配置中同步 `source_root`，见 [形式化验证配置](../formal-verification.md)。

保存为 `examples/format-demo/agda/Identity/.qprint-formal.yaml`：

```yaml
toolchain:
  agda: "2.8.0"
dependencies: {}
policy:
  safe: inherit
  mode: standard
```

`.agda-lib` 提供原生 include、depend 和模块选项，但通常不固定编译器版本；`.qprint-formal.yaml` 补充精确版本与 Qprint 验证策略。旧式 `project.yaml` 仍可兼容，新增项目推荐使用上面的配置。

`safe` 接受 `inherit`、`require`、`off`：默认 `inherit` 保留源码原有策略，本例源码自身开启 `--safe`；`require` 显式要求安全检查，`off` 也不会撤销源码里的 `--safe`。`mode` 接受 `standard`、`cubical`、`erased-cubical`，应与实际源码和库要求一致。

使用外部库时，在 `.agda-lib` 中声明真实依赖，并在元数据中固定受支持依赖的精确 `version` 或完整 40 字符提交 `revision`，二选一。Cubical 项目还需保留其原生 OPTIONS；不要把本例 `standard` 配置直接套到 Cubical 源码上。更多示例见 [项目配置解析](../formal-resolution.md)。

## Blueprint 绑定

将下列字段放入节点的 `qprint` 围栏：

```yaml
agda:
  - declaration: Identity.identity
    file: Identity/Identity.agda
```

`file` 相对工作区的 `agda/`；`Identity/` 外层目录是项目目录，模块仍叫 `Identity`，声明名不是 `Identity.Identity.identity`。

不填 `lines` 时，导航器扫描顶层 `名称 : 类型` 签名；需要精确截取时可加 `lines: [10, 11]`，对应本例定理的签名与定义。行号控制显示，无法替代 Agda 类型检查或导出名称检查。复杂嵌套、参数化模块、特殊语法或私有声明可能不适合当前公共声明探针。

## 验证入口与文学化源码

从 Qprint 根目录执行：

```powershell
.\.conda\python.exe -m qprint formal verify --project examples/format-demo/agda/Identity --language agda --entry Identity.agda --offline
```

`--entry` 相对项目根目录，Agda 检查目标模块及其导入依赖，不生成可执行程序。工作区内节点绑定的验证使用总索引中的 `qprint verify`。只有配置解析成功不代表类型检查成功。

Qprint 也识别 `.lagda`、`.lagda.tex`、`.lagda.md`、`.lagda.rst`、`.lagda.org` 和 `.lagda.typ`；这些文件仍须遵守相应 Agda 文学化语法。完整后缀会从模块名中去除，例如 `Identity.lagda.md` 对应 `Identity`。本说明文件 `agda.md` 只是格式文档，不是 Agda 文学化源码。新建最小项目时使用上面的普通 `.agda` 示例即可。
