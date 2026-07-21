# WildfireGuardian · 산불 골든타임 — 시연 (CodeFair 2026 demo)

`wildfire_demo.html` is a single self-contained file. **Double-click to open**
(works on `file://`, offline, no server/build). It renders a deterministic
6-scene walkthrough of the predict → route → rescue coupling on the 2025 영덕
(Yeongdeok) fire. Autoplays on a loop for the 시연영상; the presenter can
pause / scrub / step scenes (Space = play·pause, ← / → = step scene) for live
발표 and Q&A.

The screenshot `divergence_1920x1080.png` is the S2→S3 signature moment.

## Every on-screen number is regenerated from a committed artifact

```
# 1. metrics + committed point geometry  (pure stdlib, offline, always runs)
python scripts/export_demo_data.py          -> data/processed/demo_data.json
# 2. route geometry: real 영덕 OSM walk net vs the committed observed-approx front
python scripts/build_demo_routes.py         -> data/processed/demo_geometry.json
```

`export_demo_data.py` reads `demo_geometry.json` and inlines the full bundle into
the HTML's `<script type="application/json">` block, so the demo is bulletproof
offline. `build_demo_routes.py` loads the committed OSM graph
(`data/processed/demo_yeongdeok_walk.graphml`) and runs **offline and
bit-identically**; delete that file and it re-pulls the graph from OpenStreetMap.
Seed `20250603`. No randomness anywhere.

## Provenance of each figure

| Shown | Value | Source |
|---|---|---|
| 예측 AUC (pooled) | 0.905 | `spread_v2_lofo.json :: pooled_auc` |
| 일반화 AUC (mean-of-folds ± std) | 0.890 ± 0.107 | `spread_v2_lofo.json :: mean/std(per_fire_auc)`, recomputed & asserted |
| 심각도 ≫ 풍향 | ≈44× | `spread_v2_lofo.json :: severity_over_direction_ratio` |
| 최중요 변수 | days_since_rain (#1) | `spread_v2_lofo.json :: permutation_importance` |
| 대상 원점 N | 439 | `rescue_routing.json :: n_origins` |
| 스스로 대피 불가 | 167 / 439 = 38.0% | `rescue_verify_fc.json :: needs_rescuer.baseline` |
| 구조 8팀 → 수요 대비 | 14.4% | `rescue_capacity.json :: sweep_units_baseline_delay[8]` |
| 미래 인지 경로 우회 | +110 min | `demo_geometry.json :: routes.future_aware.detour_min` |

Model: sklearn **HistGradientBoosting**, Leave-One-Fire-Out CV over 6 real Korean
fires. Data: NASA FIRMS (VIIRS+MODIS) · ERA5 · SRTM · ESA WorldCover; routing:
time-expanded graph + Dijkstra (OSMnx), Tobler (1993) elderly-walk correction.

## Honest scope (stated on screen, not hidden)

- **The drawn fire front is the committed *observed-approximate* perimeter**
  (ellipse reconstruction from public reporting), **not** the spread_v2
  prediction. The spread_v2 forward-sim isochrones + the router's own polylines
  are FIRMS-locked: they exist only in the git-ignored `routing_demo.npz`, and
  `run_routing_integration.py` aborts without the FIRMS bundle. Rather than
  fabricate a front, the demo computes the two routes **for real** on the live
  영덕 OSM network against that observed-approx front, and shows AUC 0.905 as the
  model's separately-validated skill. (The real spread_v2 run's aggregate
  contrast — naive 334.3 vs future-aware 23.1 prob·min — is committed in
  `routing_demo.json`.)
- **Rescue demand / capacity** are on real OSM roads with a **synthetic hazard**
  (FIRMS absent). The demo anchors on the real-OSM flip (N=439): 38.0% cannot
  self-evacuate; 8 teams meet 14.4% of that demand (the pre-flip synthetic
  baseline's "9.1% / <10%" is superseded and not mixed in). Contrasts are robust;
  absolute magnitudes are illustrative single-fire PoC figures.
- Footprint IoU is deliberately omitted from the main view (the 0.874 single-step
  value is dominated by shared burned area; the honest forward-sim envelope IoU is
  ≈0.40). AUC is the headline accuracy metric.
