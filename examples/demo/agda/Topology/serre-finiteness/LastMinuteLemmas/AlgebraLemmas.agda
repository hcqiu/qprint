{-# OPTIONS --lossy-unification --safe #-}
{-
For n : ℤ, ℤ/nℤ can be defined as Fin (abs n) or as a quotient
group ℤ/im(n·_). This module proves the two definitions equivalent.

It also contains a proof that ℤ[Fin n] is ℤ̂ⁿ
-}
module LastMinuteLemmas.AlgebraLemmas where

open import Cubical.Foundations.Prelude
open import Cubical.Foundations.Isomorphism
open import Cubical.Foundations.Function

open import Cubical.Data.Nat renaming (_·_ to _·ℕ_ ; _+_ to _+ℕ_)
open import Cubical.Data.Nat.Mod
open import Cubical.Data.Sigma
open import Cubical.Data.Int
open import Cubical.Data.Empty as ⊥
open import Cubical.Data.FinData
open import Cubical.Data.Fin renaming (Fin to FinInd)
open import Cubical.Data.Fin.Arithmetic
open import Cubical.Data.Nat.Order

open import Cubical.Algebra.AbGroup.Instances.IntMod
open import Cubical.Algebra.AbGroup.Instances.Int
open import Cubical.Algebra.AbGroup.Base
open import Cubical.Algebra.AbGroup.Properties
open import Cubical.Algebra.AbGroup.Instances.FreeAbGroup

open import Cubical.Algebra.Group.Base
open import Cubical.Algebra.Group.Properties
open import Cubical.Algebra.Group.Morphisms
open import Cubical.Algebra.Group.MorphismProperties
open import Cubical.Algebra.Group.Instances.IntMod
open import Cubical.Algebra.Group.ZAction

open import Cubical.HITs.SetQuotients as SQ renaming ([_] to [_]')
open import Cubical.HITs.PropositionalTruncation as PT

open import Cubical.Data.Fin as FinAlt
  renaming (fsuc to fsuc* ; fzero to fzero* ; flast to flast*)

open Iso

--------------- Preliminaries ---------------
-- Elimination principle for G /Im ϕ
/ImElim : ∀ {ℓ ℓ'} {G : Group ℓ} {H : AbGroup ℓ} {R : Group ℓ'}
  (ϕ : GroupHom G (AbGroup→Group H))
  (f : GroupHom (AbGroup→Group H) R)
  → compGroupHom ϕ f ≡ trivGroupHom
  → GroupHom (AbGroup→Group (H /Im ϕ)) R
fst (/ImElim {H = H} {R = R} ϕ f p) =
  SQ.rec (GroupStr.is-set (snd R)) (fst f)
    λ x y → PT.rec (GroupStr.is-set (snd R) _ _)
      λ {(g , q) → sym (GroupStr.·IdR (snd R) (fst f x))
         ∙ cong₂ (GroupStr._·_ (snd R)) refl
                 (sym ((GroupStr.·InvL (snd R)) (fst f y)))
         ∙ GroupStr.·Assoc (snd R) (fst f x) _ (fst f y)
         ∙ cong₂ (GroupStr._·_ (snd R))
            (cong₂ (GroupStr._·_ (snd R)) refl
              (sym (IsGroupHom.presinv (snd f) y))
            ∙ sym (IsGroupHom.pres· (snd f) x (AbGroupStr.-_ (snd H) y))) refl
        ∙ sym (cong (λ s → GroupStr._·_ (snd R) s (fst f y))
                    (sym (funExt⁻ (cong fst p) g) ∙ cong (fst f) q))
        ∙ (GroupStr.·IdL (snd R)) (fst f y)}
snd (/ImElim {H = H} {R = R}  ϕ f p) =
  makeIsGroupHom
    (SQ.elimProp2 (λ _ _ → GroupStr.is-set (snd R) _ _)
    (IsGroupHom.pres· (snd f)))

-- some modular arithmetic lemmas
-ₘ-fzero : (n : ℕ) → -ₘ_ {n = n} fzero* ≡ fzero*
-ₘ-fzero n = sym (+ₘ-lUnit (-ₘ_ {n = n} fzero*))
           ∙ +ₘ-rCancel {n = n} fzero*

0mod : (n : ℕ) → zero mod n ≡ 0
0mod zero = refl
0mod (suc n) = refl

open import Cubical.Data.Nat.Order.Inductive

upstream1 : {m n : ℕ} → m < suc n → m ≤ n
upstream1 h .fst = fst h
upstream1 {m} h .snd = cong predℕ (sym (+-suc (h .fst) m) ∙ snd h)

upstream2 : {m n : ℕ} → m ≤ n → m < suc n
upstream2 h .fst = h .fst
upstream2 h .snd = +-suc _ _ ∙ cong suc (h .snd)

-ₘ< : ∀ {n : ℕ} (x : ℕ) (y : suc x <ᵗ suc n)
  → fst (-ₘ (suc x , y)) ≡ n ∸ x
-ₘ< {n = n} x t = goal
  where
  goal : (n ∸ x) mod (suc n) ≡ n ∸ x
  goal = <→mod≡id (n ∸ x) (suc n) (upstream2 (∸-≤ n x))

--------------- Part 1: Equivalence of both definitions of ℤ/k ---------------
-- Definition of ℤ/im(n·_)
ℤAbGroup/' : ℤ → AbGroup ℓ-zero
ℤAbGroup/' x = ℤAbGroup /Im multₗHom ℤAbGroup x

-- n mod k for n an integer
_modℤ_ : (n : ℤ) (k : ℕ) → FinAlt.Fin (suc k)
pos n modℤ k = n mod (suc k) , <→<ᵗ (mod< k n)
negsuc n modℤ k = -ₘ (pos (suc n) modℤ k)

-- ℤ → ℤ/k
ℤ→ℤAbGroup/ : (k : ℕ) → ℤ → fst (ℤAbGroup/ k)
ℤ→ℤAbGroup/ zero x = x
ℤ→ℤAbGroup/ (suc k) x = x modℤ k

-- A bunch of basic properties of ℤ→ℤAbGroup/ (culminating in
-- a proof that it is a group homomorphism)
module ℤ→ℤAbGroup/Lemmas where
  ℤ→ℤAbGroup/Vanish-pos : (x : ℕ) (y : ℤ)
    → ℤ→ℤAbGroup/ x (pos x · y) ≡ GroupStr.1g (snd (ℤGroup/ x))
  ℤ→ℤAbGroup/Vanish-pos zero y = refl
  ℤ→ℤAbGroup/Vanish-pos (suc n) (pos k) =
    cong (_modℤ n) (sym (pos·pos (suc n) k) ∙ cong pos (·-comm (suc n) k))
    ∙ Σ≡Prop (λ _ → isProp<ᵗ) (zero-charac-gen (suc n) k)
  ℤ→ℤAbGroup/Vanish-pos (suc n) (negsuc r) =
    cong (_modℤ n) (pos·negsuc (suc n) r
                   ∙ sym (cong -_ (pos·pos (suc n) (suc r))))
    ∙ cong (-ₘ_ {n = n}) (Σ≡Prop (λ _ → isProp<ᵗ)
         {u = pos (suc n ·ℕ suc r) modℤ n} {v = fzero*}
         (cong (_mod (suc n)) (·-comm (suc n) (suc r))
         ∙ zero-charac-gen (suc n) (suc r)))
    ∙ -ₘ-fzero n

  ℤ→ℤAbGroup/Vanish : (x y : ℤ)
    → ℤ→ℤAbGroup/ (abs x) (x · y) ≡ GroupStr.1g (snd (ℤGroup/ abs x))
  ℤ→ℤAbGroup/Vanish (pos n) y = ℤ→ℤAbGroup/Vanish-pos n y
  ℤ→ℤAbGroup/Vanish (negsuc n) (pos k) =
     cong (_modℤ n) (negsuc·pos n k ∙ -DistR· (pos (suc n)) (pos k))
    ∙ ℤ→ℤAbGroup/Vanish-pos (suc n) (- (pos k))
  ℤ→ℤAbGroup/Vanish (negsuc n) (negsuc r) =
    cong (_modℤ n) (negsuc·negsuc n r)
    ∙ ℤ→ℤAbGroup/Vanish-pos (suc n) (pos (suc r))

  ℤ→ℤAbGroup/-ₘ : (k : ℕ) (x : ℤ)
    → ℤ→ℤAbGroup/ (suc k) (- x) ≡ -ₘ ℤ→ℤAbGroup/ (suc k) x
  ℤ→ℤAbGroup/-ₘ k (pos zero) = sym (-ₘ-fzero k)
  ℤ→ℤAbGroup/-ₘ k (pos (suc n)) = refl
  ℤ→ℤAbGroup/-ₘ k (negsuc n) =
    sym (GroupTheory.invInv (ℤGroup/ (suc k))
      (ℤ→ℤAbGroup/ (suc k) (- negsuc n)))

  ℤ→ℤAbGroup/- : (k : ℕ) (x : ℤ)
    → ℤ→ℤAbGroup/ k (- x)
     ≡ AbGroupStr.-_ (snd (ℤAbGroup/ k)) (ℤ→ℤAbGroup/ k x)
  ℤ→ℤAbGroup/- zero x = refl
  ℤ→ℤAbGroup/- (suc k) x = ℤ→ℤAbGroup/-ₘ k x

  ℤ→ℤAbGroup/sucℤ : (k : ℕ) (y : ℤ)
    → ℤ→ℤAbGroup/ (suc k) (sucℤ y)
     ≡ ℤ→ℤAbGroup/ (suc k) 1 +ₘ (ℤ→ℤAbGroup/ (suc k) y)
  ℤ→ℤAbGroup/sucℤ k (pos n) =
    Σ≡Prop (λ _ → isProp<ᵗ)
           (mod+mod≡mod (suc k) 1 n)
  ℤ→ℤAbGroup/sucℤ zero (negsuc n) =
    isContr→isProp
      ((zero , tt)
      , uncurry λ { zero q  → Σ≡Prop (λ _ → isProp<ᵗ) refl}) _ _
  ℤ→ℤAbGroup/sucℤ (suc k) (negsuc zero) =
    sym (+ₘ-rCancel (modInd (suc k) 1 , <→<ᵗ (mod< (suc k) 1)))
  ℤ→ℤAbGroup/sucℤ (suc k') (negsuc (suc n)) = lem
    where
    k = suc k'
    one' x y : (ℤAbGroup/ suc k) .fst
    one' = pos (suc zero) modℤ k
    x = pos (suc n) modℤ k
    y = pos (suc (suc n)) modℤ k

    lem' : y ≡ one' +ₘ x
    lem' = Σ≡Prop (λ _ → isProp<ᵗ)
                  (mod+mod≡mod (suc k) (suc zero) (suc n))

    lem : -ₘ x ≡ one' +ₘ -ₘ y
    lem = sym (+ₘ-lUnit (-ₘ x))
     ∙ cong (_-ₘ x) (sym (+ₘ-rCancel y))
     ∙ +ₘ-assoc y (-ₘ y) (-ₘ x)
     ∙ cong (y +ₘ_) (+ₘ-comm (-ₘ y) (-ₘ x))
     ∙ cong (_+ₘ (-ₘ x -ₘ y)) lem'
     ∙ +ₘ-assoc one' x (((-ₘ x) -ₘ y))
     ∙ cong (one' +ₘ_)
            (sym (+ₘ-assoc x (-ₘ x) (-ₘ y))
           ∙ cong (_-ₘ y) (+ₘ-rCancel x)
           ∙ +ₘ-lUnit (-ₘ y) )

  upstream3 : (k : ℕ) → (suc k ∸ (1 mod suc k)) mod suc k ≡ k
  upstream3 zero = refl
  upstream3 (suc k) = <→mod≡id _ _ (0 , refl)

  ℤ→ℤAbGroup/predℤ : (k : ℕ) (y : ℤ)
    → ℤ→ℤAbGroup/ (suc k) (predℤ y)
     ≡ (-ₘ ℤ→ℤAbGroup/ (suc k) 1) +ₘ (ℤ→ℤAbGroup/ (suc k) y)
  ℤ→ℤAbGroup/predℤ k (pos zero) = sym (+ₘ-rUnit _)
  ℤ→ℤAbGroup/predℤ k (pos (suc n)) = Σ≡Prop (λ _ → isProp<ᵗ) goal
    where
    -- ih : ℤ→ℤAbGroup/ (suc k) (predℤ (pos n)) ≡
    --       -ₘ ℤ→ℤAbGroup/ (suc k) 1 +ₘ ℤ→ℤAbGroup/ (suc k) (pos n)
    -- ih = ℤ→ℤAbGroup/predℤ k (pos n)
    goal : n mod suc k ≡ (((suc k ∸ (1 mod suc k)) mod suc k) +ℕ (suc n mod suc k)) mod suc k                          
    goal = n mod suc k   ≡⟨ mod-rUnit _ _ ⟩
           (n +ℕ suc k) mod suc k 
                         ≡⟨ cong (_mod suc k) (+-comm n (suc k) ∙ sym (+-suc _ _)) ⟩
           (k +ℕ suc n) mod suc k 
                         ≡⟨ cong (λ x → (x +ℕ suc n) mod suc k) (sym (upstream3 _)) ⟩
           (((suc k ∸ (1 mod suc k)) mod suc k +ℕ suc n) mod suc k)
                         ≡⟨ sym (mod-lCancel _ _ _) ⟩                         
           ((((suc k ∸ (1 mod suc k)) +ℕ suc n)) mod suc k)
                         ≡⟨ mod+mod≡mod _ _ _ ⟩
           ((((suc k ∸ (1 mod suc k)) mod suc k) +ℕ (suc n mod suc k)) mod suc k)
                ∎
  ℤ→ℤAbGroup/predℤ k (negsuc n) =
      ℤ→ℤAbGroup/- (suc k) (pos (suc (suc n)))
    ∙ cong -ₘ_ (ℤ→ℤAbGroup/sucℤ k (pos (suc n)))
    ∙ GroupTheory.invDistr (ℤGroup/ (suc k))
        (ℤ→ℤAbGroup/ (suc k) 1) (ℤ→ℤAbGroup/ (suc k) (pos (suc n)))
    ∙ +ₘ-comm (-ₘ (ℤ→ℤAbGroup/ (suc k) (pos (suc n))))
              (-ₘ (ℤ→ℤAbGroup/ (suc k) 1))

  ℤ→ℤAbGroup/isHomPos : (k x : ℕ) (y : ℤ)
    → ℤ→ℤAbGroup/ (suc k) (pos x + y)
     ≡ ℤ→ℤAbGroup/ (suc k) (pos x) +ₘ ℤ→ℤAbGroup/ (suc k) y
  ℤ→ℤAbGroup/isHomPos k zero y = cong (_modℤ k) (+Comm 0 y)
    ∙ sym (+ₘ-lUnit (y modℤ k))
  ℤ→ℤAbGroup/isHomPos k (suc x) y =
    cong (ℤ→ℤAbGroup/ (suc k)) (sym (sucℤ+ (pos x) y))
    ∙ ℤ→ℤAbGroup/sucℤ k (pos x + y)
    ∙ cong₂ _+ₘ_ refl (ℤ→ℤAbGroup/isHomPos k x y)
    ∙ sym (+ₘ-assoc _ _ _)
    ∙ cong₂ _+ₘ_ (sym (ℤ→ℤAbGroup/sucℤ k (pos x))) refl

  ℤ→ℤAbGroup/isHom : (k : ℕ) (x y : ℤ)
    → ℤ→ℤAbGroup/ (suc k) (x + y)
     ≡ ℤ→ℤAbGroup/ (suc k) x +ₘ ℤ→ℤAbGroup/ (suc k) y
  ℤ→ℤAbGroup/isHom k (pos n) y = ℤ→ℤAbGroup/isHomPos k n y
  ℤ→ℤAbGroup/isHom k (negsuc zero) x =
    cong (_modℤ k) (+Comm -1 x) ∙ ℤ→ℤAbGroup/predℤ k x
  ℤ→ℤAbGroup/isHom k (negsuc (suc n)) x =
      cong (ℤ→ℤAbGroup/ (suc k))
           (cong (_+ x) (+Comm _ _)
           ∙ sym (+Assoc -1 (negsuc n) x)
           ∙ (+Comm -1 (negsuc n + x)))
    ∙ ℤ→ℤAbGroup/predℤ k (negsuc n + x)
    ∙ cong₂ _+ₘ_ refl (ℤ→ℤAbGroup/isHom k (negsuc n) x)
    ∙ sym (+ₘ-assoc _ _ _)
    ∙ cong₂ _+ₘ_ (sym (ℤ→ℤAbGroup/predℤ k (negsuc n))) refl

open ℤ→ℤAbGroup/Lemmas public

-- Finally, ℤ → ℤAbGroup/ as a group hom
ℤ→ℤAbGroup/Hom : (k : ℕ) → AbGroupHom ℤAbGroup (ℤAbGroup/ k)
fst (ℤ→ℤAbGroup/Hom k) = ℤ→ℤAbGroup/ k
snd (ℤ→ℤAbGroup/Hom zero) = idGroupHom .snd
snd (ℤ→ℤAbGroup/Hom (suc k)) = makeIsGroupHom (ℤ→ℤAbGroup/isHom k)

-- ℤAbGroup/' → ℤAbGroup/
ℤAbGroup/'→ℤAbGroup/ : (k : ℤ)
  → AbGroupHom (ℤAbGroup/' k) (ℤAbGroup/ (abs k))
ℤAbGroup/'→ℤAbGroup/ k =
  /ImElim _
    (ℤ→ℤAbGroup/Hom (abs k))
    (Σ≡Prop (λ _ → isPropIsGroupHom _ _)
      (funExt λ x → cong (ℤ→ℤAbGroup/ (abs k)) (sym (ℤ·≡· k x)) ∙ main k x))
  where
  main : (k x : ℤ)
    → ℤ→ℤAbGroup/ (abs k) (k · x)
     ≡ AbGroupStr.0g (snd (ℤAbGroup/ abs k))
  main (pos zero) x = refl
  main (pos (suc n)) (pos k) =
      cong (_modℤ n) (sym (pos·pos (suc n) k))
    ∙ Σ≡Prop (λ _ → isProp<ᵗ)
             (cong (_mod suc n) (·-comm (suc n) k) ∙ zero-charac-gen (suc n) k)
  main (pos (suc n)) (negsuc k) =
      cong (_modℤ n) (pos·negsuc (suc n) k
                    ∙ cong -_ (sym (pos·pos (suc n) (suc k))))
    ∙ cong -ₘ_ (Σ≡Prop (λ _ → isProp<ᵗ)
               (cong (_mod (suc n)) (·-comm (suc n) (suc k))
               ∙ zero-charac-gen (suc n) (suc k)))
    ∙ -ₘ-fzero _
  main (negsuc n) (pos k) =
    cong (_modℤ n) (negsuc·pos n k
                  ∙ cong -_ (sym (pos·pos (suc n) k)))
    ∙ ℤ→ℤAbGroup/- (suc n) (pos (suc n ·ℕ k))
    ∙ cong -ₘ_ (Σ≡Prop (λ _ → isProp<ᵗ)
                 (cong (_mod (suc n)) (·-comm (suc n) k)
                 ∙ zero-charac-gen (suc n) k))
    ∙ -ₘ-fzero _
  main (negsuc n) (negsuc k) =
    cong (_modℤ n) (negsuc·negsuc n k)
    ∙ main (pos (suc n)) (pos (suc k))


-- ℤAbGroup/ → ℤAbGroup/'
ℤAbGroup/→ℤAbGroup/'Fun : (k : ℤ)
  → fst (ℤAbGroup/ (abs k)) → fst (ℤAbGroup/' k)
ℤAbGroup/→ℤAbGroup/'Fun (pos zero) = [_]'
ℤAbGroup/→ℤAbGroup/'Fun (pos (suc n)) x = [ pos (fst x) ]'
ℤAbGroup/→ℤAbGroup/'Fun (negsuc n) x = [ pos (fst x) ]'

-- The fun preserves inversion
ℤAbGroup/→ℤAbGroup/'Fun-inv : (k : ℤ) (x : fst (ℤAbGroup/ abs k))
  → ℤAbGroup/→ℤAbGroup/'Fun k (AbGroupStr.-_ (snd (ℤAbGroup/ abs k)) x)
    ≡ AbGroupStr.-_ (snd (ℤAbGroup/' k)) (ℤAbGroup/→ℤAbGroup/'Fun k x)
ℤAbGroup/→ℤAbGroup/'Fun-inv (pos zero) = λ _ → refl
ℤAbGroup/→ℤAbGroup/'Fun-inv (pos (suc n)) (zero , r) =
  cong [_]' (cong pos (cong fst (cong -ₘ_
    (Σ≡Prop (λ _ → isProp<ᵗ) {u = (zero , tt)} refl)
    ∙ -ₘ-fzero n)))
ℤAbGroup/→ℤAbGroup/'Fun-inv (pos (suc n)) (suc x' , r) =
    sym (+IdL t)
  ∙ cong₂ _+*_ (sym (+InvL [ pos x ]')) refl
  ∙ sym (+Assoc* (-* [ pos x ]') [ pos x ]' t)
  ∙ cong (λ w → (-* [ pos x ]') +* w) main
  ∙ +IdR _
  where
  open AbGroupStr (snd (ℤAbGroup/' (pos (suc n))))
    renaming (_+_ to _+*_ ; -_ to -*_ ; +Assoc to +Assoc* )
    hiding (+Comm)

  x = suc x'
  t = [ pos (fst ((AbGroupStr.- snd (ℤAbGroup/ suc n)) (x , r))) ]'

  main : [ pos x ]' +* t ≡ [ 0 ]'
  main = cong [_]' (sym (pos+ _ _)
    ∙ cong pos ((cong (x +ℕ_)
                     ((λ _ → fst (-ₘ (x , r))) ∙ -ₘ< {n = n} x' r))
    ∙ cong (1 +ℕ_) (+-comm x' (n ∸ x') ∙ ≤-∸-+-cancel (≤-trans (1 , refl) (pred-≤-pred (<ᵗ→< {suc x'} r))))))
    ∙ eq/ _ _ ∣ 1 , sym (ℤ·≡· (pos (suc n)) 1)
                  ∙ ·Comm (pos (suc n)) 1 ∣₁

ℤAbGroup/→ℤAbGroup/'Fun-inv (negsuc n) (zero , r) =
  cong [_]'
    (cong pos
      (cong fst
        (cong -ₘ_ (Σ≡Prop (λ _ → isProp<ᵗ)
                   {u = (zero , tt)} refl) ∙ -ₘ-fzero n)))
ℤAbGroup/→ℤAbGroup/'Fun-inv (negsuc n) (suc x' , r) =
    sym (+IdL t) -- sym (+IdL t)
  ∙ cong₂ _+*_ (sym (+InvL [ pos x ]')) refl
  ∙ sym (+Assoc* (-* [ pos x ]') [ pos x ]' t)
  ∙ cong (λ w → (-* [ pos x ]') +* w) main
  ∙ +IdR _ --  _
  where
  open AbGroupStr (snd (ℤAbGroup/' (negsuc n)))
    renaming (_+_ to _+*_ ; -_ to -*_ ; +Assoc to +Assoc* )
    hiding (+Comm)
  x = suc x'
  t = [ pos (fst ((AbGroupStr.- snd (ℤAbGroup/ suc n)) (x , r))) ]'

  helper : x' +ℕ (n ∸ x') ≡ n
  helper = +-comm x' (n ∸ x')
   ∙ ≤-∸-+-cancel {m = x'} {n = n}
      (≤-trans (1 , refl) (pred-≤-pred (<ᵗ→< {suc x'} r)))

  main : [ pos x ]' +* t ≡ [ 0 ]'
  main = cong [_]'
     (sym (pos+ _ _)
   ∙ cong pos (cong (x +ℕ_) ((λ _ → fst (-ₘ (x , r))) ∙ -ₘ< {n = n} x' r)
   ∙ λ i → suc (helper i)))
   ∙ eq/ _ _ ∣ -1
   , (sym (ℤ·≡· (negsuc n) -1)
   ∙ ·Comm (negsuc n) (negsuc 0)) ∣₁

-- Main result: ℤAbGroup/ ≅ ℤAbGroup/'
ℤAbGroup/≅ℤAbGroup/' : (k : ℤ)
  → AbGroupIso (ℤAbGroup/' k) (ℤAbGroup/ (abs k))
fun (fst (ℤAbGroup/≅ℤAbGroup/' k)) = ℤAbGroup/'→ℤAbGroup/ k .fst
inv (fst (ℤAbGroup/≅ℤAbGroup/' k)) = ℤAbGroup/→ℤAbGroup/'Fun k
sec (fst (ℤAbGroup/≅ℤAbGroup/' (pos zero))) _ = refl
sec (fst (ℤAbGroup/≅ℤAbGroup/' (pos (suc n)))) x =
  Σ≡Prop (λ _ → isProp<ᵗ) (<→mod≡id _ _ (<ᵗ→< (snd x)))
sec (fst (ℤAbGroup/≅ℤAbGroup/' (negsuc n))) x =
  Σ≡Prop (λ _ → isProp<ᵗ) (<→mod≡id _ _ (<ᵗ→< (snd x)))
ret (fst (ℤAbGroup/≅ℤAbGroup/' (pos zero))) =
  SQ.elimProp (λ _ → squash/ _ _) λ _ → refl
ret (fst (ℤAbGroup/≅ℤAbGroup/' (pos (suc n)))) =
  SQ.elimProp (λ _ → squash/ _ _)
  λ { (pos n) → lem n
    ; (negsuc a) →
      ℤAbGroup/→ℤAbGroup/'Fun-inv (pos (suc n)) (pos (suc a) modℤ n)
      ∙ cong (AbGroupStr.-_ (snd (ℤAbGroup/' (pos (suc n))))) (lem (suc a))}
  where
  lem : (a : ℕ) → [ pos (fst (pos a modℤ n)) ]' ≡ [ pos a ]'
  lem a = cong [_]' (cong pos λ _ → a mod suc n)
        ∙ (eq/ _ _ ∣ - pos (quotient a / suc n)
                   , sym (ℤ·≡· (pos (suc n)) (- pos (quotient a / suc n)))
                   ∙ sym (-DistR· (pos (suc n)) (pos (quotient a / suc n)))
                   ∙ cong -_ (sym (pos·pos _ _))
                   ∙ +Comm _ 0
                   ∙ cong₂ _+_ (sym (AbGroupStr.+InvR (snd ℤAbGroup) _)) refl
                   ∙ sym (+Assoc _ _ _)
                   ∙ cong₂ _+_ refl
                      (sym (-Dist+ (pos (a mod (suc n)))
                               (pos (suc n ·ℕ (quotient a / suc n))))
                      ∙ cong -_ (sym (pos+ (remainder a / suc n)
                                (suc n ·ℕ (quotient a / suc n)))
                      ∙ cong pos (≡remainder+quotient (suc n) a))) ∣₁)
ret (fst (ℤAbGroup/≅ℤAbGroup/' (negsuc n))) =
  SQ.elimProp (λ _ → squash/ _ _)
  λ { (pos n) → lem n
    ; (negsuc a) →
      ℤAbGroup/→ℤAbGroup/'Fun-inv (negsuc n) (pos (suc a) modℤ n)
      ∙ cong (AbGroupStr.-_ (snd (ℤAbGroup/' (negsuc n)))) (lem (suc a))}
  where
  lem : (a : ℕ) → [ pos (fst (pos a modℤ n)) ]' ≡ [ pos a ]'
  lem a = cong [_]' (cong pos λ _ → a mod suc n)
        ∙ (eq/ _ _ ∣ pos (quotient a / suc n)
                   , sym (ℤ·≡· (negsuc n) (pos (quotient a / suc n)))
                   ∙ negsuc·pos n (quotient a / suc n)
                   ∙ cong -_ (sym (pos·pos _ _))
                   ∙ +Comm _ 0
                   ∙ cong₂ _+_ (sym (AbGroupStr.+InvR (snd ℤAbGroup) _)) refl
                   ∙ sym (+Assoc _ _ _)
                   ∙ cong₂ _+_ refl
                      (sym (-Dist+ (pos (a mod (suc n)))
                               (pos (suc n ·ℕ (quotient a / suc n))))
                      ∙ cong -_ (sym (pos+ (remainder a / suc n)
                                (suc n ·ℕ (quotient a / suc n)))
                      ∙ cong pos (≡remainder+quotient (suc n) a))) ∣₁)
snd (ℤAbGroup/≅ℤAbGroup/' k) = ℤAbGroup/'→ℤAbGroup/ k .snd

--------------- Part 2: ℤ[Fin n] ≅ ℤ̂ⁿ ---------------

-- Definition of ℤⁿ
dirProdAbIt : ∀ {ℓ} (m : ℕ) (G : AbGroup ℓ) → AbGroup ℓ
dirProdAbIt zero G = trivialAbGroup
dirProdAbIt (suc m) G = dirProdAb G (dirProdAbIt m G)

-- ℤ[Fin n] → ℤⁿ
ℤ[Fin]→ℤᵐFun : (m : ℕ)
  → ℤ[Fin m ] .fst → dirProdAbIt m ℤAbGroup .fst
ℤ[Fin]→ℤᵐFun zero f = lift tt
ℤ[Fin]→ℤᵐFun (suc m) f = (f fzero) , (ℤ[Fin]→ℤᵐFun m (f ∘ fsuc))

ℤ[Fin]→ℤᵐisHom : (m : ℕ) (f g : ℤ[Fin m ] .fst)
  → ℤ[Fin]→ℤᵐFun m (λ x → f x + g x)
  ≡ AbGroupStr._+_ (snd (dirProdAbIt m ℤAbGroup))
                   (ℤ[Fin]→ℤᵐFun m f)
                   (ℤ[Fin]→ℤᵐFun m g)
ℤ[Fin]→ℤᵐisHom zero f g = refl
ℤ[Fin]→ℤᵐisHom (suc m) f g = ΣPathP (refl , ℤ[Fin]→ℤᵐisHom m _ _)

ℤ[Fin]→ℤᵐ : (m : ℕ) → AbGroupHom ℤ[Fin m ] (dirProdAbIt m ℤAbGroup)
fst (ℤ[Fin]→ℤᵐ m) = ℤ[Fin]→ℤᵐFun m
snd (ℤ[Fin]→ℤᵐ m) = makeIsGroupHom (ℤ[Fin]→ℤᵐisHom m)

-- ℤⁿ → ℤ[Fin n]
ℤᵐ→ℤ[Fin]Fun : (m : ℕ) → (dirProdAbIt m ℤAbGroup) .fst → ℤ[Fin m ] .fst
ℤᵐ→ℤ[Fin]Fun zero _ _ = 0
ℤᵐ→ℤ[Fin]Fun (suc m) (x , t) = elimFin-alt x (ℤᵐ→ℤ[Fin]Fun m t)

ℤᵐ→ℤ[Fin]isHom : (m : ℕ) (x y : (dirProdAbIt m ℤAbGroup) .fst)
  → ℤᵐ→ℤ[Fin]Fun m (AbGroupStr._+_ (snd (dirProdAbIt m ℤAbGroup)) x y)
  ≡ λ a → ℤᵐ→ℤ[Fin]Fun m x a + ℤᵐ→ℤ[Fin]Fun m y a
ℤᵐ→ℤ[Fin]isHom zero x y = refl
ℤᵐ→ℤ[Fin]isHom one x y = funExt λ { (zero , y) → refl}
ℤᵐ→ℤ[Fin]isHom (suc (suc m)) (x , x') (y , y') i (zero , t) = x + y
ℤᵐ→ℤ[Fin]isHom (suc (suc m)) (x , x') (y , y') i (suc s , t) =
  ℤᵐ→ℤ[Fin]isHom (suc m) x' y' i (s , t)

ℤᵐ→ℤ[Fin] : (m : ℕ) → AbGroupHom  (dirProdAbIt m ℤAbGroup) ℤ[Fin m ]
fst (ℤᵐ→ℤ[Fin] m) = ℤᵐ→ℤ[Fin]Fun m
snd (ℤᵐ→ℤ[Fin] m) = makeIsGroupHom (ℤᵐ→ℤ[Fin]isHom m)

-- Main result: ℤ[Fin n] ≅ ℤⁿ
ℤ[Fin]≅ℤᵐ : (m : ℕ) → AbGroupIso ℤ[Fin m ] (dirProdAbIt m ℤAbGroup)
fun (fst (ℤ[Fin]≅ℤᵐ m)) = ℤ[Fin]→ℤᵐ m .fst
inv (fst (ℤ[Fin]≅ℤᵐ m)) = ℤᵐ→ℤ[Fin] m .fst
sec (fst (ℤ[Fin]≅ℤᵐ zero)) _ = refl
sec (fst (ℤ[Fin]≅ℤᵐ one)) (s , t) = refl
sec (fst (ℤ[Fin]≅ℤᵐ (suc (suc m)))) (s , t) =
  ΣPathP (refl , sec (fst (ℤ[Fin]≅ℤᵐ (suc m))) t)
ret (fst (ℤ[Fin]≅ℤᵐ one)) f i (zero , s) = f fzero
ret (fst (ℤ[Fin]≅ℤᵐ (suc (suc m)))) f i (zero , s) = f fzero
ret (fst (ℤ[Fin]≅ℤᵐ (suc (suc m)))) f i (suc x , s) =
  ret (fst (ℤ[Fin]≅ℤᵐ (suc m))) (f ∘ fsuc) i (x , s)
snd (ℤ[Fin]≅ℤᵐ m) = ℤ[Fin]→ℤᵐ m .snd

