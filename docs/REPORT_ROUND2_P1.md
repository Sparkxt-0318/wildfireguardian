# Round 2 — Phase 1: flipping the rescue/evacuation routing stack to real data

**Scope of this pass (honest, up front).** This PR flips the rescue-aware
evacuation routing stack from its synthetic fallbacks to **real OpenStreetMap
geometry** for the road networks, refuges, and responder depots on the 영덕
(Yeongdeok) extent, and reruns every rescue-routing analysis on that geometry.
It is a **PARTIAL real flip**: the highest-value input — the fire **hazard**
surface (the spread_v2 forward-sim) — and the **terrain** (land–sea mask) remain
**synthetic**, because the git-ignored FIRMS fire-data bundle that the forward-sim
needs is **not present** in this environment and cannot be fetched here. Every
survival / reachability number below is therefore still driven by a *synthetic
fire on a synthetic coastline over real roads*. Contrasts are the robust result;
absolute magnitudes stay illustrative until the real hazard is flipped in (Phase 2).

All numbers in this report trace to a committed JSON:

- **NEW (real)** → `data/processed/rescue_routing.json`, `rescue_verify.json`,
  `rescue_verify_fc.json`, `rescue_capacity.json`.
- **OLD (synthetic)** → `data/processed/rescue_baseline_synthetic/*.json`
  (an in-tree snapshot of the pre-flip committed synthetic outputs, kept so the
  OLD column is verifiable in the same commit).

---

## 1. What flipped, what did not — provenance table

| Input | Before (synthetic) | After (this PR) | `source` tag | Notes |
|---|---|---|---|---|
| Drive (vehicle) network | 8-connected lattice on synthetic extent | **Real OSM `drive` graph**, 영덕 bbox, EPSG:5179, disk-cached | `osm` | 1 664 nodes / 4 251 edges |
| Walk (pedestrian) network | slope-aware lattice (synthetic) | **Real OSM `walk` graph**, EPSG:5179, disk-cached | `osm` | 8 439 nodes / 22 266 edges; new `load_walk_network` loader |
| Refuges / shelters | seeded coastal + inland POIs | **Real OSM POIs** (`amenity=shelter`/`community_centre`, `leisure=park`) | `osm` | 50 refuges |
| Responder depots | 2 seeded near-town nodes | **Real OSM fire stations** (`amenity=fire_station`) | `osm` | 4 depots: 영덕소방서, 영덕119안전센터, 강구119안전센터 ×2 |
| Fire **hazard** surface | severity-scaled envelope | **still synthetic** (labelled) | `synthetic` | **BLOCKED** — needs FIRMS bundle for spread_v2 forward-sim |
| **Terrain** / land–sea mask | synthetic coastal DEM | **still synthetic** (labelled) | `synthetic` | **BLOCKED** — DEM lives in the FIRMS bundle |
| Origins (elderly homes) | sampled candidates | sampled candidates | `sampled candidates` | real per-household locations are private (by design) |
| Speeds / cutoffs / delays / seed | assumed constants | unchanged | `assumed` | walk 0.7 m/s, veh 40 km/h, cut 0.5/0.7, dispatch 30 min, immobile 0.3, seed 20250603 |

**Origin count.** The OSM `walk` graph is ~6× denser than the synthetic lattice
(8 439 vs ~1 400 nodes). The origin-scan *procedure* is unchanged; only its stride
knob is adapted (`REAL_OSM_SCAN_STRIDE = 18`, up from the synthetic default 3) so
the sampled-candidate count stays near the synthetic scale (**N = 439** real vs
**452** synthetic) and the full-N verification sweeps stay tractable  <!-- forbidden-ok: 452 -->
(~61 s/`_split_counts` at N = 439).

---

## 2. Headline routing numbers — OLD (synthetic) vs NEW (real)

All at the single baseline: dispatch delay 30 min, vehicle cutoff 0.7, walk cutoff
0.5, immobile fraction 0.3, seed 20250603.

