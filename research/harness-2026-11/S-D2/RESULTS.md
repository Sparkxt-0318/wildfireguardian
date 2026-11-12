# S-D2: a likelihood on what the sensors observed — first results

Stream S-D2 of the November 2026 harness. Scope: labels and likelihood for the SMOKE fire-arrival forecast
(`forecast/`). Status: **research checkpoint**. Nothing here changes the frozen forecast, its checkpoints or any
published result. Every number below was measured by the command next to it. Statements labelled
*hypothesis* were not tested.

## 0. What already exists (correction to the direction document)

* The default model's (c651 / M548 line) hourly labels are hard: `newly = 1{t-1 < arrival <= t}` from the kriged
  arrival mean (`forecast/wildfire/data.py:483-487`). Rows come from `prepare_event`
  (`forecast/wildfire/prepare.py:851`), which uses stratified negatives and inverse-inclusion weights. The kriging SD is
  loaded (`arrival_std_hours`) but unused.
* forecast-v2 **already** trains with interval-censored survival endpoints on NIROPS perimeter pairs
  (`forecast/wildfire/survival.py`). Its loss is the mean-field endpoint Brier score. Its "mixed" variant adds kriged windows
  weighted by `w = 1/(1+(sd/L)^2)` (`research/forecast-v2/scripts/pipeline.py:252`). That family failed its superiority
  rule against persistence (`research/forecast-v2/README.md`).
* How D2 differs: the likelihood is the probability of the observation itself (a bracket, or an error model around a
  recalibrated kriged mean). It is marginalised over latent arrival fields, including the input state at the start of
  a window. The SD changes *which arrival times are plausible*, not only how much a cell counts.

## 1. The kriging SD is miscalibrated and large (real data)

`python calibrate_kriging_sd.py --rasters <zenodo>/rasters_us --out results/kriging_sd_calibration.json` (≈3 s)

Independent reference: forecast-v2 held-out NIROPS survey rows for the six US 2024 fires. Their row/col index the
Zenodo grid. The kriging inputs are VIIRS/GOES detections, not NIROPS. For each cell, the tightest bracket
`(L, U]` gives an interval-censored likelihood for a scale `c` (and shift `b`) on `N(mu + b, (c·sd)^2)`.

| Fire | Cells (mapped) | Median SD (h) | Median bracket (h) | c (scale only) | c, b (h) with shift |
|---|---:|---:|---:|---:|---:|
| Wapiti | 3,781 (3,744) | 46.2 | 23.6 | 1.86 | 1.85, −11.4 |
| Goat | 1,051 (438) | 96.3 | 26.7 | 1.36 | 1.44, +53.5 |
| Lava | 2,807 (662) | 27.1 | 23.0 | 2.18 | 2.53, +53.3 |
| RedRock | 2,222 (962) | 58.4 | 24.0 | 2.21 | 2.32, +56.7 |
| Pioneer | 1,048 (956) | 74.5 | 24.5 | 1.07 | 1.07, −2.2 |
| FishCreek | 2,415 (1,758) | 87.2 | 24.8 | 1.22 | 1.22, +13.5 |
| **Pooled** | 13,324 (8,520) | | | **1.75** | 1.78, +15.1 |

The pooled NLL is 26,763 at c = 1.75, against 31,143 at c = 1. The 8,520 mapped cells equal forecast-v2's count of
newly mapped held-out cells.

Consequences:

* **Verified (Hannah, PASS WITH NOTES, 6d125bd):** the kriging SD understates uncertainty *relative to the NIROPS
  bracket reference*. c > 1 also absorbs NIROPS survey-time and mapping error. The pooled factor is 1.75; per fire it
  runs from 1.07 (Pioneer) to 2.21 (RedRock). The per-fire 95% profile-likelihood intervals are narrow (for example
  Wapiti [1.83, 1.90], Pioneer [1.03, 1.11]) and do not overlap, so the fires differ. These intervals treat cells as
  independent, so the range across fires (geometric mean 1.59) is the honest uncertainty. Brackets are 0.27–0.82 SD
  wide, so the scale is identifiable.
