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

### 5b. What GitHub said after the parking push, which is worse than the above

The push triggered `auto-gates` on the red branch, and reading its result turned this from
「a sandbox disagrees with the laptop」 into something the author needs to know:

- **This PR's run** (34768396034, `0212790`): `verify`, `snapshot-verify`, `env-check` pass,
  `baseline-verify` warns as designed, `pytest-full` **fails** with `1 failed, 2320 passed,
  63 skipped` — the same single test and the **same three** `hill.png` values.
- **The base branch is red too.** Run 425 on `auto/dev` at `bb820d6` failed with the same
  test and the same three values, which is the 「red on the base branch too」 case: this
  failure is established as not this PR's, not assumed to be.
- **`auto/dev` has been red on GitHub for five consecutive pushes** (runs 421 to 425:
  `30f9ec5`, `e96471c`, `0619826`, `2da2dd5`, `bb820d6`), and **every one of those commit
  messages says 「ALL GREEN on the laptop」**. The last green run is 417 at `3c3225e`
  (2026-09-12T16:18Z); runs 418 to 420 were cancelled by the workflow's own
  `cancel-in-progress`, so they carry no signal.
- **The commit that put it there is `7750d8f`**, the author's own laptop commit
  (`2026-09-13 01:10:15 +0800`) that says 「finals screen and bundle rebuilt」; its diff
  rewrites the `"hill"` entries in `web/finals.html`, and its CI run (420) was one of the
  cancelled ones, so the red first became visible one commit later.
- **`promote` declares `needs: gates`**, so no `auto/dev` push since run 417 has been able
  to promote `Main`.

So the split is not 「the author's laptop versus one sandbox」; it is 「the author's laptop
versus every other machine」, GitHub's own runner included, on three machines measured. All
of this is in NH-061. **No fix exists that this session is permitted to port**, and a re-run
would not help: the failure is deterministic and reproduced on two independent machines.

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
6. **Should this replay be re-run on the leak-free field?** `docs/leakfree_fold.md` landed on
   `auto/dev` while this branch was parked, and it measures a training leak in the very field
   this replay stands on: the leak-free 영덕 field is about half the size of the canonical one
   and under-predicts the fire's growth. Every deadline, closing minute and abort minute here
   is read off the canonical field. **It was not re-run** — the brief names the canonical
   field, and swapping it is not a lap's call — and §5 of `docs/truck_crew_replay.md` now says
   so rather than leaving the page quieter than the repository. The observed grading (the
   30-of-52 corridor count) is the part least exposed, for the same reason that page gives
   about its own numbers. If HQ wants the paired run, it is one flag on the build script and
   about eight minutes.
7. **Nothing here is registered and nothing is judge-facing.** `docs/NUMBERS.json`, the
   README, `web/finals.html`, `docs/auto/JUDGE_QA.md` and the printed kit are untouched.
   If any of these numbers is to be quoted at the booth it needs a registrar entry, which
   this session did not create.

---

# Addendum, 2026-09-14: HQ's six decisions carried out

`docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md` answered the six questions above. This
addendum records what was done and what it measured. Rules first: §6 of
`docs/truck_crew_replay.md` was written before the v2 run, §7 is the run's own output and
§8 the reading. New artifacts, new filenames; v1's are untouched.

| decision | done | where |
|---|---|---|
| 1 · success line not quotable, travels with the corridor count | respected; no line filled, nothing judge-facing | §7, §8 |
| 2 · abort rule v2 on the vehicle's own passage | built and run | §6a, §7, `scripts/build_truck_crew_replay_v2.py` |
| 3 · four populations, headline from the honest core | built and run | §6b, §7 |
| 4 · footnote the scheduler defects, fix under a new name, re-run | done | `docs/vehicle_pickup_intervention.md` §4 footnote, `schedule_fixed`, `..._fixed_yeongdeok.json` |
| 5 · one PR from the green head, then stop re-cutting | done | this PR |
| 6 · leak-free field as a sensitivity arm | built and run | §6c, §7 |

## What the decisions produced, including where they disappointed

