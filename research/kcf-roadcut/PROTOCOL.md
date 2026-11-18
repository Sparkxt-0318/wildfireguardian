# kcf-roadcut: how much earlier is the last road cut than the village is reached? (frozen before any outcome)

Frozen 2026-11-18, Main at `896bd41` (PR #193). Hard stop: Fri 20 Nov 2026, 18:00 Shanghai (10:00 UTC).
Deliverables: `PROTOCOL.md` (this file), `RESULTS.md`, `numbers.json`, one figure (`gap_per_place.png`), one validation
table (`validation_table.csv`, also printed in RESULTS.md).

Nothing in §1–§7 changes after the first outcome is computed. A mistake found later is corrected by a dated
**amendment** at the bottom, with the reason, never by editing this text. What had been looked at when this was
written: the structure (column names, keys, file layout) of `research/kcf-replay/per_place.csv`, of
`research/harness-2026-11/F-3.1/results/HEADLINE_NR2_summary.json` and of the Choi TOA raster header; the code of
`research/kcf-replay/replay.py`, `analyze.py`, `measured_arms.py` and `research/harness-2026-11/F-DYN/fdyn/variants.py`;
the committed RESULTS.md files of those directories (which state the step counts and latest-departure tables already
published). No gap, no T_village, no window set and no validation comparison had been computed. Three web searches for
records (§5) were started at the same time; their results are records, not model outcomes, and none had come back.

**Every number this work produces is model output on reconstructed inputs. It is not what happened to people.** Every
table says so. Nothing here is a claim about what any official should have done.

## 1 Inputs (two families, never pooled)

| id | family | units | source |
|---|---|---|---|
| R | kcf-replay, 25 Mar 2025 12:00–24:00 KST | 174 places × 13 issue hours × 6 arms × 2 horizons (5 h, 8 h) = 27,144 place-hours | `research/kcf-replay` (rules `HOTSPOT_RULE.md`, `MEASURED_RULE.md` unchanged) |
| M | multi-hour F-DYN HEADLINE deadline-field run, `no_reentry/2` | 174 places × 6 starts × 2 horizons × 3 timing variants (kriged_mean, firms_early, envelope) = 6,264 rows | `research/harness-2026-11/F-3.1/results/HEADLINE_NR2_summary.json` (VERIFIED, ledger row 72) |

Arms of R: ORDINARY, RUNNING, WORST (stand-ins), MEASURED, MEASURED_GUST (ERA5, **PROVISIONAL**), MEASURED_GUST_KMA.
The static envelope_burnset row of M has no timing and is not used.

**Primary configuration for the one-line headline:** R, MEASURED, 8 h. Every other arm and horizon is reported in the
same tables with the same weight; the primary is named only so that the headline sentence is fixed in advance.

### 1.1 Rerun of R to recover the full window sets

The committed `per_place.csv` keeps only the last departure and the number of pieces. The window sets
(`sets_by_shelter_node`), cell closures (`close_s`) and witness routes are in the raw run files, which were not committed.
`replay.py` is rerun **unchanged** (`--workers 4`, all six arms, both horizons, both regions, 13 hours) on the frozen
inputs (`tools/fetch_routing_inputs.py`, SHA-verified) into scratch. Reproduction check, before any gap is computed:
for all 27,144 rows, `analyze.py` on the rerun must give identical `government_step`, `departure_state`,
`latest_safe_departure_kst`, `last_departure_in_horizon_kst`, `departure_set_pieces`, `shelter_id` and `arrival_kst`
to the committed `per_place.csv`. Every mismatch is reported; mismatching rows are reported separately and kept out of
the headline. (The committed MEASURED_GUST_KMA rows reuse the ERA5 run where the classes are equal; the rerun computes
that arm directly, which must give the same rows.)

## 2 Definitions

All times are absolute (KST shown); T = issue time (R) or start time (M); H = horizon.

### 2.1 T_village (when fire reaches the place)

The place is its planner entry node (진입 지점), the same point the replay and the government step use.

* **R:** d = distance of the entry node's routing-grid cell to the known fire area at T. T_village = T + closure_s(d)
  with the arm's own curve (`replay.closure_s` / `measured_arms.closure_s`), i.e. the closure time of the place's own
  cell. d = 0 → **INSIDE** (already reached at T; no gap). closure_s(d) > H → T_village **censored, "> T + H"**.
* **M:** T_village = the variant's arrival time at the KFS_01 export-grid cell (375 m, EPSG:5179, affine
  375/1085250/1845375) containing the entry node: kriged_mean = Choi 2026 TOA (`data-fetch/small/choi2026_kfs01`,
  committed); firms_early = `variants.firms_variants` on that TOA and the committed FIRMS files; envelope = its earliest
  bracket edge, which is firms_early (ASSUMED reading of "lo = firms_early"). No finite arrival (outside the kriged
  footprint) → never reached. T_village ≤ T, or the row labelled "start point on ground the model shows as burned
  before this start time: not evaluated" → **INSIDE**. T_village > T + H → censored. The arrival rasters are rebuilt
  here, not read from the F-DYN packets (not on Main); this is stated as a limit.