* **Declared use (ledger):** the US2024 held-out NIROPS brackets were used for this calibration only (no training, no
  model choice). Per Victor (S-D9), US2024 is a descriptive reference for D2, not a test set, and D2 is scored on
  part c. Recorded in S-D9 ledger/ACCESS_CONTROL.md.
* On three fires the mean is also shifted by about two days (+53 to +57 h). Soft labels built on the raw SD inherit this.
* The SD is **large relative to an hour**. The US medians are 27–96 h. The Korean training rasters have medians of
  5–21 h (KFS_01, the largest training event: 17 h). Hourly hard labels therefore claim timing precision the
  reconstruction does not have. A calibrated soft hourly label is nearly flat, with a peak of about `1/(2.5·c·sd)`, so
  it carries little hourly timing information.
* **Block-CV standardized residuals (detections):**
  `python blockcv_kriging_sd.py --choi <zenodo> --firms firms_us2024_heldout6.csv.gz` (about 150 s).
  * Method: VIIRS cells are held out by spatial block, following Choi et al.'s U.S. design, and
    `z = (obs − pred)/kriging SD` is computed for each held-out cell. Kriging uses `choi_kriging.py`, my port of the
    published algorithm; the downloaded code is not executed. This is P-OK without GOES points, with detections
    selected by the raster mask.
  * **Verified: Owen, PASS WITH NOTES (b8aeafb).** All z values use the **block-CV kriging SD of the port** (median
    116–326 h), **not** the product SD raster (27–96 h) on which c = 1.75 was measured.
  * Result, all 6 fires, 12,905 cells: z SD 1.08; |z| > 1.645 in 10.2% (nominal 10%); |z| > 1.96 in 7.8% (nominal 5%);
    robust SD (MAD) 0.36.
  * Result, only the 3 fires that replicate Choi's CV (Wapiti, Goat, Lava; 6,951 cells; Owen's pooling): |z| > 1.96
    in 5.4%, |z| > 1.645 in 6.8%.
  * So **the core is too narrow** on every fire except Pioneer (robust SD 0.10–0.46; Pioneer 1.05), which is robust.
    **"Heavy tails" holds only when the poorly replicated fires are included** (Pioneer alone has 25% of |z| above
    1.96), so it is not established.
  * Per-fire z SD runs from 0.74 to 1.44.
  * Replication of Choi's published P-OK CV is close for Goat (r 0.857 vs 0.853, MAE 108 vs 108 h) and rough for
    Wapiti and Lava. It is poor for Pioneer, FishCreek and RedRock, probably because the mask selection admits
    outliers that the polygon selection excludes. Per-fire values there are not reliable.
  * Reading (*hypothesis*): the two checks measure different things. Block CV tests the kriging variance against
    detection times at extrapolated locations, where the SD is about 200 h. The NIROPS check tests the product SD
    (27–96 h) against mapped-extent timing, where c = 1.75. Together they say a Gaussian error law with the product
    SD is the wrong shape and scale for training. A heavy-tailed law, or the raw brackets, is better founded.
* Not done: block-CV residuals for PSwt-OK itself, which needs GOES points. Korean calibration is also not done; it
  needs independent Korean brackets (the 2025 FIRMS detections now exist, which allows a first detection-bracket
  check). Mapped extent is not flame arrival.

## 2. Soft labels (step 2)

`soft_labels.py` computes `P(a < tau <= b)` under `N(mu, sd)`, optionally truncated to a support window and optionally
conditional on `tau > a`. It uses the loader's `(t-1, t]` convention and reproduces the hard label exactly at `sd = 0`.
Tests: `tests/test_soft_labels.py` (11). They check that windows sum to the probability of their union, that the
truncated version sums to one, that sd = 0 matches the loader rule exactly, the limit as sd → 0, that the conditional
hazard telescopes to survival, agreement with Monte Carlo, upper-tail precision, and invalid inputs.

## 3. Synthetic known-kernel study (step 3)

`python run_synthetic.py --replicates 16 --workers 4 --out results/synthetic.json` (596 s on 4 CPUs)

