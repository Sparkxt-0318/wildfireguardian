# 3D booth replay: 영덕, the night of 2025-03-25 (`web/finals3d.html`)

**Who proposed what.** The author asked for a 3D replay as the booth centrepiece
(2026-09-29, laptop session). The deadline rule it draws (two readings of one satellite
record, below) was proposed in the same session by the review agent and is recorded in
the docstring of `scripts/build_finals3d.py` before any of its numbers existed.

## What the page shows

A 3D terrain of 영덕 (SRTM, the committed snapshot) at night, replayed from 21:25 KST on
2025-03-25 for 600 minutes:

| layer | source | how it is drawn |
|---|---|---|
| fire | `obs_stack` of `data/processed/routing_demo_canonical.npz`: FIRMS detections, cumulative, 500 m cells, one surface per overpass | a cell glows from the pass that first detected it; burned ground turns charred; the flaming edge glows |
| "could already be burning" haze | the same record: a cell first detected at pass *k* was not detected at pass *k*−1 | amber haze between those two passes (the satellite could not see it) |
| roads | committed OSM walk graph snapshot | an edge turns amber when the pessimistic reading closes it and red when the satellite confirms fire on it (cell membership, 50 m sampling) |
| houses | 도로명주소 주건물 (`data/processed/external/juso_buildings_yeongdeok/`) with their floor count | green / amber / red by the rule below; grey = not on the walk network within 500 m |
| refuges | committed OSM shelter snapshot | cyan beams |
| model forecast (off by default) | `haz_stack` of the same file, p ≥ 0.5 crossing, leave-one-complex-out **hindcast** | violet hatching |

Every count on screen is computed in the browser from `web/assets/finals3d/data.js`; no
number is typed into the page. The payload is built by `python scripts/build_finals3d.py
assemble`, which also writes `data/processed/finals3d/finals3d_scene.json` (counts at
fixed minutes, the ROI, the payload hash). `tests/test_finals3d.py` re-derives those
counts from the payload and checks the hash.

## The rule each house is coloured by

For every building-origin walk node, the latest departure (10-minute grid, up to 600
minutes) at which the committed time-aware router still reaches a refuge without
entering a burning cell (`measure_last_safe_departure.lsd_search`, unchanged), computed
twice from the one observation:

* **R** (optimistic): each cell burns from the pass that detected it;
* **L** (pessimistic): each cell burns from just after the previous pass.

Every fire history consistent with the record (under the assumptions below) puts the true
deadline between the two. The R reading at the committed elderly speed is the same
computation as K-SPREAD metric 4's observation "truth" (same router, same step hazard, same
building population), and `tests/test_finals3d.py` checks that its per-building classes
equal the ones recorded in `data/processed/benchmark/leaderboard_v0_2.json`. At replay
minute *t* a house is

* **green** "지금 떠나면 걸어서 대피 가능" when *t* ≤ LSD_L (open under every consistent history);
* **amber** "위성으로는 판단 불가" when LSD_L < *t* ≤ LSD_R (the record cannot decide);
* **red** "걸어서 나가기엔 이미 늦음" when *t* > LSD_R or LSD_R = −1 (closed even on the optimistic reading).

The three walking speeds are 1.2 m/s (assumed, general adult), 0.7 m/s (the committed
elderly value, `config/default.yaml` `pedestrian.elderly_flat_speed_ms`) and 0.5 m/s
(assumed, frail). Only the speed changes between runs; slope handling, refuges, grid and
budget are the committed ones.

## Caveats, first

* **A replay, not a forecast.** The houses are coloured from what satellites saw
  afterwards. The page says so on screen (「재생 모드 … 실시간 예측이 아닙니다」).
* **Never detected = never burned** (A4 in `docs/regrade_three_way.md`), and a detection
  means part of a 500 m cell burned, not that the fire front reached the road. A cloud,
  smoke or a missed pixel would make a green house optimistic.
* **The bracket is an outer bound under the cell-box reading.** Real spread couples
  neighbouring cells; the L reading lets every later-detected cell burn at once.
* The router samples the field **bilinearly**, the road colours use **cell membership**
  (`docs/regrade_three_way.md` §A5 describes the difference).
* **Walk network coverage**: the 영덕 walk network covers only part of the fire core
  (the README's coverage caveat applies to every absolute count).
* **Refuges are the OSM shelter set**, not designated wildfire refuges
  (`docs/refuge_provenance.md`).
* **Exaggeration**: building footprint and height and terrain height are scaled up so a
  house is visible from a kilometre away; the page states the factors.
* A walk longer than 90 minutes is flagged on the house card as possibly needing a
  vehicle; it is not recoloured.

## What it does not show

Where anyone actually was, who needed help, or whether a vehicle could have reached them.
No count on this page is a count of people or households, and none is a claim about lives.

## Rebuilding

```
python scripts/build_finals3d.py lsd --bound R --speed 0.7    # six runs: R/L x 1.2/0.7/0.5
python scripts/build_finals3d.py assemble
cd web/src/finals3d && npm ci && npm run build                # three.js bundle, offline
```

Open `web/finals3d.html` from disk; it needs no network.
