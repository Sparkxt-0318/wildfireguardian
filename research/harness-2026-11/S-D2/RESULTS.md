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
* On three fires the mean is also shifted by about two days (+53 to +57 h). Any soft target built on the raw SD inherits this.
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

## 2. Soft window labels (step 2: the label utility, not a candidate)

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

1. **The soft-hourly variant (the low-cost step as specified) is harmful, and it is not a candidate.** This is the
   kriged soft-hourly arm with a hard risk set (total_rate_ratio 0.530, held-out excess NLL 0.195; the worst kriged
   arm in results/synthetic.json). The finding concerns that variant only, not "soft labels" in general: the soft
   risk set with soft source features (soft_risk_softfeat, 0.033) has the best NLL after the oracle. The supported
   path is the bracket likelihood on survey perimeters. The variant replaces the hard label by `P(t<tau<=t+1)` but keeps
   the hard risk
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

## 3d. rate_composite (A1 §3.2 item 23, step 1; verified: Owen, PASS WITH NOTES, 7a160ee)

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
* **Owen's notes.**
  * Every condition reproduces.
  * The conclusion rests on the **slow regime alone**, where all three conditions fail by wide margins.
  * The fast regime is nearly uninformative as designed, because the grid burns out within 48 h. Its cells,
    including MCEM's 0.58, are **not evidence about either estimator's tail behaviour**: the rate is unidentified on a
    saturated grid. A non-saturating test is pending (Iris).
  * The fast/12 h rate margin is thin and MC-sensitive (0.033 vs 0.042 on rerun; limit 0.05).
* **Observed, but see Owen's note (2):** in the fast regime with 24 h brackets (about 12× the crossing time), **MCEM is
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
* **Rank of the observed reach among the 64 simulated reaches** (Iris's calibration check, 206 intervals):
  * Decile histogram: **67** / 21 / 22 / 3 / 8 / 12 / 16 / 12 / 16 / **29**. It is U-shaped and heavier at the low
    end.
  * Rank < 0.05 in 27.2% of intervals; rank ≥ 0.95 in 11.7%, fire-clustered bootstrap 95% CI [5.8%, 18.5%], against
    5% nominal.
  * So the model is **too fast on many intervals and too slow on some**, with the low end, slow days, the larger
    misfit. The top excess only just clears nominal once clustering by fire is respected.
* **Iris's checks** (`python displacement_checks.py`; `results/displacement_{mcem,plugin}.json`, which supersede
  `displacement.json`):
  * **Ties broken at random:** deciles 63 / 25 / 13 / 8 / 10 / 13 / 17 / 15 / 14 / 28.
  * **Low tail (rank < 0.05):** 24.8%, fire-clustered 95% CI [16.4%, 34.3%], so robust. The low-rank intervals have
    a median observed reach of 2 cells, and 22% reach ≤ 1 cell.
  * **Top tail (rank ≥ 0.95):** 10.7% [5.2%, 17.0%]. **With detached intervals removed: 10.3% [4.7%, 16.5%], which
    includes 5%.** The run excess is not established once spotting or mapping candidates are excluded.
  * **Covariates:** the night-time fraction (local mean solar time) does not separate low-rank intervals (mean 0.50
    vs 0.50). **Interval length does:** intervals > 26 h are low-rank 42% of the time, against 19% for ≤ 26 h. Some
    of the "too fast" end is a constant rate integrated over longer gaps, and that is observable at forecast time.
  * **Kernel used:** the main run uses each fire's MCEM kernel, the corrected and higher rate. With the **plug-in
    kernel** (`--estimator plugin`), 93% of intervals fall below rank 0.05 and none above 0.95: the plug-in
    over-reaches almost everywhere despite its 0.45× total rate.
* **Kernel shape on real fires:** the share of the fitted rate on distance-2 offsets (median over 25 fires) is
  plug-in 0.635 and mean-field NLL 0.679, against MCEM 0.066 and composite 0.006. The estimators that treat
  survey-time states as exact assign most of the rate to **long-range** offsets, because cells mapped together in one
  survey look like simultaneous arrivals from distant sources. Their error is **misallocation toward reach**, not
  just a low total rate.
* **Stalled intervals** (no new burn): 7 of 213 (3.3%), small.
* **Detached far burn:** 5 of the 25 run intervals have their farthest new cell in an 8-connected component that
  contains no cutoff-burned cell. Over all intervals the share is 15%. Spot fires or mapping changes may account for
  part of the runs.