* **Truth:** continuous-time lattice spread with `lambda_i(t) = k0 + sum_d k_d 1{tau_(i-d) <= t}`. The kernel is 5×5
  (24 offsets), anisotropic and decaying with distance. Arrival times are simulated exactly on a 56×56 grid over 48 h,
  with 8 seeds per replicate.
* **Score:** held-out excess negative log-likelihood per arrival, using the *true* arrival times of three fresh fields
  per replicate and measured relative to the true kernel. Also reported: kernel relative L2 error (near 8 and far 16
  offsets) and total-rate ratio Σk̂/Σk.
* **Observation models:**
  * kriged: `tau_hat = tau + N(0, sd)` with sd drawn from {0.5, 2, 6} h, known and *calibrated*;
  * perimeter: brackets between surveys every 12 h.

**Perimeter brackets (16 replicates):**

| Estimator | Held-out excess NLL | Kernel rel. L2 | Σk̂/Σk |
|---|---:|---:|---:|
| complete-data MLE on true tau ("oracle"; not a floor) | 0.0445 ± 0.0269 | 0.325 ± 0.074 | 0.999 ± 0.024 |
| plug-in at first observation time (Ganguly-style) | 0.2752 ± 0.0574 | 0.773 ± 0.066 | 0.882 ± 0.035 |
| **MCEM interval-censored** | **0.0909 ± 0.0444** | **0.602 ± 0.131** | **1.012 ± 0.023** |

On held-out NLL, MCEM beats the plug-in in **16/16** replicates (paired Δ −0.184 ± 0.073); on kernel L2 it wins 15/16.

**Kriged observations with calibrated Gaussian error (16 replicates):**

| Estimator | Held-out excess NLL | Kernel rel. L2 | Σk̂/Σk |
|---|---:|---:|---:|
| complete-data MLE on true tau ("oracle") | 0.0445 ± 0.0269 | 0.325 ± 0.074 | 0.999 ± 0.024 |
| plug-in (kriged mean as exact) | 0.0578 ± 0.0137 | 0.451 ± 0.077 | 0.861 ± 0.028 |
| hard hourly (current pipeline) | 0.0502 ± 0.0112 | 0.432 ± 0.068 | 0.911 ± 0.031 |
| sd-weighted hard hourly (forecast-v2 rule, L = 1 h) | 0.1238 ± 0.0261 | 0.499 ± 0.056 | 0.673 ± 0.050 |
| **soft hourly, as specified (hard risk set)** | 0.1953 ± 0.0207 | 0.623 ± 0.025 | **0.530 ± 0.022** |
| soft risk set (weight P(tau>t), conditional hazard) | 0.0536 ± 0.0100 | 0.402 ± 0.053 | 0.886 ± 0.026 |
| soft risk set + soft source features | **0.0333 ± 0.0094** | 0.392 ± 0.069 | 0.879 ± 0.024 |
| MCEM (Gaussian error model) | 0.0777 ± 0.0400 | 0.507 ± 0.143 | **0.998 ± 0.030** |

**Verification (Hannah, PASS WITH NOTES, c7f7df3).** She re-ran replicates 0–3 on py3.12 / numpy 2.5.4:
* the simulation is identical;
* the deterministic estimators agree within 3.2e-4 relative;
* MCEM rows differ by up to 34% per replicate across builds, because the chain amplifies last-digit differences.

All paired directions held (perimeter MCEM beat the plug-in 4/4; kriged MCEM beat hard hourly 0/4). MCEM rows are Monte
Carlo estimates whose variability is comparable to the between-replicate sd, so close counts such as 3/16 are not
decision inputs. "Oracle" is the complete-data MLE on one training field, not the true θ, so it is not a floor:
soft_risk_softfeat beats it on held-out NLL.

Findings (synthetic, conditional on this generator):

1. **The low-cost step as specified is harmful.** It replaces the hard label by `P(t<tau<=t+1)` but keeps the hard risk
   set, so all probability mass after the kriged mean falls on rows that do not exist. The total rate is halved
   (0.53), and the held-out NLL is the worst of all estimators. MCEM beats it in 16/16 replicates. The corrected version
   is a soft risk set with soft source features, i.e. a fixed-q expected complete-data likelihood. It has the best
   held-out NLL here, but it still underestimates the total rate (0.88).
