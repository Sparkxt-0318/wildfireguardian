# kcf-defend: where would holding the fire buy the most safe departure time? (frozen before any outcome)

Frozen 2026-11-18 (≈ 15:45 UTC, Wed 18 Nov 23:45 Shanghai), repository Main at `16c0957`. **Hard stop: Sun 22 Nov 2026,
12:00 Shanghai (04:00 UTC).** Whatever is finished then is what is reported; anything unfinished is listed as not done.

Origin: an idea from a firefighter interview — tell the Korea Forest Service which location to hold. This study computes,
for candidate locations, how much **safe departure window** (minutes in which leaving still reaches a shelter, in the
F-3.1 deadline field) villages would gain if fire arrival there were delayed by 30, 60 or 120 minutes, weighted by
population, and ranks the candidates at each issue hour of the 25 March 2025 replay.

Nothing in §1–§8 changes after the first outcome is computed. A mistake found later is corrected by a dated
**amendment** at the bottom, with the reason, never by editing this text. What had been looked at when this was written:
the code of `research/kcf-replay/replay.py`, `measured_arms.py`, `research/harness-2026-11/F-3.1/deadline_field/core.py`
and `intervals.py`, `research/kcf-roadcut/replay_gaps.py` (head) and `overture/fetch_overture_theme.py`; the headers and
arm counts of `research/kcf-replay/per_place.csv`; `kcf-roadcut/RESULTS.md` §0 (published); the structure of the road
graphs and `places.geojson`; one test read of the Meta HRSL population raster (a window sum over a 1° × 0.4° box, to
confirm access). No window gain, no candidate benefit and no ranking had been computed. The prior-work search (§9) had
not been started.

**Every number this work produces is model output on reconstructed inputs. It is not what happened to people, and it
is not a claim that any suppression action would have changed any outcome.** Every page and table says so.

## 1 Inputs (unchanged from kcf-replay)

* Known fire area at issue time T: `research/kcf-replay/fire_discs.json` (discs with t < T), rule `HOTSPOT_RULE.md`.
* 13 issue hours T = 25 Mar 2025 12:00 … 24:00 KST; horizons H = 5 h and 8 h; 2 regions (영덕 `yeongdeok_2025`,
  의성·안동 `uiseong_andong_2025`); the 174 checkable planner places (villages, hamlets, care facilities) with their 3
  planner shelters each (`replay.planner_candidates`); road graphs from `tools/fetch_routing_inputs.py` (SHA-verified).
* Six arms R(h), each giving closure seconds per routing-grid cell (375 m) from its distance d to the known fire area:
  ORDINARY, RUNNING, WORST (`replay.closure_s`), MEASURED, MEASURED_GUST (ERA5, **PROVISIONAL**), MEASURED_GUST_KMA
  (`measured_arms`). Closure b_c = ceil(curve(d_c)) seconds after T, kept if ≤ H; permanent; d_c = 0 → closed at T.
* **Primary configuration (fixed now, as in kcf-roadcut): MEASURED arm, 8 h horizon, delay 60 min.** Every other arm,
  horizon and delay is computed and reported with the same tables; the primary only fixes which ranking the pages lead
  with.

## 2 Window of a village

Window W(v) = measure, in seconds, of the union over v's 3 planner shelters of the F-3.1 issue sets (`core.issue_set`)
within [0, H], under the given closures. Reported in minutes. "Village" below means any of the 174 places.

### 2.1 Fast exact solver, and the gate it must pass

With permanent closures every issue set and every edge-state set R[s] is a prefix [0, L] of [0, H] (proof sketch: the
acceptance sets are prefixes; pre-image under an edge maps a prefix to a prefix; subtracting a suffix block [lo, H]
keeps a prefix; unions of prefixes are prefixes; waiting only extends downward). The field then reduces to one integer
per edge state, computed by a bottleneck (max–min) label-setting pass per shelter:
g_j = max(R_j, a_j) with a_j the acceptance top of edge j; for every allowed predecessor s of j (forbidden turns
respected), candidate = min(g_j − D_j, lo_j − 1) where lo_j is the edge's block start (∞ if unblocked); R_s = max over
candidates ≥ 0. The issue value at origin o = min(max over out-edges j of min(g_j − D_j, lo_j − 1), b_o − 1); window =
value + 1 seconds, or 0 if value < 0. Block starts, acceptance and the origin's issue block are computed exactly as in
`replay.Region.instance`, `.accept` and `run_one`.

