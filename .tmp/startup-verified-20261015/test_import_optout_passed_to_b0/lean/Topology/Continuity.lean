import Mathlib.Topology.Basic

namespace Qprint

theorem identity_continuous {X : Type*} [TopologicalSpace X] :
    Continuous (fun x : X => x) := continuous_id

theorem composition_continuous {X Y Z : Type*}
    [TopologicalSpace X] [TopologicalSpace Y] [TopologicalSpace Z]
    {f : X → Y} {g : Y → Z} (hf : Continuous f) (hg : Continuous g) : Continuous (g ∘ f) := hg.comp hf

end Qprint