- **Decision 2 did not achieve its purpose, and that is the headline of this addendum.**
  The rule is now a continuous minute derived from the vehicle's own passage, consistent
  with the router's own test, and it catches **8** genuine mid-mission aborts instead of
  about one. But across the 16 v2 runs, **81 of 89 aborts are still the 「never safe to
  depart」 class** the rule was rebuilt to get away from. The cause is the sampling
  mismatch `docs/oracle_gap.md` already names: the router tests cell membership at route
  nodes, the abort rule reads the interpolated field along the driven line at 150 m, and an
  edge interior between two admissible nodes can be over the cutoff from minute 0. Closing
  it means making the router and the rule sample the same way, which changes the router.
  **That is the next decision HQ has to make, and it is not a lap's call.**
- **Decision 3 changed the picture, downward.** On the honest core at *k* = 4 (canonical
  field): `core_credible` orders 6 trips, 4 reached, 2 aborted; `no_safe_walk` orders 21,
  8 reached, 1 not reached, **12 aborted**. v1's 52 / 42 came almost entirely from the 30 %
  draw. On the population this project can defend, more than half the orders are cancelled
  by the screen's own rule. The fleet sweep is flat (6 / 4 / 2 at k = 2, 4 and 6).
- **Decision 4 found the defects real and the published numbers safe.** `schedule_fixed`
  repairs both; re-run over all 12 fleet × dispatch combinations it returns **9 of 24 nodes
  and 40 of 74 buildings, identical to the committed table every time**. What moves is the
  trip count: **9 dispatched trips become 6**, because three were repeat visits to a road
  point already served. The footnote on `docs/vehicle_pickup_intervention.md` §4 is purely
  additive; no number there was changed.
- **Decision 6 is the reassuring one.** The leak-free field moves the immobile arm a lot
  (52 / 41 / 5 → 54 / 51 / 0 at k = 4) and the honest core almost not at all:
  `core_credible` is **identical** on both fields, `no_safe_walk` moves from 8 reached / 12
  aborted to 9 / 9. **The populations a finals sentence would be written from are the ones
  least sensitive to the training leak.** The canonical field stays the base, as instructed.

## Open questions for HQ, round two

