# Track A metrics and scoring domain

Code: `firecast_lab.metrics` (scores) and `firecast_lab.domain` (domain and masks). Tests in `tests/` pin
every definition below to hand-computed values or known identities on SYNTHETIC data. The data caveats behind
these choices are in `docs/DATA_NOTES.md`. Fixed on 2026-10-31, before any Track A model output exists.
Changing a definition needs Siyeong's approval.

## 1. What is scored

- **Quantity.** For a window (cutoff `c`, lead `L`), a cell's outcome is "new burn": it burns in `(c, c + L]`.
  - Headline lead `L = 24 h`; 12 h is diagnostic only.
  - With reconstruction truth: `y = 1` if `c < arrival <= c + L`.
  - With NIROPS truth: `y = 1` if the cell centre is inside the cumulative mapped union at the endpoint survey
    but not at the cutoff survey.
- **Cohort.** Cells burned at the cutoff are not scored: every forecast gets them right.
- **Forecast.** `p` is the forecast probability of new burn by `c + L`. For a K-member scenario set, `p` is the
  share of members that burn the cell by `c + L`.
- **Units of evidence.** Windows of one fire are not independent. Intervals resample whole fires (§5).
- **Never pooled.** Korean scores (reconstruction truth) and US scores (NIROPS truth) are reported separately.

## 2. Label states and the scoring domain

Each cell and verification time has one of three label states:

| State | Meaning | Source |
|---|---|---|
| `1` | inside the mapped burned extent by that time | reconstruction (arrival at or before the time) or NIROPS union |
| `0` | outside the mapped extent at that time | inside the scar before its arrival, or outside the final perimeter within the domain |
| unknown | not mapped | excluded from scoring; never counted as unburned |

A `0` means **outside the mapped extent**. It never means "certified unburned". This is the policy of
`forecast/wildfire/observed_evaluation.py:185`.

**Headline domain** (`domain.headline_domain`): cells whose centre lies within **3 km** of a final-perimeter
cell centre, clipped to the event grid. Three reasons for 3 km:

1. **It covers a baseline's false alarms.** The dev-tuned best dilation of the earlier study grows 1 cell per
   8 h (`forecast/documents/preregistration_blind_test.md:62`), i.e. 3 cells (1.1 km) per 24 h. 3 km
   (8 cells) is about 2.7 times that, so every cell such a baseline can falsely flag at the headline lead is
   scored, with room for faster runs. It is also one c651 9x9 context width (3.4 km).
2. **It uses all the mapped ground near the fire.** It is wider than the 2 km margin of the US grids, so on US
   fires the ring reaches the grid edge wherever the perimeter touches its bounding box.
3. **It leaves out easy far-field negatives.** A larger buffer mostly adds far cells that every model gets
   right, which inflates skill. Those cells belong to the secondary score.

The final perimeter is the finite-arrival mask of the reconstruction (`docs/DATA_NOTES.md` §5).

**Secondary domain** (`domain.full_rectangle`): the whole event grid. It keeps continuity with the earlier
studies, which scored the full rectangle with outside-the-union negatives. It includes the easy far field, so it
is never the basis of a claim. Korean grids are tight bounding boxes of the final perimeter, so there the two
domains differ little.

**Never-mapped cells.** These are excluded from both domains and never padded as unburned:
- ring cells that fall beyond the grid (counted by `domain.ring_cells_off_grid`);
- verification times without a NIROPS survey (no interpolation);
- any cell whose label a truth product leaves unknown.

**Scoring mask** (`domain.scoring_mask`) =
`domain & label known at cutoff and endpoint & not burned at the cutoff & supported by every compared model`.
- All models are scored on identical cells, and nothing is imputed.
- Next to every score, report how many domain cells each model's support removes. A model must not look better
  by leaving hard cells unsupported.
- Unsupported cells also count as `unresolved` in the decision metric, never as safe.

Every metric function takes this mask explicitly. Inside it, every input must be finite and in range, or the
function raises. Values outside it are never read, and may be NaN.

## 3. Probability metrics (`y` in {0, 1}, `p` in [0, 1], over the `N` scored cells)