2. **MCEM is the only estimator without rate bias in both observation models** (Σk̂/Σk ≈ 1.00). With 12 h brackets it
   is clearly best. With a calibrated Gaussian error of at most 6 h, its higher variance outweighs the bias removal: it
   beats hard hourly on held-out NLL in only 3/16 replicates. Most of that variance is in the far (distance-2) offsets
   (rel. L2 0.79), where short-range competition makes long-range coefficients weakly identified. The direction
   document anticipated this.
3. The forecast-v2 SD weight biases the rate down (0.67) when applied to hourly windows. In v2 it was applied to
   multi-hour windows (L = window length), which this study does not reproduce.

Not verified: real-data refit. Also not verified: correlated (kriging-smoothed) errors, miscalibrated SD in the
synthetic generator, VIIRS-style one-sided brackets, environmental covariates, and more MCEM Monte Carlo samples (which
should cut the variance in finding 2; *hypothesis*).

## 3b. Robustness study (round 2; synthetic)

`python run_robust.py --replicates 8 --workers 4` (1,916 s); memory: `--replicates 1 --memory`
(`results/robust_memory.json`). Tables are in `results/robust.md`. **Verified: Owen, PASS WITH NOTES (4bb7933)**, on
replicates 0–3 for 3/12/24 h brackets.

**Bracket width against cell-crossing time** (Markov truth, median crossing time 6.6 h; mean of 8 replicates):

| Bracket | Plug-in Σk̂/Σk | Composite | Mean-field NLL | MCEM | MCEM beats plug-in on held-out NLL |
|---|---:|---:|---:|---:|---:|
| 3 h | 1.014 | 0.861 | 1.094 | 1.025 | 3/8 |
| 6 h | 0.989 | 1.000 | 1.081 | 1.028 | 5/8 |
| 12 h | 0.905 | 0.894 | 1.039 | 1.039 | 8/8 |
| 24 h | 0.665 | 0.647 | 0.982 | 1.040 | 8/8 |

* **What MCEM recovers.** It recovers the total rate *nearly* unbiasedly. Its ratios run 1.025–1.040, a small,
  consistent **upward** bias of 2–3 SE (Owen), which errs toward a fast model. It wins on held-out NLL. It does
  **not** win on kernel shape: at 12 h and 24 h the composite has lower rel-L2 (0.546 vs 0.625, 0.620 vs 0.670). Wide
  brackets identify the rate, not the shape.
* **Mean-field fits.** They get the rate roughly right but the shape badly wrong (rel-L2 0.88–1.28 at 12–24 h), so
  their held-out NLL is poor. `meanfield_brier` at 3 h converged to the floor (rate 0, NLL 15.0), an optimizer failure
  that is reported, not hidden.
* **Kriged inputs** (calibrated, correlated, or with the SD understated 1.75×): MCEM is *worse* than the simple arms
  on held-out NLL (calibrated: 0.0756 vs soft risk set 0.0286; 0/8). With the SD understated, every arm is biased low;
  only MCEM given the corrected SD is not (1.03). **The perimeter result does not carry over to kriged inputs**, which
  confirms dropping the kriged arms.
* **Longer MCEM** (60×6 sweeps): held-out NLL 0.060 ± 0.021 vs 0.076 ± 0.037. Variance falls, but it still does not
  beat hard labels at small calibrated error.
* **Spotting outside the fitted kernel:** MCEM is best (NLL 0.039, rate 1.10, absorbing the spotting).
  **Non-exponential delays:** every estimator gives about 0.3; the Markov kernel is misspecified, so this is not a
  bias measure.
* **Cost:**
  * Wall time per fit (8 replicates, 4 workers): plug-in < 0.1 s, composite 1–5 s, mean field 4–57 s, MCEM about
    30–55 s, long MCEM about 170 s.
  * Peak Python heap (`tracemalloc`): plug-in 1.8 MiB, mean field ≤ 1.6, hard hourly 6.4, composite ≤ 9.7, MCEM 12,
    soft risk set 61.
