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
| task | per-cell `P(ignites by next satellite overpass)`, sklearn `HistGradientBoostingClassifier` | `spread_v2/model.py` |
| grid / CRS | hazard **500 m**, routing 750 m / EPSG:5179 — ⚠ not 375 m: this card's LOFO numbers (151,904 rows) and the canonical hazard fields are 500 m products; 375 m is the RESCUE layer's own grid (`grid.hazard_cell_m`, `rescue.py`) | `run_routing_integration.py` (`grid.routing_integration_hazard_cell_m`) |
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
> `gangneung_2023`, has only ~8 positives).**

- Mean-of-folds ROC-AUC = **0.890 ± 0.107** (sample sd; range 0.682–0.974, N=6) —
  *recomputed from* `spread_v2_lofo.json/per_fire_auc` via
  `validation/auc_stats.mean_of_folds_interval`. This is the generalization figure.
  With only n=6 folds the spread is wide (the 0.68 `gangneung_2023` fold inflates the
  SD), so we report **mean ± SD with the range** and lean on the **per-fold DeLong
  CIs** (each fold = thousands of cells) as the stronger evidence (see below) — a
  6-point t-interval is not reported because its upper limit pins to the AUC ceiling.
- Excluding the tiny `gangneung_2023` fold, the other five fires average **0.931 ±
  0.036**, 95 % t-CI [0.887, 0.976] (n=5) — recomputed from the same file.

### Per-fire ROC-AUC

| fire | ROC-AUC | DeLong 95 % CI | note |
|---|---|---|---|
| miryang_2022 | 0.974 | [0.941, 0.989] | |
| hongseong_2023 | 0.945 | [0.916, 0.964] | |
| yeongdeok_2025 | 0.941 | [0.936, 0.946] | the demonstration fire (held out) |
| uljin_samcheok_2022 | 0.918 | [0.911, 0.924] | |
| uiseong_andong_2025 | 0.878 | [0.871, 0.884] | |
| gangneung_2023 | **0.682** | [0.577, 0.771] | **~8 positives — fold far too small for a stable estimate; treat as noisy** |

`[ROC-AUC src: spread_v2_lofo.json/per_fire_auc; DeLong CIs: scripts/auc_intervals.py]`

**All six folds are significant vs AUC = 0.5** (`gangneung_2023` p = 2.7×10⁻⁴; the
other five p ≪ 0.001) — the test hypothesis H1 needs. The per-fire DeLong CIs above
and those p-values come from `scripts/auc_intervals.py`, which re-runs the canonical
model (seed 20250603, same 16 features/folds), **gates** against pooled 0.905 /
mean-of-folds 0.890 / the per-fire AUCs, persists the out-of-fold predictions, and
emits the per-fire `AUC [95 % CI]` table + p-values to
`data/processed/auc_intervals.json`. The script **STOPs cleanly (exit 2)** where the
FIRMS/ERA5/DEM bundle is absent (e.g. a fresh clone) rather than fabricate — re-run
it where the data is present to regenerate the JSON. Method: `docs/auc_intervals.md`;
statistics unit-tested in `tests/test_auc_stats.py`.

### Pooled and far-band (labeled — NOT the generalization figure)

- **Pooled** out-of-fold ROC-AUC = **0.905** — one ROC over *all* held-out folds'
  predictions concatenated (`model.py:184–186`). Pooling is flattered by the
  larger/easier folds; it is **not** the generalization estimate (it sits only
  +0.016 above the mean-of-folds here). `[src: spread_v2_lofo.json/pooled_auc]`
- **Far-band (>3 km) mean-of-folds** ROC-AUC = **0.925** (n=3 fires with far-band
  positives); **pooled far-band 0.877**, mid-band (1–3 km) 0.870. The mean-of-folds
  far-band comes from the gated `scripts/auc_intervals.py` re-run (which also
  persists the per-fire far-band AUCs); the pooled scalars are stored.
  `[pooled src: spread_v2_lofo.json/far_band_auc, mid_band_auc; mean-of-folds: scripts/auc_intervals.py]`
  ⚠ On the corrected DEMs the pooled far-band reads **0.8408** — see the
  DEM-correction section below before quoting 0.877 anywhere.

## The 2026-08-02 DEM correction — what moved, what did not