### 2.2 Windows and T_road (end of the last safe departure window)

* **R:** the window set of a place = the union over its 3 planner shelters of the F-3.1 issue sets
  (`core.issue_set`, integer seconds after T), merged where intervals overlap or touch (b + 1 = a). T_road = T + the
  last second of the last window. Every window is kept in the per-row output. A **hole** = a gap between two windows of
  the merged set; reported per place-hour (count of windows, total hole seconds), and also per shelter.
* **M:** under `no_reentry/2` every feasible set is a prefix (0 non-prefix sets, F-3.1 RESULTS); the window is
  [T, T + leave_by_s] and T_road = T + leave_by_s. Holes cannot occur and none are reported. Windows of the timing
  variants are reported side by side, never merged.

Departure state of T_road (same words as the replay):
* **CUT** — R: `departure_state = LATEST_SAFE_DEPARTURE`; M: `horizon_censored = false`.
* **NOT_CUT_WITHIN_H** — the set ends only at the horizon cap; T_road censored ("not cut within H").
* **NO_WINDOW** — not INSIDE, and the set is empty: the last road is already cut at T (T_road ≤ T).
* **INSIDE** — as §2.1.

### 2.3 Gap

gap = T_village − T_road.

| T_road | T_village within H | T_village censored |
|---|---|---|
| CUT | **exact gap** (seconds) | lower bound: gap > T + H − T_road |
| NO_WINDOW | lower bound: gap ≥ T_village − T | lower bound: gap > H |
| NOT_CUT_WITHIN_H | not determined (reported as a count) | not determined |
| INSIDE | excluded (counted) | – |

Medians and maxima are taken over **exact gaps only**; lower bounds are counted and their largest value is reported
separately. Nothing censored is imputed.

### 2.4 "Road cut before the village is reached"

In R the place's own cell closing at T_village always ends departures a little before T_village (the car must leave
the cell), so gap > 0 holds by construction and is not a finding. The test is therefore **which closure ends the last
window**. For each CUT place-hour the witness route at T_road (`route_edges`, the attaining shelter) is walked as in
`analyze.recheck`; for every segment the slack = closure second of its cell − (departure + D·z_end), and for the dwell
slack = closure of the shelter cell − (arrival + 120 s). The **binding cell** is the minimum-slack one:
* **ORIGIN_CELL** — the place's own entry cell: the window ends because the village itself is reached;
* **ROAD_CELL** — any other cell on the route: **the road is cut before the village is reached**;
* **SHELTER_CELL** — the dwell at the shelter: the destination is cut (reported separately, counted as cut before the
  village only in a separately labelled line);
* **UNCLEAR** — minimum slack > 60 s (reported, not counted either way).

