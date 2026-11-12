# Pre-stated rule: wide-grid state family (round 2 against the same 25 part-a fires; Iris/orchestrator)

**Timing.** Written at about 20:18 UTC on 2026-11-12, before any code for this family exists and before any run. The
git timestamp of this commit is the record. Already known when this was written (3ec5a8bc, unverified):
- mcem_state 0.0605, mcem_rate 0.0686, plug-in 0.0569, logistic_cf 0.0566, persistence 0.0646, MCEM 0.0660;
- the top grid edge (m = 2) was binding.

**Earlier tries, disclosed.** Two arms (mcem_rate, mcem_state; RULE_rate_arm.md) were tried on these fires and
failed. The per-fire online multiplier is dropped and is not carried forward.

**Common setup.** Folds, fires, intervals, scored cells and labels are identical to cv_part_a, checked element by
element.
- Grid m ∈ {1/16, 1/8, 1/4, 1/2, 1, 2, 4, 8}. A uniform multiplier is an exact time change for first passage, so
  every p_m comes from ONE simulation set per kernel, run to 8T.
- 512 simulations per interval. Seeds: 99_000 + 31·fold + i for the MCEM kernel, 99_500 + 31·fold + i for the
  plug-in kernel.
- Probabilities are clipped to [1/513, 1 − 1/513] wherever a likelihood is taken.
- Nothing from a test fire's current or later intervals is ever used.

**Arms (three; one declared family):**
1. **mcem_state_wide.** MCEM kernel, quiet/active state per interval. The weights π over the grid are fitted by EM
   on the Bernoulli likelihood of intervals of fires in the OTHER four folds. Forecast p = Σ π_m p_m.
2. **mcem_lag1_wide.** MCEM kernel. The weights for interval j of a fire depend only on that fire's interval j − 1:
   - w_j = ρ · q_{j−1} + (1 − ρ) · π, where q_{j−1} ∝ π_m · exp(κ · ℓ̄_m(j−1)) and ℓ̄_m is the per-cell MEAN Bernoulli
     log-likelihood of interval j − 1 under p_m (tempered: κ is an effective number of observations);
   - the first interval of each fire uses π;
   - π as in arm 1 for that fold;
   - (ρ, κ) are chosen from the fixed grid ρ ∈ {0, 0.25, 0.5, 0.75, 0.9} × κ ∈ {1, 10, 100, 1000}, by maximising the
     untempered Bernoulli predictive log-likelihood of the OTHER four folds' intervals (each fold separately);
   - ρ = 0 is exactly arm 1.
3. **plugin_state_wide.** Arm 1's form on the plug-in kernel (fold plug-in thetas). It may correct for what
   plug-in's bias already compensates; if only this arm passes, the report says so plainly.

**Bar (per arm, each judged on its own).** The arm must beat BOTH plug-in and logistic_cf on pooled Brier, and for
each comparison both of these must hold:
1. the paired fire-bootstrap 95% interval (10 000 draws, seed 20261112) lies entirely below 0;
2. the exact sign-flip randomisation p over fires (10 000 flips, seed 20261112) is < 0.05/3 = 0.0167. This is the
   multiplicity correction for three arms; it is round 2 on the same fires.

**Stopping rule, stated now.** If none of the three passes, the kernel line produces NO part-b candidate and no
further kernel arms are run for that purpose. Part b stays unnamed. Any further kernel work is diagnostic only. If
one or more passes, each passing arm is reported, with no preference among them on this evidence.

**Reported, with no decision attached:**
- the three reference rows (persistence, dilation_8h, logistic_cf), plus MCEM, plug-in and mcem_state from round 1;
- per-band Brier (0–1, 1–2, 2–4 km);
- weight at m = 8 and at m = 1/16 per fold (arms 1 and 3);
- the chosen (ρ, κ) per fold (arm 2);
- first vs later intervals for arm 2, with the comparators on the same cells;
- an internal check: the m = 1 forecast must reproduce MCEM and plug-in within Monte Carlo error, and the round-1
  m ≤ 2 grid must reproduce mcem_state within Monte Carlo error.

**Scope.** Covariate-free, homogeneous kernels; part-a development data (25 fires, including 4 H-dev); not the neural
refit. Unverified until Owen.