| Metric | OLD (synthetic) | NEW (real OSM) | Source key |
|---|---|---|---|
| Origins N | 452 | **439** | `n_origins` |  <!-- forbidden-ok: 452 -->
| Four-way — `already_safe` | 154 | **262** | `four_way_counts` |  <!-- forbidden-ok: 154 -->
| Four-way — `saved_by_rescue_reachable_refuge` | 34 | **10** | " |
| Four-way — `no_safe_pedestrian_route` (needs rescuer, reachable) | 244 | **143** | " |
| Four-way — `no_surviving_vehicle_ingress` (beyond reach) | 20 | **24** | " |
| Four-way sums to N | 452 ✓ | 439 ✓ | `four_way_sums_to_n` |  <!-- forbidden-ok: 452 -->
| Refuges rescue-reachable | 19 / 20 | **24 / 50** | `n_refuges_rescue_reachable` |
| Resident exposure — naive (prob·min) | 24.06 | **9.16** | `resident_exposure.naive.mean` |
| Resident exposure — future-aware→any | 3.55 | **1.59** | `…future_aware_any.mean` |
| Resident exposure — future-aware→rescue-reachable | 3.47 | **2.22** | `…future_aware_rescue.mean` |
| Policy-c re-routed off a cut-off refuge | 2 | **0** | `policy_c_changed_refuge_count` |
| Responder exposure — survival-aware (veh, prob·min) | 0.079 | **1.71** | `responder_exposure.survival_aware.mean` |
| Responder exposure — shortest-path | 0.172 | **6.12** | `…shortest_path.mean` |
| Dispatch (reachable, needs rescuer) | 244 | **143** | `n_dispatch` |
| Unreachable (beyond reach) | 20 | **24** | `n_unreachable` |
| Need-rescuer immobile / walk-cut split | 136 / 128 | **132 / 35** | `n_need_rescue_immobile` / `_walk_cut` |
| Dispatch-delay 0→60 trend, beyond-reach **(full-N, cutoff 0.7)** | 6 → 34 | **6 → 66** | `rescue_verify.json / grid` |
| Dispatch-delay 0→60 trend, `no-ingress` (sampled sweep) | 2 → 13 | **1 → 21** | `sensitivity_sweep.responder_dispatch_delay_min` |
| Vehicle-cutoff 0.4→0.8, `no-ingress` (sampled sweep) | 12→6 | **21→2** | `sensitivity_sweep.vehicle_cutoff` |
| Walk-failure `w` (full-N, assumption-light) — range | 0.333–0.450 | **0.091–0.174** | `walk_failure.summary` (verify_fc) |
| `needs_rescuer` baseline % of N (full-N) | 58.4 % (264) | **38.0 % (167)** | `needs_rescuer` (verify_fc) |  <!-- forbidden-ok: 264 -->
| Capacity: % demand met @ 3 units (PoC) | 3.4 % | **5.4 %** | `sweep_units_baseline_delay` (capacity) |
| Capacity: geometry ceiling on timely rescue | 92.4 % | **85.6 %** | `geometry_ceiling_pct` (capacity) |

### Reading the changes honestly

- **Far more residents are already safe on real roads (154 → 262).** Real 영덕 road  <!-- forbidden-ok: 154 -->
  topology gives residents genuine connectivity to refuges the coarse synthetic
  lattice lacked, so `already_safe` and the reachable/self-evacuable share rise and
  `no_safe_pedestrian_route` falls sharply (244 → 143). This is the single biggest
  shift and it is a *geometry* effect, not a hazard effect.
- **`saved_by_rescue_reachable_refuge` drops (34 → 10) and policy-c re-routes 0
  origins (was 2).** With 50 real refuges (24 rescue-reachable) most residents whose
  naive walk is unsafe already reach *some* rescue-reachable refuge, so the marginal
  origins the rescue constraint uniquely "saves" are fewer. This looks worse for the
  feature's headline count, and we report it as-is: the resident-side win is smaller
  on this synthetic-fire/real-road combination.
- **Beyond-reach rises slightly (20 → 24)** and the full-N dispatch-delay trend is
  much steeper: beyond-reach at cutoff 0.7 rises 6 → 34 with delay 0→60 on the
  synthetic lattice but 6 → **66** on real roads — real corridors are far more brittle
  to a delayed responder than the forgiving synthetic lattice.
