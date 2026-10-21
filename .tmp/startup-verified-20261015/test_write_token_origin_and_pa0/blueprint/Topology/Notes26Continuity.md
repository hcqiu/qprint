# Identity map
```qprint
kind: definition
status: complete
tex: Topology/Notes26Continuity#identity
lean:
  - declaration: Qprint.identity
    file: Topology/Maps.lean
    lines: [4, 4]
agda:
  - declaration: identity
    file: Topology/Maps.agda
    lines: [3, 4]
coq:
  - declaration: identity
    file: Topology/Maps.v
    lines: [1, 1]
```
恒等映射是最简单的结构保持映射。一个节点可以同时绑定 Lean、Agda 和 Coq 的实现；点击右侧标签可切换语言。

# Continuity of the identity
```qprint
kind: theorem
status: complete
tex: Topology/Notes26Continuity#continuous-id
uses:
  - "[[#Identity map]]"
  - "[[Topology/Maps#Continuous]]"
lean:
  - declaration: Qprint.identity_continuous
    file: Topology/Continuity.lean
    lines: [5, 6]
```
恒等映射保持每一个开集的原像，因此连续。这个简单的事实是构建拓扑空间范畴的起点。

# Composition of continuous maps
```qprint
kind: theorem
status: complete
tex: Topology/Notes26Continuity#continuous-comp
uses:
  - "[[Topology/Maps#Continuous]]"
inspired_by:
  - "[[#Continuity of the identity]]"
lean:
  - declaration: Qprint.composition_continuous
    file: Topology/Continuity.lean
    lines: [8, 10]
```
连续映射在复合下封闭。先取 $g$ 的原像，再取 $f$ 的原像，便得到复合映射的原像。

# Composition proof
```qprint
kind: proof
status: in_progress
tex: Topology/Notes26Continuity#composition-proof
uses:
  - "[[#Composition of continuous maps]]"
  - "[[Algebra/Functions#Preimage composition]]"
```
以开集原像为主线的证明。当前仅绑定非形式化说明，独立的形式化证明尚待补充。

# Topological spaces form a category
```qprint
kind: theorem
status: not_started
tex: Topology/Notes26Continuity#top-category
uses:
  - "[[#Continuity of the identity]]"
  - "[[#Composition of continuous maps]]"
  - "[[Algebra/Functions#Associativity]]"
```
以拓扑空间为对象、连续映射为态射，恒等映射与函数复合给出一个范畴。这一节点尚未绑定形式化代码。
