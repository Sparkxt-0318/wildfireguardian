# kcf-reopen protocol: a road cell is closed for a window, not forever

Frozen 2026-11-21, before any reopening number was computed. Base: Main at `c437771f` (after PRs #231–#233). Later
changes are logged as dated amendments at the end; nothing above them is edited.

**What this is.** Model output on inputs rebuilt from public observations and on reconstructions, scored against
other observations. Not what happened to people. No claim about what any responder or official should have done.

**Not a first look.** The Camp Fire workbook, its classes, the 195 blocked-road reports, the 23 passable reports, the 23
burnovers and the two documented movements were all used in `research/kcf-camp` (RESULTS.md, merged at PR #232). I have
read those results (RESULTS.md and PROTOCOL.md, which quote several reports with their times and model closures) and
its code; I have not opened its per-report output tables before freezing this file. The Korean VDS closure runs (`research/kcf-validate/out/vds/vds2_closure_runs.csv`,
with the end of each run) were also published there and I have seen their file header and first rows, not their
reopening times by section. Everything below is chosen knowing the kcf-camp finding: the permanent closure kept 22 of
23 passable roads closed, and both movements were infeasible because their start cells burned over before the trip.

## 1. The rule under test

For a road cell c, three quantities:

* **C_c**, the margin-adjusted closure time: exactly the closure of the variant under test (kcf-camp §3: M0, M30, MR,
  MR-running; product: the input raster's closure second, after any `shift_s`).
* **A_c**, the fire-arrival time: evidence that fire reached the cell (definitions per setting in §3). A cell with no
  A_c never reopens.
* **τ**, the burn-out time (§2).

The cell's state at time t:

| state | when | routing |
|---|---|---|
| **open** | t < C_c | usable by everyone |
| **closed by fire** | C_c ≤ t < R_c, R_c = max(C_c, A_c + τ) | usable by no one |
| **burned over** | t ≥ R_c | responders: usable by default. Residents: usable only when **confirmed** (§1.1); otherwise treated as closed to the end of the horizon, exactly as today |

So for residents the default is unchanged: the closure is permanent unless a confirmation exists. The window applies to
responders by default, and to residents only for confirmed cells.

**1.1 Confirmation (residents).** A burned-over cell is confirmed at t when, at some time u with R_c ≤ u ≤ t, there is
(i) a road report that the road in that cell is passable or open (Camp: a `ROAD_PASSABLE` row or a vehicle-present
observation, §2.1, in the input set and not the row being scored; Korea: an official 한국도로공사 reopening message for a
section containing the cell), or (ii) a vehicle unit `REOPENED` event (`hardware/vehicle-unit`, `api/live.py`) whose
point lies in the cell. Confirmation never shortens a closure: before R_c the cell is closed whatever is reported.

**1.2 Edges, waits, shelters, origins.** A cell closed on [b, r) (b = C_c, r = R_c for responders or confirmed cells,
r = ∞ otherwise) gives, with the edge's segment through c covering fractions [z_in, z_out] of travel time D_j:

* edge j blocked for start seconds t with t + D_j·z_out ≥ b and t + D_j·z_in < r, i.e. [⌈b − D_j z_out⌉, ⌈r − D_j z_in⌉ − 1];
* waiting [t, t + 1] at a waitable node in c blocked for t ∈ [b − 1, r − 1];
* a shelter in c refuses arrival a when the stay [a, a + dwell] meets [b, r): a ∈ [b − dwell, r − 1];
* departure from an origin in c refused for t ∈ [b, r − 1].

All clipped to [0, H]; r = ∞ reproduces the product's `engine.build_instance` / `accept` / `origin_closure` exactly
(this is tested). The deadline field (`core.backward`, `issue_set`, `witness`) is not changed; Theorem 1 of
`research/kcf-theorem` says it is exact for any interval sets.

## 2. Burn-out time τ

**2.1 Candidates, each with its source** (reported in RESULTS.md as a table):

* Literature, point-scale flaming residence (`/Users/jp/Desktop/wildfire/documents/flame_residence_literature.md`):
  Wotton et al. 2012 main front 37 s (SD 14 s), plus 37–74 s continuous and 75–127 s intermittent flaming after it;
  Anderson 1969 T = 8 min per inch of particle diameter (1-h fuel ≈ 2 min, 10-h up to 8 min, 100-h 8–24 min); Burrows
  1994 T = 0.871 d^1.875 s (16 mm: 159 s); Andrews 2018 T = 384/σ min (σ in ft⁻¹). These are flaming durations at a
  point. They are lower bounds for a 375 m cell and do not cover burning structures, vehicles, fallen trees or lines.
* `research/kcf-radiation` amendment A7: it **uses no residence time** (it rejected one because the age of a burn is not
  in the inputs) and keeps burned-out cells radiating; that is τ = ∞, the current product.
* The Camp Fire estimate below.

**2.2 Camp Fire estimate.** Rows of `research/kcf-camp/data/observations_dedup.csv` with times, classes from
`classes_final.csv`, placed on the kcf-camp graph's road cells by kcf-camp's `Graph.match` (own cell, else nearest road
cell within 375 m). A **vehicle-present observation** is a row whose `location_source` contains `AVL` (an apparatus
location record): a vehicle was at that place at that time, whatever the row's class. Per road cell c:

* E_c = earliest time of a `FIRE_ARRIVAL` or `ROAD_CLOSED` row in c (first fire evidence);
* g_block(c) = latest `ROAD_CLOSED` time in c − E_c;
* g_open(c) = earliest time u > E_c of a `ROAD_PASSABLE` row or vehicle-present observation in c, − E_c;
* g_open_after_block(c) = earliest such u later than the last `ROAD_CLOSED` row in c, − E_c (cells with both bracket
  the burn-out time between g_block and this).

All rows are used (this is estimation, no hold-out). Reported: n, quantiles, by day, and per cell.

**Frozen choice, fixed now:** τ = the 80th percentile of g_block over cells with g_block > 0 (blocked again after fire
was first seen there), rounded up to a multiple of 15 min. τ_low = the median, τ_high = the 95th percentile, same set,
same rounding. Floor 15 min. If fewer than 10 cells have g_block > 0: τ = 180, τ_low = 60, τ_high = 360 min.
*Why blocked reports set τ and passable/vehicle gaps do not:* a blocked report is direct evidence that the road was
still closed; 19 of the 23 passable reports describe fire on or beside the road being driven (kcf-camp), so passable and
vehicle gaps measure what fire crews drove through, not burn-out. The 80th percentile matches kcf-camp's 80 % hit
threshold. The g_open gaps are reported beside it. The literature values are not used to set τ (point scale).

**2.3 In-sample warning and cross-fit.** τ comes from the Camp workbook and Test 4 scores the same workbook. As a
secondary check, road cells are split at the median easting of cells with g_block > 0; τ is re-estimated on each half
by §2.2 and Test 4.3's reopened-too-early count is recomputed with each half scored by the other half's τ.

## 3. Arrival A_c in each setting

* **Camp (Tests 4.1–4.3).** A_c = earliest `FIRE_ARRIVAL` observation in cell c in that test's input set (kcf-camp
  §4: the same hold-outs). Secondary: A_c from the earliest input observation within 375 m of the cell centre
  (neighbour arrival), reported as exploratory.
* **Korea replay (Steps 5–7).** System arrival: the replay's known area, A_c = earliest time a detection disc of
  `research/kcf-replay/fire_discs.json` covers the cell centre (kcf-replay `analyze.first_cut_times`). For a forecast
  closure that is not yet in the known area at issue T, A_c = the central forecast F50 (kcf-robust §2, R50 curve); if F50
  does not reach the cell within H, no reopening. Secondary for Step 5: the Choi reconstruction
  `/Users/jp/Desktop/wildfire/data/regions/{uiseong_andong_2025,yeongdeok_2025}/arrival_time_hours.tif`.
* **Twin.** System as replay (synthetic detections; F50). Truth: closed on [true arrival, true arrival + τ). This makes
  the twin truth obey the same τ by construction; stated as a limit.
* **Product.** A_c = the input raster's value by default; an optional second raster gives the central arrival when the
  input raster is already margin-adjusted (INTERFACE.md). Cells burning at issue (value ≤ 0) have A_c = 0, i.e. reopen
  at issue + τ, never earlier than the true burn-out when the true arrival was before the issue time.

## 4. Step 3: routing with reopening

At least **5,000** random instances built through the windowed builder of §1.2 (random graphs of 2–7 nodes, up to 12
edges, D 1–4, H 8–30, random forbidden turns and waitable nodes, cells with random [b, r) of which at least half end
inside H, random shelters and dwell). For each: `core.backward` + `issue_set` against the brute-force `feasible_set` of
`research/kcf-theorem/checker.py` (which imports nothing from the repository), and every witness `core.witness` returns
for the first and last second of every feasible interval checked by `checker.check_route`. **PASS**: 0 disagreements
and 0 invalid witnesses, and the r = ∞ builder equals the product's on every case. Also on the real Camp graph: every
witness of Test 4.1 checked by `check_route`. The product's own certificate tests are run unchanged.

## 5. Step 4: Camp Fire tests

Graph: kcf-camp `build_graph_osm.py` on the same Overpass query (four tiles). If the tile checksums differ from
`research/kcf-camp/data/osm_tiles_sha256.txt`, I rebuild, rerun kcf-camp's permanent rule on the new graph, report any
difference from kcf-camp's numbers, and use the rerun as the baseline. Variants M0, M30, MR, MR-running; "without margin"
= M0, "with margin" = MR (primary). Rules: **perm** (kcf-camp), **window** at τ, τ_low, τ_high (responders), **resident**
(window only where confirmed). Tolerance 15 min as kcf-camp.

**4.1 The two movements** (kcf-camp §2.5, §6 Test 3: issue at the documented time, input = fire observations before
it, horizon 2 h, dwell 120 s). Reopening R_c = A_c + τ with A_c from the input. **PASS** for a movement: feasible at the
documented departure (13:58 for b) and ≥ 80 % of the witness route on the documented roads. Reported for every rule and
τ, both movements; the route and its road sequence printed.

**4.2 Passable reports and vehicle-present observations.** Model state at the reported time t: **closed** when
C ≤ t − 15 and R > t + 15 (closed throughout ±15 min); otherwise open or burned over (labelled: open if C > t − 15, else
burned over). Passable reports: kcf-camp's strict Test 1 input. Vehicle-present observations on a road cell: one field
per observation, input = all `FIRE_ARRIVAL` rows except that row and those within 500 m and ±60 min of it. Counts of
open, burned over and closed; distinct cells reported. **PASS** per class and variant: share closed ≤ 0.20, judged with
the Wilson interval as kcf-camp (FAIL when the interval excludes 0.20 from below, INCONCLUSIVE when it contains it).

**4.3 Guards.** (i) The 195 blocked-road reports, kcf-camp strict input: hit = C ≤ t + 15 and R > t − 15.
**Reopened too early** = C ≤ t + 15 and R ≤ t − 15 (the model had already reopened the cell). (ii) The 23 burnovers,
kcf-camp Test 2 input: at τ' ∈ {t − 60, t − 30, t}, CLOSED if any cell has C ≤ τ' < R; UNSAFE if not closed and any cell
has C ≤ τ' + 30 and R > τ'; else OPEN. **PASS** per variant: hits and CLOSED-or-UNSAFE counts at every lead equal to the
perm baseline (no loss at all), i.e. 0 reports reopened too early and no burnover state lost.

Every test is reported with and without margin; failures are stated as failures.

## 6. Step 5: Korean expressway reopenings

Closure runs of `vds2_closure_runs.csv` (15-minute volumes, kcf-validate amendments 13 and 15) inside the official
closure sections of `research/kcf-validate/out/kec_official_closure_events.csv`. Traffic return = the run's end
(`reopen_kst`); per section the median over its conzone-directions. Section cells: the region graphs' edges of the
route between the two named interchanges (OSM names), clipped to the grid; if an interchange is not on the graph, the
route's in-grid cells (kcf-roadcut `road_cells` rule), marked. Model reopening of a section = the latest A_c + τ over its
cells with an A_c (§3, discs; Choi as secondary); a section with no A_c on any cell is reported as "not reached by fire in
the model", with no reopening time. Reported per section: official closure and reopening messages, traffic return,
model reopening at τ, τ_low, τ_high, and the difference model − traffic (min). Descriptive; no pass rule; the sample is
what exists.

## 7. Step 6: margin field and kcf-robust, responder setting

Margin field = `research/kcf-idea-routing/margin_field` (unchanged), on the windowed closures. Plain slack at departure t
= L − t, with L the latest departure of the interval containing t. For each place, issue and shelter set: margin at
departure 0 vs slack at 0; count place-issues where they differ, and the largest difference. Gyeongbuk replay
(`research/kcf-robust`, 2 regions, issues 03:00–15:00 UTC on 25 March) and the twin (12 seeds × 2 issue offsets). Then
kcf-robust's comparison (rules a–e, its definitions, its m\*, r\* calibration and pass rule) rerun with responder windows
in both system and truth. If nothing changes, RESULTS.md says so.

## 8. Step 7: effect on the Gyeongbuk replay and the product

Per place and issue time (174 places, 13 issues), rule CURRENT (R90): a **later window** = the issue set under the window
rule contains a departure later than the latest departure under perm (including a new interval after a gap). Counted for
responders (all reopenings) and residents (confirmed only: official reopening messages sent before the issue time for
sections containing the cell; there are no vehicle-unit events for March 2025). The product gets the rule as an option
(`[reopen]` in settings, `--reopen`), off by default for residents; INTERFACE.md updated.

## 9. Limits stated in RESULTS.md

Fallen trees, power lines, smoke and burning buildings behind the front are not modelled; the reopening sample is small;
firefighter vehicles are not residents; τ is estimated and scored on the same fire; the twin truth uses the same τ.

## Data and keys

"wildfire 3 (1)" was found only in the Trash (`~/.Trash/wildfire 3 (1)`), holding `DATA_INDEX.md` alone; there is no
`keys/keys.env`. No step here needs a key (Overpass is keyless; KEC data are the user's files). `NEEDS.md` records this.

## Amendments

1. **2026-11-21, during the run; results of steps 1–4 had been computed, step 5 primary numbers had been seen for
   one run.** (i) *Camp graph:* the refetched Overpass tiles (four quadrants of the same box, same filter) have other
   checksums than kcf-camp's and give 4,349 nodes, 9,584 edges and 2,114 road cells (kcf-camp: 4,350, 9,585, 2,121).
   kcf-camp's permanent rule rerun on this graph reproduces every road-state state and closure time and every burnover
   state of kcf-camp exactly (230 rows, 0 differences; `out/camp_baseline/`). (ii) *Step 5, traffic return:* the VDS run
   used per conzone-direction is the first run with onset ≤ official closure + 6 h and reopen later than the official
   closure (the near-zero spell in effect at the closure or starting within kcf-validate's 6 h matching window).
   Chosen after listing the runs, before any model reopening time was computed. (iii) *Step 5, geometry:* OSM maps
   each carriageway as its own component, joined only by `motorway_link` ramps; links and mainline pieces without the
   route's ref are used at 5× cost, and the share of the path on the route's ref is reported (96–100 %). (iv) *Step 5,
   secondary column added after seeing the primary:* the model's closed spell (union over cells of [A_c, A_c + τ))
   that covers the official closure time, and its end. The pre-registered "latest A_c + τ over the section" counts fire
   that reached the section after a closure had already ended; the secondary column does not. Both are reported; the
   primary is unchanged.
