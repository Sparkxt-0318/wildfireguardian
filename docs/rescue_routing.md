# Rescue-aware evacuation routing — methods note

> **Round 2 · Phase 1 — real-data flip (2026-07).** The committed
> `data/processed/rescue_*.json` have been flipped from synthetic fallbacks to
> **real OpenStreetMap** road/refuge/depot geometry (fire **hazard** + **terrain**
> remain synthetic, pending the FIRMS bundle). The numbers throughout this methods
> note (§4a/§4b/§4c below) are the **current real-OSM results** (N = 439). The
> pre-flip synthetic baseline is preserved at
> `data/processed/rescue_baseline_synthetic/` and in the OLD column of
> `docs/REPORT_ROUND2_P1.md`, which also has the full OLD-vs-NEW comparison and the
> new real-road finding (§3 there: 63 of 143 dispatchable homes reachable only via a
> survival-aware detour). The **method** described here is unchanged.

*What it is, why it is built this way, what it does **not** claim, and where every
input comes from. Companion to `src/wildfireguardian/routing/rescue.py` and
`rescue_demo.py`; regenerate results with `python scripts/run_rescue_routing.py &&
python scripts/make_rescue_figures.py`.*

> **Results draft:** see `docs/results_rescue_draft.md` for the honestly-hedged
> results section (claims ledger + the assumption-light walk-failure rate `w` ≈
> 9–17 %, derived from the committed fc sweep via `scripts/derive_walk_failure.py`).
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
set N = 439**, regenerable with `python scripts/verify_rescue_routing.py`
(`data/processed/rescue_verify.json`). The verify sweep runs at full N, so its
**baseline cell equals the headline** (asserted in code and by a test). Roads,
refuges, and depots are **real OpenStreetMap** geometry; the fire hazard and
terrain remain synthetic. Treat absolute counts as illustrative (single-fire PoC +
synthetic hazard/terrain); the robust claim is the **direction/contrast**.

**Baseline:** walk 0.7 m/s · vehicle 40 km/h · pedestrian cutoff 0.5 · vehicle
cutoff 0.7 · dispatch delay 30 min · safety margin 12 min · resident/responder
budget 600/75 min · seed 20250603 · roads/refuges/depots real OSM, hazard/terrain
synthetic (tagged).

**Two metrics, never compared across scales** (labelled `route_type` in the
output): resident exposure is over **pedestrian** routes; responder over
**vehicle** routes; both in `prob·min`.

**Why N = 439 (not the synthetic 452):** the real OSM `walk` graph is ~6× denser
than the synthetic lattice (8 439 vs ~1 400 nodes); the origin-scan *procedure* is
unchanged, only its stride knob is adapted (`REAL_OSM_SCAN_STRIDE = 18`, up from the
synthetic default 3) so the sampled-candidate count stays near the synthetic scale
and the full-N verification sweeps stay tractable. (An earlier synthetic-era change,
`scan_stride=3` + a fire-reach latitude band, had taken the origin count from 407 to
452; the real-OSM flip is a second, independent change to the same knob.)

**Four-way split @ baseline (sums to 439):** already-safe **262** · saved-by-
rescue-reachable-refuge **10** · no-walk-rescuer-reaches **143** · unreachable
**24**. Self-evacuable (already-safe + saved) **272 (62 %)**; needs-rescuer
(no-walk-rescuer + unreachable) **167 (38 %)**. Resident exposure (pedestrian,
prob·min) naive/​b/​c = **9.16 / 1.59 / 2.22** (paired b vs c over the same 155
origins = 2.22 / 2.22; c re-routed 0 off a cut-off refuge, down from 2 on the
synthetic lattice — with 50 real refuges most safe walks already land on a
rescue-reachable one). Responder ingress (vehicle, prob·min) shortest-path/​
survival-aware = **6.12 / 1.71** (dispatch 143, unreachable 24) — survival-aware
routing is still ≈3.6× (≈72 %) lower exposure than shortest-path, even though both
absolute numbers are ~20× larger than on the synthetic lattice (real vehicle
corridors traverse more hazard cells).

**2-D sweep — unreachable count (dispatch delay × vehicle cutoff), full N = 439:**

