# Routing on the widened road graph (rule; DRAFT, plan only; written before any build or run)

**Status.**
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
| **pessimistic** | closed on [0, H), under both the closed and the router rules | "fire may be anywhere outside the export grid" |
| **optimistic** | open | "no fire outside the export grid" |

**Label on both arms:** **"no fire data outside the export grid; not shown safe"**.

### 2.3 Result classes (fixed before any run)

For each (place, start, horizon, variant):

| Pessimistic arm | Optimistic arm | Class |
|---|---|---|
| checked route | (any) | **has a checked road route on the widened graph** (pre-fire roads; padding assumed burning) |
| no route | checked route | **undetermined: depends on fire outside the export grid** (never "has a road escape") |
| no route | no route | **no checked route on the widened graph**. If the reachable set again touches the widened boundary, it is "undetermined: map window too small (widened)". |

- **Refusal claims** come from ROUTER on the pessimistic arm only.
- **The NO_CHECKED_ROUTE set and the AIR-EXTRACT §1 counts** take only the pessimistic class. An "undetermined" place
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
- **P4, extension monotonicity.** Arm (a) × the pessimistic arm. Every (place, start, horizon, variant, departure)
  that had a checked route on the old graph under `/2` still has one on the widened graph.
  - Why it must hold: the old graph is a subgraph inside the windows, the hazard on export cells is equal, and the
    padding is closed.
  - Any violation is a FAIL and stops the work.
- **P5, refusals.** Every packet with padding is refused by full_check, the kit checker and the F-3.2 certifier. This
  confirms that no certificate is issued on it.

**Reported, not asserted:**
- the class counts per region, start and horizon;
- the road effect and the waiting effect;
- which of the 34 candidates change class.

## 6. What this rule does not do

- **Results.** It changes no verified one-hour result and no `/2` headline number. Results on the widened graph are
  reported alongside, labelled.
- **Fire data.** It adds no fire data outside the export grid.
- **Destinations.** It adds no destinations.
- **The owner graphs.** It does not replace the owner graphs for anything else.