Headline count A (R) = place-hours, and places with ≥ 1 such place-hour, with binding = ROAD_CELL, plus every
NO_WINDOW place-hour that is not INSIDE (no road out at T while the village is not yet reached). M has no committed
witness routes, so in M "cut before reached" = exact gap ≥ 5 min or NO_WINDOW with T_village > T (threshold fixed here);
the same threshold is also reported for R so the two can be set side by side. Gap thresholds reported for both: > 0,
≥ 5, ≥ 15, ≥ 30, ≥ 60 min.

## 3 Headline numbers (all with n)

Per family, arm/variant and horizon:
1. place-hours by state (CUT / NOT_CUT_WITHIN_H / NO_WINDOW / INSIDE) and by binding cell;
2. count A (§2.4): place-hours and distinct places (of 174);
3. median, 10th/90th percentile and maximum exact gap (minutes), n; the largest lower bound;
4. place-hours with holes, number of holes, median and maximum hole length;
5. the government-rule counts of §4.

Place-level summary: for each place, its exact gaps over issue hours (min, median, max), and the gap at the first issue
hour at which its state is CUT. The figure plots these for the primary configuration.

## 4 The government rule as applied here (a reading, not their system)

Rule (YTN 2025-04-16, `research/kcf-replay/SOURCES.md`): where the fire line is known, areas the fire can reach within
5 h are 위험구역, within 8 h 잠재적 위험구역 (vulnerable people pre-evacuate). Assumptions, all ASSUMED:
1. "Leave now" = 5 h zone, "prepare" = 8 h zone (the replay's reading; the source does not map zones to these words).
2. The reach time is to the place's entry point, i.e. T_village of §2.1.
3. The reach time is computed **with the same arm / variant as the road model**, from the same known fire area at T. The
   comparison isolates village-versus-road; it does not reproduce the Korea Forest Service's spread estimate, data,
   timing or delivery.
4. The designation is made at each issue hour / start and acts at once (no notification or mobilisation time).

Step(T) = LEAVE_NOW if T_village − T ≤ 5 h (or INSIDE), PREPARE if ≤ 8 h, NONE otherwise; in R this equals the
committed `government_step` (checked; mismatches reported). Counted on the **8 h runs**:
* **P5** = place-hours with Step ∈ {PREPARE, NONE} and (T_road state CUT with T_road − T ≤ 5 h, or NO_WINDOW): told
  "prepare" or nothing while the last road closes inside the 5 h "leave now" period;
* **P8** = place-hours with Step = NONE and (CUT with T_road − T ≤ 8 h, or NO_WINDOW);
* each split by Step, with distinct places, and the same counts on the 5 h runs for P5 only.

## 5 Validation against records the model never used

Records are searched on the web (road and expressway closure times on 25 March 2025; official evacuation order times
per town; satellite burned-area maps). For each: source, URL, publication time, **retrieval time (UTC)**, and whether
the page itself was read. Anything from a news report is marked **REPORTED**. Records already in
`research/kcf-replay/SOURCES.md` are reused with their original retrieval date and re-marked by this rule.
The replay's inputs (FIRMS, AHI, Choi TOA, KMA/ERA5 gusts, the margin tables) are not records for this purpose.

### 5.1 Road closures (model closure time vs recorded)

* Location: the named point (IC, junction, pass) is given coordinates from a cited map source; a named segment
  "A~B" is the shortest-length path on the region's road graph between the graph nodes nearest A and B.
* Model closure time of a record = the earliest closure second over the routing-grid cells of that point / path, for
  each arm, 8 h, at the **latest issue hour T ≤ t_recorded − 1 h** (lead ≥ 1 h); if none exists, the 12:00 KST issue
  and the lead are stated. Also reported: the reconstruction's first cut (`analyze.first_cut_times`, all detections
  including those after T) and the Choi TOA arrival at the same cells (both model inputs, labelled as such).
* error = t_model − t_recorded (minutes, signed). Cell inside the known fire area at T → "closed at issue"
  (error ≤ T − t_recorded, a bound). Closure beyond T + H → **MISS** ("model: not closed by T + H"). Outside both
  region grids → "outside model domain" (counted, not an error). A recorded closure is an administrative act, not a
  measured fire arrival; the comparison measures the difference, it does not say which is right.
