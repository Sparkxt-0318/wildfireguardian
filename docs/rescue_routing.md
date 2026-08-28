# Rescue-aware evacuation routing — methods note

> ⚠️ **DO NOT CITE THESE NUMBERS / 제출·인용 금지 — SUPERSEDED.** The `N`, four-way split,
> and `w` figures in this note are the **pre-flip synthetic baseline** and must **not** be
> quoted in the submission. The committed real-OSM values are **N = 439**, four-way
> **262 / 10 / 143 / 24**, needs-rescuer **38.0 % (167)**, walk-failure **`w` = 0.091–0.174**
> — see `docs/REPORT_ROUND2_P1.md` for the authoritative OLD-vs-NEW table.

> **Round 2 · Phase 1 — real-data flip (2026-07).** The committed
> `data/processed/rescue_*.json` have since been flipped from synthetic fallbacks to
> **real OpenStreetMap** road/refuge/depot geometry (fire **hazard** + **terrain**
> remain synthetic, pending the FIRMS bundle). The synthetic **numbers** quoted in
> this methods note (e.g. N = 452, the four-way split, `w` ≈ 40 %) describe the  <!-- forbidden-ok: 452 -->
> **pre-flip** baseline, preserved at `data/processed/rescue_baseline_synthetic/`;
> the current real values and an OLD-vs-NEW comparison are in
> `docs/REPORT_ROUND2_P1.md`. The **method** described here is unchanged.

*What it is, why it is built this way, what it does **not** claim, and where every
input comes from. Companion to `src/wildfireguardian/routing/rescue.py` and
`rescue_demo.py`; regenerate results with `python scripts/run_rescue_routing.py &&
python scripts/make_rescue_figures.py`.*

> **Results draft:** see `docs/results_rescue_draft.md` for the honestly-hedged
> results section (claims ledger + the assumption-light walk-failure rate `w` ≈ 40 %,
> derived from the committed fc sweep via `scripts/derive_walk_failure.py`).
>
> **Spread-model numbers:** the canonical foundation model (Build B) is documented in
> `docs/MODEL_CARD.md` — headline LOFO **mean-of-folds ROC-AUC 0.89 ± 0.11** (pooled
> 0.905), forward-sim footprint IoU **~0.40**.

---

## 1. What

A tightly-scoped layer **on top of** the existing future-aware evacuation router
(`routing/evacuation.py`) and the spread model's probabilistic hazard
(`routing/hazard.py::HazardSequence`). It adds:

1. **A drivable road + auxiliary-data layer.** OSM `walk` (residents) and `drive`
   (responders) networks, candidate refuges (대피소·긴급대피장소), and responder
   depots (119안전센터 / `amenity=fire_station`). Each loader has a real source
   **and** a clearly-labelled synthetic fallback so the pipeline runs end-to-end
   with no network access or API key.
2. **Ingress-corridor survival.** For each refuge (and, on the rescuer side, each
   home) we take the vehicle access route from the nearest depot, sample it into
   points, read each point's time-sliced ignition probability, and compute the
   earliest forecast slice at which **any** segment exceeds a *separate, higher*
   vehicle-impassability cutoff. A destination is `rescue_reachable` iff that
   survival time ≥ the responder ETA + a safety margin.
3. **Resident- and rescuer-side routing.** Residents are routed only to
   rescue-reachable refuges; for people who cannot self-evacuate the responder's
   route (depot → home) is computed on the drive network. The honest four-way
   outcome split always sums to N and the unreachable set is reported, never
   imputed.

## 2. Why (the science, briefly)

- **Shelter-in-refuge / be-rescued is a recognised protective action** in
  wildfire-evacuation science (Cova et al.), but it is only safe if the *access
  route and the responders survive* the fire — which the spread model already
  predicts. So we model "rescue-reachable" as a **constraint on top of the
  existing hazard prediction**, not a new black box.
- **Travel time dominates feasibility.** The elder's slow walking speed (0.7 m/s,
  Tobler-slope-adjusted) and the responder's ingress time are first-class.
