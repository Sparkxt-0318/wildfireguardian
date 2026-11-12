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
  * Result, pooled over 12,905 cells: z SD 1.08, and 10.2% of |z| exceed 1.645 (nominal 10%). In aggregate the
    variance is about right, **but the shape is not Gaussian**: the robust SD (MAD) is 0.36, and 7.8% of |z| exceed
    1.96 (nominal 5%). The core is too narrow and the tails too heavy.
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

## 4. Ideas and gaps

* *Hypothesis:* given §1, the raw-bracket arm (NIROPS survey pairs, VIIRS overpasses) is better founded than any
  kriged-label arm. The kriged SD is both large and miscalibrated, and the synthetic study shows the bracket
  likelihood's gain is largest exactly when the observation is coarse.
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
