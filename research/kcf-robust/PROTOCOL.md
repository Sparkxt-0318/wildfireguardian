# kcf-robust: does robust routing improve an outcome? (protocol)

Written and committed before any routing result of this folder was computed. Later changes are logged as dated
amendments in section 9 and say whether any result had been seen. Everything in this folder is **model output on
synthetic or reconstructed inputs. It is not what happened to people and makes no claim about what any official
should have done.**

## 0. Question

`research/kcf-idea-routing` gives, for every departure, the closure-timing error it tolerates (the margin field) and
one route valid for every error up to that margin. It is proved and tested, but nothing shows it improves an outcome.
This study asks: when the same caution is spent in different ways, does a rule that chooses route and leave-by for
tolerance (in time, in distance, or from a forecast's own expected error) give **fewer failed evacuations than the
product's current rule at equal or less lead time given up**?

## 1. Data

Nothing outside the repository and its release archive is used. The user's local folder "wildfire 3 (1)" (finals
forecast and heat data, keys) **could not be reached from the cloud session that ran this study** (no computer
attached); the repository's own inputs are used instead and no key is needed.

| what | source |
|---|---|
| road graphs, places, shelters | release archive `research-final-20261015` via `tools/fetch_routing_inputs.py`, then `product/wfg-roadlayer` `setup`. Regions `yeongdeok_2025` (91 places, 90 checkable) and `uiseong_andong_2025` (86, 84 checkable): the **174 places** |
| known fire area, 25 March 2025 | `research/kcf-replay/fire_discs.json` (discs with t < T) |
| twin truth and detections | `research/kcf-validate/twin` (`twin_lib.py`, `run_twin.py make`), unchanged: 12 seeds x issue offsets {24 h, 36 h} after ignition 2025-03-24 12:00 UTC, region `yeongdeok_2025` |
| fixed reach margin R90(h) | `research/kcf-replay/measured_arms.py` (`R_KM`, MEASURED arm: class by prior-3 h spread), = `research/kcf-margin` alpha 0.10 |
| central reach curve R50(h) | `make_r50.py` → `r50.json`: kcf-margin's own `calibrate.load`, `class_mask`, `reach.conformal_R` at alpha 0.50, fire set all28, same classes and draws. It reproduces the published alpha 0.10 values. Values (km, R5 / R8): all 0.00 / 0.75; quiet 0.00 / 0.00; slow 1.35 / 1.55; running 2.40 / 2.65 |
| expected reach error | `research/kcf-adaptive4/derived/expected_error.csv.gz` (format in its `EXPECTED_ERROR_FORMAT.md`) |
| official times | `research/kcf-validate/out/jaenan_replacement.csv` (`official_kst`), events located by `research/kcf-roadcut/validation.py` (`ROAD_RECORDS`, `EVAC_RECORDS`, `road_cells`, place-to-town assignment) |
| engine | `product/wfg-roadlayer` (`pipeline.compute`, `engine`, vendored F-3.1 `core`), unchanged |
| margin field | `research/kcf-idea-routing/margin_field` (branch `research/kcf-idea-routing`, copied into this branch unchanged) |

Horizon H = 8 h = 28,800 s, dwell 120 s, 3 nearest shelters per place: the product's default settings.

## 2. Common forecast and closure rasters

For an issue time T, the known area K_T is the union of the discs with t < T (replay: real discs; twin: the system's
synthetic detections). For every cell of the 375 m KFS_01 lattice (214 x 67, the lattice of
`product/wfg-roadlayer/examples/build_example_raster.py` and of the twin) d = distance from the cell centre to K_T
(min over discs of max(0, centre distance - radius)), as in `build_example_raster.py` and `run_twin.system_minutes`.

A **reach curve** g(h) (km, h in hours after T, non-decreasing, g(0) >= 0) gives a closure raster: the cell closes at
the first h with g(h) >= d, rounded up to the second, and is not closed within the horizon if g(8 h) < d. Every
closure raster is turned into the road instance by the product (`fireinput` resampling, `engine.build_instance`,
`engine.accept`, `engine.origin_closure`), unchanged. All closures in this model are permanent.

