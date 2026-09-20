{-# OPTIONS --lossy-unification --safe #-}
module SAF where

open import Cubical.Foundations.Prelude
open import Cubical.Foundations.Pointed
open import Cubical.Foundations.Function
open import Cubical.Foundations.Isomorphism
open import Cubical.Foundations.Equiv
open import Cubical.Foundations.GroupoidLaws
open import Cubical.Foundations.HLevels
open import Cubical.Foundations.Path
open import Cubical.Foundations.Transport
open import Cubical.Foundations.Univalence

open import Cubical.Algebra.AbGroup
open import Cubical.Algebra.AbGroup.Instances.DirectProduct
open import Cubical.Algebra.AbGroup.Instances.Int renaming (ℤAbGroup to ℤ)

open import Cubical.Data.Nat renaming (elim to elimℕ)
open import Cubical.Data.Nat.Order
open import Cubical.Data.Fin
open import Cubical.Data.Sigma

open import Cubical.Homotopy.Connected
open import Cubical.Homotopy.EilenbergMacLane.Base

open import Cubical.HITs.S1
open import Cubical.HITs.EilenbergMacLane1 as EM1
open import Cubical.HITs.Join
open import Cubical.HITs.SmashProduct
open import Cubical.HITs.Wedge
open import Cubical.HITs.Pushout
open import Cubical.HITs.Susp
open import Cubical.HITs.Susp.SuspProduct
open import Cubical.HITs.Sn hiding (S)
open import Cubical.HITs.Truncation as TR
open import Cubical.HITs.PropositionalTruncation as PT

open import Cubical.CW.Base
open import Cubical.CW.Instances.Lift
open import Cubical.CW.Instances.Sn

open import FiniteCW
open import PointedHITs
open import HomotopyGroups
open import FiberOrCofiberSequences.Base
open import FiberOrCofiberSequences.CofiberBase
open import FiberOrCofiberSequences.PuppeLemma
open import Connectedness

open import LastMinuteLemmas.EM
open import LastMinuteLemmas.ConnectedLemmas
open import LastMinuteLemmas.SmashLemmas
open import LastMinuteLemmas.CWLemmas
open import LastMinuteLemmas.SuspLemmas
open import LastMinuteLemmas.CWResize

private
  variable
    ℓ ℓ' : Level


srthmetic : (m n : ℕ) → (m + suc n) ≡ (suc (m + n))
srthmetic m n = +-suc m n


-- stably almost finite spaces

-- probably this is defined elsewhere
Susp→^ : {X Y : Type ℓ} (n : ℕ) (f : X → Y) → Susp^ n X → Susp^ n Y
Susp→^ n f = Susp^Fun f n

Susp^-need : {X : Type ℓ} (m' m : ℕ) → Susp^ (m' + m) X ≡ Susp^ m' (Susp^ m X)
Susp^-need zero m = refl
Susp^-need (suc m') m = Susp^-comm (m' + m) _ ∙ cong (Susp) (Susp^-need m' m) ∙ Susp^-comm m' _ ⁻¹

Susp→^-conn : {X Y : Type ℓ} (n m : ℕ) (f : X → Y) → isConnectedFun m f
            → isConnectedFun (n + m) (Susp→^ n f)
Susp→^-conn n m f cf = isConnectedSusp^Fun f m n cf

isConnectedPoint* : ∀ (n : HLevel) {A : Type ℓ}
  → isConnected (suc n) A
  → (a : A) → isConnectedFun n (λ(_ : Unit* {ℓ}) → a)
isConnectedPoint* n connA a₀ a =
  isConnectedRetract n
    snd (_ ,_) (λ _ → refl)
    (isConnectedPath n connA a₀ a)

isEquivTrnspId : {X Y : Type ℓ} (p : X ≡ Y)
  → isEquiv (transport (λ i → p i → X) (λ x → x))
isEquivTrnspId {X = X} p =
  transport (λ j → isEquiv (transp (λ i → p (i ∧ j) → X)
                                    (~ j) (λ x → x)))
    (idIsEquiv X)

isConnectedUnit* : (n : ℕ) → isConnected n (Unit* {ℓ})
isConnectedUnit* zero = tt* , (λ _ → refl)
isConnectedUnit* (suc n) .fst = ∣ tt* ∣
isConnectedUnit* (suc n) .snd =
  TR.elim (λ _ → isOfHLevelPath (suc n) (isOfHLevelTrunc (suc n)) _ _)
          λ _ → refl

arithmetric : (M₁ M₂ k n m : ℕ)
               → (k ≤ n + m)
               → (M₁ + M₂ + k ≤ M₁ + n + (M₂ + m))
arithmetric M₁ M₂ k n m p =
  subst2 (_≤_)
    (+-comm k (M₁ + M₂))
    (+-comm (n + m) (M₁ + M₂)
    ∙ sym (+-assoc M₁ M₂ (n + m))
    ∙ cong (M₁ +_) (+-assoc M₂ n m
                   ∙ cong (_+ m) (+-comm M₂ n)
                   ∙ sym (+-assoc n M₂ m))
    ∙ +-assoc M₁ n (M₂ + m))
    (≤-+k {k = M₁ + M₂} p)

arithmetric' : (M₁ M₂ k n m : ℕ)
               → (k ≤ n + m)
               → (M₂ + M₁ + k ≤ M₁ + n + (M₂ + m))
arithmetric' M₁ M₂ k n m p =
  subst2 (_≤_)
    (+-comm k (M₂ + M₁))
    (sym (+-assoc n m (M₂ + M₁))
    ∙ cong (n +_) (+-comm m (M₂ + M₁)
                ∙ (sym (+-assoc M₂ M₁ m)
                ∙ cong (M₂ +_) (+-comm M₁ m)
                ∙ +-assoc M₂ m M₁)
                ∙ +-comm (M₂ + m) M₁)
    ∙ +-assoc n M₁ (M₂ + m)
    ∙ sym (cong (_+ (M₂ + m)) (+-comm M₁ n)))
    (≤-+k {k = M₂ + M₁} p)

isConnectedTrnspConnected : {X Y Z : Type ℓ} {n : ℕ} (p : Y ≡ Z) (f : X → Y)
  → isConnectedFun n f
  → isConnectedFun n (transport (λ i → X → (p i)) f)
isConnectedTrnspConnected {X = X} {n = n} p f conf  =
  transport (λ i → isConnectedFun n
                    (transp (λ j → X → (p (j ∧ i))) (~ i) f))
    conf

-- spheres with arbitrary universe level?
S : ℕ → Pointed ℓ
S {ℓ = ℓ} n = S₊∙ n ×∙ (Unit* {ℓ} , tt*)

isFinCWS : (n : ℕ) → isFinCW (S {ℓ} n .fst)
isFinCWS n = subst isFinCW (isoToPath lem)
             (snd (finCWLift _ (_ , isFinCWSn)))
  where
  lem : Iso (Lift _ (S₊ n)) (S n .fst)
  lem = compIso (invIso LiftIso) (invIso rUnit*×Iso)

isConnectedS : (n : ℕ) → isConnected (suc n) (S {ℓ} n .fst)
isConnectedS n = isConnectedRetractFromIso (suc n) rUnit*×Iso (sphereConnected n)

-- `nFinite n X` corresponds to "X is (n-1)-finite" on paper,
-- because `isConnectedFun n f` corresponds to "f is (n-2)-connected".
nFinite : HLevel → Type ℓ → Type (ℓ-suc ℓ)
nFinite {ℓ} n X =
  ∥ (Σ[ C ∈ FinCW ℓ ] Σ[ f ∈ (decodeFinCW C → X) ] isConnectedFun n f) ∥₁

nFinite-isProp : {n : HLevel} {X : Type ℓ} → isProp (nFinite n X)
nFinite-isProp = squash₁

-- "X admits an (n-2)-connected map from an (n-1)-dimensional CW complex"
nFinite-nDim : HLevel → Type ℓ → Type (ℓ-suc ℓ)
nFinite-nDim {ℓ} n X =
  ∥ (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ] Σ[ f ∈ (C → X) ] isConnectedFun n f) ∥₁

nFinite-nDim-isProp : {n : HLevel} {X : Type ℓ} → isProp (nFinite-nDim n X)
nFinite-nDim-isProp = squash₁

nDim→nFinite : {n : HLevel} {X : Type ℓ} → nFinite-nDim n X → nFinite n X
nDim→nFinite {ℓ} {n} {X} hX =
  PT.rec nFinite-isProp
  (λ hX' → ∣ (fst hX' , isNDimFinCW→isFinCW (fst (snd hX')))
                      , (snd (snd hX')) ∣₁)
  hX

nFinite→nDim : {n : HLevel} {X : Type ℓ} → nFinite n X → nFinite-nDim n X
nFinite→nDim {ℓ} {n} {X} hX = PT.rec squash₁ γ hX
  where

    β :(C : Σ[ C ∈ FinCW ℓ ] Σ[ f ∈ (decodeFinCW C → X) ] isConnectedFun n f)
       → Σ[ Y ∈ Type ℓ ] (Σ[ hY ∈ (isNDimFinCW n Y) ]
                            Σ[ g ∈ (Y → typ (fst C)) ] isConnectedFun n g)
       → nFinite-nDim n X
    β (C , f , cf) (Y , hY , g , cg) =
      ∣ Y , hY , ((f ∘ g) , (isConnectedComp f g n cf cg)) ∣₁


    γ : (Σ[ C ∈ FinCW ℓ ] Σ[ f ∈ (decodeFinCW C → X) ] isConnectedFun n f)
        → nFinite-nDim n X
    γ (C , f , cf) = PT.rec squash₁ (β (C , f , cf)) (mapFromNSkel (typ C) (snd C) n)

-- closure of n-finiteness under cofibers

cofNFinite'' : {n : ℕ} {X Y Z : Pointed ℓ} (CS : CofiberSeq X Y Z)
  → nFinite-nDim n (typ (CofiberSeqDom CS))
  → nFinite (1 + n) (typ (CofiberSeqExt CS))
  → nFinite (1 + n) (typ (CofiberSeqCof CS))
cofNFinite'' {ℓ} {n} CS hDom hExt =
  PT.rec squash₁ step2 hDom
 where
   step0 :  (C1 : Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ]
                                  Σ[ f ∈ (C → (typ (CofiberSeqDom CS))) ]
                                  isConnectedFun n f)
         → (D1 : Σ[ C ∈ FinCW ℓ ]
                  Σ[ f ∈ (decodeFinCW C → (typ (CofiberSeqExt CS))) ]
                    isConnectedFun (1 + n) f)
         → (Σ[ l ∈ ((fst C1) → (typ (fst D1))) ]
             ((fst (snd D1)) ∘ l
               ≡ (fst (CofiberSeqInc CS) ∘ (fst (snd (snd C1))))))
         → nFinite (1 + n) (typ (CofiberSeqCof CS))
   step0 (C , hC , f , cf) (D , g , cg) (l , p) =
     ∣ ((typ (CofiberSeqCof₋ (cofiber-CofiberSeq₋ l))) ,
       isFinCWCofiberSeq₋ {S = cofiber-CofiberSeq₋ l}
         (cofiberDom-isFinCWCofiberSeq₋ l (isNDimFinCW→isFinCW hC))
         (cofiberExt-isFinCWCofiberSeq₋ l (snd D))) ,
       (fst (CofiberSeqMap-cofiber l CS f g p)) ,
       CofiberSeqMapConn-cofiber n l CS f g p cf cg ∣₁

   step1 : (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ]
                            Σ[ f ∈ (C → (typ (CofiberSeqDom CS))) ]
                            isConnectedFun n f)
         → (Σ[ C ∈ FinCW ℓ ]
             Σ[ f ∈ (decodeFinCW C → (typ (CofiberSeqExt CS))) ]
             isConnectedFun (1 + n) f)
         → nFinite (1 + n) (typ (CofiberSeqCof CS))
   step1 (C , hC , f , cf) (D , g , cg) =
     PT.rec squash₁ (step0 (C , hC , f , cf) (D , g , cg))
       (liftFromNDimFinCW n C hC g (isConnectedFunSubtr n 1 g cg) ((fst (CofiberSeqInc CS)) ∘ f))

   step2 : (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ]
                            Σ[ f ∈ (C → (typ (CofiberSeqDom CS))) ]
                            isConnectedFun n f)
           → nFinite (1 + n) (typ (CofiberSeqCof CS))
   step2 (C , hC , f , cf) =
     PT.rec squash₁ (step1 (C , hC , f , cf)) hExt

cofNFinite' : {n : ℕ} {X Y Z : Pointed ℓ} (CS : CofiberSeq X Y Z)
  → nFinite n (typ (CofiberSeqDom CS))
  → nFinite (1 + n) (typ (CofiberSeqExt CS))
  → nFinite (1 + n) (typ (CofiberSeqCof CS))
cofNFinite' {ℓ = ℓ} {n = n} CS hDom hExt =
  cofNFinite'' CS (nFinite→nDim hDom) hExt

cofNFinite : {n : ℕ} {X Y Z : Pointed ℓ} → CofiberSeq X Y Z
    → nFinite n (typ X)
    → nFinite (1 + n) (typ Y)
    → nFinite (1 + n) (typ Z)
cofNFinite {ℓ} {n} CS hX hY =
  transport (λ i → nFinite (1 + n) (typ (CofiberSeqCof-Id {S = CS} i)))
            (cofNFinite' CS
              (transport (λ i → nFinite n (typ (CofiberSeqDom-Id {S = CS} (~ i)))) hX)
              (transport (λ i → nFinite (1 + n) (typ (CofiberSeqExt-Id {S = CS} (~ i)))) hY))

susp-nFinite : {X : Type ℓ} (n : ℕ) → nFinite n X → nFinite (suc n) (Susp X)
susp-nFinite {X = X} n = PT.map
  λ {(X , w , q)
  → (Susp (fst X)
  , isFinCWSusp {n = 1} (fst X) (snd X))
  , (suspFun w , isConnectedSuspFun w n q)}

-- If X is (n-1)-finite and f : X -> Y is (n-2)-connected then Y is (n-1)-finite.
nFiniteApprox :  {X Y : Type ℓ} (f : X → Y)
    (n : HLevel) (hf : isConnectedFun n f)
    → nFinite n X → nFinite n Y
nFiniteApprox f n hf = PT.rec squash₁ (λ hX → ∣ (fst hX) , ((f ∘ fst (snd hX)) , (isConnectedComp f (fst (snd hX)) n hf (snd (snd hX)))) ∣₁)

-- If Y is (n-1)-finite and f : X -> Y is (n-1)-connected then Y is (n-1)-finite.
nFiniteApprox' :  {X Y : Type ℓ} (f : X → Y)
  (n : HLevel) (hf : isConnectedFun (1 + n) f)
  → nFinite n Y → nFinite n X
nFiniteApprox' {ℓ} {X} {Y} f n hf hY = PT.rec nFinite-isProp γ (nFinite→nDim hY)
  where
    α : (hY : Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ]
          Σ[ g ∈ (C → Y) ] isConnectedFun n g)
       → ∃[ l ∈ ((fst hY) → X) ] (f ∘ l ≡ (fst (snd (snd hY))))
    α (C , hC , g , cg) =
      liftFromNDimFinCW n C hC f (isConnectedFunSubtr n 1 f hf) g

    β :  (hY : Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ]
          Σ[ g ∈ (C → Y) ] isConnectedFun n g)
         → (hl : Σ[ l ∈ ((fst hY) → X) ] (f ∘ l ≡ (fst (snd (snd hY)))))
         → (isConnectedFun n (fst hl))
    β (C , hC , g , cg) (l , hl) =
      isConnectedFunCancel' l f n hf
        (transport (λ i → isConnectedFun n (hl (~ i)))
                   cg)

    γ : (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW n C ]
          Σ[ g ∈ (C → Y) ] isConnectedFun n g)
        → nFinite n X
    γ (C , hC , g , cg) =
      nDim→nFinite
        (PT.rec
           squash₁
           (λ hl → ∣ C , (hC , ((fst hl) , (β (C , hC , g , cg) hl))) ∣₁)
           (α (C , hC , g , cg)))

