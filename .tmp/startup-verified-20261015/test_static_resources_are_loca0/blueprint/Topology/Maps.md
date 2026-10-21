# Continuous
```qprint
kind: definition
status: complete
lean:
  - declaration: Continuous
    url: https://github.com/leanprover-community/mathlib4/blob/master/Mathlib/Topology/Defs/Basic.lean
```
连续映射把开集的原像保持为开集。这是连接空间结构与函数行为的基本语言。

对于拓扑空间 $X$ 和 $Y$，映射 $f : X \to Y$ 连续，当且仅当每个开集 $V \subseteq Y$ 的原像 $f^{-1}(V)$ 在 $X$ 中是开的。

# Homeomorphism
```qprint
kind: definition
status: not_started
uses:
  - "[[#Continuous]]"
```
同胚是一个连续双射，其逆映射也连续。它表达两个拓扑空间具有相同的拓扑结构。

# Homotopy
```qprint
kind: definition
status: in_progress
uses:
  - "[[#Continuous]]"
inspired_by:
  - "[[#Homeomorphism]]"
```
同伦是一族连续变化的映射。给定 $f,g:X\to Y$，同伦 $H:X\times[0,1]\to Y$ 连接 $f$ 和 $g$。
