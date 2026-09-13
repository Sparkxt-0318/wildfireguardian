# Report back on the truck-crew replay brief

Laptop session, 2026-09-13, `auto/dev` (harness paused). Brief:
`docs/auto/briefs/TRUCK_CREW_REPLAY.md`. Rule page: `docs/truck_crew_replay.md`.
Work commit: `c7f2f06`. **The gates are RED at that commit and the work is therefore
parked on `auto/red/…` under CHARTER §3.9, not on `auto/dev`.** The red is not this
build's; §5 below, and NH-061.

## 1. What was built

All four deliverables exist, in the order the brief set.

1. **`docs/truck_crew_replay.md` §1 to §3b, written before anything ran.** It declares the
   population (§1), the scheduler, the deadline, the corridor closing minute, the margin,
   the **abort rule** and the fallback corridor (§2), the observed grading rule and the
   four counts the finals may quote (§3), and what the screen does not show (§3b). §4 is
   appended by the run and §5 is the reading written after it.
2. **`scripts/build_truck_crew_replay.py`** → `data/processed/truck_crew_replay_yeongdeok.json`
   (1.46 MiB). It **imports** and does not re-implement: `schedule` from
   `run_vehicle_pickup_intervention.py`, `build_scenario` from
   `run_rescue_routing_real_hazard.py`, `materialise_snapshots`, `rescuer_route`,
   `ingress_corridor`, `assess_destinations`, `node_survival_time`,
   `corridor_survival_time`, `sample_corridor_points`, `round_trip_margin`,
   `_immobile_homes`, and `classify_route` / `first_seen_grid` from `regrade_three_way.py`.
   A test asserts that list and asserts the script defines none of them.
3. **`web/truck_crew_replay.html`** (768 KiB), built from
   `scripts/truck_crew_replay.template.html` by the same script: one file, no external
   asset, opens from `file://`. Clock slider 0 to 720 min with the 5 h and 8 h doctrine
   markers, an SVG map drawn from the EPSG:5179 geometry with no tiles (roads, forecast
   cutoff cells, observed FIRMS cells, depots, refuges, pickups, the selected vehicle's
   ingress and egress legs), the per-trip card with the abort minute in bold, the four
   crew buttons writing local timestamps into `localStorage`, a one-page A4 print view and
   GeoJSON/KML download. The same geometry is also written to
   `outputs/truck_crew_replay/20260913T160454Z/` (24 files, WGS84) because a sandboxed
   viewer cannot save the file the page offers.
4. **`tests/test_truck_crew_replay.py`**, 15 guards, all passing: every headline count
   re-derives from the trip rows it summarises; the four counts partition the ordered
   trips; the population counts re-derive from the pickup rows and every pickup is a
   distinct drive node; the success line contains the three measured numbers and no other
   digits; **every trip's abort minute is `closing − 12`**; a trip arriving after it is
   flagged aborted and never counted reached; the deadline and the 720-minute clock bound
   every arrival; a fallback corridor is always from a different depot road node; the page
   passes the repository's own offline and dash gates; the payload strings carry no banned
   dash (the gate's own recorded blind spot); the page is the template with the payload
   substituted; the rule sections precede the results; and **the printed vehicle sheet is
   one A4 page**, measured with headless Chromium for the page as it loads and for the
   busiest vehicle (15 trips), skipped with a reason where no Chromium exists rather than
   passing by default.

## 2. The measured counts, and the brief's success line

Population: the 주건물 population's **1,530 rescue-needing walk nodes** (54 no-safe-walk
class + 1,491 from the pipeline's own immobile draw at fraction 0.3, seed 20250603,
overlapping) out of 4,970 building walk nodes. They snap onto **774 pickups** (road
points) carrying **5,865 buildings**. 756 walk nodes share a pickup with another.

| fleet | trips ordered | reached before observed closure | not reached | aborted by rule | ingress leg inadmissible (m = 0) | buildings behind ordered trips |
|---|---:|---:|---:|---:|---:|---:|
| 2 | 26 | 21 | 3 | 2 | 12 | 286 |
| **4** | **52** | **42** | **7** | **3** | **30** | **504** |
| 6 | 74 | 60 | 6 | 8 | 33 | 673 |

