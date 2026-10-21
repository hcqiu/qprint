# Preimage composition
```qprint
kind: lemma
status: complete
lean:
  - declaration: Set.preimage_comp
    url: https://github.com/leanprover-community/mathlib4/blob/master/Mathlib/Data/Set/Preimage.lean
```
原像将函数复合反向变为集合操作的复合：$(g \circ f)^{-1}(S)=f^{-1}(g^{-1}(S))$。

# Associativity
```qprint
kind: lemma
status: complete
lean:
  - declaration: Qprint.composition_assoc
    file: Topology/Maps.lean
    lines: [6, 8]
```
函数复合满足结合律：$h\circ(g\circ f)=(h\circ g)\circ f$。在 Lean 中，这可以直接通过定义相等证明。