* **Reading (*hypothesis*):** one constant rate is **overdispersed in the wrong way**. It over-reaches on most
  intervals and under-reaches on about 12%, which is the slow-day / run-day mixture (Sofia, Iris). It argues for a
  run-state or frailty term on top of the corrected average rate, and for checking whether wind predicts the run
  intervals (Victor).
* **Caveats:**
  * D_obs can include spot fires, new ignitions or mapping changes far from the front, not only frontal runs.
  * No covariates; mapped extent, not flame arrival.
  * 64 simulations give a coarse 95th percentile.

## 3f. Part-a fire-level CV in the pinned environment E3 (unverified; sent to Owen)

Caveats: covariate-free, homogeneous, 25 part-a fires incl. 4 H-dev, not the neural refit.
Pinned E3 (Python 3.12.3, numpy 1.26.4, scipy 1.13.1, pandas 2.2.3, scikit-learn 1.5.2); same seeds and folds as E1.
Every pooled number, pinned vs unpinned: results/cv_pinned_vs_unpinned.md (172 rows; compare_pinned.py). Receipt: CV_RECEIPT.md.

| arm | Brier E1 | Brier E3 | E3 − E1 |
|---|---|---|---|
| logistic_cf (reference) | 0.0566464 | 0.0566464 | 0 |
| plugin | 0.0569083 | 0.0569278 | +2.0e-5 |
| meanfield_nll | 0.0579771 | 0.0579677 | −9.3e-6 |
| composite | ~~0.062702~~ INVALID | 0.0636893 | — |
| persistence (reference) | 0.0646172 | 0.0646172 | 0 |
| mcem | 0.0659775 | 0.0659965 | +1.9e-5 |
| dilation_8h = dilation_best (reference) | 0.341693 | 0.341693 | 0 |

- No E3 fit tripped the FitFailed guard. check_bounds: PASS for all 4 estimators in all 5 folds (composite share at floor 0.20–0.32).
- Every non-composite pooled Brier moved by < 3e-5. Paired MCEM − plug-in: 0.009069 [0.005665, 0.012423], 5/25 fires (E1 0.009069 [0.005676, 0.012400]).
- The composite is now valid. MCEM − composite: +0.002307 [0.001076, 0.003440], 5/25 fires better for MCEM. Composite − plug-in: +0.006762 [0.004395, 0.009063], 4/25 fires better for the composite.
  So the composite sits between plug-in/logistic_cf and persistence, and is worse than plug-in.
- Conclusions for plug-in, mean-field NLL and MCEM are unchanged. MCEM is still the worst and has no skill over persistence. Plug-in is still ≈ logistic_cf.

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

### Verifier notes on §3e and its follow-ups (Owen, 2026-11-12)

- **Displacement inputs** (652b58cb, 84e41e76): **PASS WITH NOTES.** Owen reran the full chain from his own part-a
  extraction. The per-interval rows, both summaries and displacement_checks.json are identical. This lifts the
  input caveat on lag-1 persistence (fba72fbf, PASS WITH NOTES) and on the cutoff covariates (c317bef6, PASS WITH
  NOTES).
- **Notes:**
  1. Kernels are in-sample and per fire. The histogram tests in-sample adequacy, not out-of-sample calibration.
  2. The rank resolution is 1/64. Low-rank intervals have a median observed reach of 2 cells, and 21.6% are at ≤ 1
     cell, so the low tail is partly quantisation and mapping resolution.
  3. Quote the tie rule used: the mid-rank gives a low share of 27.2%; the seeded random tie-break gives 24.8%.
  4. The composite far share on real data is a median of 0.006.
  5. The scope is 25 part-a fires, including 4 GOFER fires assigned to H-dev (A1 item 25). This is development
     evidence only.
- **Shape recovery** (780cbabe): PASS. **Step check** (8b0fde65): PASS WITH NOTES (synthetic only).
- **Covariates:** previous-interval growth shows no clear association. All covariate results are marginal
  associations.
- **Reach slope** (`reach_slope.py` at 560a64d6) and **real far share** (`real_far_share.py` at 28540968):
  **PASS WITH NOTES** (Owen, rerun on his independently regenerated inputs).
  - Only the overall slope (0.381), the non-length slope (0.38) and the between-fire slope (0.359) are well
    determined. The length-part and within-fire intervals are wide.
  - A slope below 1 is a **calibration slope, not a mechanism**. It may be partly attenuation: the simulated median
    comes from 64 simulations and is quantised to the cell size.
  - **No-GOFER subset** (b7cb892f): **PASS** (Owen). Dropping the 4 GOFER-matched (H-dev) fires, which use NIROPS brackets
    like all the others, leaves every main result in place.