| Metric | Definition | Function |
|---|---|---|
| Brier score | `BS = mean (p - y)^2` | `brier` |
| Brier skill vs persistence | `1 - BS / BS_pers`. Persistence forecasts no new burn (`p = 0`), so `BS_pers` = observed frequency | `brier_skill(y, p, 0, mask)` |
| Brier skill vs calibrated best dilation | `1 - BS / BS_ref`, with `BS_ref` the Brier score of the calibrated best-dilation probabilities (the bar to beat; defined by the baseline task) | `brier_skill(y, p, reference, mask)` |
| Reliability diagram | rows of count, mean forecast and observed frequency. The first row is `p == 0` exactly; then `[0, 0.1%)`, `[0.1, 0.3%)`, `[0.3, 1%)`, `[1, 3%)`, `[3, 10%)`, `[10, 20%)`, `[20, 30%)`, `[30, 50%)`, `[50, 70%)`, `[70, 100%]` (the 0.1% bin excludes `p == 0`) | `reliability` |
| ECE | `sum over rows of abs(sum p - sum y) / N`, using the rows above | `ece` |
| Average precision | step-wise: precision at each distinct forecast value (ties grouped), weighted by the recall gained. The no-skill level is the base rate, which is always reported alongside | `average_precision` (reuses `wildfire.baselines`) |

Why there are bins below 1%:
- c651 put 37% of new burns in its below-1% bin and gave 617 positives exactly zero probability
  (`firecast-lab/CLAUDE.md`).
- A false-safe decision is made precisely at low probabilities.
- Most cells sit in the low bins, so ECE is dominated by them. The exact-zero row shows the zero-probability
  positives directly (its `observed_sum`).

`summary()` returns the pooled scores of `wildfire.baselines.score` (Brier, `bss_vs_persistence`, AP, ROC AUC,
`ece_10_bins`, clipped NLL, exact-zero positives) plus base rate, ECE and the rows above. The 10 equal-width-bin
ECE is kept only for continuity with earlier reports; `ece` is the Track A definition.

## 4. Spatial and ensemble metrics

**Fractions Skill Score** (Roberts & Lean 2008; `fss`, `fss_terms`, `fss_scales`).
- `Pf` and `Po` are the means of `p` and `y` over the scored cells of the `n x n` window around each scored
  cell. Cells outside the mask or the grid belong to no window.
- `FSS(n) = 1 - sum (Pf - Po)^2 / sum (Pf^2 + Po^2)`, summed over scored cells.
- **Pooling.** Windows and fires are pooled by summing numerator and denominator (aggregate FSS), never by
  averaging FSS values.
- **Sizes:** `n = 1, 3, 9, 17, 33` cells, i.e. 0.375, 1.125, 3.375, 6.375 and 12.375 km.
- **Forecast field.** Taking `p` as the forecast field makes `Pf` the expected member fraction (by linearity).
- **Reading it.** Skill is "useful" above `0.5 + f0 / 2`, with `f0` the observed fraction (`fss_useful`). At
  `n = 1`, `FSS = 1 - BS / mean(p^2 + y^2)`. For a window covering the whole grid, FSS tends to
  `2 F O / (F^2 + O^2)` (tested).

**CRPS on arrival time** (`hourly_arrival`, `crps_arrival`, `crps_arrival_terms`).
- **Lattice.** Arrival is the hour after the cutoff in which the cell burns: `(h - 1, h] -> h` for `h = 1..H`,
  and `H + 1` means not by the horizon (censored).
- **Definition.** For members `x_1..x_K` and observation `o`:
  `CRPS = sum_{i=1..H} (F_i - 1{o <= i})^2` hours, where `F_i` is the share of members burned by hour `i`.
  - It is the Brier score of "burned by hour `i`" summed over the hourly leads (Hersbach 2000), so censoring at
    the horizon is exact.
  - It equals the kernel form `E|X - o| - E|X - X'| / 2` on the censored values (tested).
  - A single deterministic member gives the censored absolute error in hours.
- **Fair version.** `fair=True` subtracts `F_i (1 - F_i) / (K - 1)` per lead (Ferro 2014). Use it when
  comparing ensembles of different K.
- **Inputs.** Members must be supported on every scored cell, and cells burned at the cutoff are rejected.
- **Truth limits.** Only the reconstruction gives hourly truth, with roughly 10 h Korean timing error, so
  arrival CRPS is a reconstruction-truth metric. With NIROPS truth there is one verification time per window
  and CRPS reduces to the endpoint Brier score.

**Rank histogram** (`rank_histogram`).
- The rank (0..K) of the observed censored arrival among the K member arrivals; ties are broken uniformly at
  random (Hamill 2001; seeded).