- **Responder exposures are ~20× larger in absolute terms (0.079 → 1.71 survival-
  aware; 0.172 → 6.12 shortest-path)** because real vehicle corridors traverse more
  cells of the (synthetic) hazard than the short synthetic lattice hops did. The
  *contrast* — survival-aware ≈ 3.6× lower exposure than shortest-path — survives and
  is the robust result; the absolute magnitudes are hazard-synthetic and will change
  again when the real hazard lands.
- **The assumption-light rescue burden falls on real roads.** Full-N,
  `needs_rescuer` drops from 58.4 % (264) to **38.0 % (167)** of origins, and the  <!-- forbidden-ok: 264 -->
  walk-failure fraction of *mobile* residents `w` falls from **0.33–0.45** to
  **0.09–0.17** — real pedestrian connectivity lets many more elders reach a refuge
  on foot. `w` stays approximately flat across the immobile fraction (max spread
  0.035), so this is a genuine walkability signal, not an artifact of the assumed
  immobile fraction. Both directions (`needs_rescuer ↑` with immobile fraction and as
  the walk cutoff falls; `self_evacuable ↑` with the walk cutoff) remain monotone.

---

## 3. New real-data finding — dispatchable ≠ direct-corridor-open

On the **synthetic** run, unlimited rescue units rescued *all* dispatchable homes
(the capacity invariant `unlimited → deferred = 0` held). On **real** roads it does
**not**: **63 of 143** dispatchable homes are reachable **only via a
survival-aware detour** while their **direct** ingress corridor is already cut
before the responder's direct ETA (`closing_window < 0`). The capacity model credits
only the direct corridor, so those homes are deferred even with unlimited units.

This is a genuine consequence of real road topology (real networks have alternate
routes the synthetic lattice did not) and is **reported, not tuned away**. The verify
script's capacity invariant was corrected from the synthetic-only assumption
(`unlimited → all dispatch rescued`) to the mathematically-correct statement
(`unlimited → the deadline-feasible subset`), with the new counts
`n_dispatch_deadline_feasible` and `n_dispatch_direct_corridor_cut_reachable_by_detour`
persisted to `rescue_capacity.json`. No core routing/capacity logic or parameter was
changed.

---

## 4. What could NOT be flipped, and why

### 4.1 Fire hazard + terrain — BLOCKED on the FIRMS bundle

