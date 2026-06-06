# Model card — `spread_v2` per-cell ignition model (canonical build)

> **Single source of truth** for the spread-model numbers reported across this
> repo. The canonical model is **Build B** — the build in the repository whose
> hazard surfaces produced **every** downstream result (routing exposures, the
> rescue four-way split, the walk-failure rate `w`, the dispatch-delay finding).
> You must report the model that produced the results. Every number is cited to a
> committed artifact or marked recomputed-from-`<file>`. No model code was changed
> to produce this card.

## Model id

| field | value | source |
|---|---|---|
| build | **Build B** (`src/wildfireguardian/spread_v2`) | — |
| task | per-cell `P(ignites by next satellite overpass)`, XGBoost | `spread_v2/model.py` |
| grid / CRS | 375 m / EPSG:5179 | `run_routing_integration.py` |
| seed | **20250603** | `spread_v2_lofo.json/seed` |
| evaluation | leave-one-fire-out (LOFO), hold out whole fires | `model.py::leave_one_fire_out` |
| n features | **16** | `spread_v2/features.py::FEATURE_COLUMNS` |
| rows / positives | 151,904 / 2,989 (~1.97 %) | `spread_v2_lofo.json` |
| fires (N=6, all weather-complete) | gangneung_2023, hongseong_2023, miryang_2022, uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025 | `spread_v2_lofo.json/fires_used` |

**16 features:** `dist_to_fire_m, active_frac_1500m, active_frac_3000m,
n_active_adjacent, elevation_m, slope_deg, elev_above_source_m, burnable_frac,
wind_speed_ms, temp_c, rh_pct, vpd_kpa, days_since_rain, precip_24h_mm, dt_hours,
wind_alignment` `[src: features.py/FEATURE_COLUMNS]`.

## Headline metric — generalization (mean-of-folds, with spread)

> **LOFO ROC-AUC = 0.89 (range 0.68–0.97 across 6 fires; the 0.68 fold,
> `gangneung_2023`, has only ~17 detections).**

- Mean-of-folds ROC-AUC = **0.890 ± 0.107** (sample sd; range 0.682–0.974, N=6)
  — *recomputed from* `spread_v2_lofo.json/per_fire_auc`. This is the
  generalization figure.
- Excluding the tiny `gangneung_2023` fold, the other five fires average **0.931**
  (0.878–0.974) — recomputed from the same file.

### Per-fire ROC-AUC

| fire | ROC-AUC | note |
|---|---|---|
| miryang_2022 | 0.974 | |
| hongseong_2023 | 0.945 | |
| yeongdeok_2025 | 0.941 | the demonstration fire (held out) |
| uljin_samcheok_2022 | 0.918 | |
| uiseong_andong_2025 | 0.878 | |
| gangneung_2023 | **0.682** | **~17 detections — fold far too small for a stable estimate; treat as noisy** |

`[src: spread_v2_lofo.json/per_fire_auc]`

### Pooled and far-band (labeled — NOT the generalization figure)

- **Pooled** out-of-fold ROC-AUC = **0.905** — one ROC over *all* held-out folds'
  predictions concatenated (`model.py:184–186`). Pooling is flattered by the
  larger/easier folds; it is **not** the generalization estimate (it sits only
  +0.016 above the mean-of-folds here). `[src: spread_v2_lofo.json/pooled_auc]`
- **Pooled far-band (>3 km)** ROC-AUC = **0.877**; mid-band (1–3 km) 0.870.
  **Per-fire far-band AUC is not stored**, so a mean-of-folds far-band cannot be
  computed without re-running LOFO — report this number **as pooled**, with that
  limitation. `[src: spread_v2_lofo.json/far_band_auc, mid_band_auc]`

## Footprint IoU — honest figure

> **Footprint IoU ≈ 0.40** (forward-simulated envelope vs observed, Yeongdeok,
> 3–12 h horizon).

| IoU | value | exact definition | use? |
|---|---|---|---|
| forward-sim envelope | **~0.40** | forward-simulated cumulative envelope vs observed FIRMS footprint at 3/6/9/12 h (0.37/0.40/0.39/0.40), Yeongdeok, threshold `p_cut` | **YES — the honest footprint/reach figure** `[src: yeongdeok_forward_sim.json/drift]` |
| single-step cumulative | 0.874 | `pred_cum = active ∪ pred_new` IoU `obs_next` (which **also contains `active`**); dominated by the shared already-burned area — measures "next overpass *given* the current burned area," not a from-scratch footprint (`model.py:285–286`) | **NO — REPORT-BLOCKED** as a footprint result `[src: spread_v2_lofo.json/footprint_iou_single_step]` |
| new-ring-only | ~0.07 | IoU on only the *newly*-burned ring (≈ persistence) — the hardest "exactly which new cells" metric | context only `[src: docs/ROUTING_INTEGRATION_REPORT.md §3]` |

**Do not report 0.874 as a footprint result** — it is not leakage (no future
information), but it measures an easier task; the honest figure is **~0.40**.

## Headline finding (severity ≫ wind direction)

Permutation importance: `days_since_rain` 0.077 is the top predictor; summed
fire-weather **severity** importance 0.102 vs `wind_alignment` 0.0023 — a **44×**
ratio. `[src: spread_v2_lofo.json/permutation_importance]`

## Provenance — two builds exist; why they are NOT directly comparable