| delay \ cutoff | 0.50 | 0.60 | 0.70 | 0.80 | 0.90 |
|---|---|---|---|---|---|
| 0 min | 13 | 7 | **6** | 4 | 0 |
| 15 | 38 | 20 | 11 | 7 | 3 |
| 30 (baseline) | 60 | 41 | **24** | 13 | 7 |
| 45 | 70 | 62 | 51 | 38 | 11 |
| 60 | 72 | 71 | **66** | 60 | 24 |

(`already_safe`=262 and `saved`=10 are constant across the grid; `no_walk` = 167 −
unreachable, since the needs-rescuer pool (167) doesn't move with the vehicle
knobs. See `docs/figures/rescue_sweep_2d.png`.) On the pre-flip synthetic lattice
the same table topped out at unreachable=34 (delay 60, cutoff 0.7); at full N on
**real roads the baseline unreachable is 24 and the dispatch 0→60 bracket at
cutoff 0.7 is 6 → 66** — a much sharper penalty than the synthetic 6 → 34, because
real corridors have less redundancy against a delayed responder than the forgiving
synthetic lattice did.

**Robustness verdict:**

| quantity | verdict | basis |
|---|---|---|
| unreachable rises with dispatch delay (0→60: **6→66** at cutoff 0.7) | **robust direction** | monotone non-decreasing for *every* cutoff |
| unreachable rises as the vehicle cutoff gets harsher | **robust direction** | monotone for *every* delay |
| `no_walk_rescuer` (ranges 95–167 across the vehicle knobs, mean 136) | **complement of unreachable within the constant 167-home needs-rescue pool** — rel-spread 0.53, *wider* than the synthetic lattice's 0.09 (i.e. real roads make the dispatch/unreachable split noticeably more vehicle-knob-sensitive); its *level* is still set primarily by the assumed immobile fraction (0.3) + walk cutoff (§4b), not vehicle cutoff/speed directly | grid 95–167 |
| `unreachable` point estimate (24) | **directional only** (grid 0–72) — report the direction + range, not the point value | central rel-spread 2.31 (wider than the synthetic 1.17) |

`rescue_reachable ⊆ safe` holds at every cutoff. The headline four-way and the
sweep's baseline cell are identical.

**New real-road finding (§3 of `docs/REPORT_ROUND2_P1.md`):** of the 143
dispatch-reachable homes, **63 are reachable only via a survival-aware detour** —
their **direct** ingress corridor is already cut before the responder's direct ETA.
On the synthetic lattice every dispatchable home also had a surviving *direct*
corridor, so unlimited rescue units recovered all of dispatch; on real roads
unlimited units instead recover only the **deadline-feasible** subset (80 of 143).
See §4c.

## 4b. The rescue burden is assumption-driven (immobile_fraction × walk_cutoff)

The vehicle×delay sweep (§4a) only *splits* a **fixed** needs-rescuer pool into
`no_walk_rescuer` vs `unreachable`; it never moved the pool's size. The two knobs
that set that size are `immobile_fraction` and `walk_cutoff`. Decompose the
partition: `self_evacuable = already_safe + saved`, `needs_rescuer =
no_walk_rescuer + unreachable`; the headline "38% need a rescuer" is `167/439`.

**How `immobile_fraction` routes origins (from the code):** `_immobile_homes`
draws a **random `f·N`** origins (`rng.choice(..., replace=False)`) and the loop
does `if n in immobile: needs_rescue; continue` — they **skip the walk checks
regardless of whether they could have walked out**. So `already_safe`/`saved` are
computed only over the mobile `(1−f)` pool and **fall as `f` rises** — they are
**not** invariant to `f` (the §4a "constant 262/10" was true only for the
vehicle×delay grid, where `f` was fixed).

**f × c sweep, full N = 439** (`scripts/verify_rescue_routing.py --sweep fc`,
`rescue_verify_fc.json`; baseline cell f=0.30, c=0.50 == headline, asserted):