* "Deterministic" estimators are deterministic **up to optimizer tolerance** (plug-in ≤ 2e-5; composite held-out NLL up
  to 0.018 across builds).

## 3c. Real raw brackets, covariate-free (NIROPS part a)

`python nirops_brackets.py --shp <NIROPS> --allowlist PART_A_ALLOWLIST_FINAL.csv --source-ref <commit> --out B` (93 s),
then `python real_bracket_fit.py --brackets B --hours 240 --workers 4` (2,071 s).

* **Data and access.**
  * S-D9 part a only: allowlist sha256 7db3cc0e at 2d40d170, rule surveys ≥ 20, giving 42 incidents. Each incident is
    read through an `Incident_C` attribute filter; the use is logged.
  * Perimeters are rasterized on a 375 m EPSG:5070 grid with the cell-centre rule and a cumulative union.
  * **No arrival raster is read**, which is A1 §4.1 rule 3. Every cell of the full grid is at risk, and never-mapped
    cells are censored negatives.
* **Fit.** The homogeneous spatial hazard (5×5 kernel plus background) is fit over the first 240 h after the first
  survey. Twenty-five fires qualify (≥ 100 arrivals, grid ≤ 140, initial burned cells present); the 17 exclusions are
  listed with reasons in the JSON. Survey gaps are about 24 h.

**Verified: Owen, PASS WITH NOTES (8667f5a).** His independent rerun gives plug-in 0.455, composite 0.967 and
mean-field 0.588, with an identical access log and a 0-cell bracket difference on 2 fires.
* The reference is MCEM, not truth, so the safe wording is **"plug-in is about 0.45 of the bracket-likelihood
  rate"**.
* The strong statement: the two bracket-likelihood estimators agree within about 3%, while plug-in and mean-field fall
  far below on 25/25 fires.

**Total spread rate relative to MCEM:**

| Estimator | Geometric mean | Range | Fires below MCEM |
|---|---:|---:|---:|
| Plug-in (first observation time; Ganguly-style) | **0.454** | 0.08–0.85 | 25/25 |
| Mean-field endpoint NLL (forecast-v2 regime, NLL loss) | **0.587** | 0.26–0.88 | 25/25 |
| Independent-bracket composite | 0.967 | 0.84–1.07 | 18/25 |

* The median MCEM total rate is 0.055/h, a crossing time of about 18 h, against about 24 h brackets. That is the
  synthetic regime (brackets 1–2× the crossing time) where composite and MCEM agree on the rate, and they do here.
* **Reading (hypothesis, not a forecast result):**
  * Treating survey brackets as exact times cuts the fitted spread rate about 2.2× on real NIROPS fires (up to 12×).
  * The mean-field endpoint fit, the existing perimeter regime, is also low on every fire. This fits the registered
    P-D2 ordering, under which `d2_bracket_rebuilt`, not `d2_nll_rebuilt`, should move the near-zero tail.
* **GOFER overlap (ledger):** Bobcat, CZU, KNP, LNU-Meyers and Slater are GOFER fires. **Per A1 item 25** (Victor's
  ruling) they are H-dev, not H-test, and may be used in all part-a development and the refit pool. Sensitivity
  without the four that entered the fit (21 fires): plug-in 0.450 (21/21 below), composite 0.973, mean-field NLL 0.566
  (21/21 below).
* **Not shown:**
  * The model has no covariates and a constant rate, so day-to-day variability (Sofia: run days vs slow days) is
    folded into one rate.
  * MCEM carries about 3% synthetic upward bias.
  * Nothing here is scored against held-out perimeters.

## 3d. rate_composite (A1 §3.2 item 23, step 1; unverified)

`python run_rate_composite.py --workers 4 --out results/rate_composite.json` (1,077 s).

* **Estimator.** Composite kernel shape, then one scalar fit by the bracket likelihood: a one-parameter latent-time
  EM with a closed-form M-step. It is compared with full MCEM on seeds 0–4.
* **Regimes, fixed in A1 before the run:**
  * slow: verified Markov setting, crossing time about 6.6 h;
  * fast: kernel ×4, crossing time about 2 h, and the 56×56 grid burns out within 48 h.
