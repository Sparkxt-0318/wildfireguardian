# kcf-robust: does the margin field improve an outcome?

**Model output on a synthetic twin and on a reconstruction of 25 March 2025. No claim about what happened to people.**
Rules: [PROTOCOL.md](PROTOCOL.md), committed before any result. The two amendments are in its section 9 and summarised at the end of this file. Every number here comes from a file in `out/`.

## Answer

**No.** On the twin (the primary test, where truth is known), none of TIME-ROBUST (b), REACH-ROBUST (c) or
FORECAST-AWARE (e) has fewer failed evacuations than CURRENT with a 95 % interval that excludes no difference. The
pre-registered pass rule fails for all three (`out/twin_scores.json`, `verdict`):

* **b** has 0 failed evacuations against CURRENT's 5. It achieves this by never advising a departure: at its
  calibrated setting it calls every place it cuts "cut now". It misses 57 of 221 true cut-offs (CURRENT: 12). The
  interval for the difference in failures is [-10, 0], so a difference of zero is not excluded.
* **c** has 1 failed against 5, interval [-9, 0]. It also gives up 29 min more lead time (median), interval [+8, +91].
* **e** has 4 failed against 5, interval [-6, +3]. It gives up 30 min less lead time, interval [-63, +3], and has half
  CURRENT's false cut-offs (73 against 146) but more misses (20 against 12).

The margin field did not improve an outcome here, and the reason is structural. In this product every road closure
is permanent. Under permanent closures, the margin field for leaving now equals the time left until the leave-by
time (checked below). So "maximise the tolerated timing error" reduces to "take the fastest route on the forecast
and leave a fixed time earlier". A timing buffer cannot cover a road the forecast never reaches, and the twin's
errors are mostly of that kind: the fire goes where the forecast says it does not.

## The table (twin, primary: 12 fires x 2 issue times, 90 places, 2,160 place-pairs)

| rule | failed evacuations | missed cut-offs | false cut-offs | lead time given up, median (min) | n |
|---|---:|---:|---:|---:|---:|
| a. CURRENT (R90 deadline field, the product) | **5** / 210 advised | 12 / 221 | 146 / 1,939 | 165.8 | 2,160 |
| b. TIME-ROBUST (margin field, m\* = 7 h 55 min) | **0** / 0 advised | 57 / 221 | 12 / 1,939 | 23.8 | 2,160 |
| c. REACH-ROBUST (reach margin, r\* = 2.75 km) | **1** / 30 advised | 16 / 221 | 71 / 1,939 | 195.1 | 2,160 |
| d. FASTEST (time-dependent fastest path, central forecast) | **7** / 26 advised | 64 / 221 | 12 / 1,939 | -21.3 | 2,160 |
| e. FORECAST-AWARE (expected-error bound p = 0.90 at the lead time on each road) | **4** / 127 advised | 20 / 221 | 73 / 1,939 | 135.4 | 2,160 |

Column definitions:

* **failed**: the rule gives a leave-by and its own route, leaving at that time, is not valid against the truth.
  The denominator is the number of place-pairs where the rule advised a departure.
* **missed / false**: these follow kcf-validate's definitions.
* **lead time given up**: true latest safe departure minus the rule's leave-by, on the 118 place-pairs the truth cuts
  with a safe departure left. A negative value means the rule advised leaving later than the truth allowed.

**Baseline check passed:** rule a reproduces kcf-validate's system arm on all 2,160 of 2,160 place-pairs: 12 / 221
missed and 146 / 1,939 false. Every failed evacuation in the table is late: the rule's leave-by is after the truth's
latest safe departure, so no route would have worked.

**Differences against CURRENT.** Cluster bootstrap over the 12 fires, 10,000 resamples, seed 20261119.

| rule | failed X − a | 95 % | 98.33 % (Bonferroni) | median lead given up X − a, 95 % | passes? |
|---|---:|---|---|---|---|
| b | −5 | [−10, 0] | [−12, 0] | [−201, −82] | no (interval reaches 0) |
| c | −4 | [−9, 0] | [−10, 0] | [+8, +91] | no (interval reaches 0; gives up more lead) |
| d | +2 | [−8, +12] | [−9, +15] | [−220, −120] | (not a candidate) |
| e | −1 | [−6, +3] | [−7, +3] | [−63, +3] | no |