**Gate (before any delay is evaluated):**
1. For all 27,144 rows of `per_place.csv` (6 arms × 2 horizons × 13 hours × 174 places), the fast solver's latest
   departure, shelter and arrival-free state must equal the committed values at the committed resolution (minute text
   of `latest_safe_departure_kst` / `last_departure_in_horizon_kst`, `departure_state`, `shelter_id`; ties between
   shelters broken as `replay.run_one` does: first shelter in its iteration order with a strictly larger value).
2. Exact (second) equality of the full issue sets against `core.backward` + `core.issue_set` on: 4 base jobs (each
   region × {MEASURED 8 h at 19:00 KST, WORST 5 h at 15:00 KST}, all places) and 40 delayed instances drawn with a fixed
   seed (`random.Random(20261118)`) from the candidates of §3 (20 road, 20 front; random region, arm, horizon, hour,
   delay).
If the gate fails and cannot be explained by a stated tie rule, the fast solver is not used: delays are evaluated with
`core.backward` itself for the primary configuration only, and the reduced scope is stated.

**Exact pruning (allowed, not an approximation).** A shelter's field is recomputed for a delay only if some changed
cell is that shelter's own cell, or contains a segment of an edge j that is binding in the undelayed field
(lo_j − 1 < g_j − D_j, with the changed cell attaining lo_j). Otherwise every min() in the pass is unchanged and the
field is identical. A village's window is recomputed if one of its shelters' fields changed or its own cell changed.

## 3 Candidates and delays

Delays Δ ∈ {30, 60, 120} min. A delay only ever postpones closures; a cell already inside the known fire area at T
(d = 0) is **never** changed (fire already there is not "delayed").