* **Matching rule, agreed before the run.**

| Regime, bracket | Rate: full advantage (≤ 0.05 holds) | Log-lik: full − rc (tolerance) | Shape: rc − full (tolerance) | Σk̂/Σk MCEM / rc | Holds |
|---|---:|---:|---:|---:|---|
| slow 12 h | 0.078 ✗ | 0.155 (0.117) ✗ | 0.116 (0.059) ✗ | 1.051 / 1.136 | no |
| slow 24 h | 0.117 ✗ | 0.395 (0.180) ✗ | 0.292 (0.180) ✗ | 1.059 / 1.192 | no |
| fast 12 h | 0.033 ✓ | 0.383 (0.117) ✗ | 0.652 (0.056) ✗ | 0.921 / 1.123 | no |
| fast 24 h | −0.191 ✓ | 0.574 (0.216) ✗ | 0.200 (0.066) ✗ | 0.582 / 0.705 | no |

* **Verdict by the agreed rule:** `rate_composite` is **not** the refit candidate, and the full method stays. Full
  MCEM wins on held-out likelihood and shape in every cell. Cost is the same (about 31–158 s each), since both share
  the E-step.
* **New limit on the full method:** in the fast regime with 24 h brackets (about 12× the crossing time), **MCEM is
  itself biased low (0.58)**, and `rate_composite` is less wrong on rate there (0.71). With 12 h brackets MCEM gives
  0.92.
* Reading (*hypothesis*): when brackets span many crossing times and the grid saturates, the brackets carry little
  timing information and the latent-time posterior is weakly identified. The +2.5–4% bias seen at slow spread does
  not hold at fast spread.
* Real NIROPS fires sit at about 1.3× the crossing time (§3c), well inside the regime where MCEM is near unbiased.
  Fast runs in real data, however, are exactly the high-ratio case.

## 3e. Displacement diagnostic on part a (Iris; unverified)

`python displacement_diag.py --brackets B --sims 64` (411 s).

* **Method.** For each survey interval, the farthest new-burn distance from the cutoff mapped extent (D_obs) is a
  lower bound on displacement that does not depend on latent times. It is compared with the 95th percentile of the
  same quantity (D_95) in 64 exact simulations of that fire's fitted MCEM kernel, started from the actual cutoff
  state.
* **Result** (206 intervals, 25 fires, first 240 h):
  * **12.1% of intervals** (25, in 12 fires) have D_obs > D_95, against 5% if model reach were calibrated. They carry
    **8.2% of new burn**.
  * Their median ratio D_obs/D_95 is 1.63, and the largest are 2.4–3.2: KNP 5.3 km in 27 h; Line 5.0 km in 28 h;
    Limepoint, Shoe, MudLick, SouthYaak.
  * **The median ratio over all intervals is 0.33**: in a typical interval the fire got only a third as far as the
    model's 95th percentile.
  * No interval touched the grid edge (saturation flag 0).
* **Reading (*hypothesis*):** one constant rate is **overdispersed in the wrong way**. It over-reaches on most
  intervals and under-reaches on about 12%, which is the slow-day / run-day mixture (Sofia, Iris). It argues for a
  run-state or frailty term on top of the corrected average rate, and for checking whether wind predicts the run
  intervals (Victor).
* **Caveats:**
  * D_obs can include spot fires, new ignitions or mapping changes far from the front, not only frontal runs.
  * No covariates; mapped extent, not flame arrival.
  * 64 simulations give a coarse 95th percentile.

## 4. Ideas and gaps

* *Hypothesis:* given §1, the raw-bracket arm (NIROPS survey pairs, VIIRS overpasses) is better founded than any
  kriged-label arm. The kriged SD is both large and miscalibrated, and the synthetic study shows the bracket
  likelihood's gain is largest exactly when the observation is coarse.