nFiniteDrop : {X : Type ℓ} (n : HLevel)
  → nFinite (1 + n) X → nFinite n X
nFiniteDrop n = PT.rec nFinite-isProp
                       (λ hX → ∣ (fst hX)
                                , ((fst (snd hX))
                                , isConnectedFunSubtr n 1 (fst (snd hX)) (snd (snd hX))) ∣₁)


-- should change to use pointed suspension
-- `stablyNFinite n X` means "X is stably (n-1)-finite".
stablyNFinite : HLevel → Pointed ℓ → Type (ℓ-suc ℓ)
stablyNFinite {ℓ} n X = ∥ (Σ[ m ∈ ℕ ] nFinite (m + n) (Susp^ m (typ X))) ∥₁

pointIrrelSNFnt : (n : ℕ) (X : Pointed ℓ) (x : typ X)
                  → stablyNFinite n X → stablyNFinite n (typ X , x)
pointIrrelSNFnt n X x hyp = hyp

-- alternative version of `stablyNFinite` with a single existential
stablyNFinite' : HLevel → Pointed ℓ → Type (ℓ-suc ℓ)
stablyNFinite' {ℓ} n X =
  ∥ (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X))) ]
     isConnectedFun (m + n) f)) ∥₁

stablyNFinite-isProp : {n : HLevel} {X : Pointed ℓ} → isProp (stablyNFinite n X)
stablyNFinite-isProp = squash₁