- Flat is necessary, not sufficient, for calibration.
- Reading the shape:
  - U-shape: overconfident (members too similar);
  - dome: over-dispersed;
  - mass at low ranks: the fire arrived earlier than the members, i.e. members too slow.
- `fully_tied` counts cells where every member equals the observation, typically all censored. Their ranks are
  uniform by construction, so a large count flattens the histogram without showing calibration. Always report
  it.

**Spread-skill** (Fortin et al. 2014; `spread_skill`).
- With `s^2` the unbiased member variance, an exchangeable ensemble satisfies
  `E[(mean - o)^2] = (K + 1) / K * E[s^2]`.
- `ratio = sqrt((K + 1) / K * mean s^2) / RMSE(mean)`: 1 is consistent, below 1 overconfident, above 1
  over-dispersed.
- **Caution with binned rows.** Rows group cells by the ensemble's own `s^2`, which selects on sampling noise.
  On a SYNTHETIC exchangeable ensemble the decile ratios run from 0.76 to 1.23 at K = 10, but stay within
  0.98-1.04 at K = 256; the overall ratio is unbiased at any K (tested).
  - Read rows only at K of about 256 or more.
  - Otherwise, compare them with a synthetic exchangeable ensemble of the same K.
- **Variable.** By default the censored arrival hour; the same function works for the 0/1 burned-by-lead
  indicator.

## 5. Uncertainty: whole-fire paired bootstrap

**Scheme.**
- Each draw resamples the F fires with replacement and pools their per-entry terms. A fire drawn twice counts
  twice.
- Candidate and reference use the same draws.
- Interval: the 95% percentile interval over 10,000 draws.
- The seed is recorded; the default 20261029 is that of `wildfire.baselines.paired_fire_bootstrap`.

**Functions.**
- `paired_brier_bootstrap` is `wildfire.baselines.paired_fire_bootstrap` applied to the masked entries:
  candidate Brier minus reference Brier, where negative favours the candidate.
- `fire_bootstrap(fire, terms, statistic)` covers every other pooled metric from additive per-entry terms:
  - Brier skill: `[(p - y)^2, (r - y)^2]` mapped to `1 - s0 / s1`;
  - FSS: `fss_terms`;
  - CRPS or CRPS skill: `crps_arrival_terms`;
  - ECE: per-bin sums.
- It reproduces `paired_fire_bootstrap` on Brier differences (tested).
- `brier_skill_bootstrap` uses the same draws as `paired_brier_bootstrap`. In every draw the skill is positive
  exactly when the Brier difference is negative.

**Properties.**
- Repeating windows inside fires leaves the interval unchanged (tested): windows are not fires.
- Draws where a statistic is undefined, such as a zero reference Brier score, are counted in `undefined_draws`
  and left out of the quantiles.

**Caveat on few fires.** Percentile intervals from few fires are coarse and tend to be too narrow. Four Korean
test fires allow only 35 distinct resamples, and six US test fires 462. Report the number of fires next to
every interval.

## 6. Reporting rules

- **Result rows** record the git commit, seed, config and host. Results on SYNTHETIC data say SYNTHETIC
  everywhere, including figures.
- **Claim rule** (`firecast-lab/CLAUDE.md`). A model counts as an improvement only if, on held-out fires, it
  beats calibrated best dilation with a whole-fire bootstrap interval that excludes zero, on Brier skill
  (headline domain, 24 h) or on the decision metric. If nothing clears the bar, say so plainly.
- **Always shown together:** headline and secondary domains, Korean and US, coverage, and the number of fires.

## References

- Roberts, N. M. & Lean, H. W. (2008). Scale-selective verification of rainfall accumulations from
  high-resolution forecasts of convective events. *Mon. Wea. Rev.* 136, 78-97.
- Hersbach, H. (2000). Decomposition of the continuous ranked probability score for ensemble prediction systems.
  *Wea. Forecasting* 15, 559-570.
- Gneiting, T. & Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and estimation. *JASA* 102,
  359-378.
- Ferro, C. A. T. (2014). Fair scores for ensemble forecasts. *Q. J. R. Meteorol. Soc.* 140, 1917-1923.
- Hamill, T. M. (2001). Interpretation of rank histograms for verifying ensemble forecasts. *Mon. Wea. Rev.*
  129, 550-560.
- Fortin, V., Abaza, M., Anctil, F. & Turcotte, R. (2014). Why should ensemble spread match the RMSE of the
  ensemble mean? *J. Hydrometeorol.* 15, 1708-1713.
