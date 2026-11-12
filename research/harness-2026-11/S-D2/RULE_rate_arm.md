# Pre-stated rule: between-fire rate arm on the MCEM kernel (Iris item 2; orchestrator)

**Timing.** Written at about 19:55 UTC on 2026-11-12, before any code for this arm exists and before any run. The git
timestamp of this commit is the record. The baselines and banded Brier (7cc21f47) were already known when this was
written: MCEM 0.0660, plug-in 0.0569, logistic_cf 0.0566, persistence 0.0646.

**Arm ("mcem_rate").** It uses the MCEM kernel shape from the same fold (results/cv_part_a.json thetas) with a per-fire
rate multiplier m. Folds, fires, intervals, scored cells and labels are identical to cv_part_a.
- Grid m ∈ {1/16, 1/8, 1/4, 1/2, 1, 2}. A uniform multiplier on all rates (background included) is an exact time
  change for first passage, so p_m(cell) = P(τ ≤ m·T) is read from ONE set of simulations run to 2T.
- Simulations: 512 per interval, seed 88_000 + 31·fold + i.
- Prior over the grid, anchored on the pooled fit: w(m = 1) = 0.5 and 0.1 on each of the other five.
- Online (causal) update: before interval j of a fire, the weights are the prior times the Bernoulli likelihood of
  that fire's EARLIER intervals' scored cells under p_m, with p clipped to [1/513, 1 − 1/513]. The current interval's
  labels are never used. The first interval uses the prior.
- Forecast: p = Σ_m w_m p_m (mixture predictive).
- Internal check: the m = 1 forecast from these runs must reproduce the CV's MCEM Brier within Monte Carlo error.

**Comparators,** on the same cells: plug-in (0.0569) and logistic_cf (0.0566) from 7cc21f47. Persistence and
dilation_8h are reported as reference rows.

**Rule for "deserves part-b consideration".** mcem_rate must beat BOTH plug-in and logistic_cf on pooled Brier,
and for EACH comparison both of these must hold:
1. the paired fire-bootstrap 95% interval (10 000 draws, seed 20261112) lies entirely below 0;
2. the exact sign-flip randomisation p over fires (10 000 flips, seed 20261112) is < 0.05.

Owen found the bootstrap mildly anti-conservative with 25 fires, which is why condition 2 is required too. No other
margin. If either comparison fails, it does not qualify, and the result is reported as it is.

Also reported, with no decision attached: mcem_rate vs MCEM (the gain from per-fire rates), the per-band Brier
(0–1, 1–2, 2–4 km), the posterior mean m per fire at its last interval, and the share of weight on m = 1.

**Scope.** Covariate-free, homogeneous kernel, part-a development data (25 fires, including 4 H-dev). Not the neural
refit. Unverified until Owen.
