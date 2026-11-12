# Conformal risk control for warning zones on cohort R (DEVELOPMENT-ONLY)

This is A1 §5.4 (revision 27). The procedure, the α values and the predictors were committed at 2c9f6349 **before** this run. It uses cohort R only: 6 exposed US2024 fires, full-rectangle perimeter labels, leave-one-fire-out, so each fold calibrates on n = 5 fires. **Nothing here is confirmatory, and no sealed fire is used.**

Reproduce: `python derive/crc_dev.py --dist <derive_dist output> --out CRC_DEV.json` (sha256 9ddfc33a…; the earlier 41c35991… output lacked the feasible-only means, and its numbers are otherwise unchanged).

**What is reported.**
- The zone is {p ≥ t̂}. The FNR is the share of a held-out fire's new-burn cells that fall outside its zone.
- "Zone share" is the zone's share of scored cells (cells unburned at cutoff), averaged over held-out fires.
- **Feasible** means t̂ > 0. Otherwise the zone is the whole domain and the result is uninformative.
- At n = 5, α = 0.1 is infeasible by arithmetic (stated before the run), and it is infeasible for every predictor.

## Primary: α = 0.2, full rectangle

| predictor | feasible folds | mean held-out FNR | mean zone share | zone, mean cells per interval | per-fire held-out FNR (Wapiti, Goat, Lava, RedRock, Pioneer, FishCreek) |
|---|---|---|---|---|---|
| d4_wind_seed0 | 6/6 | 0.048 | **0.289** | 1,742 | 0.155, 0.000, 0.026, 0.000, 0.001, 0.108 |
| logistic | 6/6 | 0.058 | 0.384 | 2,391 | 0.038, 0.000, 0.302, 0.000, 0.000, 0.009 |
| c651_mc | 0/6 | — | 1.000 (uninformative) | 6,223 | — |
| dilation_8h | 0/6 | — | 1.000 (uninformative) | 6,223 | — |

**Secondary results.**
- **α = 0.3, full rectangle.**
  - d4_wind: mean zone share 0.133, held-out FNR 0.170.
  - c651_mc: 0.154 and 0.168.
  - logistic: 0.162 and 0.173.
  - dilation_8h: infeasible.
- **4 km band, α = 0.2.**
  - d4_wind: zone share 0.676 of band cells, FNR 0.046.
  - logistic: 0.857 and 0.058.
  - c651_mc: feasible on 2 of 6 folds only. *Averaged over all folds* it shows FNR 0.031 and zone 0.897, but that mixes in 4 uninformative whole-domain folds. **Over the 2 feasible folds only** it is FNR 0.092 and zone 0.690 (Hannah's note). Every summary now reports both kinds of mean.

## Reading

1. **At α = 0.2, d4_wind needs the smallest warning zone:** about 29% of the scored rectangle, against 38% for the logistic. By the A1 §5.4 rule, a smaller zone at the same α is more useful for warnings. That inverts the Brier ranking, where the logistic is slightly better. Its held-out FNRs average 0.048, well under α. The procedure is conservative at n = 5.
2. **d4_wind's thresholds are tiny** (10⁻¹¹ to 10⁻⁸). CRC uses only the **ordering** of p, so d4_wind's ranking of cells is useful even where its probabilities are badly calibrated (§ LOGISTIC_DEV). An operational zone would be stated as an area or a rank, not as "p ≥ 10⁻¹¹".
3. **c651_mc and dilation_8h are uninformative at α = 0.2.**
   - c651's exact Monte Carlo zeros cover about 10% of positives on average, above the 4% the bound allows at n = 5, so any t > 0 fails.
   - dilation_8h is binary, and its misses are too many.
   - At α = 0.3, c651 is feasible and its zone is close to the others'.
4. **Per-fire FNR varies widely.** For example, the logistic misses 30% on Lava, and d4_wind misses 15.5% on Wapiti. The guarantee holds only in expectation over exchangeable fires, and 6 fires cannot verify it.

## Limits

- **The guarantee is a marginal expectation over exchangeable fires.** It says nothing about any single fire, and 6 leave-one-fire-out folds cannot check it empirically.

- Cohort R is exposed, and the 6 fires are from one season.
- Intervals within a fire are dependent.
- The zone share depends on the fixed rectangles, which were drawn with hindsight (A1 §3.1 item 4).
- This must not be applied to part b, c or d, or to H-test, without a prior amendment.