**ROAD candidate** (the model's unit of road is the 375 m routing cell): every cell c that contains at least one road
edge segment and has 0 < b_c ≤ H. Delay: b_c → b_c + 60Δ (dropped if > H: not closed within the horizon). Everything in
that cell is delayed (edges, node, a shelter or village entry in it). Location given as cell centre (lat/lon), the
nearest planner place, the OSM ways of its edges and, where the join works, the Overture 2026-10-21.0 road refs/names
of those ways (as in kcf-roadcut amendment 2(b)).

**FRONT candidate** (a section of fire front): the known-fire discs at T grouped by the 2 km × 2 km tile (EPSG:5179,
floor(x/2000), floor(y/2000)) containing the disc centre. Holding section S for Δ: for every cell with d_c > 0,
b_c = ceil(min(curve(d_c^¬S), 60Δ + curve(d_c^S))) where d^S and d^¬S are the distances to the discs in / not in S
(kept if ≤ H). Candidates: tiles whose discs are the nearest disc of at least one cell with 0 < b_c ≤ H. Location: tile
centre (lat/lon), nearest planner place, number of discs.

The class of MEASURED / gust arms is not changed by a delay (it is fixed per T, H from the undelayed inputs).

## 4 Benefit and ranking

Per candidate k, delay Δ, configuration (arm, H) and issue hour T:
* gain_v = W_k,Δ(v) − W(v) ≥ 0 (minutes) for every village v of the candidate's region;
* **benefit B = Σ_v pop_v · gain_v (person-minutes)** — the ranking quantity;
* also: unweighted Σ_v gain_v (village-minutes), villages helped = #{v : gain_v > 0}, and the list of helped villages
  with their gain.
Ranking: per (configuration, T, Δ), all candidates of both regions in one list, by B descending; ties by unweighted
minutes, then villages helped, then candidate id. Candidates with B = 0 and no village helped are not ranked.
Top ten per issue hour is reported for the primary configuration at Δ = 60 with its Δ = 30 and Δ = 120 values beside it,
and the Δ = 30 and Δ = 120 top tens are also given (overlap with the Δ = 60 list stated).

By construction: a village INSIDE the known fire area at T cannot gain (its cell is never delayed); a village whose
window already runs to the horizon cap cannot gain; gains are truncated by the horizon H. Stated on every page.

## 5 Population

Meta / CIESIN High Resolution Settlement Layer, `hrsl_general` (1 arc-second, AWS open bucket `dataforgood-fb-data`,
`hrsl-cogs/hrsl_general/hrsl_general-latest.vrt`; the version it resolves to and the retrieval time are recorded).
Every raster pixel within 2 km (haversine, pixel centre) of at least one of the 174 places is assigned to the nearest
place (Voronoi; ties to the lower place id); pop_v = sum of its pixels. Care facilities are places like any other and
take their Voronoi share. This is a modelled residential estimate, not who was present on 25 March 2025; a place with
pop_v = 0 still counts in the unweighted measures. If the raster cannot be read, B is replaced by the unweighted sum
and this is stated (no other source is substituted).

## 6 Stability across arms

For each issue hour, with Δ = 60 and H = 8 h: the top-ten overlap |top10(primary) ∩ top10(arm)| for each of the other
five arms, and the rank in every arm of each primary top-ten candidate (absent = not ranked). The same for MEASURED 5 h
vs 8 h, and for unweighted vs weighted ranking (primary). Summary over hours: median and range of the overlap per arm.
A candidate is called **stable** at an hour if it is in the top ten of the primary and of at least 4 of the 5 other arms
(8 h, Δ = 60). No other stability claim is made.

## 7 Outputs

* `pages/HH00_KST.ko.md` and `pages/HH00_KST.en.md`: **one page per issue hour in Korean and in English** (13 × 2),
  same content: issue time, configuration, known fire state (discs, villages INSIDE / cut / not cut), top-ten table
  (rank, type, location, Δ30/Δ60/Δ120 person-minutes and village-minutes, villages helped with names and minutes),
  stability line, the "not modelled" box (§8) and the disclaimer. A printable PDF of the 26 pages if time allows.
* `RESULTS.md` (summary, gate result, stability, prior work comparison), `numbers.json`, `ranking.csv.gz` (every ranked
  candidate × configuration × hour × Δ), `population.csv`, `PRIOR_WORK.md`, code.

## 8 What is not modelled (printed on every page)

* Whether a crew, engine or aircraft **can reach** the location in time, **hold** it, or for how long; access roads, terrain,
  water, line construction rates. A delay is simply imposed.
* **Aircraft** limits: availability, turnaround, wind and visibility limits, night operations (most of 25 March evening
  is night), the national helicopter fleet's commitments elsewhere.
* **Crew safety**: escape routes, safety zones, entrapment risk at the held point. A location ranked high here may be
  one no crew should be sent to.
* Fire behaviour: the delay is a uniform postponement of the arm's distance-based closure curve; spotting, fire going
  around a held section, re-ignition after the hold, and the effect of a hold on any other part of the fire are not
  modelled. Only one location is held at a time (no combinations, no resource constraint).
* Evacuation itself: traffic, congestion, warning delivery, who has already left; population is a residential estimate.
* The arms' closure curves, the known fire area and the deadline field carry every limit stated in kcf-replay and
  kcf-roadcut.
* **No claim is made that any action would have changed any outcome**, nor about what any official or crew should have
  done.

## 9 Prior work

Before results are written, a search for prior work on placing suppression to protect evacuation, starting with Harris,
Forbes and Taimre, "Logic-Based Benders Decomposition for Wildfire Suppression". `PRIOR_WORK.md` records each source
(citation, URL, retrieval time UTC, whether the full text or only the abstract/snippet was read) and states how this
study differs. The search does not change §1–§8.

## Amendments

1. **2026-11-18 ~15:50 UTC, before any delay was evaluated and before the gate was run.** A FRONT tile (§3) is defined on
   the known-fire discs, which are shared by both region grids. A tile is therefore **one candidate across both
   regions**: its benefit, village-minutes and villages helped are summed over the villages of both regions (cells of
   both grids are delayed together). ROAD candidates belong to one region. In §3 "cells with 0 < b_c ≤ H" and "d_c > 0"
   both apply to ROAD candidates (under WORST, cells within 3 km of the known area have d_c > 0 but b_c = 0 and are not
   ROAD candidates; a FRONT hold still delays them, as §3 says).
2. **2026-11-18 ~16:40 UTC, after the gate (§2.1) passed and before any production delay run.** Gate result: part 1, all
   27,144 rows equal on latest departure (minute) and shelter; 9 rows differ only on the CUT / NOT_CUT label, because
   the replay labels by a greedy (not earliest) witness arrival while the fast solver compares with the exact fire-free
   value. Window gains do not use that label (`gate1.json`). Part 2, 0 mismatching places in the 4 base jobs (348
   place-rows, exact seconds) and in 32 delayed instances (8 of the 40 draws had no candidate of the drawn kind and were
   skipped); pruned = unpruned in all 32 (`gate2.json`). Only 3 of the 32 had any gain (8 gaining places), so one
   **extra check** is added (no method change): after the production run, for the primary configuration and Δ = 60,
   the rank-1 candidate of every issue hour that has one is re-evaluated with `core.backward` for every gaining place,
   and the gains must be equal to the second. Results reported in RESULTS.md.
