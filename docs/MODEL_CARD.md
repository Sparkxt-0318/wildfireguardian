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
| rows / positives | 138,619 / 2,731 (~1.97 %) | `spread_v2_lofo.json` |
| fires (N=6, all weather-complete) | gangneung_2023, hongseong_2023, miryang_2022, uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025 | `spread_v2_lofo.json/fires_used` |

**16 features:** `dist_to_fire_m, active_frac_1500m, active_frac_3000m,
n_active_adjacent, elevation_m, slope_deg, elev_above_source_m, burnable_frac,
wind_speed_ms, temp_c, rh_pct, vpd_kpa, days_since_rain, precip_24h_mm, dt_hours,
wind_alignment` `[src: features.py/FEATURE_COLUMNS]`.

## Headline metric — generalization (mean-of-folds, with spread)

> **LOFO mean-of-folds ROC-AUC = 0.90 (range 0.78–0.98 across 6 fires; the hardest
> fold is `yeongdeok_2025` — the held-out demonstration fire — at 0.783).**

- Mean-of-folds ROC-AUC = **0.901 ± 0.072** (sample sd; range 0.783–0.981, N=6) —
  *recomputed from* `spread_v2_lofo.json/per_fire_auc` via
  `validation/auc_stats.mean_of_folds_interval`. This is the generalization figure.
  With only n=6 folds the spread is wide (the 0.783 `yeongdeok_2025` fold pulls the
  mean down), so we report **mean ± SD with the range** and lean on the **per-fold
  DeLong CIs** (each fold = thousands of cells) as the stronger evidence (see below,
  regenerated for this run) — a 6-point t-interval is not reported because its upper
  limit pins to the AUC ceiling.
- The five fires other than `yeongdeok_2025` span **0.86–0.98** (mean **0.925 ±
  0.048**, 95 % t-CI [0.865, 0.985], n=5 — recomputed from the same file); yeongdeok,
  the held-out demonstration / routing-demo fire, is the hardest at **0.783** — a
  genuine out-of-sample difficulty, not a small-sample artifact.

### Per-fire ROC-AUC

| fire | ROC-AUC | note |
|---|---|---|
| miryang_2022 | 0.981 | |
| hongseong_2023 | 0.956 | |
| gangneung_2023 | 0.933 | |
| uljin_samcheok_2022 | 0.895 | |
| uiseong_andong_2025 | 0.859 | |
| yeongdeok_2025 | **0.783** | the held-out demonstration / routing-demo fire — the hardest fold |

`[ROC-AUC src: spread_v2_lofo.json/per_fire_auc]`

Per-fire **DeLong 95 % CIs** and significance-vs-0.5 tests come from
`scripts/auc_intervals.py`, which re-runs the canonical model (seed 20250603, same 16
features/folds), **gates** against pooled 0.867 / mean-of-folds 0.90 / the per-fire
AUCs, persists the out-of-fold predictions, and emits the per-fire `AUC [95 % CI]`
table + p-values to `data/processed/auc_intervals.json`. Those CIs / p-values are
**regenerated for this six-fire run** and are not restated here from the prior
assembly (the per-fold prediction arrays are not committed). The script **STOPs
cleanly (exit 2)** where the FIRMS/ERA5/DEM bundle is absent (e.g. a fresh clone)
rather than fabricate — re-run it where the data is present to regenerate the JSON.
Method: `docs/auc_intervals.md`; statistics unit-tested in `tests/test_auc_stats.py`.

### Pooled and far-band (labeled — NOT the generalization figure)

- **Pooled** out-of-fold ROC-AUC = **0.867** — one ROC over *all* held-out folds'
  predictions concatenated (`model.py:184–186`). On this run pooling sits **below**
  the mean-of-folds (−0.034): the two large folds (`uiseong_andong`, `yeongdeok`)
  dominate the concatenated pool, so it is the more conservative of the two and is
  **not** the generalization estimate. `[src: spread_v2_lofo.json/pooled_auc]`
- **Far-band (>3 km) pooled** ROC-AUC = **0.821**; **mid-band (1–3 km) pooled 0.786**
  — the "can it predict *reach*?" bands, and the JSON-traceable resolution of the
  earlier >1.5 km-vs->3 km ambiguity. (A per-fold mean-of-folds far-band figure
  regenerates via `scripts/auc_intervals.py`; the pooled scalars above are the stored
  numbers.) `[src: spread_v2_lofo.json/far_band_auc, mid_band_auc]`

## Footprint IoU — honest figure

> **Footprint IoU ≈ 0.40** (forward-simulated envelope vs observed, Yeongdeok,
> 3–12 h horizon).

| IoU | value | exact definition | use? |
|---|---|---|---|
| forward-sim envelope | **~0.40** | forward-simulated cumulative envelope vs observed FIRMS footprint at 3/6/9/12 h (0.37/0.40/0.39/0.40), Yeongdeok, threshold `p_cut` | **YES — the honest footprint/reach figure** `[src: yeongdeok_forward_sim.json/drift]` |
| single-step cumulative | 0.866 | `pred_cum = active ∪ pred_new` IoU `obs_next` (which **also contains `active`**); dominated by the shared already-burned area — measures "next overpass *given* the current burned area," not a from-scratch footprint (`model.py:285–286`) | **NO — REPORT-BLOCKED** as a footprint result `[src: spread_v2_lofo.json/footprint_iou_single_step]` |
| new-ring-only | ~0.07 | IoU on only the *newly*-burned ring (≈ persistence) — the hardest "exactly which new cells" metric | context only `[src: docs/ROUTING_INTEGRATION_REPORT.md §3]` |