1. **The abort rule's remaining 81-of-89.** Do you want the router and the abort rule to
   sample the same way (a change to `rescuer_route`'s admissibility test), or should the
   rule keep the finer sampling and be renamed so it stops claiming to be a mid-mission
   abort? Either is defensible; both change something this session may not change alone.
2. **`core_credible` orders six trips.** That may be too small to carry a finals sentence at
   all. If so, the honest answer at the booth may be the 21-trip `no_safe_walk` line with
   its 12 aborts, which is a harder story than the one the brief imagined.
3. **Nothing is registered.** Registration remains an HQ action.

## Addendum 2, same day: the benchmark changes how this page must be read

`docs/benchmark/results_v0.1.md` landed after the decisions above were carried out. Two of
its findings bear on this build and are now §9 of `docs/truck_crew_replay.md`:

1. **The committed field is hindcast-track** — `forward_simulate` uses ERA5 at times after
   T0 — so every 「forecast」 on the replay page is a **reconstruction**, and the screen is
   not evidence that a forecast was available at minute 0.
2. **On roads the field is almost entirely static.** Measured at the vehicle cutoff on the
   drive network (`scripts/measure_field_road_closure.py`): of 1,664 drive nodes, **37 are
   already at or above 0.7 at t = 0 and the canonical field adds only 9 later; the leak-free
   field adds 0.**

**Together these explain the v2 result rather than sitting beside it.** The 81-of-89
「never safe to depart」 aborts and the leak-free arm's zero aborts are the same fact: there
is almost no dynamic road closure in this field, so the abort rule has nothing to fire on
except minute-0 conditions. **Round-two open question 1 should be read in that light — a
third rebuild of the rule cannot fix a limit that lives in the field.** The useful next move
is probably a forecast-track entrant (the benchmark says one is buildable), not another
abort rule.

---

# §7. Round-two answers carried out, 2026-09-14 (dated append; nothing above is rewritten)

HQ's round-two answers. Rules first: §10 of `docs/truck_crew_replay.md` was pre-registered
before the line-sampled arm ran, §11 is its output, §12 the reading. `rescuer_route` is
unchanged; the abort rule keeps its v2 name and definition; no committed artifact was
modified and nothing was deleted.

## 7.1 Answer 1 — the line-sampled arm, and what it found

`rescue.rescuer_route_line_sampled` (new, beside the untouched `rescuer_route`) makes the
router's admissibility test read the same 150 m interpolated line the abort rule v2 reads:
an edge may be entered no later than `E_e = min_j (T_j − t_j)` over its sampled points. The
arm runs the identical scheduler and build path with the name `rescuer_route` **bound** to
the new function for the duration of the run; no module was edited.

**The finding: the aborts were the router's mistake, not the fire's.** At *k* = 4 on the
canonical field, `no_safe_walk` goes from **12 aborts to 1**, `core_credible` from 2 to 0,
`immobile_30pct` from 5 to 0. The committed router planned trips down lines it had not
looked at and the abort rule then cancelled them; when the two tests agree there is almost
nothing left to cancel. The price is that far fewer trips are ordered — `no_safe_walk` 21 →
11 — because the doomed ones are now never ordered. **「Reached before the observed closure」
barely moves: 8 → 9.** The trips the screen would have completed are the same trips.

The road network itself is the ceiling: of 4,638 directed edges, **94 ever close** on the
canonical field and **54** on the leak-free one, and **46 are already cut at t = 0 on both**.

## 7.2 Answer 2 — the finals sentence, drafted as a proposal

⚠ **2026-09-14, after this section was written:** HQ chose option (b) — the sentence is
written from the line-sampled arm. **§8 below supersedes this draft.** Nothing in this
section is edited; it is kept as the record of what was proposed first.

**⚠ NOT QUOTABLE.** HQ decision 1 says no sentence is quotable yet and this one is a draft
for HQ to accept, amend or reject. It is written from the 21-trip `no_safe_walk` line as
instructed, and it states the aborts and the corridor count in the same sentence.

> 「2025년 3월 25일 영덕 산불에서, 걸어 나갈 안전한 길이 없는 것으로 분류된 54개 지점(28개
> 도로 접점, 건물 190동)에 대해 이 화면이 차량 4대에 내린 출동 지시는 **21건**이었다. 그중
> **8건**은 위성이 관측한 화선이 승차 지점에 도달하기 전에 도착했고, **12건**은 이 화면이
> 스스로 중단 규칙으로 취소했으며, 같은 21건 가운데 **12건**의 진입로는 관측상 이미 화선
> 안에 있었다. 이 경로들을 계획한 확산면은 발화 이후 실제로 관측된 기상으로 다시 만든 사후
> 재구성(hindcast)이다.」
>
> EN: 「On the 2025-03-25 영덕 fire, for the 54 points classified as having no safe walk-out
> (28 road pickups, 190 buildings), this screen issued **21** dispatch orders to four
> vehicles. **8** arrived before the satellite-observed fire line reached the pickup, **12**
> were cancelled by the screen's own abort rule, and **12** of those same 21 drove an ingress
> corridor the observation places inside the footprint. The spread field these routes were
> planned on is a hindcast, reconstructed with the weather that actually occurred after
> ignition.」

Every number traces to `data/processed/truck_crew_replay_v2_yeongdeok.json`:

| number | artifact key |
|---:|---|
| 54 | `populations["canonical.no_safe_walk"].rescue_needing_walk_nodes` |
| 28 | `populations["canonical.no_safe_walk"].pickups` |
| 190 | `populations["canonical.no_safe_walk"].buildings_behind_pickups` |
| 4 | `runs["canonical.no_safe_walk.k4"].vehicles` |
| 21 | `runs["canonical.no_safe_walk.k4"].v2.trips_ordered` |
| 8 | `runs["canonical.no_safe_walk.k4"].v2.reached_before_observed_closure` |
| 12 (aborted) | `runs["canonical.no_safe_walk.k4"].v2.aborted_by_rule` |
| 12 (corridors) | `runs["canonical.no_safe_walk.k4"].v2.trips_with_an_inadmissible_ingress_leg_m0` |

The two 12s are different quantities that happen to coincide at this setting; a reader will
assume they are the same number, so **if this sentence is ever used, one of them should be
re-expressed** (for example the corridor count as 「21건 중 12건」 spelled differently, or the
abort count moved to a second sentence). Flagging it rather than silently reusing the digit.

The hindcast clause is `docs/auto/briefs/HINDCAST_CORRECTION.md` A2's wording, shortened;
the full sentence there is the one for judge surfaces, which this build does not touch.

## 7.3 What a reviewer should attack

1. **The binding trick.** The line-sampled arm swaps `rescuer_route` by rebinding the name in
   three modules. If any caller resolves the symbol differently, the arm silently ran the old
   router. Check `arm.how_run` in the artifact and re-derive one route by hand.
2. **`E_e` is a single number per edge.** That is only correct because the field is monotone
   in time. If a future field is not monotone, `edge_line_closing_minutes` is wrong and will
   fail silently. It is checked for these two fields and nowhere else.
3. **Dijkstra optimality under the time window.** Arriving earlier is never worse *given
   monotonicity*; that is the whole argument for using plain Dijkstra. Attack the argument,
   not the code.
4. **The two 12s** in §7.2, above.
5. **`core_credible` is six trips and four under the honest router.** Any sentence built on
   it would be noise; the report says so, but a reviewer should check nothing downstream
   quietly uses it.
6. **The abort rule was not re-derived for this arm** — it is v2, unchanged, applied to new
   routes. That is what HQ asked for, and it means the arm's abort counts are not a test of
   the abort rule.
7. **Everything still rests on one fire, one observation, and a hindcast field.**

## 7.4 Gates and which run was read

`python scripts/auto/gates.py --mode full` was run in the foreground on the commit that is
pushed, its exit code read, and `--assert-head` run before the push. **GitHub's own
`auto-gates` run on the PR head was then read** (CHARTER §4b, and the lesson of NH-061 that a
laptop-green tree can be red on the runner). Both results are stated in the PR comment that
accompanies this push.

# §8. The finals sentence rewritten under HQ's option (b), 2026-09-14 (dated append; §7 is not rewritten)

HQ's round-two decision block in `docs/auto/briefs/TRUCK_CREW_REPLAY_DECISIONS.md` ("Round
two, after PR #36's report and its two follow-on commits") chose **option (b)**: the finals
line is written from the `no_safe_walk` population, with the aborts and the
inadmissible-corridor count in the same sentence, and **from the line-sampled arm**, which
turns 「cancelled by the rule」 into 「never ordered because the road closes」. The v2 arm stays
the record. §7.2's draft was written before that decision reached this branch; it stands as
written and is superseded by this section. Nothing in §7 is edited.

**⚠ NOT QUOTABLE.** This is a proposal for HQ to accept, amend or reject. Nothing is
registered; `README`, `web/finals.html`, `docs/auto/JUDGE_QA.md`, `docs/NUMBERS.json` and the
printables kit are untouched by this branch.

> 「2025년 3월 25일 영덕 산불에서, 걸어 나갈 안전한 길이 없는 것으로 분류된 54개 지점(28개 도로
> 접점, 건물 190동)에 대해, 이 화면이 차량 4대에 실제로 내린 출동 지시는 **11건**이었다. 나머지
> **17개 접점에는 지시 자체가 나가지 않았다** — 진입로가 그 시점에 이미 닫혀 있었기 때문이다.
> 나간 11건 가운데 **9건**은 위성이 관측한 화선이 승차 지점에 도달하기 전에 도착했고, **1건**은
> 이 화면이 스스로 중단 규칙으로 취소했으며, **4건**의 진입로는 관측상 이미 화선 안에 있었다. 이
> 경로들을 계획한 확산면은 발화 이후 실제로 관측된 기상으로 다시 만든 사후 재구성(hindcast)이다.」
>
> EN: 「On the 2025-03-25 영덕 fire, for the 54 points classified as having no safe walk-out
> (28 road pickups, 190 buildings), this screen issued **11** dispatch orders to four
> vehicles. The other **17 pickups were never ordered at all**, because the road into them
> was already closed. Of the 11 that went out, **9** arrived before the satellite-observed
> fire line reached the pickup, **1** was cancelled by the screen's own abort rule, and **4**
> drove an ingress corridor the observation places inside the footprint. The spread field
> these routes were planned on is a hindcast, reconstructed with the weather that actually
> occurred after ignition.」

**Every number, traced to a committed artifact key.** The population is the same
pre-registered population as the v2 arm (`docs/truck_crew_replay.md` §1), so its three counts
are read from the v2 artifact; the trip counts are the line-sampled arm's, under abort rule
v2, which live in the `v2` sub-object of each run record.

| number | artifact | key |
|---:|---|---|
| 54 | `data/processed/truck_crew_replay_v2_yeongdeok.json` | `populations["canonical.no_safe_walk"].rescue_needing_walk_nodes` |
| 28 | `data/processed/truck_crew_replay_v2_yeongdeok.json` | `populations["canonical.no_safe_walk"].pickups` |
| 190 | `data/processed/truck_crew_replay_v2_yeongdeok.json` | `populations["canonical.no_safe_walk"].buildings_behind_pickups` |
| 4 (vehicles) | `data/processed/truck_crew_replay_yeongdeok_v2_linesampled.json` | `runs["canonical.no_safe_walk.k4"].vehicles` |
| 11 | `…_linesampled.json` | `runs["canonical.no_safe_walk.k4"].v2.trips_ordered` |
| 17 | derived, `28 − 11` | `populations[…].pickups − runs[…].v2.trips_ordered`; one trip per distinct pickup here (`runs[…].distinct_pickups_ordered` = 11) |
| 9 | `…_linesampled.json` | `runs["canonical.no_safe_walk.k4"].v2.reached_before_observed_closure` |
| 1 | `…_linesampled.json` | `runs["canonical.no_safe_walk.k4"].v2.aborted_by_rule` |
| 4 (corridors) | `…_linesampled.json` | `runs["canonical.no_safe_walk.k4"].v2.trips_with_an_inadmissible_ingress_leg_m0` |

The same four counts are printed in `docs/truck_crew_replay.md` §11, canonical /
`no_safe_walk` / *k* = 4 / line-sampled row: 11 ordered, 9 reached, 1 not reached, 1 aborted,
4 inadmissible ingress corridors. The partition is 9 + 1 + 1 = 11.

**What changed against §7.2, and why it is not a softer number.** The v2 arm's sentence said
21 orders, 8 reached, 12 aborted, 12 bad corridors. The line-sampled arm's says 11 orders, 9
reached, 1 aborted, 4 bad corridors. The screen does not do more; it *claims* less. The trips
it would have completed are the same trips (8 → 9), and the ten trips that disappear are the
ones the committed router had planned down lines it never tested and the abort rule then
cancelled. The **17 never-ordered pickups** are the honest form of the same fact: for those
points this tool has nothing to offer, and saying so in the finals line is the point of
option (b). The 「두 개의 12」 ambiguity §7.2 flagged is gone with the numbers that caused it.

**Two things a reviewer should still attack in this sentence.** (1) 「이미 닫혀 있었기
때문이다 / because the road into them was already closed」 is the line-sampled router's
verdict on the *hindcast* field, not an observation: 46 of 4,638 directed edges are cut at
t = 0 on both fields, and that is what most of the 17 hit — it is a claim about the model, so
the hindcast clause at the end of the sentence has to stay attached to it. (2) 1 abort is one
trip; a single trip cannot support any claim about the abort rule working, and §12 of
`docs/truck_crew_replay.md` says so.

# §9. The rebase onto `auto/dev`, and one thing it turned up, 2026-09-14

HQ's merge path: "Rebase once onto the current green `auto/dev` head, confirm GitHub's
`auto-gates` is green on the rebased head, then the author merges. No further re-cuts."

Done, and **twice**: the branch was rebased onto `a13a27b`, and then — because `auto/dev`
advanced three more commits while the gates were running, and the ledger conflicted again —
onto `7f2c4bd`. Both were rebases of the same branch into the same PR, not re-cuts: #36 is
still the one PR and no new branch was made. The result is a linear branch with **zero merge
commits** (the merge-commit
route is what broke `test_the_staleness_threshold_and_its_helper_are_both_graded` last time,
§5). Two files conflicted, both mechanically, both as HQ predicted:

* `docs/auto/NEEDS_HUMAN.md` — **unioned**, at both rebases. `auto/dev` had added NH-062 at
  the same position this branch adds NH-061, and then closed it. Both entries are kept, in
  number order, with the file's own `---` separator between them; **NH-062 keeps `auto/dev`'s
  `closed` heading** and NH-061 keeps its `open` one. Neither entry's text was touched.
* `docs/artifact_manifest.json` — **regenerated** with `python scripts/build_artifact_manifest.py`,
  as instructed, never edited by hand. It now reports 143 artifacts / 24.7 MiB, all git-tracked.

**What the regeneration turned up, reported rather than repaired.** The regenerated manifest
changes one line that has nothing to do with this branch:

    data/processed/routing_demo_leakfree.npz
    data/processed/leakfree_yeongdeok_fold.json
      regenerate: "python scripts/run_leakfree_yeongdeok_fold.py"      (before)
      regenerate: "python scripts/run_forecast_track_f1.py"            (after)

`scripts/run_forecast_track_f1.py` (added by `auto/dev` in the K-SPREAD Stage 2 lap) only
**reads** that file — it holds the full path as a string literal at line 147 — and
`_writers()` in `build_artifact_manifest.py` attributes a full-path literal to the first
script alphabetically (`by_path.setdefault`), so the reader wins over the writer. This is the
same mis-attribution class this branch worked around in its own build script by assembling
input paths from parts; the fix on the other side is not this branch's to make, and editing
the tool's output by hand would be worse. **The committed regeneration command for both files is now
wrong, and `auto/dev`'s own manifest was already stale (generated at `a070258`, 138
artifacts, before that lap's own new artifacts).** Flagged here for HQ rather than silently
carried; running the named script would not reproduce either file.

No committed artifact was modified, nothing was deleted, nothing was force-regenerated, and
no file outside this branch's own set was changed by the rebase.

## 9b. What the rebase made red, and how it was cleared

The rebase moved this branch onto a tree that had, in the meantime, registered **WC-022** in
`docs/auto/withdrawn_claims.json`: the committed spread field may no longer be *described* as
a forecast (the method's name is untouched, and no number moves). This branch's pages were
written before that registration, so `make check-withdrawn-claims` — and with it
`tests/test_withdrawn_claims_registry.py`, two tests — went red on **six** lines that had been
green when they were written. That is the registry working as designed, not a defect.

Cleared as follows, and the split is deliberate:

* **Five lines were reworded**, on HQ's explicit round-two instruction that the docs name the
  field a hindcast: `docs/truck_crew_replay.md` §0, §2, §3b, §6a and §10c. Four of those are
  **pre-registration prose**, so the rewording is recorded in §10c with a dated ⚠ paragraph
  saying exactly which lines moved and that **no rule, threshold, definition or number changed
  with them** — only the name of the field. `git diff` on this commit is the check.
* **One line was licensed, not reworded**: `outputs/truck_crew_replay/20260913T160454Z/README.md:7`,
  the caption of a committed output directory. CHARTER §3 rule 2 protects it, so it carries a
  per-line `forbidden-ok: wc022-forecast-field` pragma with the reason above it — the same
  route WC-022's own `known_stale` rows take for `paper/manuscript.md:533` and
  `docs/auto/knowledge/FIGURE_STYLE_REFERENCE.md:27`. The caption's prose is byte-unchanged.
  **The generator (`scripts/build_truck_crew_replay.py`) was corrected**, so any future run
  writes the hindcast wording and the pragma becomes a debt against one frozen directory
  rather than a standing exemption.

No `known_stale` row was added to WC-022 for that line: the registry belongs to the lap that
wrote it, nothing enforces those rows, and inventing an entry in another lap's ledger is worse
than naming the debt here. **HQ may want the row added when WC-022 is next revised.**