The project's 작품설명서 / brief cites **0.834 / 0.80 / 0.32** from an earlier,
**different** build ("Build A" — `docs/SPREAD_MODEL_REPORT_V2_FINAL.md`,
`data/processed/spread_v2/`). Build A and the canonical Build B are **two
independent reconstructions and are not a like-for-like comparison** — the
0.834-vs-0.905 difference cannot be read as "B is better." The specific
non-comparability reasons:

1. **Different fire set.** Build A's 6th fold is `gangneung_donghae_2022`
   (weather-incomplete — 0-byte ERA5, weather = NaN); Build B's 6th fold is
   `gangneung_2023`. The builds even **disagree on `gangneung_2023`'s usability**
   (Build A *excluded* it as "1 transition, 8 positives"; Build B *included* it as
   a fold). `[src: data/processed/spread_v2/class_balance.json vs spread_v2_lofo.json]`
2. **Different features (16 vs 19, different definitions).** Build A uses
   FRP-intensity features (`frp_sum_nearby`, `frp_max_nearby`) and more directional
   terms (`wind_direction`, `downwind_distance_proj`, `v1_alignment`,
   `slope_alignment`); Build B uses none of those and adds `vpd_kpa`,
   `precip_24h_mm`, `dt_hours`, `elev_above_source_m`.
3. **Different seed** (Build A = 42; Build B = 20250603).
4. **Different evaluation code / package** (Build A = `scripts/spread_v2/` feature
   table; Build B = `src/wildfireguardian/spread_v2`).

Despite these differences, **both builds independently corroborate the central
finding** (fire-weather *severity* ≫ wind *direction* for far-field skill). No
across-the-board "improvement" of B over A is claimed here; B is canonical purely
**by consistency** — it is the model that produced every downstream result, and it
is strong (0.88–0.97 ROC-AUC) on the five fires shared with Build A.

## Downstream: rescue capacity / triage (PoC)

The rescue-routing layer that consumes this model's hazard surfaces now reports a
**demand–supply** split, not just demand. Of N = 452 영덕 origins, **264 need a
rescuer** = **244 dispatch-reachable** + **20 geometry-unreachable** (no surviving
ingress). A parameterized capacity model (`RescueCapacityConfig`,
`rescue.py::capacity_triage`, `--sweep capacity`) partitions the 264 into
**rescued_in_time / capacity_deferred / geometry_unreachable** using the existing
priority order (closing window) as the triage rule:

| rescue units | rescued_in_time | capacity_deferred | geometry_unreachable | % demand met |
|---:|---:|---:|---:|---:|
| 1 | 3 | 241 | 20 | 1.1 % |
| 3 (baseline) | 9 | 235 | 20 | 3.4 % |
| 8 | 24 | 220 | 20 | 9.1 % |

Timely-rescue supply ≈ `units × ⌊W/service⌋` (3 per unit at W = 75 min, service =
25 min) is far below the 244 reachable demand — the quantitative case for
pre-positioning + triage. **Capacity here is a PoC parameter, NOT measured 영덕
fire-service capacity**; report the curve, not a single "X rescued"/"lives saved".
At unlimited units `capacity_deferred → 0` and the honest geometry-unreachable set
(20) is recovered (asserted). Detail + figure: `docs/rescue_routing.md` §4c,
`docs/figures/rescue_capacity.png`, `data/processed/rescue_capacity.json`.

## Caveats

- Single-fire (영덕) downstream PoC; synthetic-and-tagged auxiliary routing data.
- Rescue **capacity** (unit count + service time) is a PoC parameter, **not**
  measured 영덕 fire-service capacity — the demand–supply result is a curve and a
  direction, never a single "X rescued" or "lives saved" figure (§ Downstream).
- The `gangneung_2023` fold (~17 detections) is too small for a stable AUC —
  report mean-of-folds **with** the range and this caveat.
- Per-fire far-band AUC and per-fold prediction arrays are **not** committed; only
  the pooled far-band and per-fire overall AUC scalars are stored.
- Overpass-scale time resolution (hours, not minutes).

## 작품설명서 (Korean writeup) correction mapping

The 작품설명서 is **not in this repo** — apply these old→new corrections there
(values are Build B / this card):

| field | old (Build A / brief) | new (Build B, canonical) |
|---|---|---|
| ROC-AUC (headline) | 0.83 / 0.834 | **0.89 (LOFO mean-of-folds, range 0.68–0.97)**; pooled 0.905 if labeled "pooled" |
| far-band (>3 km) AUC | ~0.80 | **0.877 (pooled)** |
| footprint IoU | 0.32 | **~0.40 (forward-sim envelope, 3–12 h)** — do not use 0.874 |
| feature count | 19 | **16** |

Suggested replacement sentence (formal 합니다체):

> 본 시스템의 산불 확산 모델(spread_v2, 16개 특징)의 LOFO(한 산불씩 제외 교차검증)
> 평균 ROC-AUC는 **0.89**입니다(6개 산불, 범위 0.68–0.97; 0.68은 탐지 약 17건의
> 소규모 산불 폴드입니다). 전체 보류예측 통합(pooled) AUC는 0.905이나, 일반화
> 성능 지표로는 폴드 평균을 보고합니다. 순방향 모의 화선(footprint) IoU는 약
> **0.40**입니다(영덕, 3–12시간).

*Build comparison note for the author: the earlier 0.834 / 0.80 / 0.32 came from a
different build (different fire set, 19 features, seed 42) and is not a like-for-like
comparison; report the canonical Build B numbers above.*