The Uljin-Samcheok raster in the training bundle **filled the East Sea with a
ramp to −497 m** across 49 % of its extent, and LOFO trains every fold on the
one shared dataset, so every number on this card was measured with that raster
in the training set (`docs/dem_defect_2026-08-02.md`). The corrected re-run is
committed as
[`spread_v2_lofo_dem_corrected.json`](../data/processed/spread_v2_lofo_dem_corrected.json);
its control arm reproduces the committed values exactly on the pre-fix rasters,
which is what makes the deltas attributable to the DEM alone.

| quantity | committed (this card) | corrected DEMs | reading |
|---|---:|---:|---|
| mean-of-folds AUC | 0.8895 | 0.8943 | **+0.0048 — headline effectively unaffected** |
| pooled AUC | 0.9053 | 0.9036 | −0.0017 — same |
| **pooled far-band AUC** | **0.8766** | **0.8408** | **−0.0357 — a real change; carry this caveat with every far-band quote** |
| `elev_above_source_m` importance rank | 8 | 15 | the other real change |
| `vpd_kpa` importance | 0.00097 (rank 12) | 0.0015 (rank 11) | pre- vs post-DEM-fix values — there was never a "VPD unit fix" (HANDOFF §4-B) |

The corrected file declares `does_not_supersede`: the committed values remain
the reported ones **by recorded decision** (README §Round 3 — re-running the
committed artifacts would move figures the submission cites). What that decision
costs is exactly this section: the committed far-band is quotable only with the
corrected value beside it.

## Footprint IoU — honest figure

> **Footprint IoU ≈ 0.40** (forward-simulated envelope vs observed, Yeongdeok,
> 3–12 h horizon).

| IoU | value | exact definition | use? |
|---|---|---|---|
| forward-sim envelope | **~0.40** | forward-simulated cumulative envelope vs observed FIRMS footprint at 3/6/9/12 h (0.37/0.40/0.39/0.40), Yeongdeok, threshold `p_cut` | **YES — the honest footprint/reach figure** `[src: yeongdeok_forward_sim.json/drift]` |
| single-step cumulative | 0.874 | `pred_cum = active ∪ pred_new` IoU `obs_next` (which **also contains `active`**); dominated by the shared already-burned area — measures "next overpass *given* the current burned area," not a from-scratch footprint (`model.py:285–286`) | **NO — REPORT-BLOCKED** as a footprint result `[src: spread_v2_lofo.json/footprint_iou_single_step]` |  <!-- forbidden-ok: 0.874 -->
| new-ring-only | ~0.07 | IoU on only the *newly*-burned ring (≈ persistence) — the hardest "exactly which new cells" metric | context only `[src: docs/ROUTING_INTEGRATION_REPORT.md §3]` |

**Do not report 0.874 as a footprint result** — it is not leakage (no future  <!-- forbidden-ok: 0.874 -->
information), but it measures an easier task; the honest figure is **~0.40**.

## Permutation importance — what it measures, and what it does NOT establish

Permutation importance: `days_since_rain` 0.077 is the top-ranked feature; summed
fire-weather **severity** importance 0.102 vs `wind_alignment` 0.0023 — a **44×**
ratio. `[src: spread_v2_lofo.json/permutation_importance]`

⚠ **THIS SECTION WAS HEADED "Headline finding (severity ≫ wind direction)" AND
THAT CLAIM IS WITHDRAWN AS NOT ESTABLISHED.** The measurement above is real and
reproducible; the *conclusion* drawn from it was not supported. Three reasons,
each checkable:

1. **It sets a six-feature SUM against a single variable.** The severity group is
   `days_since_rain`, `vpd_kpa`, `rh_pct`, `temp_c`, `precip_24h_mm` and
   `wind_speed_ms`; `wind_alignment` is one feature. A sum of six will beat one
   almost regardless of what they measure.
2. **ERA5 is 0.25° (~28 km), so it does not resolve the wind the comparison is
   about.** The severity features are near-uniform across a single fire at a
   single instant, so they discriminate among *days and fires* — they set the
   magnitude of the reach — rather than placing ignitions *within* an overpass.
   `docs/ROUTING_INTEGRATION_REPORT.md` §"Honest nuance".