* **Negative result: composite shape + simulated scalar rate** (Iris's cheaper candidate).
  * Run: `python run_composite_scale.py --replicates 8` (96 s; `results/composite_scale.md`). It uses the same
    truths and brackets as the stored robustness rows.
  * Method: the composite kernel shape is rescaled by one multiplier, chosen by exact forward simulation from the
    known survey states so the simulated new-burn count matches the observed count.
  * **Verified: Owen, PASS WITH NOTES (d68d790).** It **overshoots** the total rate: about 1.08 (6 h), 1.18 (12 h),
    1.37 (24 h), 1.30 (spotting), against MCEM's 1.03–1.10. Means vary by about ±0.01 on rerun: the estimator is not
    bit-reproducible (per replicate up to ±0.06 in rate, probably composite-fit drift amplified by the bisection).
    The win counts are reproduced exactly.
  * The recovery test band (true 3 → m in 2.4–3.7) is loose. It would not catch a 15% bias, which is adequate only
    for a negative result.
  * Its held-out NLL is no better than plain composite and beats MCEM in 0–1/8 per scenario. Its cost is 5–15 s
    versus MCEM's 30–55 s.
  * Reading (*hypothesis*): front speed depends on how rate is distributed across offsets, so matching burned-area
    counts with a misallocated shape over-corrects the total. Rate and shape are not separable this way.
  * MCEM stays the `d2_bracket` reference. A cheaper exact alternative would need a joint (shape + scale) fit.
* **Missed detections** (Iris's arm).
  * Run: `python run_missed.py --replicates 4` (`results/missed.md`). Overpasses come every 12 h, and each overpass
    after arrival misses with probability q. A cell never detected by T looks unburned. Fits are MCEM.
  * Total rate ratio, hard lower bound vs left-open `(0, t_detect]`:

    | q | Hard | Left-open | Never-detected cells |
    |---:|---:|---:|---:|
    | 0 | 1.046 | 0.900 | 0 |
    | 0.2 | 0.839 | 0.668 | 76 |
    | 0.4 | 0.622 | 0.460 | 189 |

  * Held-out NLL is worse for left-open at every q.
  * Reading (*hypothesis*): missed detections bias the rate **down**, as Iris expected. But the bias comes mainly from
    the late upper bound (detection after arrival) and from never-detected cells counted as unburned, not from the
    lower bound. Opening the lower bound discards information and makes things worse.
  * Active-fire brackets therefore need an explicit detection-probability model: P(detect | burning at overpass) < 1
    for both the first-detection time and the never-detected cells. Left-opening alone is not enough. NIROPS mapped
    extents are less affected, but a lagging perimeter acts the same way.
* **Shared fire-day frailty** (Sofia): a random rate multiplier per fire-day, possibly a gamma with closed-form
  integration, to absorb run days. It is not yet tested.
* **Refit arms:** a full-rectangle label-validity arm (same loss as today) runs separately from the likelihood change
  (Iris), so the two effects are not mixed.
* A cheap middle ground is the fixed-q soft risk set. It is one pass with no sampling, and its q should be recalibrated
  (c ≈ 1.75) or built from brackets.
* Persistence wins Brier at a 0.5% base rate, so no change in training likelihood alone is expected to pass the
  forecast-v2 superiority rule. Acceptance should follow Iris's per-fire perimeter metrics: calibration gap and
  zero-probability positives.

## Files

| File | Purpose |
|---|---|
| `soft_labels.py` | soft and hard window labels, row targets |
| `synthetic.py` | generator, complete-data likelihood, hourly Bernoulli fits, soft risk set, Gibbs sampler, MCEM |
| `run_synthetic.py` | replicate runner → `results/synthetic.{json,md}` |
| `calibrate_kriging_sd.py` | kriging-SD calibration against NIROPS brackets → `results/kriging_sd_calibration.json` |
| `tests/` | 18 tests: `python -m pytest -q tests` (about 1 s) |

Environment for these runs: Python 3.13, NumPy 2.1.3, SciPy 1.14.1, pandas 2.2.3, rasterio 1.4.3, 4 CPUs (Linux).
Inputs: Zenodo 10.5281/zenodo.21788344 (sha256 612edf5f…), fetched with `research/harness-2026-11/data-fetch/fetch.py`
from branch `daniel/data-fetch`.