- **A delayed/unavailable responder is itself a documented cause of death** for
  people who cannot self-evacuate. The responder ETA therefore explicitly
  includes a **dispatch delay** (detection + mobilisation), not just drive time —
  ETA = dispatch_delay + travel_time — and the system pushes a concrete route
  rather than assuming one is improvised.

## 3. How (algorithm)

- **Vehicle vs pedestrian cutoffs are separate.** The walking elder is held to a
  conservative `walk_cutoff = 0.5`; the responder vehicle (fast, accepts more
  risk) to a higher `vehicle_cutoff = 0.7`. Both are explicit config and swept.
- **`ingress_survival_time`** iterates the hazard's *discrete* forecast slices
  (mirroring `evacuation._time_to_cutoff`) and returns the earliest slice at which
  any sampled corridor point reaches the vehicle cutoff (∞ if never). The unit
  test pins this to a known slice.
- **`rescue_reachable` (refuge screening, brief §2)** uses the **direct** access
  route (shortest-time drive path) and the formula
  `survival ≥ ETA + safety_margin`. By construction `rescue_reachable ⊆ safe`
  (the refuge is the corridor endpoint, so corridor survival ≤ the refuge's own
  survival).
- **Home reachability (the four-way `no_surviving_vehicle_ingress` class and the
  dispatch/unreachable split)** uses the **strongest honest test**: can the
  *survival-aware, exposure-minimising, detouring* responder router actually reach
  the home safely within the time budget (`rescuer_reachable`)? A home is only
  ever called unreachable when even that fails. This is intentionally stronger
  than the direct-corridor screening used for refuges — a refuge is endorsed only
  if it has a surviving *direct* road, while a trapped resident is declared
  unreachable only if *no* route (direct or detour) survives.
- **Resident policies (brief §3), same refuge universe, only the policy differs:**
  (a) `naive` fire-blind nearest refuge; (b) `future_aware → any safe refuge`
  (the current method); (c) `future_aware → nearest rescue-reachable refuge` (the
  new method). The b→c contrast isolates the cost of the rescue-reachability
  constraint.
- **Rescuer routing (brief §4)** reuses the future-aware time-expanded router on
  the drive network at vehicle speed and the vehicle cutoff, departing at the
  dispatch delay. The **dispatch list** ranks reachable homes by urgency =
  `ingress_survival_time − responder_ETA` ascending (smallest closing window
  first); the **unreachable set** is reported separately.
- **Immobile residents** (config fraction) cannot self-evacuate, so they are
  forced onto the rescuer path — never `already_safe`/`saved`. The four-way
  `no_safe_pedestrian_route` / `no_surviving_vehicle_ingress` counts therefore
  equal the dispatch / unreachable split exactly.

### 3a. Round-trip margin, trigger line, advisory output (Session 8, additive)

Motivated by a 현장 실무자 자문 (N = 1, qualitative —
`firefighter_consultation.md`; a statement of practice, never a data source):
a categorical 「구조대가 갈 수 없습니다」 is the wrong shape for field use, and
withdrawal is a spatial judgment, not a clock. Cova, Dennison, Kim & Moritz
(2005, *Transactions in GIS* 9(4)) formalise the spatial form as evacuation
**trigger points**. Implementation: `routing/margins.py`, additive on top of
everything above — the 7-key classification, the four-way split and the
dispatch ranking are unchanged.

- **Round-trip margin.** The committed urgency is one-way
  (`ingress_survival − responder_ETA`). The margin extends it to the full
  mission: `M = S − (ETA_in + t_load + ETA_out)`, with the egress leg
  evaluated **at the egress departure time** `ETA_in + t_load` — the same
  corridor at ingress time and at egress time is a different edge of the
  time-expanded graph. A corridor survivable at ingress but closed at egress
  produces a **negative** margin (pinned by
  `tests/test_margins.py::test_ingress_ok_egress_closed_gives_negative_margin`).
  `t_load` (on-scene pickup) is a **new ASSUMED config value**
  (`responder.t_load_min`), swept in `scripts/run_margin_sweep.py`; it is
  never presented as measured. `egress_policy = "same_route"` (default;
  doctrine per the consultation — 「들어가서 그 길로 나오는 게 원칙」, N = 1)
  vs `"free"` (survival-aware router picks a fresh egress route at the egress
  departure time) is likewise config + swept.
