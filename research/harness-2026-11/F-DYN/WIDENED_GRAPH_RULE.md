# Routing on the widened road graph (rule; DRAFT, plan only; written before any build or run)

**Status.**
- **The assessor read de025de1 (13 Nov) and passed the design; the build may start after the assessor's changes,** which are
  applied in this revision: class wording, arm names, agency visibility, P6, the window-exit report and §6.
- Draft. The rule and the pass criteria are committed before any build or run.
- The assessor reads the rule before anything is built. The independent verifier verifies the result.
- **No verified one-hour result changes.** None of the re-run candidates is in the one-hour panel.

**Order (the orchestrator's message of 2026-11-13 02:29 UTC).**
1. This rule.
2. The assessor's reading.
3. Builds and runs.

This comes after the routing author's `/2` headline rerun, which has finished: 48/48, 54bcb96e. AIR-EXTRACT §2 keeps its place in the queue.

## 1. The graph

**Source.** The widened road graph `kfs01_grid5km.json`, sha256 `2232df00…`, from `daniel/data-fetch-3` @ 6b37ebed
(`roads/step1/`, `STEP2_RESULT.md`).
- **Input:** built from the owner-supplied OSM snapshot of 2025-01-01 (pbf sha256 `9b67fc95…`).
- **Extent:** the KFS_01 export grid plus 14 cells (5,250 m) on every side. That is 265 × 107 cells of 375 m, EPSG:5179,
  x0 1,080,000, y0 1,810,500.
- **Cell index:** `row*265 + col`, with row 0 at the south edge. Export cell (r, c) maps to (r + 14, c + 14).
- **Size:** 185,747 nodes, 367,094 edges.
- **Label on every output:** **"roads as of 2025-01-01 (before the March 2025 fires)"**.
- **Mismatch with the owner graphs.** Step 1 against the owner graphs fails strictly, because the owner graphs are 79 days
  newer (`STEP1_RESULT.md`). Every output states this.

**Use.**
- The graph is not committed (132.7 MB). Each user rebuilds it from the pbf with the committed scripts (pyosmium 4.3.2,
  pyproj 3.8.0) and must match all 5 MANIFEST sha256 values before use. A mismatch stops the run.
- **The pbf's Drive id is private.** It lives in an environment variable only, and never in any committed file, log or
  script.
- **Start condition:** this rule is used only after the reviewers and the independent verifier have given their verdict
  on the graph itself (step 1 and step 2).

## 2. The padding contract: no fire data outside the export grid is not "safe"

**The gap.** The fire inputs (export, arrival rasters, burn set) exist only on the export grid. The 9,632 padding
cells (265 × 107 − 237 × 79) have **no fire information at all**.

**The danger.** The routing author's reader treats a cell with no phases as OPEN. Padding would therefore read as safe
unless it is marked.

### 2.1 Packets on the widened grid

The checker refuses a packet whose grid differs from the graph's ("HAZARD grid differs from the graph grid"), so the
packets are rebuilt on the 265 × 107 grid:

- **Padded export** (`fdyn/pad_export.py`, new). It is written before any build and adds no fire. The export arrays are
  copied into the centre. Padding cells get:
  - `probability_valid = false` (the writer's policy_assigned_zero: no new-burn source);
  - `source_burned_area_valid = false` (burned state unknown);
  - `heat__initial_burning_valid = false`;
  - the export's own fill values elsewhere.

  Present fire and known-burned cells are those of the export, so none lie in padding. The record keeps the original
  export sha256, plus `fdyn_padding = {cells: 14, rule: WIDENED_GRAPH_RULE.md}`.
- **Padded arrival rasters.** These are NaN in padding (no arrival, never ignites). C0 and B0 (NOREENTRY2_RULE.md) are
  therefore unchanged: both are computed on export cells only.
- **The build.** It uses the same `fdyn/build.py --no-reentry2` with the padded export and rasters on the widened
  grid, and gets its own output directory (`packets_v38_widened/`).
- **Radiation.** Flux is computed on the widened grid. The fire is the same, so the flux on export cells is unchanged
  (checked as P2).
- **Support mask.** Through the verified F-9.3 wrapper path (`--support-mask`, `supplied/1`), support = false on every
  padding cell. The provenance is `{"rule": "WIDENED_GRAPH_RULE.md §2", "reason": "export-grid padding, no fire data",
  "padding_cells": 9632}`. The F-3.2 certifier, the kit checker and the replay `Packet` refuse such packets by design.
  That is why the results here are router-only and labelled.

**If the frozen writer refuses a padded export** (an invalid probability or burned state over a large area), the build
stops. The refusal is reported, and this rule returns to the orchestrator. Nothing is worked around.

### 2.2 Two hazard arms over the padding

Every run is made twice, using the routing author's `PacketModel(extra_blocks=…)`:

| Arm | Padding cells | Reads as |
|---|---|---|
| **padding closed** | closed on [0, H), under both the closed and the router rules | "fire may be anywhere outside the export grid" |
| **padding open** | open | "no fire outside the export grid" |

**What "padding closed" is conservative about.** It is conservative about the padding **only**. Inside the export
grid, cells with no fire information still read as open, exactly as in the headline. It is not a worst case inside
the export grid (assessor, 13 Nov).

**Label on both arms:** **"no fire data outside the export grid; not shown safe"**.

### 2.3 Result classes (fixed before any run)

For each (place, start, horizon, variant):

| Padding closed | Padding open | Class |
|---|---|---|
| route found | (any) | **route found by the router on the widened graph, to the listed destinations; not independently checked** (pre-fire roads; padding assumed burning) |
| no route | route found | **undetermined: depends on fire outside the export grid** (never "has a road escape") |
| no route | no route | **no route found by the router on the widened graph to the listed destinations; not independently checked**. If the reachable set again touches the widened boundary, it is "undetermined: map window too small (widened)". |

**Why the classes are worded this way** (assessor):
- **"Checked" is not used.** Every checker refuses the padded packets (§2.1, P5), so these routes are found by the
  router and checked by nothing. In this project "checked" means an independent checker accepted the route.
- **"To the listed destinations".** The destination set is unchanged and lies inside the old area. A "no route" here
  means no route to those places. It does **not** mean that no road leads away from the fire, and it is not the same
  as "no road escape".

**What agencies see** (assessor):
- Only the three classes, and facts from the **padding-closed** arm.
- The padding-open arm stays internal. Its only outward trace is the class "undetermined: depends on fire outside the
  export grid".
- **No route geometry, time or count from the padding-open arm goes to an agency.** A line drawn through cells where
  we have no fire data would be read as a way out.

- **Refusal claims** come from ROUTER on the padding-closed arm only.
- **The NO_CHECKED_ROUTE set and the AIR-EXTRACT §1 counts** take only the padding-closed class. An "undetermined" place
  stays out of every count of no-escape places.

## 3. Waiting: two arms, so that the road effect and the waiting effect are separated

On the widened graph, waitable (exactly 1 distinct neighbour; ROAD_RULE addendum 1) changes **inside** the old
windows. Edge dead ends now connect outward (`STEP2_WAITABLE_DELTA.json` @ ccc1de58):
- UA: 565 → 479 (478 unchanged, 87 removed, 1 added);
- YD: 1,524 → 1,456 (1,454 unchanged, 70 removed, 2 added).

The two arms:
- **(a) Old waiting set.** Nodes present in the step-1 graph keep their step-1 waitable value. Every node absent from
  step 1 follows the widened dead-end rule: the 3 in-window additions and all out-of-window nodes. (a) changes only
  what the old graph could not express.
- **(b) Widened dead-end rule.** The dead-end rule is applied to the whole widened graph.

**Reporting.**
- The **road effect** is (a) against the old graph.
- The **waiting effect** is (b) against (a).
- **(b) is the headline.** It is the documented rule applied to the graph actually used.
- **Waiting wording.** The final (S)/(R) wording applies (F-3.1 WAITING_SENSITIVITY_RULE.md @ 1b792c77). The
  "waiting allowed everywhere" sensitivity row is reported as always.

## 4. What is re-run

**The candidates.** The `possibly_road_limited` set from the routing author's `/2` headline (54bcb96e): no CERT route
at the departure, with the reachable set touching a graph-window boundary node. That is **34 (region, start, place)**,
each at h5 and h8:
- UA 23T01Z: 17;
- UA 24T09Z: 10;
- UA 25T17Z: 6;
- YD 25T19Z: 1.

The per-place list (boundary-node and reachable counts) is committed with the run as its input, before any run.

**For each candidate:**
- the timing variants: kriged_mean, firms_early, envelope, plus envelope_burnset as its own row;
- × the 2 hazard arms (§2.2);
- × the 2 waiting arms (§3);
- on the same 30-min departure grid;
- with the **same destination set** as the headline (INSTANCE). Adding destinations outside the export grid would be a
  separate decision.

**"possibly_road_limited" is a reachability heuristic.** It is not proof that the window caused the no-route. The
re-run is what tests it.

**Not re-run: "origin point closed at departure".** 1,074 of the 1,322 place rows that lose their route from `/1` to
`/2` are in this class: the place's point is on or touches ground that burned out before the start (B0). A wider
graph does not change them, so they are not re-run.

**Execution.**
- One place at a time.
- A memory sizing check comes first. YD all-waitable already peaks at about 12 GB on the old graph, and the widened
  graph has 185,747 nodes.
- UA candidates first, YD last.

## 5. Pass criteria (fixed before any build or run)

- **P1, graph.** All 5 MANIFEST sha256 values match after the rebuild. Inside both old windows the step-2 comparison
  passes (0 missing, extra or differing).
- **P2, packet.** For every widened packet against its v3.7 `/2` packet, on every export cell (mapped by the +14
  offset):
  - flame per member and bin is equal;
  - flux is equal within the A1 rule (relative ≤ 1e-9 or absolute ≤ 1e-12 kW/m²);
  - breakpoints are equal;
  - the identity is new (scenario ids differ).

  On padding cells: flame is false in every bin, and support is false.
- **P3, support.** Support = false on exactly the 9,632 padding cells, and true on every export cell (or as in the
  v3.7 packet).
- **P4, extension monotonicity.** Arm (a) × the padding-closed arm. Every (place, start, horizon, variant, departure)
  that had a checked route on the old graph under `/2` still has one on the widened graph.
  - Why it must hold: the old graph is a subgraph inside the windows, the hazard on export cells is equal, and the
    padding is closed.
  - Any violation is a FAIL and stops the work.
- **P6, arm geometry** (assessor):
  - no route in the padding-closed arm touches a padding cell;
  - every route that exists only in the padding-open arm does touch one.

  This follows from the construction, so it is asserted. A violation means the arms are not what the table says, and
  it is a FAIL.
- **P5, refusals.** Every packet with padding is refused by full_check, the kit checker and the F-3.2 certifier. This
  confirms that no certificate is issued on it.

**Reported, not asserted:**
- **Per padding-closed route result: does the route leave the old window at all?** If it does not, the old graph
  should already have found it. That is a discrepancy to explain, not a gain (assessor).
- the class counts per region, start and horizon;
- the road effect and the waiting effect;
- which of the 34 candidates change class.

**Later, not now: a checker mode** (assessor). It would accept a route when every cell the route touches has support
true. Padding-closed routes lie wholly on export cells, so they could then be independently checked. That is a change
to a verified checker, and it needs its own plan-first step.

## 6. What this rule does not do

- **It certifies nothing.** No route on the widened graph is independently checked, and no certificate is issued.
  Nothing here may feed a resident channel, or the early-action list's times, without a separate decision.
- **It does not show that a road escape exists or does not.** The destinations are unchanged.
- **It does not test today's roads.** The map is pre-fire, 79 days older than the owner graphs, with no closures or
  damage.
- **It is not a worst case inside the export grid** (§2.2).
- **It does not re-evaluate the 1,074 rows whose start point is on ground burned before the start.** They keep their
  separate "not evaluated" state (the assessor's verdict on the `/2` headline).
- **Results.** It changes no verified one-hour result and no `/2` headline number. Results on the widened graph are
  reported alongside, labelled.
- **Fire data.** It adds no fire data outside the export grid.
- **Destinations.** It adds no destinations.
- **The owner graphs.** It does not replace the owner graphs for anything else.

## 7. Amendment 1: P4 precisely, and padding at the export-grid border (13 Nov; before any build)

The routing author found four ways P4 could fail (his message of 04:28 UTC). Each is settled here, before any build.

**(a) Ids: P4 compares like with like.**
- The INSTANCE entry and destination ids are owner-graph OSM node ids, and the owner graphs are 79 days newer than the
  snapshot.
- P4 therefore compares **Daniel's step-1 graph** (same snapshot, clipped to the old window) against **the widened
  graph**. It does not compare against the owner graph.
- **Precondition:** Daniel's inside-window equality (0 missing / extra / differing; STEP2_RESULT.md).
- **Before any run:** every INSTANCE entry and destination id is checked for presence in step-1. Missing ids are
  listed, and their rows are excluded from P4 and reported.

**(b) Edges clipped at the boundary.** Step 1 drops edges that cross the window boundary, and the widened graph has
them whole, with different geometry and ticks.
- P4 is asserted only for old routes that use edges **identical in both graphs**.
- Any old route that uses an edge differing between the graphs is listed, not asserted.

**(c) Padding at the export-grid border. Measured: both old windows reach it.**
- UA window: cols 23–95, rows 0–64. Its row 0 is the export grid's south edge.
- YD window: cols 166–236, rows 0–66. That is the export grid's south **and** east edges.

**Ruling.** The padding-closed arm uses **the same closure as fire, under both the closed and the router rules.**
- **Why.** "Padding closed" stands for possible fire, and fire closes an edge that touches its cell boundary. A
  router-rule-only padding would be weaker than fire exactly where we have no data.
- **Consequence.** An old edge, node or destination point lying on the export-grid border touches a padding cell, so
  it is blocked from 0 in that arm.
- **P4 is therefore asserted only for old routes that touch no padding cell**, counting boundary contact under the
  closed rule.
- **Old routes lost only through such contact** are listed in their own row: **"lost only by touching the edge of the
  fire-data grid (padding assumed burning); not a fire result; the result on the old graph is unchanged"**. The row
  is internal, like everything else that depends on what padding is assumed to be. That row is not a P4 failure, and not a fire result.

**(d) Waiting.** Arm (a) uses the **old** waiting set (§3). Otherwise P4 could fail through lost stops.
- **Implementation:** a `waitable_override: {node_id: bool}` in the routing author's PacketModel. It is applied to the
  raw nodes before the RoadGraph is built, so the field and full_check see the same graph.
- **Tests and failure handling:**
  - a unit test (override == graph flags gives identical fields), committed before any run;
  - unknown ids in the override are an error list, never silently ignored.
- **Source:** `daniel/data-fetch-3` @ ccc1de58, `research/harness-2026-11/data-fetch-3/roads/STEP2_WAITABLE_DELTA.json`.

**Restated P4.** For every (place, start, horizon, variant, departure) under `/2`, take each old route (step-1 graph,
old waiting set) that:
- uses only edges identical in both graphs;
- touches no padding cell;
- has its entry and destination ids present in step-1.

Each such route must still have a route on the widened graph under arm (a) × padding closed. Every violation is a
FAIL.

**Candidate input.** Fixed: `results/NR2_ROAD_LIMITED_CANDIDATES.json` @ 50535521 (routing author's branch). It has 176
rows over 34 places:
- 160 are "depends on the no-re-entry rule";
- 16 had no route on `/1` either;
- none is "not evaluated".

**§7 additions (13 Nov, from the routing author's id check; before any build):**
- **What "identical edge" means in P4:** the same edge id, u, v, **ticks and segments**. Nodes moved by 0.34–23 m
  between snapshots change the ticks, so id/u/v alone is not enough.
- **Ids are not shared with the owner graphs.** STEP1_COMPARE.txt @ 122f42a3:
  - UA has 237 owner-only and 205 rebuild-only nodes.
  - 1,582 common UA edges differ.
- **Any comparison with owner-graph results goes through an explicit id mapping.** Ids are never assumed equal.
- **Places that cannot be located.** An INSTANCE id absent from the rebuilt step-1 node set makes its place **"not
  located on the 2025-01-01 graph"**. Such places are not re-run, and they are listed.
  - **Known before the rebuild:** UA osm:12616948834, created after the snapshot. It is the entry node of place
    osm:node/415160468 at all 3 UA starts.
  - The full membership test runs on the rebuilt step-1 graph, before any routing run.

**The assessor's reading of §7 (13 Nov): border ruling accepted.** Her three additions are part of the rule:
- **P4 coverage, reported per region:** how many old routes P4 covers, and how many it excludes for touching padding.
  If most of the YD south/east-edge routes are excluded, P4 tests little there, and the report says so.
- **P4-open, asserted.** Under (a) × padding open, every old route that uses only identical edges (and whose ids are
  located) must still exist, with **no padding exclusions**: open padding adds no closure. This is the one complete
  check of the graph extension. Any violation is a FAIL.
- **The row label** for border-touch losses carries "not a fire result; the result on the old graph is unchanged",
  and the row stays internal.

**Reported with the widened-graph results; this changes nothing in the headline.** The count of `/2` headline routes
that touch the export-grid border, per region and start. These results rest on "nothing is burning just outside the
grid", and the reader should see how many there are.

**§7(d) implementation fixed (13 Nov).** The routing author's `waitable_override` is at `claude/f31-deadline-field` @
903b1668, committed before any run.
- It is applied to raw nodes before RoadGraph.
- It refuses unknown ids, non-bool values, and use together with waitable_all. Test: `tests/test_waitable_override.py`;
  the suite passes 15/15.

**How the arm (a) dict is built.** Input: `STEP2_WAITABLE_DELTA.json` @ ccc1de58.
- **Contents:** for every node present in both the step-1 graph and the widened graph, `{id: step-1 waitable}`.
- **Nodes absent from step 1** (the 3 in-window additions and all out-of-window nodes) are not in the dict, so they
  keep the widened graph's own dead-end flag. That matches §3(a).
- **Step-1-waitable nodes absent from the widened graph** cannot be set. They are listed, with their count reported,
  before any run. They are expected to be 0, given the step-2 inside-window equality.
- The dict and its sha256 are committed with the run input.

## 8. Amendment 2: the independent verifier's read (verification ledger row 78) and one further gap (13 Nov; before any routing run)

The independent verifier read the rule @ af24680e before any build and found it sound with four clarifications. They
are settled here. Item (v) is a further gap found by the author while writing them. Nothing here was decided after a
result: no padded packet has been built and no route has been computed.

**Graph inputs reproduced (not a run).** The pbf was fetched by env var only, into its own directory: 233,753,476
bytes, sha256 9b67fc95…, header replication timestamp 2025-01-01T21:21:00Z. With the data-fetch author's committed
scripts (`roads/step1/` @ 6b37ebed; extract_area.py 0d57e2f1…, build_graph.py fcc1573e…; Python 3.13.18, pyosmium
4.3.2, pyproj 3.8.0, `python -I`), the outputs are byte-identical to MANIFEST.json:
- area_grid5km.json 7865f495…;
- ua_step1.json e92cd0a8…;
- yd_step1.json 39226a07…;
- kfs01_grid5km.json 2232df00….

The widened build peaked at 0.75 GB RSS.

**(i) Padding in the padded export means "not burned".** This is a stated condition, not an assumption.
- The bridge's unknown-age policy ("known burned, age unknown → active [0, T)") applies only to *known* burned cells:
  `known_burned = source_burned_area_valid & (source_burned_area == 1)` and `unknown_age = known_burned &
  ~heat__initial_burning_valid` (`integration/src/wfg_latest/bridge.py` lines 173 and 179, frozen).
- `source_burned_area_valid = false` on padding therefore gives neither known-burned nor unknown-age. Padding gets no
  present fire and no enclosure.
- **Why P2 checks "flame false on padding in every bin":** it is the check that catches a violation of this condition.
  A violation is a FAIL and stops the build.
- **Flux on padding is nonzero.** Fire at the grid edge radiates into it. Routes that exist only in the padding-open
  arm therefore carry a dose that nothing checks. That is one more reason the padding-open arm stays internal (§2.2).

**(ii) P2, added fields.** These must also equal the v3.7 `/2` packet:
- `valid_until` and the horizon H;
- the present-fire enclosure fields (`present_fire_unknown_age_enclosed`, `unknown_age_cells_enclosed`, `R_max_s`).

Flux on export cells is held to A1 (relative 1e-9 or absolute 1e-12 kW/m²). The independent verifier's argument for why
it can hold (rfft2 over the full linear shape with zero padding, no wrap-around, and sources on export cells only in
both builds) is recorded here as the reason. A failure is still a FAIL.

**(iii) P4 restated: the same field on both graphs, feasible-set containment, and a fixed power floor.**

*1. The same field on both graphs.*
- Both sides use the routing author's deadline-field solver on `PacketModel.instance("cert", …)`, the CERT rule (router
  OR closed footprint).
- Neither side uses full_check.
- "Checked route on the old graph" is dropped from P4. Since CERT-feasible ⊂ ROUTER-feasible, a CERT loss could
  otherwise hide behind a ROUTER survival.

*2. Containment of feasible sets, not grid points.* For each (place entry node, destination, dwell), let F(G, arm) be
the exact CERT-feasible departure set on [0, H) (interval sets, integer seconds). Write G1 for the step-1 graph, with
the v3.7 `/2` packet and the old waiting set.

**The eligible old graph G1′** is G1 restricted so that it is, by construction, a sub-instance of the widened instance:
- **(a)** keep only edges identical in both graphs: id, u, v, direction, ticks and segments (§7);
- **(b)** drop every edge, wait node and destination point that touches a padding cell under the closed rule (§7(c));
- **(c)** use as forbidden turns the union of G1's and the widened graph's on the edges that remain (item (v));
- **(d)** keep G1's waitable flags.

**P4 (asserted).** F(G1′) ⊆ F(widened, waiting arm (a), padding closed), exactly, for every triple, place, start,
horizon and variant run. Any departure second in the difference is a FAIL and stops the work.

**P4-open (asserted).** G1″ is G1′ without step (b). F(G1″) ⊆ F(widened, waiting arm (a), padding open), exactly.

**Reported per region, start and triple:**
- F(G1) \ F(G1′): departures lost to the old graph only through exclusions (a), (b) or (c);
- the row "lost only by touching the edge of the fire-data grid (padding assumed burning); not a fire result; the
  result on the old graph is unchanged" (§7) is the part due to (b) alone. It stays internal.

*3. Power: a control set, and a minimum fixed now.*
- **The control set.** The 34 candidates have no CERT route at their departures by construction, so on their own they
  test containment weakly. P4 and P4-open are therefore also run on a control set: **every INSTANCE place at UA
  25T17Z and at YD 25T19Z, h5, kriged_mean, no_reentry/2**. Only waiting arm (a) is used, under both padding arms. The
  control set is internal and changes no headline number.
- **Coverage per region.** Measured in departure-seconds summed over triples: |F(G1′)| / |F(G1)| (and |F(G1″)| /
  |F(G1)| for P4-open), together with the number of triples where F(G1′) is non-empty.
- **The fixed minimum.** P4 in a region counts as a test of the extension only if both hold:
  - coverage ≥ 0.50;
  - at least 50 triples with F(G1′) non-empty.
- **Below the minimum,** that region's P4 result is reported as "held, but below the fixed coverage minimum: tests
  little". It is never reported as a plain PASS. The same minimum applies to P4-open.

*4. Mechanics.*
- **Router-only runner.** The runs use a router-only runner, `fdyn/widened_run.py` (new). It calls PacketModel and the
  deadline-field solver only, and never full_check or headline.py's witness check. It is committed and tested before
  any run.
- **P5 is a separate step.** It runs full_check, the kit checker and the F-3.2 certifier on each padded packet and
  asserts refusal.
- **Pre-build test: does PacketModel accept a support-masked packet?** Before any padded packet is built, a test checks
  that PacketModel, at the routing author's committed head, loads a support-masked packet written by the F-9.3 wrapper.
  - **Why.** Verification ledger row 42 found PacketModel @ d731b3a refusing one.
  - **Pass condition.** The packet loads, and its Instance B/W/A arrays are identical to those of the unmasked packet
    it wraps. Support does not enter the contact rules.
  - **If it refuses,** the work stops and returns to the orchestrator. The author does not patch around it, because
    PacketModel belongs to the routing author.

**(iv) Memory.** The routing author's border-touch runner hit OOM on YD at about 14 GB (969a2ca2) and now keeps one
field in memory at a time.
- The runner here does the same.
- The sizing check (§4) is measured on the widened graph with one UA candidate first.
- If YD does not fit in this 15 GB container, YD is reported **blocked, with the measured peak**. It is not truncated.

**(v) Turn restrictions differ between the graphs.**
- A node that is a dead end in step 1 because its outward edge was clipped at the window edge allows a U-turn there
  (ROAD_RULE addendum 1). The same node in the widened graph is not a dead end, so that U-turn is forbidden.
- Restriction relations skipped in step 1 as outside the window can also apply in the widened graph.
- An old route could therefore use a turn the widened graph forbids. That would break P4 without any fire or padding
  effect.
- (iii)2(c) removes this by construction. The number of turn pairs added to G1′ this way is reported per region.

**Unchanged.** §2.3's classes, §2.2's agency visibility, P1–P3, P5 and P6 stand as written. Every result stays router-only
and labelled.

**§8 read by the independent verifier (verification ledger row 78a, 13 Nov): settled.**
- **P4.** Given G1′ as stated, F(G1′) ⊆ F(widened) is a theorem given P2. P4 therefore catches implementation faults
  only.
- **(v)** is closed by the forbidden-turn union.

**Reporting addition from that read (13 Nov; before any routing run).** The headline ran on the owner graphs, which
are 79 days newer than the snapshot. A class change against the headline could therefore come from the map date
rather than from the widening. Two effects are reported separately, so that neither is credited to the other:
- **The widening effect:** widened, waiting arm (a), against G1, the same snapshot.
- **The snapshot effect:** G1 against the owner-graph `/2` headline, through the §7 explicit id mapping.

§2.3's class changes and §3's road effect are both stated against G1. The comparison with the headline is shown as the
sum of the two effects, never as one effect.

**Input checks done before any routing run (13 Nov):** `fdyn/widened_inputs.py` → `results/WIDENED_INPUTS.json`.
- **Membership.** The only unlocated id is UA osm:12616948834. Its place, osm:node/415160468, is "not located on the
  2025-01-01 graph" at all 3 UA starts.
- **Arm (a) dict.** `results/WIDENED_ARM_A_WAITABLE.json`: 79,428 entries, sha256 34d0b7d4…. Its in-window delta
  equals STEP2_WAITABLE_DELTA.json, and 0 step-1-waitable nodes are absent from the widened graph.
- **Edges.** Every step-1 edge is identical in the widened graph: UA 43,801 and YD 111,814, with 0 differing and 0
  absent.
- **§8(v) is real.** The widened graph forbids 58 (UA) and 64 (YD) turn pairs on identical edges that step 1 allows.

**§8(iii)4 pre-build test (13 Nov): FAIL. The work stops here.** The test (`fdyn/widened_pretest_packetmodel.py` →
`results/WIDENED_PRETEST_PACKETMODEL.json`) ran PacketModel at the routing author's head 969a2ca2 on an F-9.3 masked
pair: UA 25T17Z, `c651_unknown/1`, 5,068 support-false entries.
- **The unmasked twin loads.**
- **The masked packet is refused:** `PacketError: npz contract violated (current/support/events)`. This is the replay
  `Packet`'s all-true-support contract, the same refusal as in row 42.

No padded packet has been built and no route has been computed. As §8 states, the question has returned to the
orchestrator.