`spread_v2.forward_sim` produces the per-cell ignition-probability hazard the router
consumes. It needs the git-ignored **FIRMS fire-data bundle** (`firms_data.zip` →
`data/raw/firms/`), which was **absent** here (`data.data_available() == False`;
`data/raw/` holds only `.gitkeep`). It also gates `scripts/run_routing_integration.py`
(it aborts with `return 2` without the bundle) and therefore `make_routing_figures.py`
(which needs the integration run's `routing_demo.npz`). This bundle needs NASA FIRMS +
Copernicus/CDS credentials to build and cannot be fetched in this sandbox.

**Manual-download checklist to unblock the full hazard flip:**

| # | Dataset | Source | Target path | Expected schema |
|---|---|---|---|---|
| 1 | FIRMS active-fire detections (MODIS+VIIRS) | NASA FIRMS (`firms.modaps.eosdis.nasa.gov`, MAP_KEY) | `data/raw/firms/<fire>_detections.csv` | `latitude, longitude, acq_date, acq_time, frp, confidence, satellite, instrument, timestamp` |
| 2 | SRTM-class DEM (metres, EPSG:4326) | e.g. OpenTopography / USGS EarthExplorer | `data/raw/firms/<fire>_dem.tif` | single-band float elevation, ~30 m |
| 3 | ESA WorldCover land-cover (uint8) | ESA WorldCover 2021 (`esa-worldcover.org`) | `data/raw/firms/<fire>_fuel.tif` | class codes; burnability via `data_layers_manifest.json` |
| 4 | ERA5 reanalysis (3-hourly, 0.25°) | Copernicus CDS (`cds.climate.copernicus.eu`, CDS API key) | `data/raw/firms/<fire>_era5.nc` | CDS zip of two HDF5 NetCDFs: instant `u10,v10,t2m,d2m` + accum `tp` |
| 5 | Manifests | (ship with bundle) | `data/raw/firms/fire_manifest.json`, `…/data_layers_manifest.json` | fire metadata + WorldCover→burnable map |

Set `$WFG_FIRMS_DIR` or unzip into `data/raw/firms/`; then `data.data_available()`
returns True and the hazard flip (Phase 2, canonical model **spread_v2**, seed
20250603) can proceed. **Do NOT** substitute `spread_v2_xgb` (abandoned build).

### 4.2 Government shelter/depot files — used OSM fallback (sanctioned)

The 행정안전부 전국 대피소 표준데이터 and 소방청 119안전센터 현황 (data.go.kr) require a
serviceKey / manual portal download and were not present. Per the brief, we fell
through to **OSM** POIs (`source="osm"`), which for depots yielded the actual
영덕소방서 / 영덕119안전센터 / 강구119안전센터. To use the authoritative files instead:
drop them at `data/raw/shelters/` and `data/raw/depots/` and point
`RescueConfig.shelters_path` / `depots_path` at them (loaders tag `source="real"`).
data.go.kr datasets: "전국 대피소 표준데이터", "소방청_전국 119안전센터 현황".

---

## 5. Regenerate everything (exact commands)

Real OSM geometry is fetched by OSMnx and disk-cached under `data/cache/osm/`
(git-ignored). With the cache present the runs are fully offline; a fresh
environment re-fetches from OSM/Overpass automatically.

```bash
# 1. Rescue routing headline (four-way split, exposure contrasts, sampled sweep)
python scripts/run_rescue_routing.py                 # REAL (OSM) by default
python scripts/run_rescue_routing.py --synthetic     # pre-flip synthetic baseline

# 2. Full-N verification / reconciliation sweeps
python scripts/verify_rescue_routing.py --sweep vehicle    # dispatch delay × vehicle cutoff
python scripts/verify_rescue_routing.py --sweep fc         # immobile fraction × walk cutoff
python scripts/verify_rescue_routing.py --sweep capacity   # demand–supply gap

# 3. Figures (bilingual; captions state real OSM vs synthetic hazard/terrain)
python scripts/make_rescue_figures.py

# 4. BLOCKED until the FIRMS bundle is placed (see §4.1):
#    python scripts/run_routing_integration.py   # aborts: FIRMS dataset not found
#    python scripts/make_routing_figures.py       # needs routing_demo.npz from the above
```

---

## 6. Tests

- All pre-existing **synthetic-fallback** rescue tests still pass (offline CI path
  unchanged): `tests/test_rescue_routing.py`, `tests/test_rescue_capacity.py`.
- New **real-data** tests (`tests/test_rescue_routing_real.py`), skip-if-absent on
  the OSM cache + osmnx (mirroring the FIRMS/SRTM pattern): four-way sums to N;
  `rescue_reachable ⊆ safe`; dispatch/unreachable reconciliation; and dispatch-delay
  monotonicity (`no_surviving_vehicle_ingress` non-decreasing in delay) on the real
  graph. All 5 pass here; they skip cleanly where OSM is unavailable.
- Full suite: ****371 passed / 8 skipped / 1 failed**** (prior baseline in this environment: 360 passed /
  14 skipped / 1 failed — the 1 failure is `test_spread_v2_xgb`, the abandoned build
  the guardrails forbid running; xgboost is intentionally not installed).

---

## 7. Traceability

Every number above is read directly from a committed JSON — NEW from
`data/processed/rescue_{routing,verify,verify_fc,capacity}.json`, OLD from the
in-tree snapshot `data/processed/rescue_baseline_synthetic/`. Provenance blocks in
each NEW JSON carry the per-input `sources` map (`osm` / `synthetic` / `assumed` /
`sampled candidates`) and the `honesty` note stating the hazard + terrain remain
synthetic pending FIRMS.
