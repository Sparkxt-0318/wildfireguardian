# kcf-reopen: a road cell closed for a window, not forever

**Model output on inputs rebuilt from public observations and on reconstructions, scored against other observations.
Not what happened to people. No claim about what any responder or official should have done.**

Rules frozen first: [PROTOCOL.md](PROTOCOL.md) (commit `cbf460ae`, before any reopening number), amendment 1 logged
during the run. **Not a first look:** the Camp Fire workbook, its 195 blocked-road and 23 passable reports, the 23
burnovers and the two movements were all scored in `research/kcf-camp`, and its results were read before this protocol.
Every table below is generated from `out/` by `make_tables.py`; `make_results.py` inserts them here.

## Answer

1. **The window rule does what it was built for, and fails its own guard.** With a burn-out time of **τ = 240 min**
   (frozen from the Camp workbook: the 80th percentile of how long road cells were still reported blocked after fire was
   first seen there, 75 cells), the passable reports closed by the no-margin rule drop from 2 to **0 of 23**, and the
   vehicle-present observations closed from 210 to **132 of 429**. But **16 of the 195 blocked-road reports fall in a
   cell the rule had already reopened** (no margin: hits 37 → 21; spread margin: 170 → 154). At τ = 465 min it is still
   4; at τ = 105 it is 30. The guard was "no loss", so it **fails at every τ** for responders.
2. **Neither documented movement becomes feasible at the frozen τ**, with or without margin. Under τ = 240 the
   documented roads open again only at **15:39** for the Fire Station 82 convoy (left at 12:00) and **17:21** for the
   Firland Dr engines (left at 13:58): the crews drove 3½ h before the rule would have let them. Only τ = 105 makes the
   engines' trip feasible, by a route that is 9 % on Skyway: **FAIL** for both movements at every τ.
3. **With the spread margin, reopening barely changes the passable reports (22 → 20 of 23 closed)**, because the margin
   closes cells nobody reported burning, and a cell with no observed arrival never reopens.
4. **Burnovers:** with the spread margin no burnover is lost at any τ. Without margin the two 9 November burnovers
   (BO 16 Coutolenc Rd, BO 19 Concow Fire Station 37) are lost at every τ: fire was reported in those cells on
   8 November and they burned over again the next morning, more than 465 min later.
5. **Residents' rule (window only where a report confirms it) passes every guard and changes almost nothing**: with
   the held-out confirmations, no passable report and 14 of 429 vehicle observations change state.
6. **Korea:** the model's reopening of an expressway section (latest fire on the section + τ) falls between **69 h
   before and 40 h after** traffic came back (table 5). Read as the model's closed spell at the moment of each official
   closure, it was closed in 7 of 13 events and its spell ended **12–69 h before** traffic returned in 5 of them (3.6 h
   after in 2); in the other 6 the model had the section open when it was closed. 중앙선 의성~예천 stayed without traffic
   until 28 March, three days after the fire passed it. Expressway reopening followed an official decision that waited
   for the whole fire, not the burn-out of the road cells.
7. **Steps 6–7** <<STEP67_ANSWER>>
8. **Product:** the rule is in `product/wfg-roadlayer` as `--reopen` (off by default; `responders` or `confirmed`),
   with a verifier that re-derives the windowed masks and recomputes every departure set from equation (E); with
   reopening on, the 84 Uiseong–Andong certificates <<YD_CERTS>> pass, and a certificate claiming one extra second fails.

## Step 1: burn-out time

Candidates, each with its source:

| candidate | value | source | what it measures |
|---|---|---|---|
| Wotton et al. 2012 | 37 s main front (+37–74 s continuous, +75–127 s intermittent) | `flame_residence_literature.md` §2 | flaming at a point, dry eucalypt |
| Anderson 1969 | 8 min per inch of diameter: 1-h fuel ≈ 2 min, 10-h ≤ 8 min, 100-h 8–24 min | same | flaming of a passing front, point |
| Burrows 1994 | 0.871 d^1.875 s; 16 mm: 159 s | same | one round-wood particle |
| Andrews 2018 | 384/σ min | same | Rothermel residence time |
| kcf-radiation A7 | **none** (no residence time; burned-out cells keep radiating), i.e. τ = ∞ | `research/kcf-radiation/PROTOCOL.md` A7 | the current product |
| Camp Fire, this study | **240 min** (low 105, high 465) | table below | a 375 m road cell staying blocked |

The literature values are flaming times at a point and are two orders of magnitude shorter than what a road cell
shows; they do not cover burning structures, vehicles, trees or lines. A7 deliberately uses none.

<<T:Step 1>>

Reading: 429 of the 439 vehicle-located rows were placed on a road cell. Firefighter vehicles were back in a cell a
median 81 min after fire was first seen there, and after the last blocked report a median 125 min (37 cells). Blocked
reports, by the rule frozen in advance, set τ; the vehicle gaps were not used because crews drove through active fire
(kcf-camp: 19 of 23 passable reports describe fire on the road).

## Step 2: the rule

Closed from the margin-adjusted closure C until R = max(C, A + τ); A = the cell's own first fire observation. Three
states: open, closed by fire, burned over (PROTOCOL §1). Burned over is usable by responders; for residents only when a
report or a vehicle-unit `REOPENED` event confirms it after A + τ. A cell with no observed arrival never reopens.

## Step 3: routing with reopening