* **R90 raster** (the product today): g = piecewise linear through (0, 0), (5 h, R90_5), (8 h, R90_8) of the class
  (`measured_arms.curve("MEASURED", ...)` and `closure_s`, called directly).
* **F50 raster** ("the forecast"): the same with R50. The difference R90 - R50 is the product's fixed reach margin.
* **E raster** (forecast-aware): g(h) = running maximum over leads <= h of (margin_km + err_q90_km) from the
  expected-error file, linear between whole leads, g(0) = 0. Replay: rows `set = DET`, `fire = KFS_01`, at the
  latest `t_utc` <= T (15:00 UTC uses the 14:00 row, the last issued). Twin (synthetic fires, no rows of their own):
  per lead the median over all `set = KR` rows (12 Korean fires, leave-one-fire-out). Fixed before any result: p = 0.90.
* **Dilation by r** (reach tolerance): raster value at a cell = minimum over cells whose centres lie within r km
  (Euclidean, the cell itself included) of the raster value. "The fire reaches r km farther than forecast at every
  moment."
* **Shift by m** (timing tolerance): every closure second b becomes max(0, b - m), road cells, waits, the origin and
  the shelter's own fire closure alike (`pipeline.compute(shift_s=m)`). Closures here are permanent ([b, H]), so
  widening each closure by m seconds on both sides, as the margin field defines it, equals this shift except that
  the end of the horizon is not moved. The margin field of `research/kcf-idea-routing` treats the shelter's fire
  closure as part of the acceptance set and, in its keep variant, does not widen it; this study widens it, so the
  shelter's burn time is uncertain too. The equality of the two where the shelter does not burn within H is checked
  on a sample (section 7).

## 3. Decision rules (same inputs for all)