**Equal caution.** b and c each have one setting. It was chosen without using the truth, so that the rule spends the
same total caution as CURRENT (PROTOCOL section 3; `out/twin_calibration.json`).

* c reaches CURRENT's level at **r\* = 2.75 km**.
* b cannot reach it at any timing buffer up to 8 h. At the smallest-S setting, 7 h 55 min, it still leaves 4.5 % later
  in total (amendment 2). b at that setting moves every forecast closure to the issue time, so it never gives a
  leave-by inside the horizon. Its 0 failed evacuations count nothing it advised, not good advice.

**Over the whole range of each setting** (secondary, route-independent; `out/tradeoff_twin.csv`). This counts
"unsafe" place-pairs: the rule's leave-by is later than the truth's latest safe departure.

| setting | unsafe / 2,160 | lead given up, median (min) |
|---|---:|---:|
| a CURRENT (R90) | 13 | 165.8 |
| a at R80 | 31 | 118.7 |
| b, m = 0 → 8 h | 68 → 61 | −21 → 24 |
| c, r = 1 / 2 / 2.75 / 4 / 10 km | 52 / 29 / 18 / 9 / 0 | 53 / 180 / 195 / 224 / 269 |
| e, p = 0.80 / 0.90 / 0.95 / 0.99 | 44 / 22 / 19 / 2 | 74 / 135 / 184 / 209 |

* **b** never gets below 61 unsafe place-pairs, whatever the timing buffer.
* **c and e** trace the same trade-off as CURRENT, more caution for fewer unsafe place-pairs; neither has fewer unsafe
  place-pairs at equal or less lead given up.
* **e at p = 0.90** gives up 30 min less than CURRENT and has 22 unsafe against CURRENT's 13.

## 25 March 2025 replay (secondary, descriptive, no pass rule)

### Against the official alert and road-closure times

Source files: `out/official_events.csv` and `out/official_scores.json`. The 12 evacuation alerts are located to places
and the 9 road closures to road cells, as kcf-roadcut does. 1 alert unit is censored (no rule cuts it).

| rule | alerts, first village: Spearman [95 %] | median model − official (min) | median abs (min) | alerts, median village: Spearman | median abs (min) |
|---|---|---:|---:|---|---:|
| a | 0.31 [−0.45, 0.82] | −3 | 126 | 0.60 [−0.05, 0.97] | 53 |
| b | 0.29 [−0.50, 0.80] | −20 | 68 | 0.59 [−0.08, 0.98] | 38 |
| c | 0.34 [−0.39, 0.83] | −22 | 104 | 0.57 [−0.14, 0.97] | 38 |
| d | 0.34 [−0.40, 0.84] | +33 | 121 | 0.48 [−0.27, 0.95] | 73 |
| e | 0.31 [−0.45, 0.82] | −16 | **32** | 0.58 [−0.08, 0.99] | **28** |

* The order of villages cut does not separate the rules: every Spearman interval overlaps every other.
* e's timing is closest to the official alert times, median absolute 28–32 min against CURRENT's 53–126.
* **Road closures are uninformative.** 6 of the 9 closed roads are long highways that already cross the burnt area at
  the first issue hour, so every rule puts them at 12:00 KST, about 4 h before the official closure. The comparison is
  left-censored there.

### Against the reconstruction (labelled RECONSTRUCTED)

Truth here is the detection record, not a fire perimeter. Clusters are the 26 region-hours (`out/replay_scores.json`).

| rule | failed evacuations | missed cut-offs | false cut-offs | lead time given up, median (min) | n |
|---|---:|---:|---:|---:|---:|
| a | 184 / 349 | 719 / 1,887 | 126 / 375 | −187.9 | 2,262 |
| b | 0 / 0 | 699 / 1,887 | 62 / 375 | −247.8 | 2,262 |
| c (r\* = 3.25 km) | 48 / 83 | 635 / 1,887 | 99 / 375 | −201.9 | 2,262 |
| d | 52 / 123 | 751 / 1,887 | 62 / 375 | −258.2 | 2,262 |
| e | 275 / 505 | 665 / 1,887 | 150 / 375 | −136.6 | 2,262 |

On 25 March the reconstructed fire ran hours ahead of every forecast. Every rule's median leave-by is 2.3 to 4.3 h after
the reconstructed latest safe departure, and about half of each rule's advised departures fail; for e, 275 of 505.