- **Withdrawal trigger line.** The spatial dual: the hazard-field isochrone
  whose arrival time equals the mission's latest safe commitment time (where
  `M(t) → 0`), snapped **down** to the containing forecast slice
  (conservative). Emitted per mission with the arrival time and hazard slice
  index it was derived from. ⚠ Hazard time resolution is overpass-scale
  (hours), so trigger lines are **planning-scale, not tactical** (see §5 —
  same constraint, same wording).
- **Advisory output (human-facing only).** Per dispatch/unreachable home:
  `margin_minutes` (signed, round-trip); `margin_band` — the margin's spread
  over the committed §4a `vehicle_cutoff` sweep axis {0.5…0.9}, or `null`
  when no swept cutoff yields a finite margin (an interval is never
  invented); `recommendation` ∈ {진입 권장, 진입 보류 권장, 철수 권장} —
  advisory wording, never 불가; `trigger_line`; and `basis` — every field the
  recommendation was computed from, so a human commander can audit it.
  Emitted as the **additive** `margin_advisories` key of
  `rescue_routing.json`. Machine-facing keys (the 7-key classification, the
  four-way split, `dispatch_top20`, `unreachable_homes`) are unchanged — they
  are what the tests and NUMBERS.json trace to.

## 4. The four-way split (must sum to N)

Each origin (an elderly home) lands in exactly one class:

| class | meaning |
|---|---|
| `already_safe` | a mobile resident's fire-blind walk is already safe |
| `saved_by_rescue_reachable_refuge` | naive walk unsafe, but future-aware routing to a **rescue-reachable** refuge gets them out safely (the new method) |
| `no_safe_pedestrian_route` | cannot self-evacuate on foot (immobile, or walk route cut), **but a responder can reach** → dispatch |
| `no_surviving_vehicle_ingress` | cannot walk out **and** cannot be driven out — the honest unreachable set |

The surviving-ingress layer *reduces* (moves homes into the dispatchable class) but
does **not eliminate** (the last class remains) the unreachable set.

## 4a. Reconciled results & robustness (verification pass)

All headline numbers below are on **one explicit baseline**, on the **same origin
set N = 452**, regenerable with `python scripts/verify_rescue_routing.py`  <!-- forbidden-ok: 452 -->
(`data/processed/rescue_verify.json`). The verify sweep runs at full N, so its
**baseline cell equals the headline** (asserted in code and by a test). Treat
absolute counts as illustrative (single-fire PoC + synthetic inputs); the robust
claim is the **direction/contrast**.

**Baseline:** walk 0.7 m/s · vehicle 40 km/h · pedestrian cutoff 0.5 · vehicle
cutoff 0.7 · dispatch delay 30 min · safety margin 12 min · resident/responder
budget 600/75 min · seed 20250603 · all inputs synthetic (tagged).

**Two metrics, never compared across scales** (labelled `route_type` in the
output): resident exposure is over **pedestrian** routes; responder over
**vehicle** routes; both in `prob·min`.

**Why N = 452 (not the old 407):** the rescue origin scan uses `scan_stride=3`  <!-- forbidden-ok: 452 -->
plus a fire-reach latitude band on the walk-network land nodes; the older
routing-spine used a `scan_stride=4`, 14 km-band scan giving 407.

**Four-way split @ baseline (sums to 452):** already-safe **154** · saved-by-  <!-- forbidden-ok: 154, 452 -->
rescue-reachable-refuge **34** · no-walk-rescuer-reaches **244** · unreachable
**20**. Resident exposure (pedestrian, prob·min) naive/​b/​c = **24.06 / 3.55 /
3.47** (paired b vs c over the same 185 origins = 3.42 / 3.47; c re-routed 2 off a
cut-off refuge). Responder ingress (vehicle, prob·min) shortest-path/​survival-
aware = **0.172 / 0.079** (dispatch 244, unreachable 20).

**2-D sweep — unreachable count (dispatch delay × vehicle cutoff), full N = 452:**  <!-- forbidden-ok: 452 -->