Every rule gives, per place and issue time: L = latest safe departure second (-1 = no safe departure, "cut at
issue"), the cut time (L + 1, or "not cut within H" when the latest departure is set by the horizon, as the product
decides), and an advised route (the product's witness: earliest-arrival journey at L over the shelters attaining L).

| rule | closure raster | leave-by and route |
|---|---|---|
| a. CURRENT | R90 | product read-off |
| b. TIME-ROBUST | F50 shifted by m\* | latest t whose timing tolerance mu(t) >= m\*; route = witness of the m\*-shifted instance, valid for every closure-timing error up to m\* (margin field, Theorem 2) |
| c. REACH-ROBUST | F50 dilated by r\* | latest t whose reach tolerance rho(t) >= r\*; route = witness of the r\*-dilated instance, valid for every extra reach up to r\* (nested instances) |
| d. FASTEST | F50 | product read-off: time-dependent fastest (earliest-arrival) path on the forecast, leave-by = latest departure for which one exists, no margin |
| e. FORECAST-AWARE | E (p = 0.90) | product read-off: the reach each departure must survive is the expected-error bound at the lead at which the vehicle is on each road |

**Equal caution (m\*, r\*).** b and c have one knob each. It is set so that the rule spends the same total caution as
CURRENT, using no truth: S(X) = sum over all evaluated place-pairs of (L_X + 1) seconds (0 for cut at issue). m\* is
the smallest m on a 60 s grid (0 to 8 h) with S(b(m)) <= S(a); r\* is the smallest r on the 0.125 km grid (0 to
15 km) with S(c(r)) <= S(a). Set separately for the twin (all 24 issue pairs) and for the replay (all 26
region-hours). e is not tuned (p = 0.90 is the same nominal 10 % miss rate as R90).

## 4. Step 1: tolerance in distance (and time)

For each of the 174 places and each of the 13 replay issue hours (25 March 2025, 03:00 to 15:00 UTC = 12:00 to
24:00 KST), on the **product's own raster (R90)**:

* L(r) for every r on the 0.125 km grid 0 to 15 km (latest departure on the R90 raster dilated by r);
* tolerated reach R_tol = largest grid r with L(r) >= 0 (a safe departure still exists); reported as "< 0" when
  L(0) = -1 and as ">= 15 km" when L(15 km) >= 0;
* tolerated timing error T_tol = largest m on a 60 s grid with a safe departure at the issue time on the m-shifted
  raster; and mu at t = 0 from the margin field where it applies;
* binding road: on the witness route of the tolerance limit (dilated by R_tol, departing at 0), the edge with the
  least slack (closure start minus the second the route enters it); its OSM way name/ref.

**Method used for the grid.** The existing engine over a grid of r is what the brief allows. For speed a compiled
latest-departure pass is used (`reachpass.py`): with permanent closures and downward-closed acceptance every feasible
set is an interval [0, L], so the F-3.1 recursion reduces to one latest-departure label per edge state. It is used
only after it agrees exactly with (i) the unchanged engine (`core.backward` + `issue_set`) on the real instances at
>= 6 grid values per region-hour sampled before running and (ii) a brute-force search over all journeys on >= 2,000
small random instances with random rasters and dilation radii (largest r with a safe departure, and L(r)). Any
disagreement stops the study until explained. The report says which method produced each number.

## 5. Step 3: tests where truth is known

### 5.1 Twin (primary test)

24 issue pairs x 90 checkable places = 2,160 place-pairs. Truth instance: the product fed the twin's true arrival
raster (as in kcf-validate). A place-pair is evaluated when neither truth nor any rule refuses it.

**Baseline check.** Rule a must reproduce kcf-validate's system arm: 12 of 221 true cut-offs missed and 146 of 1,939
false cut-offs. If it does not, the harness is wrong; nothing is reported until it does.

**Metrics, per rule** (truth states and the miss/false definitions are kcf-validate's):

* **failed evacuation**: the rule gives a leave-by inside the horizon (cut within H and L >= 0) and its advised
  journey, departing at L, is not valid in the truth instance (an edge entered at or after its true closure start, a
  wait at a closed node, departure from a closed origin, or arrival not accepted at the shelter). Checked leg by leg
  with the instance semantics, and cross-checked with `research/kcf-theorem/checker.py` on a sample.
  n = place-pairs with such a leave-by. Also reported: late leave-by (L > true L\*), regardless of route.
* **missed cut-off**: truth CUT (cut within H, including at issue) and the rule NOT CUT or cut later than truth.
* **false cut-off**: truth NOT CUT and the rule CUT.
* **lead time given up**: on the common set of place-pairs whose true latest departure L\* is inside the horizon and
  >= 0 (truth CUT, not at issue): g = L\* - L_X minutes (L_X = -1 for cut at issue, the horizon-set L when not
  cut). Median and mean. Negative = advised later than the truth allowed.

**Uncertainty.** Cluster bootstrap over the 12 fires (both issue times of a fire resampled together), 10,000
resamples, seed 20261119, 95 % percentile intervals for the paired difference X - a in failed evacuations (count
over the same resampled set) and in median lead given up.

**Pass rule (frozen).** A rule X in {b, c, e} **passes** if (1) the 95 % interval of failed(X) - failed(a) lies
entirely below 0, and (2) median g_X <= median g_a (point estimates). If none passes, RESULTS.md says so in its first
lines. Three rules are tried; Bonferroni (98.33 %) intervals are reported next to the 95 % ones, and a pass that
holds only at 95 % is labelled so.

### 5.2 25 March 2025 replay (descriptive, no pass rule)

13 issue hours x 2 regions. Truth is not known; two comparisons:

1. **Order and timing against official times.** Events with an `official_kst` in `jaenan_replacement.csv`:
   evacuation orders (EV, located to places by town or village as kcf-roadcut does) and road closures (RD, located
   to road cells by `road_cells`). Model time per rule, independent of the official time:
   * place: tau = earliest clock time over issue hours T of T + cut (cut at issue -> T); for an EV unit, the
     earliest tau over its places (the first village the rule would cut) and, separately, the median;
   * road: tau = earliest over T of T + earliest closure second of the road's cells in the rule's closure raster
     (b: shifted; c: dilated; others as in section 3).
   * Not cut by the end of the last horizon: censored, ranked last, time difference not computed.
   Reported per rule: Spearman rank correlation between official and model times (EV, RD, pooled; with a bootstrap
   over events), median and median absolute minutes (model - official), count compared.
2. **Failed evacuations against the reconstruction** (secondary, labelled RECONSTRUCTED): truth = cell covered by a
   disc of the full detection record (`research/kcf-replay/analyze.first_cut_times`), seen at T, horizon 8 h. Same
   metrics as 5.1. The reconstruction is the detection record, not a fire perimeter.

### 5.3 Secondary (reported, not used for the verdict)

Trade-off curves (failed evacuations against median lead given up) for b over m, c over r, e over p in
{0.5, 0.8, 0.9, 0.95, 0.99}, and CURRENT at R80 (alpha 0.2); the 25 March fragility statistics; failure when
departing at the issue time instead of at the leave-by.

## 6. Step 4: product output

A fragility table for the 174 places x 13 replay hours (tolerated reach, tolerated timing error, binding road,
method). In `product/wfg-roadlayer`: an optional `--fragility` switch that adds these columns to the CSV and writes one
page per town (읍·면); off by default, existing outputs and golden files unchanged.

## 7. Checks run before the results are read

* compiled pass = engine and = brute force (section 4);
* rule a reproduces kcf-validate (section 5.1);
* timing shift = margin field (`margin_field`, keep variant) at the same m on a sample of shelters that do not burn
  within H; the relation between mu(t) and L - t is reported as found;
* E raster built from the right rows (spot check printed);
* the R90 raster equals the committed example rasters at 03:00 and 09:00 UTC.

## 8. Deliverables

`RESULTS.md`: one table (rule, failed evacuations, missed, false, lead time given up, n), the fragility table (full
CSV plus a summary), limits, and ten lines for `research/kcf-evidence/TALK_NUMBERS.md`. Every number traceable to a
file in `out/`.

## 9. Amendments

1. **2026-11-19, before any outcome (no rule had been compared with any truth or official time).**
   (a) The real-instance check of the compiled pass that ran before its first use covered 3 closure levels
   (dilation 0, 0.5, 1.5 km) on 2 region-hours (Uiseong-Andong 03:00 UTC, Yeongdeok 09:00 UTC): 1,566
   shelter-origin-level comparisons, 0 mismatches, every feasible set one interval starting at 0
   (`out/check_real.log`). That is fewer than the "at least 6 grid values per region-hour" of section 4. A wider
   check (6 levels on 4 region-hours) is run in addition and reported; if it finds a mismatch, every number from the
   pass is recomputed with the engine. The brute-force part (2,000 random instances) ran as written.
   (b) Step 4 is implemented in the product with a **forward** search (earliest-arrival route at a fixed departure per
   closure level, bisection; `product/wfg-roadlayer/wfg_roadlayer/fragility.py`), a different algorithm from the
   research backward pass. The fragility table is produced by the product code and compared place by place with the
   research pass; disagreements are reported.
   (c) The Overture locality polygons used by kcf-roadcut are the `division_area` type (the `division` type has no
   polygons); both are fetched with kcf-roadcut's own script. Event locations reproduce kcf-roadcut's table
   (same edge and place counts).

2. **2026-11-19, after the replay calibration sums were computed, before any rule was scored against a truth or an
   official time.** The calibration uses no truth. On the replay, S(b(m)) stays above S(a) for every m up to 8 h
   (at m = 8 h, S(b) / S(a) = 1.12): shifting the central forecast earlier cannot close a road the central forecast
   never reaches within the horizon, while CURRENT's 90 % reach margin does. Section 3 has no rule for this case. Rule:
   if no grid value reaches S(a), the knob is set to the smallest grid value at which S reaches its minimum (for b
   on the replay, m = 7 h 55 min; S is flat from there to 8 h) and the remaining gap is reported; the 60 s refinement is skipped. Such a rule spends less caution than CURRENT, so the
   comparison is not at equal caution; the pass/fail rule of section 6 is unchanged (it already requires equal or less
   lead time given up). The same rule applies to the twin calibration and to c.