**The brief's success line, filled (k = 4):**

「2025년 3월 25일 영덕 실제 화재에서, 이 화면이 4대의 차량에 내린 **52**건의 출동 지시 중
**42**건은 위성이 관측한 화선이 도달하기 전에 도착했고, **3**건은 이 화면이 스스로 중단
규칙으로 취소했다.」

⚠ **That sentence must not travel alone.** In the same run, **30 of those 52 trips drove an
ingress corridor that the same observation puts inside the footprint at the minute the
vehicle was in it**, and 20 of the 42 「reached」 trips are among them. 「Reached」 is a
statement about the pickup's own 500 m cell and says nothing about the road taken to it.
The rule page makes the pairing binding (§3 and §5) and the screen prints both counts side
by side with a sentence saying so.

## 3. What did not work, or worked less well than the brief expected

- **The abort rule is nearly inert on this scene, and where it fires it is mostly
  diagnosing a trip that should never have been ordered.** Across all three fleets 13
  trips are aborted; **12 of them have an ingress corridor whose forecast closing minute is
  0**, so the abort minute is −12 and the rule is really saying 「this was never feasible」.
  Exactly **one** trip (k = 6) aborts the way the rule was written for: corridor closes at
  180, abort minute 168, arrival 200.6. The cause is a sampling mismatch that the
  repository already knows about in another place (`docs/oracle_gap.md`): the closing
  minute is sampled along the driven line at 150 m through the interpolating hazard, while
  the router that planned the trip tests cell membership at route **nodes**, so the finer
  sampling catches edge interiors the router never looked at.
- **The forecast's time resolution is coarser than the rule is written in.** `haz_stack`
  has five slices (0/180/360/540/720 min), so every finite closing minute in this run is 0
  or 180 and every abort minute is −12 or 168. 「Closing − 12」 reads like a measured minute
  and is a slice boundary minus a constant. This is stated on the page and in §5.
- **The miss allowance does no work inside the replay window.** Only two of the six
  observation times (0 and 333 min) fall inside 720 min, so m = 0, 1 and ∞ give identical
  class counts for every leg. The three-way grading discriminates over a walk window and
  not over a truck shift.
- **The four OSM depots snap to two distinct drive nodes.** A fallback corridor from a
  different depot road node therefore exists for only **17 of the 52** trips, and at k = 2
  both vehicles start at the same node. The brief's 「k = 4, one per OSM depot」 is true of
  the depots and not of the road graph.
- **Coverage is small and the binding constraint is the clock.** 4 vehicles serve 52 of 774
  pickups inside 720 min; 722 are never reached. Nothing saturates (26 → 52 → 74 trips for
  2 → 4 → 6 vehicles), so this is a pure throughput limit, not an access limit. That is the
  opposite of `docs/vehicle_pickup_intervention.md`'s result on the 24 credible failures,
  and the two are consistent: that population was tiny and unreachable, this one is large
  and reachable.
- **Two trips deliver to a refuge that snaps to the pickup's own road node** (zero-minute
  egress) and **two deliveries complete after minute 720**, because the deadline binds the
  arrival, not the round trip. Both are counted and printed rather than hidden.
- **Seven of the 52 ordered trips have a median walk-to-road snap of 300 m or more, one of
  them 1.8 km.** For those,「the vehicle arrived」 means it reached a road that far from the
  buildings the pickup counts.
- **Two things the brief asked for that I read narrowly, and say so.** The brief's fleet
  list is 「k = 4; also k = 2, 6」 and that is what ran; dispatch delay was left at the
  config's 30 min and not swept. And `round_trip_margin` is reported **depot-anchored under
  the `same_route` doctrine**, beside the trip margin, rather than recomputed for the
  vehicle's mid-shift position, because the function's ETA includes the dispatch delay and
  would be wrong for a vehicle already out.

## 4. Two defects found in inputs, neither of them repaired here