* Failures differ from CURRENT's as follows: c −136 [−213, −67], d −132 [−219, −55], e +91 [+17, +175].
* c's −136 comes with 266 fewer departures advised, not with better routes.
* On the reconstruction, no rule is safe. This adds nothing in favour of the margin field: b gives no advice at all.

## Step 1: tolerance in distance and time

**Method used: the existing engine's model over a grid of R, not a one-pass method.**

* For each place and issue hour, the leave-by L(r) is computed on the product's R90 raster dilated by r, for r = 0
  to 15 km in 0.125 km steps (121 levels).
* The tolerated reach R_tol is the largest r with L(r) ≥ 0.
* The tolerated timing error is the largest earlier shift of every closure, in 60 s steps, for which a safe
  departure still exists.
* The grid is evaluated by a compiled backward latest-departure pass (`reachpass.py`). Under permanent closures every
  feasible set is one interval starting at 0, so the pass is exact.

**Checks:**

* **Brute force on small random cases:** 2,000 random instances, plus dilation cases, 0 mismatches
  (`tests/test_reachpass.py`, `out/test_reachpass.log`).
* **Against the unchanged engine on real networks:** 1,566 comparisons before first use and 6,264 afterwards (6 levels
  on 4 region-hours), 0 mismatches (`out/check_real*.log`).
* **Margin field vs timing shift:** on 56 sampled origin–shelter pairs, the shift tolerance equals the committed margin
  field (`research/kcf-idea-routing`, keep variant) at departure time 0 in 56 of 56 (`out/check_margin.json`).
  Wherever the fire limits the route (11 pairs), μ(t) = L − t at every second of the window. Elsewhere μ is the
  horizon. **So under this product's permanent closures, the margin field is the slack L − t.**

**Leave-by as a function of R:** the full curve L(r) per place and hour is in `out/replay/<region>_<hour>.json`
(`fragility.L_by_r`).

## Step 4: fragility table (174 places x 13 issue hours)

Full table: [`out/fragility_174.csv`](out/fragility_174.csv). It has 2,262 evaluated village-hours, plus 39 rows for
the 3 places the product refuses (entry too far). Each row gives, for leaving now:

* the tolerated extra reach (km; "≥ 15" censored) and the road that fails first under it (name and OSM way);
* the tolerated timing error (min; censored at the 8 h horizon) and its binding road.

The table was produced with the product's own new code, `product/wfg-roadlayer` `run --fragility`. That code uses a
forward search with bisection, a different algorithm from the research pass. It agrees with the research pass on all
2,262 reach values and all 2,262 timing values. The binding road agrees on 512 of 549 reach cases and 351 of 352
timing cases; the differences were not examined (the values themselves agree) (`out/fragility_check.json`).

In the product, `--fragility` is off by default. Without it, the output is byte-identical to before. With it, the
product appends four columns to both CSVs and writes one A4 page per 읍·면 (ko and en), most fragile village first.
The tests are in `product/wfg-roadlayer/tests/test_fragility.py`.

| region | issue (KST) | places | no safe departure now | tolerated reach, median (km) | < 1 km | ≥ 15 km | timing < 60 min |
|---|---|---:|---:|---:|---:|---:|---:|
| Uiseong-Andong | 03-25 12:00 | 84 | 34 | 6.38 | 10 | 0 | 7 |
| Uiseong-Andong | 03-25 13:00 | 84 | 36 | 5.38 | 8 | 0 | 5 |
| Uiseong-Andong | 03-25 14:00 | 84 | 39 | 5.38 | 5 | 0 | 2 |
| Uiseong-Andong | 03-25 15:00 | 84 | 44 | 4.69 | 5 | 0 | 5 |
| Uiseong-Andong | 03-25 16:00 | 84 | 55 | 4.25 | 3 | 0 | 8 |
| Uiseong-Andong | 03-25 17:00 | 84 | 80 | 0.56 | 3 | 0 | 4 |
| Uiseong-Andong | 03-25 18:00 – 03-26 00:00 (each hour) | 84 | 82 | 0.38 | 2 | 0 | 2 |
| Yeongdeok | 03-25 12:00 – 16:00 (each hour) | 90 | 0 | ≥ 15 | 0 | 90 | 0 |
| Yeongdeok | 03-25 17:00 | 90 | 0 | ≥ 15 | 0 | 79 | 0 |
| Yeongdeok | 03-25 18:00 | 90 | 0 | ≥ 15 | 2 | 51 | 2 |
| Yeongdeok | 03-25 19:00 | 90 | 14 | 9.69 | 3 | 5 | 4 |
| Yeongdeok | 03-25 20:00 | 90 | 18 | 8.88 | 1 | 0 | 5 |
| Yeongdeok | 03-25 21:00 | 90 | 38 | 3.31 | 7 | 0 | 12 |
| Yeongdeok | 03-25 22:00 | 90 | 63 | 2.12 | 5 | 0 | 10 |
| Yeongdeok | 03-25 23:00 | 90 | 63 | 2.12 | 5 | 0 | 10 |
| Yeongdeok | 03-26 00:00 | 90 | 70 | 1.81 | 5 | 0 | 8 |

