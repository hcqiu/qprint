namespace Qprint

-- The identity function, independent of topology.
def identity {A : Type} (x : A) : A := x

theorem composition_assoc {A B C D : Type}
    (f : A → B) (g : B → C) (h : C → D) :
    (fun x => h (g (f x))) = (fun x => (h ∘ g) (f x)) := rfl

end Qprint