- **`scripts/run_vehicle_pickup_intervention.py::schedule` keys its per-home outcome by
  drive node while dispatching per walk node.** In the committed
  `data/processed/vehicle_pickup_intervention_yeongdeok.json`, the 24 credible walk nodes
  collapse to **12 distinct drive nodes** (one of them repeated six times), so `per_home`
  has 12 entries, a vehicle is sent to the same road point up to six times in one run
  (visible in `runs.D30_k4.vehicle_logs`), and 「9 of 24 nodes completed」 means 「walk nodes
  whose drive node was completed」. This build sidesteps it by declaring the pickup to be
  the drive node (§1) so the population it hands the scheduler has no repeats. **The
  committed artifact and its document were not touched.** Whether the published 9/24 and
  40/74 need a footnote is HQ's call.
- **The same scheduler advances a vehicle's clock for a pickup it reaches and cannot
  safely leave** (`unsafe_egress`): it charges the loading time, leaves the vehicle at its
  **previous** location, and writes no log entry. Reconstructing trips from the log alone
  therefore runs on a clock the scheduler never had; this build recovers those events from
  the per-home outcome and replays them in arrival order, and every reconstructed minute is
  checked against the scheduler's own recorded minute (the build stops if one disagrees).
  One such event occurs at k = 2.

## 5. The gates, and why this is on `auto/red/…`

`python scripts/auto/gates.py --mode full` at `c7f2f06`: **exit 1**. `verify`,
`snapshot-verify` and `env-check` pass; `baseline-verify` is the documented soft warning
(the git-ignored FIRMS acquisition manifest exists only on the author's laptop). The single
hard failure is
`tests/test_finals_payload_rederives.py::test_every_value_the_screen_displays_is_what_the_builder_derives_today`,
with 2,318 passed / 1 failed (the baseline before this work was 2,303 passed / **the same
1 failed**; the 15 new tests are the difference).

**That failure was already there.** The same gate run was made on the clean tree at
`bb820d6` before a line of this work was written, and failed identically. Its three
differing values are the `hill.png` hillshades for the three regions. **Decoding both the
shipped and the rebuilt PNGs and comparing pixels: maximum per-channel difference 0, mean
0.0000, for all three.** The images are identical; only the PNG encoder's bytes differ.
Two rebuilds in this container are byte-identical to each other, so the encoder is
deterministic per machine and the difference is between machines.

The repair the test names is `make finals && make finals-bundle UPDATE=1`, which rewrites
`web/finals.html` — forbidden by this brief and by CHARTER §3.2 — and would only move the
failure to the author's machine. So under **CHARTER §3.9** the work is parked on
`auto/red/2026-09-13T1625Z` with this report and **NH-061**, which carries the measurement
and four options. `auto/dev` was not pushed.

## 6. Open questions for the HQ session

1. **Does the corridor count go on a judge-facing surface with the success line, or does
   neither go?** 30 of 52 is the honest number and it is not flattering. My reading is that
   the pair is stronger than the 42 alone, because it is the only place in this repository
   where the system grades its own dispatch orders against what burned. HQ decides.
2. **The abort rule needs a second version to be worth demonstrating.** As declared it
   fires on already-cut corridors, not on corridors closing during a mission. The two
   candidate repairs are to define the closing minute on the vehicle's own passage time
   rather than the corridor's earliest crossing anywhere, or to keep it and rename it
   「feasibility check」. Both change §2, so neither is a lap's call.
3. **Is the immobile draw the right population for a truck-crew screen at all?** 0.3 of
   4,970 building nodes is 1,491 nodes and it dominates everything: 774 of the 774 pickups
   come mostly from it, and the 54 no-safe-walk nodes are a rounding error inside it. A
   screen built on the no-safe-walk class alone would be much smaller and much more
   defensible, and would say something different.
4. **Do the two `run_vehicle_pickup_intervention` defects in §4 need anything?** The
   committed numbers are what they are; a footnote on `docs/vehicle_pickup_intervention.md`
   §4 would be additive and is not this session's to write.
5. **NH-061.** Until that is answered, every non-author session that runs the full gates
   will park its work on a red branch.
6. **Nothing here is registered and nothing is judge-facing.** `docs/NUMBERS.json`, the
   README, `web/finals.html`, `docs/auto/JUDGE_QA.md` and the printed kit are untouched.
   If any of these numbers is to be quoted at the booth it needs a registrar entry, which
   this session did not create.