| delay \ cutoff | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 |
|---|---|---|---|---|---|
| 0 min | 15 | 9 | **6** | 2 | 1 |
| 15 | 21 | 18 | 15 | 8 | 2 |
| 30 (baseline) | 25 | 25 | **20** | 15 | 8 |
| 45 | 37 | 31 | 25 | 20 | 15 |
| 60 | 40 | 38 | **34** | 27 | 20 |

(`already_safe`=154 and `saved`=34 are constant across the grid; `no_walk` = 264 −  <!-- forbidden-ok: 154, 264 -->
unreachable. See `docs/figures/rescue_sweep_2d.png`.) This resolves the earlier
20-vs-2/13 confusion: the old sweep was **sub-sampled to N≈151** (the convenience
`sensitivity_sweep` caps origins at `sweep_max_origins`); at full N the baseline
unreachable is 20 and the dispatch 0→60 bracket at cutoff 0.7 is **6 → 34**.

**Robustness verdict:**

| quantity | verdict | basis |
|---|---|---|
| unreachable rises with dispatch delay (0→60: **6→34** at cutoff 0.7) | **robust direction** | monotone non-decreasing for *every* cutoff |
| unreachable rises as the vehicle cutoff gets harsher | **robust direction** | monotone for *every* delay |
| `no_walk_rescuer` ≈ 244 (majority need a rescuer) | **robust to the vehicle knobs** (grid 224–263, central rel-spread 0.09) — but its *level* is set by the assumed immobile fraction (0.3) + the slow-elder-vs-fast-fire pedestrian regime, **not** by the vehicle cutoff/speed | complement of unreachable within the constant 264-home needs-rescue pool |  <!-- forbidden-ok: 264 -->
| `unreachable` point estimate (20) | **directional only** (grid 1–40) — report the direction + range, not the point value | central rel-spread 1.17 |

`rescue_reachable ⊆ safe` holds at every cutoff. The headline four-way and the
sweep's baseline cell are identical.

## 4b. The rescue burden is assumption-driven (immobile_fraction × walk_cutoff)

The vehicle×delay sweep (§4a) only *splits* a **fixed** needs-rescuer pool into
`no_walk_rescuer` vs `unreachable`; it never moved the pool's size. The two knobs
that set that size are `immobile_fraction` and `walk_cutoff`. Decompose the
partition: `self_evacuable = already_safe + saved`, `needs_rescuer =
no_walk_rescuer + unreachable`; the headline "58% need a rescuer" is `264/452`.  <!-- forbidden-ok: 264, 452 -->

**How `immobile_fraction` routes origins (from the code):** `_immobile_homes`
draws a **random `f·N`** origins (`rng.choice(..., replace=False)`) and the loop
does `if n in immobile: needs_rescue; continue` — they **skip the walk checks
regardless of whether they could have walked out**. So `already_safe`/`saved` are
computed only over the mobile `(1−f)` pool and **fall as `f` rises** — they are
**not** invariant to `f` (the pass-1 "constant 154/34" was true only for the  <!-- forbidden-ok: 154 -->
vehicle×delay grid, where `f` was fixed).

**f × c sweep, full N = 452** (`scripts/verify_rescue_routing.py --sweep fc`,  <!-- forbidden-ok: 452 -->
`rescue_verify_fc.json`; baseline cell f=0.30, c=0.50 == headline, asserted):

