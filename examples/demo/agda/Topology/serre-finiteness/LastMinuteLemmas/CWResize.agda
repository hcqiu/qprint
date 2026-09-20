{-# OPTIONS --lossy-unification --safe #-}

module LastMinuteLemmas.CWResize where

open import Cubical.Foundations.Prelude
open import Cubical.Foundations.Equiv
open import Cubical.Foundations.Equiv.Properties
open import Cubical.Foundations.Function
open import Cubical.Foundations.Isomorphism
open import Cubical.Foundations.Univalence

open import Cubical.Data.Nat renaming (_+_ to _+ℕ_)
open import Cubical.Data.Fin.Base
open import Cubical.Data.Sigma
open import Cubical.Data.Empty
open import Cubical.Data.Unit
open import Cubical.Data.Sequence

open import Cubical.Functions.Embedding
open import Cubical.Functions.Surjection

open import Cubical.HITs.Sn
open import Cubical.HITs.Pushout
open import Cubical.HITs.SequentialColimit
open import Cubical.HITs.PropositionalTruncation as PT

open import Cubical.Relation.Nullary

open import Cubical.CW.Base
open import Cubical.CW.Instances.Lift

-- Given a finite CW complex in universe ℓ,
-- construct an equivalent finite CW complex in any other universe ℓ.
-- A kind of generalization of Cubical.CW.Instances.Lift.

-- The new CW complex is also "strict" in the sense of Cubical.CW.Strictification.

-- TODO: Extend to non-finite complexes

CWskel→CWskel' : {ℓ ℓ' : Level} (C : CWskel ℓ) → Σ[ C' ∈ CWskel ℓ' ]
  Σ[ j ∈ ((n : ℕ) → fst C n ≃ fst C' n) ]
  ((n : ℕ) → equivFun (j (suc n)) ∘ CW↪ C n ≡ CW↪ C' n ∘ equivFun (j n))
CWskel→CWskel' {ℓ} {ℓ'} (X , f , α , e₀ , e₊) = ((X' , f , α' , e₀' , e₊') , j , k)
  where
    -- todo: rewrite using mutually recursive definitions

    Y : (n : ℕ) → Σ[ X' ∈ Type ℓ' ] (X n ≃ X')
    Y zero = (⊥* , uninhabEquiv e₀ (λ ()))
    Y (suc n) =
      (Pushout (equivFun (snd (Y n)) ∘ α n) fst ,
       compEquiv (e₊ n)
         (pushoutEquiv (α n) fst (equivFun (snd (Y n)) ∘ α n) fst
            (idEquiv _) (snd (Y n)) (idEquiv _) refl refl))

    X' : ℕ → Type ℓ'
    X' n = fst (Y n)

    j : (n : ℕ) → X n ≃ X' n
    j n = snd (Y n)

    α' : (n : ℕ) → (Fin (f n) × (S⁻ n)) → X' n
    α' n = equivFun (j n) ∘ α n

    e₀' : ¬ X' zero
    e₀' ()

    e₊' : (n : ℕ) → X' (suc n) ≃ Pushout (α' n) fst
    e₊' n = idEquiv (X' (suc n))

    k : (n : ℕ)
      → equivFun (j (suc n)) ∘ CW↪ (X , f , α , e₀ , e₊) n ≡
        CW↪ (X' , f , α' , e₀' , e₊') n ∘ equivFun (j n)
    k n = funExt λ x → cong
      (equivFun (pushoutEquiv (α n) fst (equivFun (snd (Y n)) ∘ α n) fst
       (idEquiv _) (snd (Y n)) (idEquiv _) refl refl))
      (secEq (e₊ n) (inl x))

finCWskel→finCWskel' : {ℓ ℓ' : Level} (d : ℕ) (C : finCWskel ℓ d)
  → Σ[ C' ∈ finCWskel ℓ' d ]
    Σ[ j ∈ ((n : ℕ) → fst C n ≃ fst C' n) ]
    Unit
finCWskel→finCWskel' {ℓ} {ℓ'} d (X , y , z) =
  (fst C' , snd C' , h) , j , tt
  where
    C' : CWskel ℓ'
    C' = fst (CWskel→CWskel' (X , y))

    j : (n : ℕ) → X n ≃ fst C' n
    j = fst (snd (CWskel→CWskel' (X , y)))

    h : (k : ℕ) → isEquiv (CW↪ C' (k +ℕ d))
    h k =
      isEquiv[f∘equivFunA≃B]→isEquiv[f] (CW↪ C' (k +ℕ d)) (j (k +ℕ d))
      (subst isEquiv (snd (snd (CWskel→CWskel' (X , y))) (k +ℕ d))
       (compEquiv (_ , z k) (j (suc (k +ℕ d))) .snd))

cancel-isEmbedding : {ℓ ℓ' ℓ'' : Level} {A : Type ℓ} {B : Type ℓ'} {C : Type ℓ''}
  → (f : A → B) → (g : B → C)
  → isEmbedding g → isEmbedding (g ∘ f) → isEmbedding f
cancel-isEmbedding f g Embg Embgf w x
  = isEquiv[equivFunA≃B∘f]→isEquiv[f] (cong f) (cong g , Embg (f w) (f x)) (Embgf w x)

module Lemmas {ℓ : Level} where
  resize : finCW ℓ-zero → finCW ℓ
  resize = finCWLift ℓ

  isEmb : isEmbedding resize
  isEmb = cancel-isEmbedding resize fst (λ _ _ → isEmbeddingFstΣProp λ _ → PT.squash₁)
                                        (isEmbedding-∘ {f = Lift ℓ} {h = fst}
                                                       (liftEmbedding ℓ-zero ℓ) λ _ _ → isEmbeddingFstΣProp λ _ → PT.squash₁)

  isSurj : isSurjection resize
  isSurj (A , p) = PT.rec PT.squash₁ main p
    where
      main : hasFinCWskel A → ∃[ C' ∈ finCW ℓ-zero ] resize C' ≡ (A , p)
      main (d , C , e) =
        ∣ (fst C' d , ∣ d , C' , j0 ∣₁) ,
          Σ≡Prop (λ _ → PT.squash₁)
            (sym (ua (compEquiv e (compEquiv j2 (compEquiv j1 LiftEquiv))))) ∣₁
        where
          C' : finCWskel ℓ-zero d
          C' = fst (finCWskel→finCWskel' d C)

          j0 : fst C' d ≃ realise (finCWskel→CWskel d C')
          j0 = isoToEquiv (converges→ColimIso d (snd (snd C')))

          j1 : fst C d ≃ fst C' d
          j1 = fst (snd (finCWskel→finCWskel' d C)) d

          j2 : realise (finCWskel→CWskel d C) ≃ fst C d
          j2 = invEquiv (isoToEquiv (converges→ColimIso d (snd (snd C))))

resizeEquiv₀ : {ℓ : Level} → finCW ℓ-zero ≃ finCW ℓ
resizeEquiv₀ .fst = Lemmas.resize
resizeEquiv₀ .snd = isEmbedding×isSurjection→isEquiv (Lemmas.isEmb , Lemmas.isSurj)

resizeEquiv₀-Equiv : {ℓ : Level} (C : finCW ℓ-zero)
  → fst C ≃ fst (fst (resizeEquiv₀ {ℓ = ℓ}) C)
resizeEquiv₀-Equiv C = LiftEquiv

-- Main results (for finite CW complexes)

resizeEquiv : {ℓ ℓ' : Level} → finCW ℓ ≃ finCW ℓ'
resizeEquiv = compEquiv (invEquiv resizeEquiv₀) resizeEquiv₀

resizeEquiv-Equiv : {ℓ ℓ' : Level} → (C : finCW ℓ)
  → fst C ≃ fst (fst (resizeEquiv {ℓ' = ℓ'}) C)
resizeEquiv-Equiv C = compEquiv e' (resizeEquiv₀-Equiv C')
  where
    C' : finCW ℓ-zero
    C' = fst (invEquiv resizeEquiv₀) C

    e : fst resizeEquiv₀ C' ≡ C
    e = secEq resizeEquiv₀ C

    e' : fst C ≃ fst C'
    e' = invEquiv (compEquiv (resizeEquiv₀-Equiv C') (pathToEquiv (cong fst e)))

-- scratch space for infinite CW complexes

-- realise≃' : {ℓ ℓ' : Level} (C : CWskel ℓ) →
--   realise C ≃ realise (fst (CWskel→CWskel' {ℓ' = ℓ'} C))
-- realise≃' {ℓ} {ℓ'} C = isoToEquiv {!!}
--   where
--     C' : CWskel ℓ'
--     C' = fst (CWskel→CWskel' {ℓ' = ℓ'} C)

--     j : (n : ℕ) → fst C n ≃ fst C' n
--     j = fst (snd (CWskel→CWskel' {ℓ' = ℓ'} C))

--     e : SequenceEquiv (realiseSeq C) (realiseSeq C')
--     e .fst .SequenceMap.map = λ n → equivFun (j n) 
--     e .fst .SequenceMap.comm = λ n →
--       funExt⁻ (sym (snd (snd (CWskel→CWskel' {ℓ' = ℓ'} C)) n))
--     e .snd = λ n → equivIsEquiv (j n)
-- -- start at sequenceEquiv→ColimIso in Cubical.HITs.SequentialColimit.Properties
