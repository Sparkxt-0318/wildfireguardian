# Track A metrics and scoring domain

Code: `firecast_lab.metrics` (scores), `firecast_lab.domain` (domain and masks) and `firecast_lab.decision` (the
decision metric, §7). Tests in `tests/` pin
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

## 7. Decision metric (`firecast_lab.decision`)

**Question.** Suppose an evacuation planner trusted the model's K members. How often would a trip the model
calls safe turn out to meet the fire? A model that never clears anything is never falsely safe, so the clearance
rate is always reported next to the false-safe rate.

**Unit.** A fixed routing request: one vehicle itinerary in one window (cutoff `c`, lead `L` = 24 h) of one fire.
Requests are not independent: they share windows and fires.

### 7.1 Requests: cutoff information only

`build_requests` uses only:
- the static road graph (for the Korean graphs, an OSM snapshot from the day before ignition);
- the cutoff burned state (`Cutoff.burned`) and the event grid;
- the lead, the fire id, the cutoff time and the run seed.

It never uses a forecast, the outcome, the final perimeter or the scoring domain (tested: two windows with the same
cutoff state but different futures give identical requests). It is deterministic per (fire, cutoff, seed). The
draws use the window seed `data.case_seed(seed, fire, cutoff)` on a stream separate from the member draws.

The rule. Parameters live in `RequestConfig` and are recorded in every result's config.

1. **Origin.** A road node, drawn uniformly among the candidates. A candidate touches no cell burned at the cutoff
   (closed cells), does not touch the grid's outside, and is within `origin_max_m` = 3 km of the nearest burned
   cell (distance between cell centres). 3 km is the headline buffer (§2), about 2.7 times the 24 h reach of the
   dev-tuned best dilation.
2. **Destination.** A road node drawn uniformly among those that are reachable from the origin, do not touch the
   grid's outside, and lie at a straight-line distance in `trip_m` = [2, 4] km from the origin.
3. **Path.** The static shortest-time path. Labels sit on edges, so forbidden turns are kept; ties go to the
   smaller edge id. If an edge touches the grid's outside, the request is drawn again.
4. **Wait.** At a waitable origin, with probability `wait_share` = 0.5, a stationary wait before departure. Its
   length is uniform in whole seconds over [1 s, `wait_max_s` = 1 h].
5. **Timing.** The vehicle is at the origin from `start` (uniform in whole seconds over
   [0, L - wait - travel - 1 s] after the cutoff). It waits, then departs, and drives at the graph's static times
   (uniform motion along each edge). It arrives before `c + L`.
6. **Count.** Up to `n_requests` = 32 per window. A failed draw is redrawn, up to `attempts` x `n_requests` draws
   in total. The number built is recorded per window.
7. **Validity.** Every request passes evacplan's hazard-free validator, so no verdict comes from a resource rule.
   A truth `model_no_route` with a `RESOURCE:` cause raises.

**As evacplan objects.**
- One `Instance` per window: the graph, plus one vehicle per request with depot = origin and `start_s` = start.
- One `Itinerary` per request: an optional `Wait`, then a `Drive`.
- Instance time 0 is the cutoff, which is also the issue time of every model and truth set.

**Budgets.** Peak 10 kW/m² and dose 100 kJ/m² in every member: the router's request budgets
(`integration/src/wfg_latest/packets.py:178`). Under the reference flux law (at most 0.703 kW/m²) the peak budget
never binds, so contact and dose decide.

### 7.2 Verdicts: only `evacplan.oracle` declares them (program rule 3)

**Model.** `evacplan.oracle` runs on the model's hazard_contract set (`producer.from_window`, K members).
- *cleared* means the oracle declares the itinerary `checked`, i.e. checked in all K members.
- `model_no_route` or `unresolved` means *not cleared*.

**Truth.** `evacplan.oracle` runs on the truth set (§7.3).
- *hit*: `model_no_route`, i.e. certain flame contact up to the horizon, or a peak or dose lower bound above budget.
- *safe*: `checked`.
- *unresolved*: excluded from the scored set and counted with its cause: unknown cells or outside the scoring
  domain, outside the grid, beyond the truth horizon, or an unresolved peak or dose. Never counted as safe.

### 7.3 Truth sets: `hazard_contract.from_perimeters`, mode `envelope`

**Sources.**
- **Korean fires** (labelled *reconstruction truth*). The reconstructed arrival's hourly isochrones
  `{arrival <= c + h}`, for integer `h` from before the first arrival up to `L`, are used as a perimeter series.
  Hourly spacing is the reconstruction's own output lattice.
- **US fires.** NIROPS survey perimeters at their survey times, up to the window's endpoint survey (none later).
  Earlier surveys date the fire that is burning at the cutoff. The horizon is the last survey, so later trips are
  unresolved. The NIROPS loader is not written yet: the perimeters are on the Mac.