- **Persistence, lags 1–3 and detrended** (6ae6dfea). Owen's verdict is **SPLIT**.
  - **Raw lags 1–3: PASS.** Rank excess: lag 1 +0.186 [0.023, 0.359], lag 2 +0.153 [0.014, 0.298], lag 3 +0.020
    [−0.117, 0.137].
  - **Detrended lag 1: FAIL (null bias).** The null detrended the values before permuting them. With about 8
    intervals per fire, that biases the detrended excess negative, by about −0.13 under iid data.
  - **Corrected rerun** (45d83d1b, null permutes first and then detrends): **PASS WITH NOTES** (Owen). Detrended lag-1
    excess (Pearson): rank +0.094 [−0.124, 0.293], p 0.115; log ratio +0.057 [−0.070, 0.198], p 0.206. Without
    detached intervals: rank +0.083 [−0.172, 0.324], log ratio +0.035 [−0.135, 0.206]. Neither is significant. This
    supersedes the FAIL on the detrended claim. Owen's independent corrected numbers agreed (+0.091/+0.060).
  - **The earlier "mostly trend" reading is WITHDRAWN.** The data cannot separate trend from state: undetermined.
  - The fix is in `lag_persistence_v2.py` (827c74d0, **PASS**), with an iid null-calibration test in
    `test_lag_persistence.py` that fails on the 6ae6dfea code.
  - Iris's restatement: within-fire persistence beyond each fire's average is present (the raw lags stand), and
    trend against state is undetermined. Fire age is not shown to suffice, though its marginal association stands as
    verified. The prequential test is unscheduled and undecided, and the fold-kernel sizing step decides it. The
    fire-age/shrinkage fit must report the lag-1 persistence of its residuals, with the corrected null and its
    pure-noise calibration.
  - **Pure-noise calibration on the real structure** (`lag_null_probe.py`, 300 iid datasets on the same 25 fires,
    intervals and runs): the mean excess is +0.004, +0.006, −0.005 and −0.002 for lags 1, 2, 3 and detrended lag 1,
    each with SE about 0.004. The corrected procedure is unbiased (1cee5ddc, **PASS**; Owen also checked the probe
    detects the old bias: −0.122).
- **Pre-weather new-burn cells outside the training crop** (`refit/preweather_unscored.py`, b7cdc48f): **PASS** (Owen,
  who reran the script and reimplemented it independently).
  - On the part-a pool, 12,384 of 122,640 new-burn cells (10.1%) lie outside `crop_box(initial)` with MARGIN 10.
  - They fall in 97 of 3,773 intervals, from 67 fires; the top 5 fires hold 62% of them.
  - pipeline.cropped drops these cells in both D2 arms. No new-burn cell inside the crop is unscored.
  - This is pre-weather: `available_at` and kernel finiteness are not applied. Development evidence only, for Victor's
    item-22 decision.
- **Leave-fire-out (fold-kernel) diagnostics** (c31aa70a and earlier; unverified).
  - Detrended lag-1 persistence: rank +0.172 [0.001, 0.340], p 0.012. Lags 2–3 are near zero.
  - Iris's wording: **"undetermined, leaning to state"**. This is weak, unadjusted evidence for a short-memory state.
  - **The displacement-tail measure is retired as a guide (Iris)** and kept as a descriptive row only. Plug-in
    over-reaches in every fold interval yet wins on Brier, and MCEM has better tails with no skill over persistence.
  - Reach slopes are unchanged from in-sample: 0.369 overall, 0.344 between fires.
  - Reporting rule for the rate arms: if both fail, the wording is "these two forms did not help", not "state does
    not matter". Neither arm has a one-interval memory. A lag-1 arm is to be proposed afterwards, with its own rule
    fixed first.

- **INVALID: every pooled-COMPOSITE number in the part-a CV** (results/cv_part_a.json 96f99bf6 and cv_baselines.json
  7cc21f47). Owen found that the pooled composite fit collapsed to the 1e-9 floor (all 25 parameters) in folds 0, 2, 3
  and 4.
  - Cause: under the run's numpy 2.1.3 / scipy 1.14.1, L-BFGS-B stopped with ABNORMAL_TERMINATION_IN_LNSRCH. The floor
    objective is about 10× worse than the optimum found in the pinned environment (numpy 1.26.4 / scipy 1.13.1).
  - Invalid numbers: pooled 0.0627, the reach profile 3,546 / 37 / 0.7, ~~the 19,264 burned cells below 1/1024~~ (WITHDRAWN),
    MCEM − composite and composite − plug-in, and the composite band Brier.
  - Fix: `_lbfgs` now raises FitFailed on an all-at-floor solution, a non-finite objective or gradient, or a result
    worse than the start. Composite is being rerun in the pinned environment (`cv_composite_rerun.py`, same seeds).
  - The in-sample per-fire fits (real_bracket_fit.json) are not affected.
  - Pending Owen: MCEM and NLL also differ slightly between environments.