stablyNFinite'-isProp : {n : HLevel} {X : Pointed ℓ} → isProp (stablyNFinite' n X)
stablyNFinite'-isProp = squash₁

stablyNFinite→stablyNFinite' : {n : HLevel} {X : Pointed ℓ}
  → stablyNFinite n X → stablyNFinite' n X
stablyNFinite→stablyNFinite' {X = X} hX =
  PT.rec (stablyNFinite'-isProp {X = X})
  (λ hX' → PT.rec (stablyNFinite'-isProp {X = X})
  (λ hX'' → ∣ (fst hX') , hX'' ∣₁) (snd hX')) hX

stablyNFinite'→stablyNFinite : {n : HLevel} {X : Pointed ℓ}
  → stablyNFinite' n X → stablyNFinite n X
stablyNFinite'→stablyNFinite {X = X} hX =
  PT.rec squash₁ (λ hX' → ∣ (fst hX') , ∣ snd hX' ∣₁ ∣₁) hX

-- `saf X` means "X is stably almost finite".
saf : Pointed ℓ → Type (ℓ-suc ℓ)
saf X = (n : ℕ) → stablyNFinite n X

saf-isProp : {X : Pointed ℓ} → isProp (saf X)
saf-isProp {X = X} = isPropΠ (λ n → stablyNFinite-isProp {n = n} {X = X})

-- depends on the implementation of FinCW
isFinCW→saf : {X : Pointed ℓ} → isFinCW (typ X) → saf X
isFinCW→saf {ℓ = ℓ }{X = X} hX =
  PT.rec (saf-isProp {X = X}) (λ p n →
                    ∣ 0 , ∣ (fst p) ,
                             (transport (λ i → (snd p i) → (typ X)) (λ x → x)
                            , isEquiv→isConnected (transport (λ i → (snd p i) → (typ X))
                                      (λ x → x))
                                      (lem p) n) ∣₁ ∣₁)
                           (isFinCW-def-fun hX)
  where
  lem : (p : Σ (FinCW ℓ) (λ v → fst X ≡ decodeFinCW v))
    → isEquiv (transport (λ i → snd p i → typ X) (λ x → x))
  lem p = isEquivTrnspId (snd p)

saf-Fin : ∀ n (b : Fin n) → saf (Fin n , b)
saf-Fin n b = isFinCW→saf {X = _ , b} (isFinCWFin n)

saf-Unit : saf {ℓ} (Unit* , tt*)
saf-Unit = isFinCW→saf {X = _ , tt*} isFinCWUnit

saf-Sn : ∀ n → saf (S {ℓ} n)
saf-Sn n = isFinCW→saf {X = _ , (ptSn n) , tt*} (isFinCWS n)

EM₁ℤ : (EM∙ {ℓ-zero} ℤ 1) ≡ S 1
EM₁ℤ = sym (ua∙ (isoToEquiv (compIso rUnit*×Iso S¹≅EM)) refl)
  where
  open import Cubical.Data.Int renaming (ℤ to Int ; _+_ to _+ℤ_)
  S¹→EM : S¹ → EM ℤ 1
  S¹→EM base = embase
  S¹→EM (loop i) = emloop 1 i

  S¹→EM-intLoop : (g : _) → cong S¹→EM (intLoop g) ≡ emloop g
  S¹→EM-intLoop (pos zero) = sym (emloop-1g _)
  S¹→EM-intLoop (pos (suc n)) =
    cong-∙ S¹→EM (intLoop (pos n)) loop
    ∙ cong₂ _∙_ (S¹→EM-intLoop (pos n)) refl
    ∙ sym (emloop-comp _ (pos n) (pos 1))
  S¹→EM-intLoop (negsuc zero) = sym (emloop-sym _ _)
  S¹→EM-intLoop (negsuc (suc n)) =
      cong-∙ S¹→EM (intLoop (negsuc n)) (sym loop)
    ∙ cong₂ _∙_ (S¹→EM-intLoop (negsuc n)) (sym (emloop-sym _ _))
    ∙ sym (emloop-comp _ (negsuc n) -1)

  EM→S¹ : EM ℤ 1 → S¹
  EM→S¹ = EM1.rec _ isGroupoidS¹ base intLoop λ g h
    → compPathL→PathP (sym (lUnit _) ∙ (intLoop-hom g h))

  S¹≅EM : Iso S¹ (EM {ℓ-zero} ℤ 1)
  S¹≅EM .Iso.fun = S¹→EM
  S¹≅EM .Iso.inv = EM→S¹
  S¹≅EM .Iso.sec = EM1.elimSet _ (λ _ → emsquash _ _) refl
    λ g i j → S¹→EM-intLoop g j i
  S¹≅EM .Iso.ret base = refl
  S¹≅EM .Iso.ret (loop i) j = lUnit loop (~ j) i

EMDirProd : {ℓ : Level} (H K : AbGroup ℓ) (n : ℕ)
  → EM∙ (AbDirProd H K) n ≡ (EM∙ H n) ×∙ (EM∙ K n)
EMDirProd H K n =
  ua∙ (EMDirProdEquiv H K n)
      (EMProd→ProdEM∙ H K n .snd)

-- all just arithmetic
stablyNFiniteOfSusp : (n : HLevel) (A : Pointed ℓ)
      → stablyNFinite (suc n) (S∙ A) → stablyNFinite n A
stablyNFiniteOfSusp n A = PT.rec (stablyNFinite-isProp {X = A})
  λ p → ∣ suc (fst p) , PT.rec nFinite-isProp (λ x → ∣ (fst x) , (fst (snd x)) ,
                        transport (λ i → isConnectedFun (+-suc (fst p) n i)
                                                         (fst (snd x)))
                                  (snd (snd x)) ∣₁) (snd p) ∣₁

susp-stablyNFinite : (n : HLevel) (A : Pointed ℓ)
  → stablyNFinite n A → stablyNFinite (suc n) (S∙ A)
susp-stablyNFinite n A = PT.rec squash₁
  (uncurry λ m → PT.rec squash₁
    (uncurry λ X → uncurry λ f c
      → ∣ (m , ∣ ((_ , isFinCWSusp {n = 1}
        (fst X) (snd X))
        , transport (p m) ∘ suspFun f
        , isConnectedComp (transport (p m))
           (suspFun f) (m + suc n)
           (isEquiv→isConnected _
             (isEquivTransport (p m)) _)
           (subst (λ k → isConnectedFun k (suspFun f))
                  (sym (+-suc m n))
                  (isConnectedSuspFun f _ c))) ∣₁) ∣₁))
  where
  p : (m : _) → _ ≡ _
  p m = cong Susp (sym (Susp^'≡Susp^ m))
      ∙ Susp^'≡Susp^ (suc m)

stablyNFiniteDrop : {X : Pointed ℓ} (n : HLevel)
    → stablyNFinite (1 + n) X → stablyNFinite n X
stablyNFiniteDrop {X = X} n =
  PT.rec (stablyNFinite-isProp {n = n} {X = X})
         λ hX → ∣ (fst hX) ,
                  nFiniteDrop (fst hX + n)
                  (transport (λ i → nFinite (srthmetic (fst hX) n i) (Susp^ (fst hX) (typ X))) (snd hX)) ∣₁

stablyNFiniteLower : {X : Pointed ℓ} (m n : HLevel)
  → stablyNFinite (m + n) X → stablyNFinite n X
stablyNFiniteLower zero n hX = hX
stablyNFiniteLower {X = X} (suc m) n hX =
  stablyNFiniteLower {X = X} m n (stablyNFiniteDrop {X = X} (m + n) hX)


-- need definitions or helper lemmas about cofiber sequences (and finite CW complexes?)
stablyNFiniteCofiber : {n : HLevel} {A B C : Pointed ℓ} (S : CofiberSeq A B C)
    → stablyNFinite n A → stablyNFinite (1 + n) B → stablyNFinite (1 + n) C
stablyNFiniteCofiber {ℓ} {n = n} {A = A} {B = B} {C = C} S hA =
  PT.rec (isProp→ squash₁)
         (λ hA' hB → PT.rec squash₁ γ5 (γ6 hA' (stablyNFinite→stablyNFinite' hB)))
         (stablyNFinite→stablyNFinite' hA)
  where

    S' : (k : ℕ) → CofiberSeq (Susp∙^ k A) (Susp∙^ k B) (Susp∙^ k C)
    S' k = copuppe-Cof k S

    rtmtc : (k k' : ℕ) → (k + (1 + k')) ≡ (1 + (k + k'))
    rtmtc k k' = +-assoc k 1 k' ∙ cong (_+ k') (+-comm k 1)
      

    γ1 : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ A))) ]
     isConnectedFun (m + n) f))
     → (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
     isConnectedFun (m + (suc n)) f))
     → (Σ[ m ∈ ℕ ]
         (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ A))) ]
         isConnectedFun (m + n) f)
         × (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
         isConnectedFun (m + (suc n)) f))
    γ1 (m , C , f , hf) (m' , C' , f' , hf') =
      (m + m') ,
      ((((Susp^ m' (typ C)) , (isFinCWSusp (typ C) (snd C)))
        , (transport (λ i → Susp^ m' (typ C) → Susp^ (+-comm m' m i) (typ A))
           (transport (λ i → Susp^ m' (typ C)
                           → Susp^-need {X = typ A} m' m (~ i))
             (Susp→^ m' f)))
        , isConnectedTrnspConnected (λ i → Susp^ (+-comm m' m i) (typ A))
          _ (isConnectedTrnspConnected (Susp^-need m' m ⁻¹) (Susp→^ m' f)
             (transport (λ i → isConnectedFun (rtmtk m m' n (~ i))
                                (Susp→^ m' f))
                        (Susp→^-conn m' (m + n) f hf) )))
      , ((Susp^ m (typ C')) , (isFinCWSusp (typ C') (snd C')))
      , (transport (λ i → Susp^ m (typ C')
                        → Susp^-need {X = typ B} m m' (~ i))
                   (Susp→^ m f'))
       , (isConnectedTrnspConnected (Susp^-need m m' ⁻¹) (Susp→^ m f')
             (transport (λ i → isConnectedFun (+-assoc m m' (suc n) i)
                                (Susp→^ m f'))
                        (Susp→^-conn m (m' + suc n) f' hf'))))
     where
      rtmtk : (k0 k1 k2 : ℕ) → (k0 + k1 + k2) ≡ k1 + (k0 + k2)
      rtmtk k0 k1 k2 = cong (_+ k2) (+-comm k0 k1) ∙ +-assoc k1 k0 k2 ⁻¹
      
    γ2 : (Σ[ m ∈ ℕ ]
     (Σ[ C ∈ FinCW ℓ ]
      Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ A))) ]
      isConnectedFun (m + n) f)
     × (Σ[ C ∈ FinCW ℓ ]
       Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
       isConnectedFun (m + (suc n)) f))
     → ∥ (Σ[ m ∈ ℕ ]
         (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW (m + n) C ]
         Σ[ f ∈ (C → (Susp^ m (typ A))) ]
         isConnectedFun (m + n) f)
         × (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
         isConnectedFun (m + (suc n)) f)) ∥₁
    γ2 (m , (C , f , hf) , (C' , f' , hf')) =
      PT.rec squash₁
      (λ C^ → ∣ m , (((fst C^) , ((fst (snd C^)) , ((f ∘ fst (snd (snd C^)))
                  , (isConnectedComp f (fst (snd (snd C^)))
                                     (m + n) hf (snd (snd (snd C^)))))))
                  , (C' , f' , hf')) ∣₁)
      (mapFromNSkel (fst C) (snd C) (m + n))

    γ3 : (T : Σ[ m ∈ ℕ ]
         (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW (m + n) C ]
         Σ[ f ∈ (C → (Susp^ m (typ A))) ]
         isConnectedFun (m + n) f)
         × (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
         isConnectedFun (m + (suc n)) f))
      → ∃[ f ∈ (fst (fst (snd T)) → typ (fst (snd (snd T)))) ]
          (fst (snd (snd (snd T))) ∘ f
          ≡ (fst (CofiberSeqInc (S' (fst T))) ∘ fst (snd (snd (fst (snd T))))))
    γ3 (m , (C , hC , f , hf) , (C' , f' , hf')) =
      liftFromNDimFinCW (m + n) C hC f'
        (isConnectedFunSubtr (m + n) 1 f'
          (transport (λ i → isConnectedFun (rtmtc m n i) f')
                     hf'))
        (fst (CofiberSeqInc (S' m)) ∘ f)

    γ4 : (T : Σ[ m ∈ ℕ ]
         (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW (m + n) C ]
         Σ[ f ∈ (C → (Susp^ m (typ A))) ]
         isConnectedFun (m + n) f)
         × (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
         isConnectedFun (m + (suc n)) f))
      → Σ[ f ∈ (fst (fst (snd T)) → typ (fst (snd (snd T)))) ]
          (fst (snd (snd (snd T))) ∘ f
          ≡ (fst (CofiberSeqInc (S' (fst T))) ∘ fst (snd (snd (fst (snd T))))))
      → stablyNFinite (1 + n) C
    γ4 (m , (C , hC , f , hf) , (C' , f' , hf')) (h , F) =
      stablyNFinite'→stablyNFinite
      ∣ m
      , ((cofib h) , isFinCWCofiberSeq₋ {S = cofiber-CofiberSeq₋ h}
                       (isNDimFinCW→isFinCW hC) (snd C'))
      , (fst (CofiberSeqMap-cofiber h (S' m) f f' F))
      , transport (λ i → isConnectedFun (rtmtc m n (~ i))
                           (fst (CofiberSeqMap-cofiber h (S' m) f f' F)))
          (CofiberSeqMapConn-cofiber (m + n) h (S' m) f f' F hf
            (transport (λ i → isConnectedFun (rtmtc m n i) f') hf')) ∣₁

    γ5 : (T : Σ[ m ∈ ℕ ]
         (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW (m + n) C ]
         Σ[ f ∈ (C → (Susp^ m (typ A))) ]
         isConnectedFun (m + n) f)
         × (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
         isConnectedFun (m + (suc n)) f))
         → stablyNFinite (1 + n) C
    γ5 T = PT.rec squash₁ (γ4 T) (γ3 T)

    γ6 : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW {ℓ = ℓ} C → (Susp^ m (typ A))) ]
     isConnectedFun (m + n) f))
     → stablyNFinite' {ℓ = ℓ} (1 + n) B
     → ∥ (Σ[ m ∈ ℕ ]
         (Σ[ C ∈ Type ℓ ] Σ[ hC ∈ isNDimFinCW (m + n) C ]
         Σ[ f ∈ (C → (Susp^ m (typ A))) ]
         isConnectedFun (m + n) f)
         × (Σ[ C ∈ FinCW ℓ ]
         Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ B))) ]
         isConnectedFun (m + (suc n)) f)) ∥₁
    γ6 hA = PT.rec squash₁ (λ hB → γ2 (γ1 hA hB))

stablyNFiniteExtension : {n : HLevel} {A B C : Pointed ℓ} (S : CofiberSeq A B C)
      → stablyNFinite n A → stablyNFinite n C → stablyNFinite n B
stablyNFiniteExtension {ℓ} {n = n} {A = A} {B = B} {C = C} S hA hC =
  stablyNFiniteOfSusp n B (stablyNFiniteCofiber S' hC (susp-stablyNFinite n A hA))
  where
    S' : CofiberSeq C (S∙ A) (S∙ B)
    S' = copuppe-Ext 0 S


safCofiber : {A B C : Pointed ℓ} → CofiberSeq A B C
    → saf A → saf B → saf C
safCofiber S sA sB 0 = stablyNFiniteDrop 0 (stablyNFiniteCofiber S (sA 0) (sB 1))
safCofiber S sA sB (suc n) = stablyNFiniteCofiber S (sA n) (sB (1 + n))

joinSuspTrick : ∀ {ℓ} (X₁ X₂ : Pointed ℓ) (M₁ M₂ : ℕ)
  → Susp^ (M₁ + M₂) (join (fst X₁) (fst X₂))
   ≡ join (Susp^ M₁ (typ X₁)) (Susp^ M₂ (typ X₂))
joinSuspTrick X₁ X₂ zero zero = refl
joinSuspTrick X₁ X₂ zero (suc M₂) =
    cong (Susp^ M₂)
      (isoToPath
       (compIso (congSuspIso join-comm)
        (compIso (invIso (Iso-joinSusp-suspJoin {A = X₂} {X₁}))
         join-comm)))
  ∙ joinSuspTrick X₁ (Susp∙ (typ X₂)) zero M₂
joinSuspTrick X₁ X₂ (suc M₁) M₂ =
    sym (cong (Susp^ (M₁ + M₂))
              (isoToPath (Iso-joinSusp-suspJoin {A = X₁} {X₂})))
  ∙ joinSuspTrick (Susp∙ (X₁ .fst)) X₂ M₁ M₂
  ∙ cong₂ join refl refl

saf⋀ : {A B : Pointed ℓ} → saf A → saf B → saf (A ⋀∙ B)
saf⋀ {ℓ = ℓ} {A = A} {B = B} sA sB m =
  PT.rec2 squash₁
    (uncurry (λ nA → PT.rec (isPropΠ (λ _ → squash₁))
      λ {(XA , f , cf)
      → uncurry (λ nB → PT.rec squash₁
      λ{(XB , g , cg)
        → main m nA nB XA XB f g
              (subst (λ k → isConnectedFun k f) (+-comm nA m) cf)
              (subst (λ k → isConnectedFun k g) (+-comm nB m) cg)})}))
    (sA m) (sB m)
  where
  main : (m nA nB : ℕ) (XA XB : FinCW ℓ)
    (f : fst XA → Susp^ nA (typ A))
    (g : fst XB → Susp^ nB (typ B))
    (cf : isConnectedFun (m + nA) f)
    (cg : isConnectedFun (m + nB) g)
    → stablyNFinite m (A ⋀∙ B)
  main zero nA nB XA XB f g cf cg =
    ∣ 0 , ∣ (_ , isFinCWUnit)
        , ((λ _ → inl tt) , (λ b → tt* , λ _ → refl)) ∣₁ ∣₁
  main (suc m) nA nB XA XB f g cf cg =
    TR.rec (isProp→isOfHLevelSuc (m + nA) squash₁)
      (λ {(x , xId)
      → TR.rec (isProp→isOfHLevelSuc (m + nB) squash₁)
        (λ {(y , yId) → ∣ ((nA + nB) , ∣
          ((((fst XA , x)) ⋀ ((fst XB , y))
          , isFinCW⋀ ((snd XA)) (snd XB))
          , (invEq (fst (Susp^⋀≃∙⋀Susp^ A B nA nB))
          ∘ ((f , xId) ⋀→ (g , yId)))
          , isConnectedComp
               (invEq (fst (Susp^⋀≃∙⋀Susp^ A B nA nB)))
               ((f , xId) ⋀→ (g , yId))
            (nA + nB + suc m)
            (isEquiv→isConnected _
              (snd (invEquiv (fst (Susp^⋀≃∙⋀Susp^ A B nA nB)))) _)
            (subst (λ k → isConnectedFun k ((f , xId) ⋀→ (g , yId)))
              (cong₂ min
                (cong (nB +_) (+-comm (suc m) nA)
                ∙ +-assoc nB nA (suc m)
                ∙ cong (_+ suc m) (+-comm nB nA))
                (cong (nA +_) (+-comm (suc m) nB)
                ∙ +-assoc nA nB (suc m)) ∙ min-diag (nA + nB + suc m))
              (isConnected⋀→ (suc (m + nA)) (suc (m + nB)) (suc nB) (suc nA)
                conXB conSuspXA (f , xId) (g , yId) cf cg))) ∣₁) ∣₁})
        (cg (Susp∙^ nB B .snd) .fst)})
      (cf (Susp∙^ nA A .snd) .fst)
        where
        conSuspXA : isConnected (suc nA) (Susp^ nA (typ A))
        conSuspXA = subst (λ r → isConnected r (Susp^ nA (typ A)))
                     (+-comm nA 1)
                     (isConnectedSusp^ (suc zero) nA
                       (∣ pt A ∣ , (isOfHLevelTrunc 1 ∣ (pt A) ∣)))

        conXB : isConnected (suc nB) (fst XB)
        conXB = isConnectedCodomain (suc nB) m g
                   (subst (λ r → isConnected r (Susp^ nB (typ B)))
                     (+-comm nB 1)
                     (isConnectedSusp^ (suc zero) nB
                       (∣ pt B ∣ , (isOfHLevelTrunc 1 ∣ (pt B) ∣))))
                       (subst (λ k → isConnectedFun k g) (sym (+-suc m nB)) cg)

saf⋁ : {A B : Pointed ℓ} → saf A → saf B → saf (A ⋁∙ₗ B)
saf⋁ {ℓ = ℓ} {A} {B} sA sB zero = PT.rec2 squash₁
  (uncurry λ nA → PT.rec (isPropΠ (λ _ → squash₁))
    λ {(XA , f , cf) → uncurry λ nB → PT.rec squash₁
    λ {(XB , g , cg) → ∣ 0 , ∣ ((_ , isFinCWUnit) , ((λ _ → inl (pt A))
    , λ b → tt* , (λ _ → refl))) ∣₁ ∣₁}})
  (sA zero) (sB zero)
saf⋁ {ℓ = ℓ} {A} {B} sA sB (suc m) = PT.rec2 squash₁
  (uncurry (λ nA → PT.rec (isPropΠ λ _ → squash₁)
    λ {(XA , f , cf) → uncurry λ nB →
      PT.rec squash₁ λ {(XB , g , cg)
      → TR.rec (isProp→isOfHLevelSuc (nA + m) squash₁)
        (λ {(x , px) →
        TR.rec (isProp→isOfHLevelSuc (nB + m) squash₁)
          (λ {(y , py) →
          ∣ d nA nB XA XB f g cf cg x y px py
          , main nA nB XA XB f g cf cg x y px py ∣₁})
          (subst (λ k → isConnectedFun k g)
               (+-suc nB m) cg
               (Susp∙^ nB B .snd) .fst)})
        (subst (λ k → isConnectedFun k f)
               (+-suc nA m) cf
               (Susp∙^ nA A .snd) .fst)}}))
  (sA (suc m)) (sB (suc m))
  where
  module _ (nA nB : ℕ) (XA XB : FinCW ℓ)
    (f : fst XA → Susp^ nA (typ A))
    (g : fst XB → Susp^ nB (typ B))
    (cf : isConnectedFun (nA + suc m) f)
    (cg : isConnectedFun (nB + suc m) g)
    (x : fst XA) (y : fst XB)
    (fp : f x ≡ Susp∙^ nA A .snd) (gp : g y ≡ Susp∙^ nB B .snd)
    where
    ma = max nA nB
    mi = min nA nB

    P : FinCW ℓ
    fst P = Susp∙^ nB (fst XA , x) ⋁ Susp∙^ nA (fst XB , y)
    snd P = isFinCW⋁ {A = Susp∙^ nB (fst XA , x)}
                     {B = Susp∙^ nA (fst XB , y)}
                     (isFinCWSusp {n = nB} (fst XA) (snd XA))
                     (isFinCWSusp {n = nA} (fst XB) (snd XB))

    d : ℕ
    d = nA + nB

    Susp^+Iso : ∀ {ℓ} {A : Type ℓ} (n m : ℕ)
      → Iso (Susp^ n (Susp^ m A)) (Susp^ (n + m) A)
    Susp^+Iso zero m = idIso
    Susp^+Iso (suc n) m =
      compIso
        (invIso (equivToIso (Susp^Equiv (isoToEquiv (Susp^-comm-Iso m _)) n)))
        (Susp^+Iso n m)

    Susp^+Iso∙ : ∀ {ℓ} (A : Pointed ℓ) (n m : ℕ)
      → Iso.fun (Susp^+Iso {A = typ A} n m) (Susp∙^ n (Susp∙^ m A) .snd)
      ≡ snd (Susp∙^ (n + m) A)
    Susp^+Iso∙ A zero m = refl
    Susp^+Iso∙ A (suc n) m =
        cong (Iso.fun (Susp^+Iso n m))
             (invEquiv∙ (Susp^Equiv∙ n
               (isoToEquiv (Susp^-comm-Iso m (typ A))
               , Susp^-comm-Equiv∙ m A .snd)) .snd)
      ∙ Susp^+Iso∙ (_ , north) n m

    f* : Σ[ f' ∈ (Susp^ nB (fst XA) → Susp^ (nA + nB) (typ A)) ]
           (isConnectedFun (suc (nA + nB + m)) f')
    f* = _
      , isConnectedComp _ (Susp^Fun f nB)
         (suc (nA + nB + m))
         (isEquiv→isConnected _
           ((isoToEquiv (Susp^+Iso nB nA)
            ∙ₑ substEquiv (λ k → Susp^ k (fst A)) (+-comm nB nA)) .snd) _)
         (subst (λ k → isConnectedFun k (Susp^Fun f nB))
                (+-comm nB (nA + suc m)
              ∙ sym (+-assoc nA (suc m) nB)
              ∙ +-suc nA (m + nB)
              ∙ cong suc (cong (nA +_) (+-comm m nB)
              ∙ +-assoc nA nB m))
                (isConnectedSusp^Fun f _ nB cf))

    g* : Σ[ g' ∈ (Susp^ nA (fst XB) → Susp^ (nA + nB) (typ B)) ]
           (isConnectedFun (suc (nA + nB + m)) g')
    g* = _
      , isConnectedComp _ (Susp^Fun g nA)
         (suc (nA + nB + m))
         (isEquiv→isConnected _ ((isoToIsEquiv (Susp^+Iso nA nB))) _)
         (subst (λ k → isConnectedFun k (Susp^Fun g nA))
                (cong (nA +_) (+-suc nB m)
                ∙ +-suc nA (nB + m)
                ∙ +-assoc (suc nA) nB m )
                (isConnectedSusp^Fun g _ nA cg))

    e : (Susp∙^ d A ⋁ Susp∙^ d B) ≃ Susp^ d (typ (A ⋁∙ₗ B))
    e = invEquiv (fst (⋁Susp^≃∙Susp^⋁ A B d))

    t : Σ[ f ∈ (decodeFinCW P → Susp∙^ d A ⋁ Susp∙^ d B) ]
         (isConnectedFun (suc (d + m)) f)
    t = _ , isConnectedPushout→
             (λ _ → Susp∙^ nB (fst XA , x) .snd)
             (λ _ → Susp∙^ nA (fst XB , y) .snd)
             (λ _ → Susp∙^ d A .snd)
             (λ _ → Susp∙^ d B .snd)
             (λ _ → tt) (fst f*) (fst g*)
             (funExt (λ x → cong (subst (λ k → Susp^ k (fst A)) (+-comm nB nA))
               (cong (Iso.fun (Susp^+Iso nB nA)) (Susp^Fun∙ (f , fp) nB .snd)
               ∙ Susp^+Iso∙ A nB nA)
               ∙ λ j → transp (λ i → Susp^ (+-comm nB nA (i ∨ j)) (fst A))
                               j (snd (Susp∙^ (+-comm nB nA j) A))))
             (funExt (λ x →
                 cong (Iso.fun (Susp^+Iso nA nB)) (Susp^Fun∙ (g , gp) nA .snd)
               ∙ Susp^+Iso∙ B nA nB))
               (d + m)
             (isEquiv→isConnected _ (idIsEquiv _) _)
             (f* .snd) (g* .snd)

    main : nFinite (d + suc m) (Susp^ d (typ (A ⋁∙ₗ B)))
    main = ∣ (P , (fst e ∘ fst t
           , isConnectedComp (fst e) (fst t)
             (d + suc m)
             (isEquiv→isConnected _ (snd e) _)
             (subst (λ k → isConnectedFun k (fst t))
                    (sym (+-suc d m)) (snd t)))) ∣₁

safSusp : {A : Pointed ℓ} → saf A → saf (Susp∙ (typ A))
safSusp {A = A} sA m =
  PT.rec squash₁
    (uncurry (λ n → PT.map
      λ {(X , f , cf) → n , ∣ ((_ , isFinCWSusp {n = 1} _ (snd X) )
        , ((transport (sym (Susp^-comm n (typ A))) ∘ suspFun f)
        , isConnectedComp
          (transport (sym (Susp^-comm n (typ A))))
          (suspFun f) (n + m)
          (isEquiv→isConnected _
            (isEquivTransport (sym (Susp^-comm n (typ A)))) (n + m))
          λ b → isConnectedSubtr (n + m) 1 (isConnectedSuspFun _ _ cf b ))) ∣₁}))
          (sA m)

isNFinite↓ : {A : Pointed ℓ} (n : ℕ)
  → stablyNFinite (suc n) (Susp∙ (typ A)) → stablyNFinite n A
isNFinite↓ {A = A} n = PT.rec squash₁
  (uncurry λ m → PT.map
    λ {(XA , f , cf) → (suc m) , ∣ XA
      , (f , subst (λ k → isConnectedFun k f) (+-suc m n) cf) ∣₁})

-- TODO: Maybe make more universe polymorphic?
saf× : {A B : Pointed ℓ} → saf A → saf B → saf (A ×∙ B)
saf× {ℓ = ℓ} {A} {B} sA sB m =
  TR.rec squash₁ (λ p →
    isNFinite↓ {A = _ , pt A , pt B} m
      (subst (stablyNFinite (suc m))
             (sym (ua∙ {A = Susp∙ (typ A × typ B)}
                  (invEquiv SuspProduct^') p))
             (safSusp {A = _ , inl (inl (pt A))}
               (saf⋁ {A = _ , inl (pt A)} {B = _ , inl tt}
                 (saf⋁ {A = A} {B = B} sA sB) (saf⋀ sA sB)) (suc m))))
  (isConnectedPath _ (isConnectedSusp 1 (∣ inl (inl (pt A)) ∣
    , (λ _ → isOfHLevelTrunc 1 _ _)))
    (fst (invEquiv SuspProduct^') north) north .fst)
  where
  SuspProduct^' : (Susp ((A ⋁∙ₗ B) ⋁ (A ⋀∙ B)))
                ≃ Susp (typ A × typ B)
  SuspProduct^' =
    compEquiv (isoToEquiv
      (compIso Iso-⋁Susp-Susp⋁
        (⋁Iso (isoToEquiv Iso-⋁Susp-Susp⋁ , refl)
              (idEquiv∙ _))))
        (SuspProduct A B)

safS1× : {A : Pointed ℓ} → saf A → saf ((S {ℓ} 1) ×∙ A)
safS1× {ℓ} {A} safA = saf× {A = S {ℓ} 1} {B = A} (saf-Sn 1) safA

safS¹× : {A : Pointed ℓ} → saf A → saf (S¹∙ ×∙ A)
safS¹× {ℓ = ℓ} {A = A} sA =
  subst saf lem (safS1× {A = A} sA)
  where
  lem : ((S {ℓ} 1) ×∙ A) ≡ S¹∙ ×∙ A
  lem = ua∙ (Σ-cong-equiv-fst (isoToEquiv rUnit*×Iso)) refl

stablyNFiniteJoin'-alt : {X₁ X₂ : Pointed ℓ} (m₁ m₂ n₂ : HLevel)
  (hXm₁ : isConnected (m₁ + 2) (typ X₁)) (hX₁ : stablyNFinite' 1 X₁)
  (hXm₂ : isConnected m₂ (typ X₂)) (hXn₂ : stablyNFinite' n₂ X₂)
  (k : HLevel) (hk₁ : k ≤ 1 + m₂) (hk₂ : k ≤ n₂ + (m₁ + 2))
  → stablyNFinite' k (join∙ X₁ X₂)
stablyNFiniteJoin'-alt {ℓ} {X₁} {X₂} m₁ m₂ n₂ hXm₁ hX₁ hXm₂ hXn₂ k hk₁ hk₂ =
  γ α
  where


    -- notice, the following construction is only possible because X₁ is pointed
    -- we could weaken this hypothesis
    -- but then we would only have an `α' up to propositional truncation
    α : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₁))) ]
     (isConnectedFun (m + 1) f) × (isConnected (m + (m₁ + 2)) (decodeFinCW C))))
    fst α = 0
    fst (snd α) = Unit* , isFinCWUnit
    fst (snd (snd α)) = λ _ → pt X₁
    fst (snd (snd (snd α))) = isConnectedPoint* 1 (isConnectedSubtr 2 m₁ hXm₁) (pt X₁)
    snd (snd (snd (snd α))) = isConnectedUnit* (m₁ + 2)


    β : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₁))) ]
     (isConnectedFun (m + 1) f) × (isConnected (m + (m₁ + 2)) (decodeFinCW C))))
      → (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₂))) ]
     isConnectedFun (m + n₂) f))
      → stablyNFinite' k (join∙ X₁ X₂)
    β (M₁ , C₁ , f₁ , cf₁ , cC₁) (M₂ , C₂ , f₂ , cf₂) =
      ∣ (M₁ + M₂)
       , (((join (typ C₁) (typ C₂))
       , (isFinCWJoin (snd C₁) (snd C₂)))
       , (transport (λ i → join (typ C₁) (typ C₂)
                                → joinSuspTrick X₁ X₂ M₁ M₂ (~ i)) (join→ f₁ f₂))
       , isConnectedTrnspConnected (sym (joinSuspTrick X₁ X₂ M₁ M₂)) (join→ f₁ f₂)
           (isConnectedFunJoin f₁ f₂ (M₁ + 1) (M₂ + n₂)
              (M₁ + (m₁ + 2)) (M₂ + m₂) (M₁ + M₂ + k)
              (arithmetric M₁ M₂ k 1 m₂ hk₁)
              (arithmetric' M₂ M₁ k n₂ (m₁ + 2) hk₂)
              cf₁ cf₂ cC₁ (Susp^-conn m₂ M₂ (typ X₂) hXm₂))) ∣₁

    γ : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₁))) ]
     (isConnectedFun (m + 1) f) × (isConnected (m + (m₁ + 2)) (decodeFinCW C))))
        → stablyNFinite' k (join∙ X₁ X₂)
    γ hX₁ = PT.rec (stablyNFinite'-isProp {ℓ} {k} {join∙ X₁ X₂})
                   (β hX₁)
                   hXn₂



-- If Xᵢ is stably (nᵢ-1)-finite and (mᵢ-2)-connected (i = 1, 2)
-- then the join X₁ * X₂ is stably min(n₁+m₂-1, n₂+m₁-1)-connected
-- provided that m₁ ≤ n₁ (i.e., that m₁-2 < n₁-1).
stablyNFiniteJoin' : {X₁ X₂ : Pointed ℓ} (m₁ n₁ m₂ n₂ : HLevel)
  (hmn₁ : m₁ ≤ n₁)
  (hXm₁ : isConnected m₁ (typ X₁)) (hXn₁ : stablyNFinite' n₁ X₁)
    (hXm₂ : isConnected m₂ (typ X₂)) (hXn₂ : stablyNFinite' n₂ X₂)
  (k : HLevel) (hk₁ : k ≤ n₁ + m₂) (hk₂ : k ≤ n₂ + m₁)
  → stablyNFinite' k (join∙ X₁ X₂)
stablyNFiniteJoin' {ℓ} {X₁} {X₂}
  m₁ n₁ m₂ n₂ (a , p) hXm₁ hXn₁ hXm₂ hXn₂ k hk₁ hk₂ =
  PT.rec (stablyNFinite'-isProp {ℓ} {k} {join∙ X₁ X₂})
     γ hXn₁
  where
    arithmetic : (M₁ : ℕ) → (a + (M₁ + m₁)) ≡ (M₁ + n₁)
    arithmetic M₁ = cong (a +_) (+-comm M₁ m₁)
                 ∙ +-assoc a m₁ M₁
                 ∙ cong (_+ M₁) p
                 ∙ +-comm n₁ M₁

    connectivityC₁ : (M₁ : ℕ) (C₁ : Type ℓ)
                     (f : C₁ → (Susp^ M₁ (typ X₁)))
                     (cf : isConnectedFun (M₁ + n₁) f)
                  → isConnected (M₁ + m₁) C₁
    connectivityC₁ M₁ C₁ f cf =
                  isConnectedFun→isConnected (M₁ + m₁)
                    (isConnectedComp (λ _ → tt) f (M₁ + m₁)
                      (isConnected→isConnectedFun (M₁ + m₁)
                        (Susp^-conn m₁ M₁ (typ X₁) hXm₁))
                      (isConnectedFunSubtr (M₁ + m₁) a f
                      (transport (λ i → isConnectedFun (arithmetic M₁ (~ i)) f) cf)))

    β : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₁))) ]
     isConnectedFun (m + n₁) f))
      → (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₂))) ]
     isConnectedFun (m + n₂) f))
      → stablyNFinite' k (join∙ X₁ X₂)
    β (M₁ , C₁ , f₁ , cf₁) (M₂ , C₂ , f₂ , cf₂) =
      ∣ M₁ + M₂ , ((join (typ C₁) (typ C₂)) , isFinCWJoin (snd C₁) (snd C₂))
               , transport (λ i → join (typ C₁) (typ C₂)
                                → joinSuspTrick X₁ X₂ M₁ M₂ (~ i)) (join→ f₁ f₂)
               , isConnectedTrnspConnected (sym (joinSuspTrick X₁ X₂ M₁ M₂))
                                           (join→ f₁ f₂)
                   (isConnectedFunJoin f₁ f₂ (M₁ + n₁) (M₂ + n₂) (M₁ + m₁)
                                       (M₂ + m₂) (M₁ + M₂ + k)
                                       (arithmetric M₁ M₂ k n₁ m₂ hk₁)
                                       (arithmetric' M₂ M₁ k n₂ m₁ hk₂)
                                       cf₁ cf₂ (connectivityC₁ M₁ (typ C₁) f₁ cf₁)
                                       (Susp^-conn m₂ M₂ (typ X₂) hXm₂)) ∣₁


    γ : (Σ[ m ∈ ℕ ] (Σ[ C ∈ FinCW ℓ ]
     Σ[ f ∈ (decodeFinCW C → (Susp^ m (typ X₁))) ]
     isConnectedFun (m + n₁) f))
        → stablyNFinite' k (join∙ X₁ X₂)
    γ hX₁ = PT.rec (stablyNFinite'-isProp {ℓ} {k} {join∙ X₁ X₂})
                   (β hX₁)
                   hXn₂

stablyNFiniteJoin-alt : {X₁ X₂ : Pointed ℓ} (m₁ m₂ n₂ : HLevel)
  (hXm₁ : isConnected (m₁ + 2) (typ X₁)) (hX₁ : stablyNFinite 1 X₁)
  (hXm₂ : isConnected m₂ (typ X₂)) (hXn₂ : stablyNFinite n₂ X₂)
  (k : HLevel) (hk₁ : k ≤ 1 + m₂) (hk₂ : k ≤ n₂ + (m₁ + 2))
  → stablyNFinite k (join∙ X₁ X₂)
stablyNFiniteJoin-alt {ℓ} {X₁} {X₂} m₁ m₂ n₂ hXm₁ hX₁ hXm₂ hXn₂ k hk₁ hk₂ =
  stablyNFinite'→stablyNFinite {X = join∙ X₁ X₂}
   (stablyNFiniteJoin'-alt {ℓ} {X₁} {X₂} m₁ m₂ n₂ hXm₁
     (stablyNFinite→stablyNFinite' {X = X₁} hX₁) hXm₂
     (stablyNFinite→stablyNFinite' {X = X₂} hXn₂) k hk₁ hk₂)

stablyNFiniteJoin : {X₁ X₂ : Pointed ℓ} (m₁ n₁ m₂ n₂ : HLevel)
  (hmn₁ : m₁ ≤ n₁)
  (hXm₁ : isConnected m₁ (typ X₁)) (hXn₁ : stablyNFinite n₁ X₁)
    (hXm₂ : isConnected m₂ (typ X₂)) (hXn₂ : stablyNFinite n₂ X₂)
  (k : HLevel) (hk₁ : k ≤ n₁ + m₂) (hk₂ : k ≤ n₂ + m₁)
  → stablyNFinite k (join∙ X₁ X₂)
stablyNFiniteJoin {ℓ} {X₁} {X₂} m₁ n₁ m₂ n₂ hmn₁ hXm₁ hXn₁ hXm₂ hXn₂ k hk₁ hk₂ =
  stablyNFinite'→stablyNFinite {X = join∙ X₁ X₂}
  (stablyNFiniteJoin' {ℓ} {X₁} {X₂} m₁ n₁ m₂ n₂ hmn₁ hXm₁
  (stablyNFinite→stablyNFinite' {X = X₁} hXn₁) hXm₂
  (stablyNFinite→stablyNFinite' {X = X₂} hXn₂) k hk₁ hk₂)

stablyNFiniteApprox : {X Y : Pointed ℓ} (f : X →∙ Y)
    (n : HLevel) (hf : isConnectedFun n (fst f))
    → stablyNFinite n X → stablyNFinite n Y
stablyNFiniteApprox f n hf hX =
  PT.rec squash₁ (λ hX' → ∣ (fst hX') ,
  (nFiniteApprox (Susp→^ (fst hX') (fst f))
  (fst hX' + n)
  (Susp→^-conn (fst hX') n (fst f) hf)
  (snd hX')) ∣₁) hX



stablyNFiniteApprox' : {X Y : Pointed ℓ} (f : X →∙ Y)
    (n : HLevel) (hf : isConnectedFun (1 + n) (fst f))
    → stablyNFinite n Y → stablyNFinite n X
stablyNFiniteApprox' {ℓ} {X} {Y} f n cf hY =
  PT.rec squash₁ (λ hY' → ∣ γ hY' ∣₁) hY
  where
    drthmtc : (m n : ℕ) → (m + (1 + n)) ≡ (1 + (m + n))
    drthmtc m n = +-suc m n

    susp-f : (m : ℕ) → Susp^ m (typ X) → Susp^ m (typ Y)
    susp-f m = Susp→^ m (fst f)

    susp-f-conn : (m : ℕ) → isConnectedFun (1 + (m + n)) (susp-f m)
    susp-f-conn m = transport (λ i → isConnectedFun (drthmtc m n i) (susp-f m))
                              (Susp→^-conn m (1 + n) (fst f) cf)

    γ : (hY' : Σ[ m ∈ ℕ ] nFinite (m + n) (Susp^ m (typ Y)))
       → Σ[ m ∈ ℕ ] nFinite (m + n) (Susp^ m (typ X))
    γ (m , hY') = m , nFiniteApprox' (susp-f m) (m + n) (susp-f-conn m) hY'


-- Invariance under isomorphism.
-- This is only interesting for levels ℓ ≠ ℓ', otherwise just use univalence.

nFiniteOfIso : {n : HLevel} {X : Type ℓ} {X' : Type ℓ'} (i : Iso X X')
  → nFinite n X → nFinite n X'
nFiniteOfIso {n = n} {X = X} {X' = X'} i = PT.map main
  where
    main : Σ[ C ∈ FinCW ℓ ] Σ[ f ∈ (decodeFinCW C → X) ] isConnectedFun n f
         → Σ[ C ∈ FinCW ℓ' ] Σ[ f ∈ (decodeFinCW C → X') ] isConnectedFun n f
    main (C , f , cf) =
      fst resizeEquiv C , i .Iso.fun ∘ f ∘ fst (invEquiv (resizeEquiv-Equiv C)) ,
      isConnectedComp (i .Iso.fun) (f ∘ fst (invEquiv (resizeEquiv-Equiv C))) n
        (isEquiv→isConnected (i .Iso.fun) (isoToEquiv i .snd) n)
        (isConnectedComp _ _ n cf
         (isEquiv→isConnected _ (snd (invEquiv (resizeEquiv-Equiv C))) n))

-- induced isomorphism between iterated suspensions
IsoSusp^ : {A : Type ℓ} {B : Type ℓ'} → Iso A B → (n : ℕ)
  → Iso (Susp^ n A) (Susp^ n B)
IsoSusp^ i zero = i
IsoSusp^ i (suc n) = IsoSusp^ (IsoType→IsoSusp i) n

stablyNFiniteOfIso : {n : HLevel} {X : Pointed ℓ} {X' : Pointed ℓ'}
  (i : Iso (typ X) (typ X')) → stablyNFinite n X → stablyNFinite n X'
stablyNFiniteOfIso {n = n} {X = X} {X' = X'} i = PT.map main
  where
    main : Σ[ m ∈ ℕ ] nFinite (m + n) (Susp^ m (typ X))
         → Σ[ m ∈ ℕ ] nFinite (m + n) (Susp^ m (typ X'))
    main (m , h) = (m , nFiniteOfIso (IsoSusp^ i m) h)

safOfIso : {X : Pointed ℓ} {X' : Pointed ℓ'}
  (i : Iso (typ X) (typ X')) → saf X → saf X'
safOfIso i h n = stablyNFiniteOfIso i (h n)