`needs_rescuer` (= can't self-evacuate on foot):

| immobile `f` \ walk cutoff | 0.40 | **0.50** | 0.60 |
|---|---|---|---|
| 0.15 | 226 (50%) | 211 (47%) | 196 (43%) |
| **0.30** | 272 (60%) | **264 (58%)** | 249 (55%) |  <!-- forbidden-ok: 264 -->
| 0.45 | 315 (70%) | 306 (68%) | 292 (65%) |

`self_evacuable` (= already_safe + saved): 0.15→{226, 241, 256}; 0.30→{180, 188,
203}; 0.45→{137, 146, 160} across walk cutoff {0.40, 0.50, 0.60}. Monotone as
expected: `self_evacuable` rises with a more permissive walk cutoff; `needs_rescuer`
rises with `f` and as the walk cutoff falls. See `docs/figures/rescue_sweep_fc.png`.

**Revised verdict on the burden numbers:**

| quantity | verdict | basis |
|---|---|---|
| `needs_rescuer` = **58 %** (264/452) | **directional, not a number** | grid 196–315 (43–70 %); **halving the assumed immobile fraction (0.30→0.15) drops it 58 %→47 %** (264→211 @ c=0.5) |  <!-- forbidden-ok: 264, 452 -->
| `no_walk_rescuer` = **244** | **re-classified directional** w.r.t. the assumption knobs (grid 178–286, rel-spread 0.46); the §4a "robust" held *only* against the vehicle knobs | moves with both `f` and `walk_cutoff` |
| `saved` = **34** | **rescue-meaningful, not a mislabel** — a pedestrian route to a *rescue-reachable* refuge (the resident-side win); it moves with `f` (over the mobile pool), so not f-invariant | — |

**Defensible headline today:** *"Under walk cutoff 0.5 and 30 % assumed immobile,
264/452 (58 %) cannot self-evacuate on foot; at 15 % assumed immobile this falls to  <!-- forbidden-ok: 264, 452 -->
211/452 (47 %). The share is driven by the assumed immobile fraction plus the  <!-- forbidden-ok: 452 -->
slow-elder pedestrian regime — not by the vehicle-side knobs."* Even at the most
optimistic swept assumptions a **large minority (≥43 %)** still cannot self-evacuate
— that direction is robust; the exact percentage is not. **Unchanged keeper:** the
§4a dispatch-delay → unreachable trend remains a robust direction.

## 4c. Rescue capacity / triage — the demand–supply gap (PoC)

§4a–4b size the **demand**: of N = 452 origins, **264 need a rescuer** = **244  <!-- forbidden-ok: 264, 452 -->
dispatch-reachable** (a vehicle corridor survives long enough to reach them) +
**20 geometry-unreachable** (no surviving ingress). They never asked whether the
fire service can **supply** that many rescues in the window. This layer
(`rescue.py::capacity_triage`, `--sweep capacity`,
`data/processed/rescue_capacity.json`, `docs/figures/rescue_capacity.png`) closes
that gap as an **additive refinement** — no change to the spread model or the
routing logic. The existing **prioritized dispatch list (ranked by closing window
= `ingress_survival − responder_ETA`, most-urgent first) IS the triage rule.**

**Supply model (PoC).** `n_rescue_units` teams operate from the depot(s); each is
busy `rescue_service_time_min` per rescue cycle. Every unit is mobilised at the
`responder_dispatch_delay` and drives the already-computed responder corridor; a
home is **`rescued_in_time`** iff a unit ARRIVES no later than its
`deadline = min(ingress_survival_time, dispatch_delay + W)` (corridor still open
*and* within the operational window `W = responder_time_budget_min = 75 min`),
else **`capacity_deferred`** (a *supply* failure — a surviving route exists but no
unit reaches it in time). `geometry_unreachable` (the 20) is unchanged. The three
outcomes **partition the 264-home needs-rescuer pool**.  <!-- forbidden-ok: 264 -->

> **These capacity numbers are PoC parameters, NOT measured 영덕 fire-service
> capacity.** The deliverable is the demand–supply **curve**, never a single
> "X rescued" or any "lives saved" figure.

**Capacity sweep @ baseline (PoC: `service = 25 min/rescue`, `W = 75 min`,
units mobilised at the 30-min dispatch delay), full N = 452:**  <!-- forbidden-ok: 452 -->

| rescue units | rescued_in_time | capacity_deferred | geometry_unreachable | % of demand met |
|---:|---:|---:|---:|---:|
| 1 | 3 | 241 | 20 | 1.1 % |
| 2 | 6 | 238 | 20 | 2.3 % |
| 3 | 9 | 235 | 20 | 3.4 % |
| 4 | 12 | 232 | 20 | 4.5 % |
| 6 | 18 | 226 | 20 | 6.8 % |
| 8 | 24 | 220 | 20 | 9.1 % |

The numbers are governed by a transparent identity: timely-rescue **supply ≈
`n_units × ⌊W / service⌋`** (here **3 rescues per unit** in a 75-min window at 25
min/rescue), which is **far below the 244 reachable demand** — so even 8 units
meet < 10 % of demand. *This gap is the quantitative case for pre-positioning
resources and for triage, not a deficiency to hide.*

**Secondary axis — dispatch delay × units** (`CAP_DELAYS = {0, 30, 60}`; the
needs-rescuer pool is delay-invariant, so its 264 split moves between reachable  <!-- forbidden-ok: 264 -->
and geometry as the delay rises): geometry-unreachable goes **6 → 20 → 34** at
delay 0/30/60 (matching the §4a finding), while the supply-limited
`rescued_in_time` per unit is **delay-invariant** (the window span `W` is the same
regardless of when it starts) — i.e. **supply, not the dispatch delay, is the
binding constraint** on timely rescue here.

**Invariants (asserted in code + `tests/test_rescue_capacity.py`):**

| invariant | result |
|---|---|
| three outcomes sum to the 264 needs-rescuer count in every cell | ✓ |  <!-- forbidden-ok: 264 -->
| unlimited units → `capacity_deferred = 0`, recovers the geometry-only set (20) — the layer is a strict refinement | ✓ |
| `rescued_in_time` monotone non-decreasing in unit count | ✓ (3→6→9→12→18→24) |
| capacity binds (1 unit leaves demand unmet) | ✓ |
| 2-D baseline cell (delay 30, units 3) reconciles with the 1-D sweep + `run_pipeline` | ✓ |

**Reading.** Geometry alone caps timely rescue at **92.4 %** of demand (244/264);  <!-- forbidden-ok: 264 -->
the residual 20 have no surviving corridor and are never imputed. The robust
result is the **shape** of the curve (sharp unmet demand at realistic unit
counts); the absolute % moves with the PoC `service`/`W` and is not a measured
capability.

## 4d. Operator-facing output (illustrative mockup)

The delivery layer is **people** (가족·복지사·지자체), so the operator's concrete
artifact is an **illustrative operator-view mockup** in the style of the rescue
PoC output (`scripts/operator_output_demo.py` → `docs/figures/operator_output.png`
+ `docs/operator_output_sample.txt`) — representative rows on synthetic-and-tagged
geometry, not a deployed product:

- a **prioritized dispatch table** (operator/responder view): priority rank,
  household id, 4-class triage (적시 구조 / 자력 대피 / 용량 지연 / 도달 불가, from
  §4c), assembly point & action (집결지/조치), surviving road (생존 도로), and
  responder ETA;
- an **auto-generated resident SMS** (Korean, short, imperative) — the figure
  shows the self-evacuation example ("지금 바로 … 해안로를 따라 … 대피하세요"); the
  system likewise composes a rescued-immobile message ("구조대가 약 N분 뒤 도착 …")
  and, honestly, a capacity-deferred one (no false ETA; mutual-aid + shelter-in-place).

> **Illustrative output of the research pipeline on synthetic-and-tagged
> geometry — NOT a deployed product/UI, NOT real residents.** Names are
> placeholders (○○○), filled from the operator's resident registry in a
> deployment.

## 5. Honest limitations

- **Single-fire (영덕) proof-of-concept.** Not multi-fire validated; not an
  operational system.
- **Rescue capacity is a PoC parameter, not a measured 영덕 fire-service value**
  (§4c). The `n_rescue_units` × `service_time` supply model is illustrative; the
  result is the demand–supply **curve** and the **direction** (supply far below
  reachable demand), never a single "X rescued" or "lives saved." Geometry-
  unreachable stays separate and reported.
- **The surviving-ingress layer reduces, not solves, unreachability.** The
  unreachable set is an expected, reported output.
- **Contrasts are the robust result; absolute magnitudes are illustrative**,
  given a single-fire PoC and synthetic auxiliary inputs.
- **In this regime, vehicles are ~15–20× faster than the fire's spread on a
  well-connected lattice**, so the resident-side `b → c` exposure cost is small
  (most *safe* refuges are also rescue-reachable). The rescue-reachability
  constraint's value concentrates in (i) excluding the occasional safe-but-cut-off
  refuge — policy (c) re-routes those residents — and (ii) the responder-side
  dispatch / unreachable accounting, where the survival-aware route materially
  lowers ingress exposure versus a fire-blind shortest path.
- **Time resolution is overpass-scale (hours).** Rules out tactical (minute-scale)
  use, exactly as the parent routing report states. This constraint carries
  unchanged into the §3a withdrawal trigger lines: they are **planning-scale,
  not tactical** — a line derived from hour-resolution hazard slices cannot
  time a minute-scale withdrawal.
- **The round-trip margin's `t_load` is assumed, and same-route egress is
  doctrine reported by one practitioner (N = 1), not a measurement.** Both are
  swept (`scripts/run_margin_sweep.py`, `data/processed/margin_sweep.json`);
  conclusions that move under that sweep are reported as directions, not
  point estimates.

## 6. Data provenance (real vs synthetic)

| input | real source (loader implemented) | fallback used here |
|---|---|---|
| Hazard `P(ignite)` per cell/time | `spread_v2.forward_sim` on FIRMS+ERA5+DEM (git-ignored) | **SYNTHETIC** growing severity-scaled envelope on the real 영덕 extent |
| Walk + drive networks | OSMnx `walk`/`drive`, reprojected to EPSG:5179, disk-cached | **SYNTHETIC** 8-connected lattice on the extent (real algorithm) |
| Refuges (대피소·긴급대피장소) | 행정안전부 / 공공데이터포털 (data.go.kr) GeoJSON/CSV at `cfg.shelters_path`, or OSM POIs | **SYNTHETIC** coastal assembly nodes + inland open-space POIs |
| Depots (119안전센터) | 소방청 공공데이터포털 / OSM `amenity=fire_station` at `cfg.depots_path` | **SYNTHETIC** near-town nodes |
| Village-edge origins (Session 8, `rescue_routing_village_edge.json`) | VWorld 건물통합정보 — **attempted 2026-08-29, HTTP 502 on every endpoint** (recorded in the artifact and `BLOCKERS.md`) | **OSM** building snapshot (124 buildings, `source="osm"`; coverage is a small region-dependent fraction — never a building count) |
| Wildland vegetation (WUI definition, Session 8) | — | **OSM** `natural=wood` / `landuse=forest` polygons, disk-cached (`source="osm"`) |

Every synthetic/assumed input is tagged `source = "synthetic"` (or `assumed`) in
the outputs (`rescue_routing.json::provenance`) and in `RescueConfig.provenance()`.

**Assumed numeric inputs (all config-driven, all swept where relevant):** elderly
walk 0.7 m/s; vehicle 40 km/h; walk cutoff 0.5; vehicle cutoff 0.7; responder
dispatch delay 30 min; safety margin 12 min; responder time budget 75 min;
corridor sample spacing 150 m; immobile fraction 0.3; seed 20250603.

**Rescue-capacity PoC inputs (§4c — `RescueCapacityConfig`, NOT measured 영덕
fire-service capacity):** `n_rescue_units` (swept {1,2,3,4,6,8}); per-rescue
service time 25 min; window `W` reuses `responder_time_budget_min` (75 min). These
are flagged `PoC_not_measured` in `RescueCapacityConfig.provenance()`.

## 7. Reproducibility

Deterministic (fixed seed, config-driven, no hidden globals). Synthetic-fallback
runs need no network or API key. Regenerate the four-way + sweeps with
`python scripts/run_rescue_routing.py && python scripts/make_rescue_figures.py`;
the reconciled baseline + 2-D sweeps with `python scripts/verify_rescue_routing.py
[--sweep vehicle|fc|capacity]` (the **capacity** sweep writes
`data/processed/rescue_capacity.json` + `docs/figures/rescue_capacity.png`).
Tests: `tests/test_rescue_routing.py` (ingress-survival at a known slice; rescuer
prefers a longer surviving corridor; road→cell sampling orientation regression;
영덕 four-way sums to N and `rescue_reachable ⊆ safe`) and
`tests/test_rescue_capacity.py` (three-way partition; unlimited-capacity recovers
the geometry-only set; priority respected; monotone in units).