3. **It is a single point estimate.** Its spread across seeds and folds was never
   measured; recomputing it needs the same data dependency and is recorded as
   future work in `docs/auc_intervals.md`.

⚠ **This does NOT mean wind direction is unimportant.** It means this
instrument, on this weather product, cannot see it. Anyone quoting the ratio must
quote these limits with it.

⚠ **AND THE TOP-RANKED FEATURE MAKES THE MODEL WORSE OUT-OF-FOLD.** *Dropping*
`days_since_rain` — rank 1 at +0.07726 — **raises** mean-of-folds AUC by
**+0.0270** and far-band AUC by **+0.0533**, while lowering pooled by −0.0143;
`gangneung_2023` alone moves **+0.1705**. For **three of the six fires**
(gangneung_2023, uiseong_andong_2025, yeongdeok_2025) the ERA5 window contains
**zero** wet samples, so the feature anchors to the window START — an
acquisition parameter — and carries no rain information for half the training
set. *(Corrected 2026-08-10: an earlier revision said it "equals the window
length exactly" and is a "per-fire constant"; measured against the canonical
training table it is neither — it is elapsed time since acquisition start,
evaluated at overpass times, one value per overpass: gangneung a single 0.125 d,
uiseong_andong 17 values 0.25–5.25 d, yeongdeok 5 values 3.5–4.75 d. The A4
ablation deltas above are measured and unaffected.)* PHASE 14,
`docs/weather_dependency.md` §②.
**"Top-ranked by permutation importance" and "good for generalisation" are not
the same property**, and here they point in opposite directions.

**Standard ML baselines** on the identical 16 features/folds/seed (20250603), via
`scripts/ml_baselines.py` (`validation/ml_baselines.py`, unit-tested) — to answer
"you only beat a bad physics model" honestly:

| model | mean-of-folds AUC ± SD | pooled |
|---|---|---|
| random_forest | 0.920 ± 0.036 | 0.898 |
| logistic | 0.903 ± 0.060 | 0.826 |
| **hist_gbm (ours)** | **0.889 ± 0.107** | **0.905** |

Random forest actually **edges the GBM on mean-of-folds** (and is more stable); the
GBM wins pooled (0.905 vs 0.898). We keep the GBM not for a large accuracy win but
for its **calibrated probabilities** (the router consumes a real `P(ignite)`),
**inference speed**, and **interpretability** (it yields a permutation-importance
ranking at all). ⚠ **The third reason used to read "produced the severity≫direction
finding"; that finding is withdrawn as not established** (see the section above),
so what remains of it is that the model is interpretable, not that a particular
conclusion was drawn. **The first two reasons stand unchanged**, and neither
depended on the withdrawn claim. Values regenerate via `scripts/ml_baselines.py` →
`data/processed/ml_baselines.json` (STOPs cleanly where the FIRMS bundle is absent).
Method: `docs/baselines.md`.

## Provenance — two builds exist; why they are NOT directly comparable

The project's 작품설명서 / brief cites **0.834 / 0.80 / 0.32** from an earlier,  <!-- forbidden-ok: 0.834 -->
**different** build ("Build A" — `docs/SPREAD_MODEL_REPORT_BUILD_A_LEGACY.md`,
`data/processed/spread_v2/`). Build A and the canonical Build B are **two
independent reconstructions and are not a like-for-like comparison** — the
0.834-vs-0.905 difference cannot be read as "B is better." The specific  <!-- forbidden-ok: 0.834 -->
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

⚠ *A sentence used to stand here saying both builds "independently corroborate
the central finding (severity ≫ direction)". That finding is WITHDRAWN as not
established (see the permutation-importance section above), and a withdrawn
conclusion does not become established by appearing in two builds — both share
the same 0.25° weather product, which is limitation 2 in the withdrawal.* What
the two builds do jointly show is only that the **measured ratio** reproduces
across implementations. No across-the-board "improvement" of B over A is claimed
here; B is canonical purely **by consistency** — it is the model that produced
every downstream result, and it is strong (0.88–0.97 ROC-AUC) on the five fires
shared with Build A.

## Downstream: rescue capacity / triage (PoC)