* **6,000 random instances**, 4,195 with a reopening inside the horizon, built by the product's windowed builder: the
  edge, wait, shelter and origin masks equal a second-by-second brute force of PROTOCOL §1.2 in every case; with no
  reopening the builder equals the unchanged product rule; `core.issue_set` equals the brute-force `feasible_set` of
  `research/kcf-theorem/checker.py` for all 20,872 origins (1,169 of them with a gap between windows), and all **16,273**
  witnesses pass `check_route`. **0 failures** (`results/routing_property.json`, `test_reopen_routing.py`).
* Camp graph: all 36 witnesses of Test 4.1 pass `check_route`.
* Product certificates: see point 8 of the answer. The verifier now handles windows by its own interval fixed point of
  equation (E) (THEOREM.md §2), not by Theorem 2, which needs permanent closures.
* **A modelling artifact found here:** the road graphs have no waitable nodes, so the only way to wait for a road or a
  shelter to reopen is to keep driving. With reopening the field counts such looping journeys as feasible (correctly,
  under the model), and the earliest-arrival witness search can then take hours of (edge, second) states. The engine
  now caps that search (`engine.witness_for`) and falls back to the field's greedy witness, which is valid but not
  necessarily earliest. Camp τ = 105 routes show the loops (Buschmann Rd / Del Monte Ave repeated). Permanent-closure
  runs never reach the cap: every golden output is byte-identical.

## Step 4: Camp Fire tests

Graph rebuilt from Overpass on 21 November 2026 (amendment 1): 2,114 road cells against kcf-camp's 2,121; kcf-camp's
permanent rule on it reproduces every road-state and burnover state of kcf-camp exactly (`out/camp_baseline/`).

<<T:Test 4.1>>

Post hoc (`out/camp_test41_route_cells_posthoc.json`): on the fire-free fastest route, the cells closed at the issue time
reopen under τ = 240 between 14:00 and 15:39 for (a) and between 14:00 and 17:21 for (b), with or without margin.

<<T:Test 4.2a>>

<<T:Test 4.2b>>

<<T:Test 4.3a>>

<<T:Test 4.3b>>

**Which tests failed (frozen τ = 240):**

| test | no margin | spread margin |
|---|---|---|
| 4.1 convoy (a) | FAIL (infeasible) | FAIL (infeasible) |
| 4.1 engines (b) | FAIL (infeasible) | FAIL (infeasible) |
| 4.2 passable reports | PASS (0 of 23 closed) | FAIL (20 of 23) |
| 4.2 vehicle-present | FAIL (132 of 429 closed, 31 %) | FAIL (299 of 429, 70 %) |
| 4.3 blocked reports (no loss) | FAIL (16 reopened too early) | FAIL (16) |
| 4.3 burnovers (no loss) | FAIL (BO 16, 19 lost) | PASS |

Residents' rule (confirmed only): passes both guards, fails 4.1 and the vehicle test, passable as permanent.

## Step 5: Korea, the only reopening evidence

<<T:Step 5>>

Reading. Only 13 section-events exist, all on 22–26 March 2025, and the traffic return of a section is the median over
1–7 conzone-directions (none for the 22 March 20:38 closure). **Primary (pre-registered):** the model's reopening comes
after traffic returned for the 23–25 March 서산영덕선 closures (+3.6 to +40 h) and 중앙선 의성~남안동 (+14 h): traffic
was back while satellites still detected fire somewhere along the section. It comes before for 중앙선 의성~예천/풍기
(−69 h) and the 26 March closures (−17 to −69 h). **Secondary (amendment 1, after seeing the primary):** the model's
closed spell covering each official closure time; closed in 7 events, ending 12–69 h before traffic returned in 5 and
3.6 h after in 2; open in 6 (the model had no fire on the section within τ of the official closure). Choi's
reconstruction (kriging SD about 17 h) moves every model reopening 7.5–27 h later and changes the sign of none of the
primary differences. The model's τ is a burn-out time; the official reopening was a decision.

## Steps 6 and 7: margin field, kcf-robust, the Gyeongbuk replay

<<STEP67>>

## Limits

* **Not modelled:** fallen trees, downed power lines, smoke, burning buildings and vehicles behind the front,
  re-ignition (the 9 November burnovers are cells that burned again), debris clearance, official inspection.
* **The reopening sample is small.** τ rests on 75 Camp road cells; the passable reports are 23; Korea has 13
  section-events on two routes. τ is estimated and scored on the same Camp workbook (cross-fit halves give 225 and
  240 min and the same 16 early reopenings).
* **Firefighter vehicles are not residents.** The vehicle-present rows and both movements are apparatus that drove
  through conditions a resident should not; a vehicle in a "closed" cell does not show the cell was safe.
* **Waiting is not modelled as waiting.** Without waitable nodes, reopening makes "drive in loops until it reopens"
  feasible; the counts of later windows include such journeys (step 7 reports how many).
* The twin truth burns out after the same τ by construction; the replay truth is the detection record.
* Present-day OSM roads stand in for 2018 (Paradise) and 2025 snapshots (Korea).

## Reproduce

```
python3 -I estimate_tau.py _work/graph.json out
python3 -m unittest research/kcf-reopen/test_reopen_routing.py
python3 -I camp_tests.py _work/graph.json out
python3 korea_reopen.py _work/kr/osm_expressways.json out
python3 robust_window.py replay out && python3 robust_window.py twin _work/twin out && python3 robust_window.py score out
python3 -I make_tables.py > out/tables.md && python3 -I make_results.py
```

`_work/` (not committed): the four Overpass tiles and graph (SHA-256 in `out/camp_osm_sha256.txt`), the expressway
extract (SHA-256 in `out/korea_reopen.json`), and the twin folder from `research/kcf-validate/twin/run_twin.py make`.
The product tests: `python3 -m pytest product/wfg-roadlayer/tests` (needs POSIX semaphores for worker processes).
