# Rescue-aware evacuation routing — methods note

*What it is, why it is built this way, what it does **not** claim, and where every
input comes from. Companion to `src/wildfireguardian/routing/rescue.py` and
`rescue_demo.py`; regenerate results with `python scripts/run_rescue_routing.py &&
python scripts/make_rescue_figures.py`.*

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

## 5. Honest limitations

- **Single-fire (영덕) proof-of-concept.** Not multi-fire validated; not an
  operational system.
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
  use, exactly as the parent routing report states.

## 6. Data provenance (real vs synthetic)

| input | real source (loader implemented) | fallback used here |
|---|---|---|
| Hazard `P(ignite)` per cell/time | `spread_v2.forward_sim` on FIRMS+ERA5+DEM (git-ignored) | **SYNTHETIC** growing severity-scaled envelope on the real 영덕 extent |
| Walk + drive networks | OSMnx `walk`/`drive`, reprojected to EPSG:5179, disk-cached | **SYNTHETIC** 8-connected lattice on the extent (real algorithm) |
| Refuges (대피소·긴급대피장소) | 행정안전부 / 공공데이터포털 (data.go.kr) GeoJSON/CSV at `cfg.shelters_path`, or OSM POIs | **SYNTHETIC** coastal assembly nodes + inland open-space POIs |
| Depots (119안전센터) | 소방청 공공데이터포털 / OSM `amenity=fire_station` at `cfg.depots_path` | **SYNTHETIC** near-town nodes |

Every synthetic/assumed input is tagged `source = "synthetic"` (or `assumed`) in
the outputs (`rescue_routing.json::provenance`) and in `RescueConfig.provenance()`.

**Assumed numeric inputs (all config-driven, all swept where relevant):** elderly
walk 0.7 m/s; vehicle 40 km/h; walk cutoff 0.5; vehicle cutoff 0.7; responder
dispatch delay 30 min; safety margin 12 min; responder time budget 75 min;
corridor sample spacing 150 m; immobile fraction 0.3; seed 20250603.

## 7. Reproducibility

Deterministic (fixed seed, config-driven, no hidden globals). Synthetic-fallback
runs need no network or API key. Tests: `tests/test_rescue_routing.py`
(ingress-survival at a known slice; rescuer prefers a longer surviving corridor;
road→cell sampling orientation regression; 영덕 four-way sums to N and
`rescue_reachable ⊆ safe`).