How to read the table:

* "No safe departure now" means that on the product's own R90 raster the place has no safe departure at the issue
  hour (1,128 of 2,262 village-hours).
* **Most fragile with a route still open:** 의성읍 and 점곡면 (동변리, 사촌리, 서변리) at 12:00–13:00 KST. They tolerate
  0.25 km of extra reach and 6–10 min of timing error, and the shelter cell itself is what fails first.
* **Timing column = time left until leave-by:** in all 349 village-hours where the fire sets the leave-by, the
  tolerated timing error equals that time. The remaining village-hours are horizon-censored, except 3 where a road on
  the route closes in the last minutes of the horizon. **The reach column is the one that adds information.**

## Checks run

* Rule a reproduces kcf-validate's system arm on 2,160 of 2,160 place-pairs.
* The twin truth rasters are regenerated byte-identical, and CURRENT's twin raster equals kcf-validate's.
* The R90 replay rasters equal the committed example rasters at 03:00 and 09:00 UTC.
* Failed-evacuation verdicts were cross-checked with the independent checker `research/kcf-theorem/checker.py` on 300
  twin and 300 replay journeys, every twin failure included: 600 of 600 agree (`out/check_failed.json`).
* The compiled pass matches brute force and the engine (Step 1). The margin field equals the timing shift (Step 1).
* The harness skips the engine's witness for departure at the issue time. Its other outputs were checked identical
  with and without the skip.

## Limits

* **Twin size and population.** Twin: 12 synthetic fires on one region (Yeongdeok), 2 issue times each. Its truth is
  a model fire, its errors come from its own generator, and 5 failures for CURRENT is a small count. The intervals are
  wide for that reason; a real effect smaller than about 5 failures in 2,160 place-pairs cannot be seen here.
* **Permanent closures make b uninformative.** In this product a closed road never reopens, so the margin field
  carries no information beyond the slack. A model with reopening roads, smoke that clears or time-limited closures
  could give a different answer. That case was not tested.
* **b's calibration.** b could not be calibrated to equal caution (amendment 2). At its setting it gives no departure
  advice, so its failure count says nothing about its advice.
* **Replay.** The replay truth is the detection record, not a perimeter. Official times are when the alerts were sent
  and roads were closed, not when roads were cut. There are 12 alert units and 9 roads, and 6 roads are left-censored
  at the first issue hour.
* **Not done:** the secondary analysis "failure when departing at the issue time instead of at the leave-by"
  (PROTOCOL 5.3) was not computed.
* **Data source.** The user's folder "wildfire 3 (1)" could not be reached from this cloud session, so no computer
  was attached. All data came from the repository: the twin of kcf-validate, the kcf-replay detection discs,
  kcf-adaptive4's `expected_error.csv.gz`, kcf-margin's calibration, Overture divisions and segments. No key was used.
* **Model output only.** None of this says what happened to people on 25 March.

## Amendments (PROTOCOL.md section 9)

1. Made before any outcome:
   * the real-instance check before first use was smaller than planned, so a wider check was added (0 mismatches);
   * the product's Step 4 uses a forward search, compared with the research pass;
   * Overture `division_area` polygons are used.
2. Made after the calibration sums and before any scoring: S(b(m)) never reaches S(a). The setting goes to the
   smallest-S grid value (7 h 55 min) and the gap is reported. The gap is 4.5 % on the twin and 12.2 % on the replay.

## Reproduce

See [README.md](README.md).