**Why `envelope`** (K = 1). A cell first inside perimeter `i` burns from `t[i-1]` until `t[i] + T`: the union of
every burning interval consistent with the perimeters.
- A truth *safe* is therefore certain: no timing consistent with the observed or reconstructed perimeters makes the
  trip meet the fire. Timing ambiguity between perimeters can never make a trip look safe that might not be.
- The price is that a truth *hit* means contact under at least one consistent timing. False-safe and miss rates are
  upper bounds with respect to timing between perimeters. This ambiguity is about 1 h plus `T` for reconstruction
  isochrones, and about a day for NIROPS surveys.
- `stratified` or `rotated` members would place ignitions at chosen fractions of each gap. A truth *checked* would
  then not be certain, and the verdict would depend on how many truth members there are.

**Shared physics.** `T` and the heat source are the producer's packet values (`T` = 3970 s). Model and truth sets
therefore differ only in when cells burn.

**Support (mapped mask).** The window's scoring domain: the headline domain by default (final perimeter + 3 km,
clipped to the grid), or the grid with `--domain full`.
- Outside the domain the truth is unknown, so the request is unresolved.
- Inside the domain, cells outside the final perimeter never burn. This is the §2 convention ("outside the mapped
  extent"), the same one the cell scores use.

**Clock.** Issue time is the cutoff. The horizon is `c + L` for reconstruction truth, or the last survey.

### 7.4 Rates

Pooled counts over the scored requests (truth *hit* or *safe*) of all windows and fires:

| Rate | Definition |
|---|---|
| **false-safe** (headline) | `P(hit \| cleared) = #(cleared and hit) / #cleared` |
| miss rate | `#(cleared and hit) / #hit`: cleared trips among the routes the fire reached |
| clearance rate | `#cleared / #scored` |
| false-unsafe rate | `#(not cleared and safe) / #safe` |

- **Undefined rates.** A rate is undefined when its denominator is 0.
  - If nothing is cleared, false-safe is reported as "undefined (clearance 0)". It is never reported as 0
    (`summarize` gives `point` None plus a note).
  - The four rates are always shown together, with their counts.
  - Next to them: the number of truth-unresolved requests and their causes, how many of those the model cleared,
    and the number of fires.
- **Intervals.** A whole-fire percentile bootstrap (`metrics.fire_bootstrap`, 10,000 draws, seed 20261029).
  - Each draw resamples fires and pools their request counts.
  - All four rates use the same draws.
  - Draws in which a rate is undefined are counted (`undefined_draws`) and left out of its quantiles, so that
    interval is conditional on the rate being defined.
  - Windows and requests are never resampled on their own.
- **Never pooled.** Korean scores (reconstruction truth) and US scores (NIROPS truth) are kept apart.

### 7.5 K curve and member couplings

**K curve.**
- Each member order is either the set's own order or one of `repeats - 1` seeded shuffles; the same shuffles are
  used in every window.
- For each order and each K' in 1, 2, 4, ..., K: a request is cleared at K' iff the oracle declares it checked on
  the scenario set of the order's first K' members.
- Each point is (clearance, false-safe), pooled over requests.
- Where nothing is cleared, false-safe is undefined. Such points are listed under the plot, never drawn at 0.

**Monotonicity.** Under the all-members rule, adding members can never clear a request again (tested on every
nested subset). So a request cleared at K is cleared at every K', and each order binary-searches the K' lattice
for the others.

**Couplings.** Both couplings of `members.coherent_members` are always reported:
- **shared**: nested members, the least conservative coupling for "every member clear";
- **Gaussian copula**: correlation length L = 8 cells (3 km), declared with `--length-cells` and stated with every
  result. It is a placeholder, not calibrated (backlog L8).

Members are drawn with the window seed, so every model gets the same random numbers. K = 64 by default, matched
across models.

### 7.6 Limits and cost

**Limits.**
- **Hindsight in the grid.** Requests live on the event grid, whose extent was cut from the final perimeter
  (`docs/DATA_NOTES.md` §5). The hindsight sits in the grid, not in the request rule, and it is the same for every
  model.
- **Reconstruction timing.** Korean reconstruction truth has about 10 h of timing error (DATA_NOTES §1). Its
  verdicts describe agreement with the reconstruction.
- **Scope of a request.** Requests are single-vehicle trips, not plans. Speeds are static (no congestion), and
  occupants' exposure before departure is not modelled.
- **Declared, not tuned.** `origin_max_m`, `trip_m`, the waits, the budgets and the copula length are declared.
  Changing them needs Siyeong's approval, like any definition here.

**Cost.** Timed on the real Uljin road graph with a SYNTHETIC hazard (timing only): about 4.6 min per window at
K = 64, 32 requests, 4 member orders and 2 couplings on the 4-vCPU cloud host. The median trip there has 105
edges. That is about 80 min per model for the 17 Korean dev windows that have road graphs. Time it on the Mac
before a full run; `--requests` and `--repeats` scale the cost.

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