The rescue-routing layer that consumes this model's hazard surfaces now reports a
**demand–supply** split, not just demand. Of N = **439** 영덕 origins, **167 need
a rescuer** = **143 dispatch-reachable** + **24 geometry-unreachable** (no
surviving ingress). A parameterized capacity model (`RescueCapacityConfig`,
`rescue.py::capacity_triage`, `--sweep capacity`) partitions the 167 into
**rescued_in_time / capacity_deferred / geometry_unreachable** using the existing
priority order (closing window) as the triage rule
(`data/processed/rescue_capacity.json`, baseline 30-min dispatch delay):

| rescue units | rescued_in_time | capacity_deferred | geometry_unreachable | % demand met |
|---:|---:|---:|---:|---:|
| 1 | 3 | 140 | 24 | 1.8 % |
| 3 (baseline) | 9 | 134 | 24 | 5.4 % |
| 8 | 24 | 119 | 24 | 14.4 % |

*(A previous revision of this table quoted a retired 452-origin / 264-demand series that
matches no committed artifact — pre-canonical values. Every number
above is read from `rescue_capacity.json`.)*

Timely-rescue supply ≈ `units × ⌊W/service⌋` (3 per unit at W = 75 min, service =
25 min) is far below the 143 reachable demand — the quantitative case for
pre-positioning + triage. **Capacity here is a PoC parameter, NOT measured 영덕
fire-service capacity**; report the curve, not a single "X rescued"/"lives saved".
At unlimited units `capacity_deferred → 0` and the honest geometry-unreachable set
(24) is recovered (asserted). Detail + figure: `docs/rescue_routing.md` §4c,
`docs/figures/rescue_capacity.png`, `data/processed/rescue_capacity.json`.

## Caveats

- Single-fire (영덕) downstream PoC; synthetic-and-tagged auxiliary routing data.
- Rescue **capacity** (unit count + service time) is a PoC parameter, **not**
  measured 영덕 fire-service capacity — the demand–supply result is a curve and a
  direction, never a single "X rescued" or "lives saved" figure (§ Downstream).
- The `gangneung_2023` fold (~8 positives) is too small for a stable AUC —
  report mean-of-folds **with** the range and this caveat.
- Per-fold prediction arrays are **not** committed; the per-fire DeLong CIs, the
  far-band mean-of-folds, and the ML-baseline table reported here come from the gated
  re-runs (`scripts/auc_intervals.py` / `scripts/ml_baselines.py`) and regenerate to
  `data/processed/{auc_intervals,ml_baselines}.json` where the FIRMS bundle is present.
- Overpass-scale time resolution (hours, not minutes).

## 작품설명서 (Korean writeup) correction mapping

The 작품설명서 is **not in this repo** — apply these old→new corrections there
(values are Build B / this card):

| field | old (Build A / brief) | new (Build B, canonical) |
|---|---|---|
| ROC-AUC (headline) | 0.83 / 0.834 | **0.89 (LOFO mean-of-folds, range 0.68–0.97)**; pooled 0.905 if labeled "pooled" |  <!-- forbidden-ok: 0.834 -->
| far-band (>3 km) AUC | ~0.80 | **0.925 (mean-of-folds, n=3); 0.877 pooled** — ⚠ corrected-DEM re-run reads 0.8408 pooled; quote with the DEM-correction caveat (§ above) |
| footprint IoU | 0.32 | **~0.40 (forward-sim envelope, 3–12 h)** — do not use 0.874 |  <!-- forbidden-ok: 0.874 -->
| feature count | 19 | **16** |

Suggested replacement sentence (formal 합니다체):

> 본 시스템의 산불 확산 모델(spread_v2, 16개 특징)의 LOFO(한 산불씩 제외 교차검증)
> 평균 ROC-AUC는 **0.89**입니다(6개 산불, 범위 0.68–0.97; 0.68은 탐지 약 17건의
> 소규모 산불 폴드입니다). 전체 보류예측 통합(pooled) AUC는 0.905이나, 일반화
> 성능 지표로는 폴드 평균을 보고합니다. 순방향 모의 화선(footprint) IoU는 약
> **0.40**입니다(영덕, 3–12시간).

*Build comparison note for the author: the earlier 0.834 / 0.80 / 0.32 came from a  <!-- forbidden-ok: 0.834 -->
different build (different fire set, 19 features, seed 42) and is not a like-for-like
comparison; report the canonical Build B numbers above.*
