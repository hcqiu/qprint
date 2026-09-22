{-# OPTIONS --safe --cubical --guardedness #-}
module Identity where

open import Cubical.Foundations.Prelude

identity : {A : Type} (x : A) → x ≡ x
identity x = refl