## Run environments (2026-11-12): every run made today

The pinned refit environment is `requirements-refit.txt` (sha256 1972d6e7…, harness/s-d1-next): Python 3.12.3,
numpy 1.26.4, scipy 1.13.1, pandas 2.2.3, scikit-learn 1.5.2, torch 2.5.1. `check_refit_env.py` reports ok.
**Every table produced outside it is marked UNPINNED until Owen confirms which numbers survive.**

| Environment | Runs |
|---|---|
| **E1, UNPINNED:** `venv`, Python 3.13.18, numpy 2.1.3, scipy 1.14.1, pandas 2.2.3 | Synthetic studies (synthetic, robust, composite_scale, missed, rate_composite, shape_recovery, step_check); kriging-SD calibration and block CV; nirops_brackets; real_bracket_fit; displacement_diag (in-sample and fold); displacement_checks; lag1 / cutoff / reach_slope / lag_persistence_v2 / lag_null_probe (in-sample and fold); real_far_share; subset (no-GOFER); **cv_part_a (all folds and the aggregate)**; fold_kernel_fit; feature_ablation generator checks |
| **E2, PARTLY PINNED:** `venv312`, Python 3.12.3, numpy 1.26.4, scipy 1.13.1, sklearn 1.5.2, torch 2.5.1, but pandas 3.0.6, pyproj 3.8.0, rasterio 1.4.4, no pyshp or shapely | refit tests and time_estep; preweather_unscored; **cv_baselines** (kernel p read from the E1 CV); **cv_rate_arm** (kernels from the E1 CV); state family (stopped at 21:13 UTC; 28 fire checkpoints set aside, NOT reused); composite rerun (stopped before any fold finished) |
| **E3, PINNED** (`venv312` after installing the exact pins; check_refit_env ok at 21:13 UTC) | everything from 21:13 on |

The verified results earlier today (Hannah and Owen) were run and rerun in E1 or in verifiers' own environments. Their
verdicts stand as recorded. Environment sensitivity is under review by Owen.

### Owen's verdicts, ledger rows 46–48 (verification/owen-smoke-2 at 6d06ca02)

- **Row 46, cv_part_a 96f99bf6: SPLIT.**
  - **Composite: FAIL** (optimizer collapse). Void until the pinned rerun.
  - **Plug-in, NLL and MCEM: PASS WITH NOTES.** Owen reran folds 0 and 2 from scratch in the pinned environment.
    - MCEM − plug-in: +0.01068 pinned vs +0.01072 E1, with per-fire sign agreement 10/10.
    - MCEM − NLL: +0.00967 vs +0.00968, 9/10.
    - The maximum per-fire relative Brier difference is 0.36%.
    - **The conclusions do not depend on the environment.** The numbers are not bit-reproducible across stacks.
  - The percentile fire bootstrap is mildly anti-conservative (6.3–6.8% under a sign-flip null). The exact sign-flip
    test gives p ≈ 0.0001 for MCEM − plug-in and MCEM − NLL.
- **Row 47, cv_baselines 7cc21f47: SPLIT.**
  - Baselines and non-composite pairs: **PASS WITH NOTES**. Composite rows: **FAIL**.
  - Correction: the 0–1 km share of the MCEM − plug-in gap is **92.5%**, not ~91%.
- **Row 48, fold-kernel diagnostics c31aa70a: PASS WITH NOTES.**
  - The chain reproduces in the pinned environment, using the E1 fold kernels (none at a bound).
  - "Weak evidence" is the right strength for the detrended persistence: the interval only just clears 0, and the p
    values are unadjusted across ~32 configurations.
- The full pinned CV (E3, results/cv_part_a_pinned.json) is still the version of record. It includes the composite
  with the guard.
- **Rate and state arms** (3ec5a8bc): **code-level check by Owen**; the numerical verdict waits for the pinned rerun.
  - Causality is confirmed: each interval uses only that fire's earlier intervals, and mcem_state's EM uses other
    folds only.
  - The time-change shortcut is exact in law for this model.
  - Internal check: m = 1 gives 0.066026 against the CV's 0.065977, consistent with Monte Carlo error.
  - The rule timing was confirmed.
  - Design note, which the rule declares: the online update treats an interval's cells as independent Bernoulli
    observations, so the posterior over m concentrates faster than the evidence warrants. This does not change the
    verdict that neither arm qualifies.
