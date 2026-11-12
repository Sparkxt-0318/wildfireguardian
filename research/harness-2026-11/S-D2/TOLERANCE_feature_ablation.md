# Pre-stated rule: which real-data feature pushes the mean-field NLL far share up? (Iris, 2026-11-12)

**Timing.** Written at about 13:10 UTC on 2026-11-12, before any code for this test exists and before any run. The
git timestamp of this commit is the checkable record.

**Question.** In the verified synthetic run (780cbabe), mean-field NLL recovers far_share: 0.095 against a true 0.072,
and 0.602 against 0.602. On the 25 real part-a fires it gives a median of 0.679, while MCEM gives 0.066. Which feature
of real data, absent from the synthetic world, makes the difference?

**Design.**
- Truth: the `low_far` kernel of `run_shape_recovery.py` (true far_share 0.072).
- Setup: the same 64×64 grid, T = 240 h, 24 h brackets, and 5 seeds per arm.
- Estimators: plug-in, composite, mean-field NLL and MCEM, with MCEM_SHORT at a 0.1 h step.
- Features: one real-data feature is added at a time, at the scale measured on part a where one exists:
  1. **State error:** error in the survey-time burned states, at the scale of the kriged label uncertainty. This
     means flipping cells near the mapped perimeter. The exact parameterisation is fixed in the code docstring
     before the first run.
  2. **Time-varying rate:** the rate varies over time within a fire, including quiet periods. A multiplicative,
     piecewise-constant rate per 24 h, including near-zero days.
  3. **Spatial heterogeneity:** unburnable patches or barriers.
  4. **Detached ignitions:** rare detached ignitions, tuned so that about 15% of intervals contain a detached
     new-burn component, as measured on part a.
- Baseline arm: no feature, i.e. the verified run.

**Pass rule (Iris), stated before any result.**
- A feature is **"the cause"** if both of these hold:
  - it moves mean-field NLL's mean recovered far_share **above 0.40** from the 0.072 truth;
  - **MCEM stays within the committed tolerance**: |mean − true| ≤ 0.05 and SD ≤ 0.05
    (TOLERANCE_shape_recovery.md).
- A feature that moves NLL above 0.40 but also takes MCEM out of tolerance is reported as **"both affected"**. It is
  not "the cause".
- If no feature qualifies, that is reported as the result. If more than one does, each is reported.
- The parameter of each feature is set from part-a measurements, or stated a priori, before the first run. It is
  **not tuned** after seeing estimator outputs. Any later change of feature scale is reported as a new arm, with the
  first arm kept.

**Scope.** Synthetic only. MCEM at a 0.1 h step (the 0.25 h step is bounded by 8b0fde65). This explains the gap
between the NLL and bracket part-c arms; by itself it does not change any accuracy number.

## Addendum (about 13:26 UTC, 2026-11-12, before any estimator run): contiguous baseline (Iris)

The synthetic baseline's detached flag is 0.7–0.8 per interval, against about 0.15 on real part a, mainly because
of background ignitions. Every feature arm is therefore also run on a **contiguous baseline**:
- the same truth kernel and seeds;
- the background rate k0 calibrated generator-only on seeds 100–109, so that the mean detached flag is closest to
  0.15. The grid is 2e-5, 5e-6, 1e-6, 2e-7 and 1e-12. The generator-only table gives 0.82, 0.55, 0.28, 0.19 and
  0.15, so k0 = 1e-12 is chosen.

That makes 10 arms in total: 5 on the original baseline and 5 with the `_contig` suffix. The same pass rule applies
to each arm.

**Additional reading, declared now.** If NLL's far share on `baseline_contig` alone is above 0.40 while MCEM is within
tolerance, then **contiguity itself** is reported as "the cause". In that case the four feature arms are read relative
to the contiguous baseline.