`needs_rescuer` (= can't self-evacuate on foot):

| immobile `f` \ walk cutoff | 0.40 | **0.50** | 0.60 |
|---|---|---|---|
| 0.15 | 118 (27%) | 108 (25%) | 100 (23%) |
| **0.30** | 177 (40%) | **167 (38%)** | 162 (37%) |
| 0.45 | 240 (55%) | 232 (53%) | 226 (51%) |

`self_evacuable` (= already_safe + saved): 0.15→{321, 331, 339}; 0.30→{262, 272,
277}; 0.45→{199, 207, 213} across walk cutoff {0.40, 0.50, 0.60}. Monotone as
expected: `self_evacuable` rises with a more permissive walk cutoff; `needs_rescuer`
rises with `f` and as the walk cutoff falls. See `docs/figures/rescue_sweep_fc.png`.

**Revised verdict on the burden numbers:**

| quantity | verdict | basis |
|---|---|---|
| `needs_rescuer` = **38 %** (167/439) | **directional, not a number** | grid 100–240 (23–55 %); **halving the assumed immobile fraction (0.30→0.15) drops it 38 %→25 %** (167→108 @ c=0.5) |
| `no_walk_rescuer` = **143** | **re-classified directional** w.r.t. the assumption knobs (grid 76–204, rel-spread 0.90 — wider than the synthetic lattice's 0.46); the §4a "robust" held *only* against the vehicle knobs | moves with both `f` and `walk_cutoff` |
| `saved` = **10** | **rescue-meaningful, not a mislabel** — a pedestrian route to a *rescue-reachable* refuge (the resident-side win); down from 34 on the synthetic lattice because with 50 real refuges most naive-unsafe walks already land on a rescue-reachable one; it moves with `f` (over the mobile pool), so not f-invariant | — |

**Defensible headline today:** *"Under walk cutoff 0.5 and 30 % assumed immobile,
167/439 (38 %) cannot self-evacuate on foot; at 15 % assumed immobile this falls to
108/439 (25 %). The share is driven by the assumed immobile fraction plus the
slow-elder pedestrian regime — not by the vehicle-side knobs."* Even at the most
optimistic swept assumptions **more than a fifth (≥23 %)** still cannot
self-evacuate — that direction is robust; the exact percentage is not. **Unchanged
keeper:** the §4a dispatch-delay → unreachable trend remains a robust direction,
and is now sharper on real roads (6 → 66 vs the synthetic 6 → 34).

## 4c. Rescue capacity / triage — the demand–supply gap (PoC)

§4a–4b size the **demand**: of N = 439 origins, **167 need a rescuer** = **143
dispatch-reachable** (a vehicle corridor survives long enough to reach them) +
**24 geometry-unreachable** (no surviving ingress). They never asked whether the
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
unit reaches it in time). `geometry_unreachable` (the 24) is unchanged. The three
outcomes **partition the 167-home needs-rescuer pool**.

> **These capacity numbers are PoC parameters, NOT measured 영덕 fire-service
> capacity.** The deliverable is the demand–supply **curve**, never a single
> "X rescued" or any "lives saved" figure.

**Capacity sweep @ baseline (PoC: `service = 25 min/rescue`, `W = 75 min`,
units mobilised at the 30-min dispatch delay), full N = 439:**

| rescue units | rescued_in_time | capacity_deferred | geometry_unreachable | % of demand met | % of reachable demand met |
|---:|---:|---:|---:|---:|---:|
| 1 | 3 | 140 | 24 | 1.8 % | 2.1 % |
| 2 | 6 | 137 | 24 | 3.6 % | 4.2 % |
| 3 | 9 | 134 | 24 | 5.4 % | 6.3 % |
| 4 | 12 | 131 | 24 | 7.2 % | 8.4 % |
| 6 | 18 | 125 | 24 | 10.8 % | 12.6 % |
| 8 | 24 | 119 | 24 | 14.4 % | 16.8 % |

The numbers are governed by a transparent identity: timely-rescue **supply ≈
`n_units × ⌊W / service⌋`** (here **3 rescues per unit** in a 75-min window at 25
min/rescue), which is **far below the 143 reachable demand** — so even 8 units
meet < 15 % of demand. *This gap is the quantitative case for pre-positioning
resources and for triage, not a deficiency to hide.*

**New real-road finding — dispatchable ≠ direct-corridor-open.** On the synthetic
lattice, unlimited rescue units rescued *all* of dispatch (every dispatchable home
also had a surviving *direct* corridor). On **real roads this invariant breaks**:
**63 of the 143** dispatchable homes are reachable **only via a survival-aware
detour**, with their **direct** corridor already cut before the responder's direct
ETA (`closing_window < 0`). The capacity model credits only the direct corridor, so
those 63 homes stay `capacity_deferred` even at unlimited units — unlimited units
instead recover the **deadline-feasible** subset, **80 of 143** (rescued
80 = deadline-feasible 80). This is a genuine consequence of real road topology
(alternate routes the synthetic lattice didn't have) and is reported, not tuned
away; the verify script's invariant was corrected accordingly (`n_dispatch_reachable`
now also reports `n_dispatch_deadline_feasible` = 80 and
`n_dispatch_direct_corridor_cut_reachable_by_detour` = 63).

**Secondary axis — dispatch delay × units** (`CAP_DELAYS = {0, 30, 60}`; the
needs-rescuer pool is delay-invariant, so its 167 split moves between reachable
and geometry as the delay rises): geometry-unreachable goes **6 → 24 → 66** at
delay 0/30/60 (matching the §4a finding — sharper than the synthetic lattice's
6 → 20 → 34), while the supply-limited `rescued_in_time` per unit is
**delay-invariant** (the window span `W` is the same regardless of when it starts)
— i.e. **supply, not the dispatch delay, is the binding constraint** on timely
rescue here.

**Invariants (asserted in code + `tests/test_rescue_capacity.py`):**

| invariant | result |
|---|---|
| three outcomes sum to the 167 needs-rescuer count in every cell | ✓ |
| unlimited units → recovers the **deadline-feasible** dispatch subset (80 of 143; not `capacity_deferred = 0`, see the detour finding above) | ✓ |
| `rescued_in_time` monotone non-decreasing in unit count | ✓ (3→6→9→12→18→24) |
| capacity binds (1 unit leaves demand unmet) | ✓ |
| 2-D baseline cell (delay 30, units 3) reconciles with the 1-D sweep + `run_pipeline` | ✓ |

**Reading.** Geometry alone caps timely rescue at **85.6 %** of demand (143/167);
the residual 24 have no surviving corridor and are never imputed. Of that
geometry-reachable 85.6 %, a further 63/143 need a detour rather than the direct
corridor (above). The robust result is the **shape** of the curve (sharp unmet
demand at realistic unit counts); the absolute % moves with the PoC `service`/`W`
and is not a measured capability.

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
  given a single-fire PoC and a synthetic fire hazard + terrain (roads, refuges,
  and depots are real OSM geometry as of Round 2 · Phase 1).
- **In this regime, vehicles are ~15–20× faster than the fire's spread on a
  well-connected lattice**, so the resident-side `b → c` exposure cost is small
  (most *safe* refuges are also rescue-reachable). The rescue-reachability
  constraint's value concentrates in (i) excluding the occasional safe-but-cut-off
  refuge — policy (c) re-routes those residents — and (ii) the responder-side
  dispatch / unreachable accounting, where the survival-aware route materially
  lowers ingress exposure versus a fire-blind shortest path.
- **Time resolution is overpass-scale (hours).** Rules out tactical (minute-scale)
  use, exactly as the parent routing report states.

## 6. Data provenance (real vs synthetic)

**As of Round 2 · Phase 1, roads/refuges/depots use the real source below; only
hazard + terrain still use the synthetic fallback** (pending the FIRMS bundle):

| input | real source (loader implemented) | used in this run | synthetic fallback (offline / no OSM cache) |
|---|---|---|---|
| Hazard `P(ignite)` per cell/time | `spread_v2.forward_sim` on FIRMS+ERA5+DEM (git-ignored) | **SYNTHETIC** (still) | growing severity-scaled envelope on the real 영덕 extent |
| Walk + drive networks | OSMnx `walk`/`drive`, reprojected to EPSG:5179, disk-cached | **REAL OSM** ✓ | 8-connected lattice on the extent (real algorithm) |
| Refuges (대피소·긴급대피장소) | 행정안전부 / 공공데이터포털 (data.go.kr) GeoJSON/CSV at `cfg.shelters_path`, or OSM POIs | **REAL OSM** ✓ (50 refuges) | coastal assembly nodes + inland open-space POIs |
| Depots (119안전센터) | 소방청 공공데이터포털 / OSM `amenity=fire_station` at `cfg.depots_path` | **REAL OSM** ✓ (4 depots) | near-town nodes |

Every input is tagged with its actual `source` (`osm` / `synthetic` / `assumed` /
`sampled candidates`) in the outputs (`rescue_routing.json::provenance`) and in
`RescueConfig.provenance()` — nothing above is asserted without that tag.

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
