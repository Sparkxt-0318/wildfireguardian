# The rescue pipeline on the real 영덕 spread surface (NH-057)

**Decided by the author 2026-09-12: 「I want you to run the whole thing.」** Run the same
day on the author's laptop, which is the only machine holding the inputs the cloud
sandbox never had. This page states what was run, what came out, and what it does not
show. Registered keys: `rrh_*` in `docs/NUMBERS.json`
(`scripts/register_rescue_routing_real_hazard.py`).

## 1. Why this run exists

Every dispatch sheet committed before today (`outputs/dispatch/`,
`outputs/dispatch_full/`) was made on a **synthetic** hazard over real OSM roads, and
every judge-facing surface said so in one sentence: 「실제 확산면으로 만든 출동 지시서는
아직 없습니다」. WFG-242 recorded why no cloud lap could close that sentence: the run
where both axes are real emitted no per-origin record, and re-running the routing needs
data the sandbox does not hold. This run closes it.

## 2. What was run

`scripts/run_rescue_routing_real_hazard.py` assembles a `RescueScenario` from

| input | source | real? |
|---|---|---|
| hazard | `data/processed/routing_demo_canonical.npz` `haz_stack` (leave-one-fire-out forward simulation of the 2025 영덕 fire; 500 m grid; 0–720 min) | **yes** — the same field every routing surface cites |
| walk network, drive network | `data/snapshots/` 2026-07-24 OSM graphs, laid out exactly as `scripts/run_rescue_routing_full.py` lays them out (`data/cache/` not read) | **yes** (geometry) |
| refuges, depots | `data/snapshots/` 2026-07-24 OSM shelters / fire stations | **yes** |
| ignition proxy | centroid of the slice-0 burning core (the rule `scripts/run_real_roads_real_hazard_slope.py` already uses) | derived from the hazard |
| origins | `_scan_origins` on the walk network, stride 18, not burning at t0, inside the reach band | **no** — sampled candidates, not households |
| walk timing | flat elderly speed; the OSM loader attaches no slope | **no** slope |
| vehicle side | config: cutoff 0.7, 40 km/h, dispatch delay, safety margin, 75-min budget | assumptions |

The script **refuses to run** if any real loader falls back to its synthetic layer, and
no synthetic terrain, envelope or coastline is constructed. Then `run_pipeline` and the
per-origin `classify_all` from the full-coverage script run unchanged; the artifact is
serialized like `rescue_routing_full.json` (with `origins_full`) so
`scripts/generate_dispatch_outputs.py --full` can read it directly.

## 3. Result

Artifact: `data/processed/rescue_routing_real_hazard.json`. Sheets:
`outputs/dispatch_real_hazard/20260912T153043Z/` (86 clusters at eps 500 m, every sheet
within one page; nothing sent).

| quantity | value | key |
|---|---:|---|
| origins scanned | 444 | `rrh_n_origins` |
| already safe on the fire-blind walk | 281 | `rrh_already_safe` |
| saved only by a rescue-reachable refuge | 29 | `rrh_saved_by_rescue_reachable_refuge` |
| needs rescue, vehicle can reach | 132 | `rrh_no_safe_pedestrian_route` |
| needs rescue, no surviving vehicle ingress | 2 | `rrh_no_surviving_vehicle_ingress` |
| refuges (OSM) / rescue-reachable | 50 / 28 | `rrh_n_refuges`, `rrh_n_refuges_rescue_reachable` |
| dispatch clusters (eps 500 m) | 86 | `rrh_n_clusters` |

Of the 134 needing rescue, 133 are the immobile draw (config `immobile_fraction` 0.3)
and 1 is a mobile resident with no safe pedestrian route: on this hazard, at this
budget, the walk-out question is almost entirely decided by mobility, not by the fire.

## 4. What this does NOT show

- **Not a household count.** 444 origins are walk-graph nodes at stride 18. The
  classes are proportions of a sample of the road network, not of the population.
- **Not comparable to the synthetic-hazard sheets.** Different hazard, different extent
  (the canonical 500 m grid, not the region bbox at 375 m), different origin set. The
  1-in-444 vs 32-in-441 「unreachable」 contrast is between two different worlds and is
  not a finding.
- **Not slope-aware.** The walk timing is flat; the slope-aware canonical routing run
  (`docs/real_roads_real_hazard.md`) is a separate arm and emits no dispatch document.
- **The hazard is a simulation of the observed fire, not the observation.** It is the
  leave-one-fire-out forward simulation; what the forecast buys against the observed
  footprint is a separate question (`docs/regrade_against_observed.md`).
- **The vehicle side is unchanged assumptions**, and the two `no_surviving_vehicle_ingress`
  sheets print the honest 사유 line (`docs/routing_limitations.md` §7).

## 5. Reproduce

    python scripts/run_rescue_routing_real_hazard.py          # ~1 min on the laptop
    python scripts/generate_dispatch_outputs.py --full \
        --source "$PWD/data/processed/rescue_routing_real_hazard.json" \
        --out-root "$PWD/outputs/dispatch_real_hazard"
    python scripts/register_rescue_routing_real_hazard.py --check

Needs `data/snapshots/` (committed) and `data/processed/routing_demo_canonical.npz`
(committed); no network, no `data/cache/`.
