# Building-origin routing on the 도로명주소 건물 layer, 영덕 (WFG-275)

**Run 2026-09-13 on the author's laptop**, from the committed layer of
`docs/juso_buildings_yeongdeok.md`, restricted to **주건물** (`bul_dpn_se == "M"`, source
`juso_main`). Artifact: `data/processed/building_origin_routing_juso_main_yeongdeok.json`
(new filename; the committed 124-footprint artifact `building_origin_routing.json` is
untouched). Docs and `data/processed/` only; nothing registered, nothing on a judge-facing
surface. Command:

    python scripts/run_building_origin_routing.py --regions yeongdeok_2025 \
        --source juso_main --out "$PWD/data/processed/building_origin_routing_juso_main_yeongdeok.json"

Same rule as the committed building arm: slope-aware DiGraph walk network from the
snapshot store (60 m sampling, |slope| ≤ 0.6), the 50 OSM refuges, the canonical LOFO
hazard, p_cut 0.5, 600-min budget, 10-min step, `net.nearest_node` as the snapper, and the
committed origin filter (not burning at t = 0, inside the reach band). Routed once per
distinct walk node; buildings inherit their node's class.

## 1. Reconciliation of the population

| step | buildings | note |
|---|---:|---|
| 주건물 with centroid inside the canonical box | 19,959 | EPSG:5179 native; 건물관리번호 unique (no duplicates); 부속건물 excluded |
| within 500 m of a walk node | 19,838 | snap distance median 27.8 m, p90 97.8 m, p99 413.5 m |
| **unsnappable** (> 500 m; listed individually in the artifact) | 121 | farthest 1,139 m from any mapped path — a statement about the walk graph, not the building |
| removed by the committed origin filter | 588 | already at p ≥ 0.5 at t = 0, or outside the reach band |
| **routable** | 19,250 | → 4,970 distinct walk nodes (median 3 buildings per node, max 59) |

Coverage denominator: the OSM arm routed 119 of 124 footprints on 108 nodes; this arm
routes 19,250 buildings on 4,970 nodes, 46× the nodes.

## 2. Result (forecast-graded, as the committed arm is)

| class | 도로명주소 주건물 (buildings) | share | OSM 124 arm (buildings) | share | committed stride arm (458 nodes) | share |
|---|---:|---:|---:|---:|---:|---:|
| both safe | 17,454 | 90.7 % | 109 | 87.9 % | 414 | 90.4 % |
| forecast-aware only | 1,606 | **8.34 %** | 10 | 8.4 % | 42 | 9.17 % |
| no safe route | **190** | 0.99 % | **0** | 0 % | 2 | 0.4 % |

At node level: 4,439 / 477 / 54 of 4,970.

- **The forecast-only share did not move.** 8.34 % against 8.4 % on the 124-footprint
  sample and 9.17 % on the stride sample. The OSM sample was 0.6 % of the building stock
  and spatially biased (`docs/building_sampling.md`), and it still returned the same
  proportion for this class. The resampling curve in the artifact says why: at N = 100
  the 95 % half-width of the forecast-only share is ±5 pp, at N = 500 ±2.1 pp, at N = 2,000
  ±1.1 pp; the OSM sample sat inside its own interval.
- **The class the sample could not see is the 「no safe route」 class.** 190 주건물 on 54
  walk nodes have no walk to any refuge that stays below the cutoff within budget on the
  forecast. The 124-footprint arm had zero of them; the stride arm had 2 nodes. That is the
  concrete thing the building layer adds: where the shortest walk enters the forecast fire
  and the time-aware search finds nothing, and how many buildings stand there.

## 3. What this does NOT show

- **Buildings are not verified occupied households.** The layer is an administrative
  inventory (건축물대장-linked); 주건물 says 「main structure」, not 「someone lives here」.
  No count here is a population.
- **Forecast-graded.** Classes are scored on the same LOFO forecast the route was planned
  on, like the committed arms; the observed-footprint reading of the route classes is
  `docs/regrade_three_way.md`, which was not run on this population.
- **500 m snap and 121 exclusions.** A building 600–1,100 m from the nearest mapped path is
  excluded, not imputed; the artifact lists each one.
- **Not the responder side.** No vehicle route, no rescue class; the rescue pipeline was
  not run from building origins.
- **One region.** 의성·안동 and 울진·삼척 have no cut of this layer yet.

## 4. Reproduce

    python scripts/run_building_origin_routing.py --regions yeongdeok_2025 --source juso_main \
        --out "$PWD/data/processed/building_origin_routing_juso_main_yeongdeok.json"   # ~6 min

Needs the committed juso artifact, the snapshot walk graph and `data/raw/firms_data/yeongdeok_2025_dem.tif`
(laptop-only DEM; the snapshot store's SRTM copy is the same raster).