* Summary (only if n ≥ 3 comparable records): n, median |error|, count within ±30 min and ±60 min, misses.

### 5.2 Evacuation orders per town

Per town (읍·면) with a recorded order time: the places of that town in R; for the primary configuration at the latest
issue hour ≤ order time, the number of places with Step LEAVE_NOW / PREPARE / NONE, their median T_road and median
T_village, and order time − median T_road (signed, minutes). This is a measured difference between two clocks. It is
not a validation of the fire model and not a judgement of the order.

### 5.3 Burned area (model arrival vs satellite map)

Map: Sentinel-2 L2A (AWS open bucket `sentinel-cogs`, COG), the MGRS tiles covering both region grids. Scenes chosen
**by metadata cloud cover only**, before any reflectance is read: pre-fire = least cloudy scene 2025-03-01..03-21;
post-fire = least cloudy scene 2025-03-29..04-30. NBR = (B8A − B12)/(B8A + B12) at 20 m; dNBR = NBR_pre − NBR_post;
pixels with SCL ∈ {0, 1, 3, 6, 8, 9, 10, 11} in either scene are invalid. Burned pixel: dNBR ≥ 0.10 (primary), 0.27
(sensitivity). A routing-grid cell (375 m) is **burned** if ≥ 25 % of its valid pixels are burned, **not assessable**
if < 50 % of its pixels are valid. If a published burned-area dataset is downloadable (found by the record search),
the same comparison is repeated against it as a second map; the official 피해면적 is reported next to the map's area
as a plausibility check only.

Comparisons (each a 2×2 table: hit, miss, false alarm, correct negative, plus not assessable):
* **places:** model "reached" (R, per arm, 8 h: INSIDE or T_village within H at any issue hour; M, per variant:
  finite arrival ≤ start + H at any start) vs the place's entry cell burned;
* **cells:** R, per arm: cells closed by T + 8 h at the 24:00 KST issue vs burned, over all cells of both grids.
The post-fire scene is days after the last forecast, so a "miss" may be fire that arrived later; a model closure means
"fire within reach", not "this cell burns". Both are stated next to the table.

Village-level fire-arrival accounts in `SOURCES.md` (all REPORTED, single-source) are listed against T_village at the
latest issue hour ≥ 1 h before, signed difference, n per account.

## 6 Ronchi et al. (Natural Hazards, 2023) verification tests

The test list is taken verbatim from the paper (citation and retrieval time in RESULTS.md). Each test is marked
**NOT APPLICABLE** when it exercises a component WildfireGuardian does not have (pedestrian movement, traffic flow or
congestion, evacuee behaviour or pre-evacuation decisions, fire-spread physics as opposed to a given arrival field),
with that reason. A test that exercises a component the model has (a road network with a given fire arrival or
closure field, single-vehicle routing, departure-time/deadline computation, the coupling of fire timing to route
availability) is **APPLICABLE**: it is built as the paper specifies on a synthetic instance and run through the
unchanged `deadline_field.core` (and `analyze.recheck`); PASS / FAIL by the paper's stated expected result. Where the
paper gives no quantitative criterion, the expected behaviour it states is used and quoted. The per-test applicability
decision is written as a dated amendment below **before** any test is run.

## 7 Reporting rules

* Every table carries: "Model output on reconstructed inputs. Not what happened to people."
* No claim about what any official should have done.
* MEASURED_GUST (ERA5) is PROVISIONAL; both gust arms' ≥ 20 m/s class rests on 9 fires; stated where used.
* n is given for every number. Censored values are bounds and are labelled so.
* Code and outputs: `research/kcf-roadcut/` (scripts, `numbers.json`, `per_unit.csv.gz` with every place-hour row
  including its windows). The raw rerun files stay in scratch (size); their SHA-256 are listed.

## Amendments

(none)