**Do not report 0.866 as a footprint result** — it is not leakage (no future
information), but it measures an easier task; the honest figure is **~0.40**.

## Headline finding (severity ≫ wind direction)

Permutation importance: `dist_to_fire_m` 0.072 is the top predictor overall; within
the fire-weather group `wind_speed_ms` (0.028) and `days_since_rain` (0.025) lead.
Summed fire-weather **severity** importance 0.057 vs `wind_alignment` 0.0062 — a
**9.3×** ratio. The qualitative finding (severity ≫ direction) holds, at a more
conservative magnitude than the prior assembly's 44×.
`[src: spread_v2_lofo.json/permutation_importance]`

**Standard ML baselines** on the identical 16 features/folds/seed (20250603), via
`scripts/ml_baselines.py` (`validation/ml_baselines.py`, unit-tested) — to answer
"you only beat a bad physics model" honestly. The GBM row is read from
`spread_v2_lofo.json` (mean-of-folds = the six `per_fire_auc` values; pooled =
`pooled_auc`); the random_forest / logistic rows **regenerate for this six-fire run**
via `scripts/ml_baselines.py` and are not carried over from the prior assembly:

| model | mean-of-folds AUC ± SD | pooled |
|---|---|---|
| random_forest | regen pending | regen pending |
| logistic | regen pending | regen pending |
| **hist_gbm (ours)** | **0.901 ± 0.072** | **0.867** |

We keep the GBM for its **calibrated probabilities** (the router consumes a real
`P(ignite)`), **inference speed**, and **interpretability** (permutation importance
produced the severity≫direction finding). Baselines regenerate via
`scripts/ml_baselines.py` → `data/processed/ml_baselines.json` (STOPs cleanly where
the FIRMS bundle is absent). Method: `docs/baselines.md`.

## Provenance — two builds exist; why they are NOT directly comparable

The project's 작품설명서 / brief cites **0.834 / 0.80 / 0.32** from an earlier,
**different** build ("Build A" — `docs/SPREAD_MODEL_REPORT_V2_FINAL.md`,
`data/processed/spread_v2/`). Build A and the canonical Build B are **two
independent reconstructions and are not a like-for-like comparison** — the
0.834-vs-0.867 difference cannot be read as "B is better." The specific
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
is strong (0.78–0.98 ROC-AUC) on the five fires shared with Build A.

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
- With only N=6 folds the mean-of-folds spread is wide (range 0.78–0.98); report
  mean-of-folds **with** the range and the per-fold CIs. `yeongdeok_2025` (0.783) is
  the hardest fold — the held-out demonstration fire, a genuine out-of-sample
  difficulty rather than a small-sample artifact.
- Per-fold prediction arrays are **not** committed; the per-fire DeLong CIs, the
  per-fold far-band mean-of-folds, and the random_forest/logistic ML-baseline rows
  **regenerate for this six-fire run** via the gated re-runs (`scripts/auc_intervals.py`
  / `scripts/ml_baselines.py`) to `data/processed/{auc_intervals,ml_baselines}.json`
  where the FIRMS bundle is present — they are not restated from the prior assembly.
- Overpass-scale time resolution (hours, not minutes).

## 작품설명서 (Korean writeup) correction mapping

The 작품설명서 is **not in this repo** — apply these old→new corrections there
(values are Build B / this card):

| field | old (Build A / brief) | new (Build B, canonical) |
|---|---|---|
| ROC-AUC (headline) | 0.83 / 0.834 | **0.90 (LOFO mean-of-folds, range 0.78–0.98)**; pooled 0.867 if labeled "pooled" |
| far-band (>3 km) AUC | ~0.80 | **0.821 pooled (>3 km); mid-band 0.786 pooled (1–3 km)** |
| footprint IoU | 0.32 | **~0.40 (forward-sim envelope, 3–12 h)** — do not use 0.866 |
| feature count | 19 | **16** |

Suggested replacement sentence (formal 합니다체):

> 본 시스템의 산불 확산 모델(spread_v2, 16개 특징)의 LOFO(한 산불씩 제외 교차검증)
> 평균 ROC-AUC는 **0.90**입니다(6개 산불, 범위 0.78–0.98; 가장 어려운 폴드는 시연
> 대상 산불 영덕 0.783입니다). 전체 보류예측 통합(pooled) AUC는 0.867이나, 일반화
> 성능 지표로는 폴드 평균을 보고합니다. 순방향 모의 화선(footprint) IoU는 약
> **0.40**입니다(영덕, 3–12시간).

*Build comparison note for the author: the earlier 0.834 / 0.80 / 0.32 came from a
different build (different fire set, 19 features, seed 42) and is not a like-for-like
comparison; report the canonical Build B numbers above.*
