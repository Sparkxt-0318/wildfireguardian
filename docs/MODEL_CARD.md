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

## ⚠ Read this before comparing any number in this card to a published benchmark

**The ROC-AUC, the IoU and the recall in this card are NOT comparable to NDWS
PR-AUC or WSTS AP figures.** Three reasons, any one of which is on its own
sufficient:

1. **Different label.** The target here is *"this 500 m cell ignites by the
   **next satellite overpass**"* at overpass cadence (a variable gap, gated at
   90 minutes). NDWS-style benchmarks predict **next-day** fire pixels on a
   fixed daily grid. A different time base is a different problem.
2. **Different geometry for IoU.** The IoU below is over the **cumulative
   burned-area envelope**, not over next-day fire pixels.
3. **Different prevalence.** This set is **1.97 %** positive. PR-AUC and AP move
   with prevalence *by construction* — the identical model scores differently on
   a differently balanced set, so the numbers are not on a common scale.

This note exists so the comparison cannot be made by accident later. If a
comparison is ever wanted, it has to be built: same label definition, same grid,
same evaluation protocol, on a shared dataset. **This project has not done
that and does not claim it.**

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

> ⚠ **Mean-of-folds is computed over folds of highly unequal size, and must
> always be reported alongside [`docs/fold_sizes.md`](fold_sizes.md).**
> The largest fold carries **208.9×** the rows of the smallest
> (`uiseong_andong_2025` 82,736 rows / 54.47 % of the evidence;
> `gangneung_2023` 396 rows / 8 positive cells / **0.26 %** of the evidence).
> Every fold casts the same one-sixth vote regardless.
> **Pooled AUC is the primary metric** because it weights each row exactly once.
> Permutation importance is unaffected by this imbalance — it is aggregated as a
> ROW-weighted average (`spread_v2/model.py::leave_one_fire_out`).
> `[src: fold_sizes.json; keys lofo_fold_rows_max_over_min,
> lofo_smallest_fold_share_of_rows]`

### Per-fire ROC-AUC

| fire | ROC-AUC | DeLong 95 % CI | note |
|---|---|---|---|
| miryang_2022 | 0.974 | [0.941, 0.989] | |
| hongseong_2023 | 0.945 | [0.916, 0.964] | |
| yeongdeok_2025 | 0.941 | [0.936, 0.946] | the demonstration fire (held out) |
| uljin_samcheok_2022 | 0.918 | [0.911, 0.924] | |
| uiseong_andong_2025 | 0.878 | [0.871, 0.884] | |
| gangneung_2023 | **0.682** | [0.577, 0.771] | **~8 positives — fold far too small for a stable estimate; treat as noisy** |

`[ROC-AUC src: spread_v2_lofo.json/per_fire_auc]`

⚠ **The CI columns above are a lineage note.** The AUC column is the committed
(pre-correction-DEM) artifact. The **committed CI/p artifact**
(`data/processed/auc_intervals.json`, 2026-08-10) gates on this machine's
bundle, which is the **corrected-DEM lineage** (`gate_lineage: "dem_corrected"`
— it matched `spread_v2_lofo_dem_corrected.json` to Δ=0 on every check), so
its point AUCs differ from this table in the third decimal — except the tiny
`gangneung_2023` fold, which reads 0.718 [0.609, 0.807] there.

**All six folds are significant vs AUC = 0.5 in the committed artifact**
(`gangneung_2023` p = 1.9×10⁻⁵; the other five p ≪ 10⁻²⁷⁰) — the test
hypothesis H1 needs, and it holds on both lineages. The CIs and p-values come
from `scripts/auc_intervals.py`, which re-runs the canonical model (seed
20250603, same 16 features/folds), **gates** against the committed numbers —
or, on a corrected-DEM bundle, against the `spread_v2_lofo_dem_corrected.json`
lineage, recording which passed in `gate_lineage` — persists the out-of-fold
predictions, and emits the per-fire `AUC [95 % CI]` table + p-values to
`data/processed/auc_intervals.json`. The script **STOPs cleanly (exit 2)**
where the FIRMS/ERA5/DEM bundle is absent (e.g. a fresh clone), and **STOPs
(exit 3)** when the re-run matches *neither* lineage. Method:
`docs/auc_intervals.md`; statistics unit-tested in `tests/test_auc_stats.py`.

### Pooled and far-band (labeled — NOT the generalization figure)

- **Pooled** out-of-fold ROC-AUC = **0.905** — one ROC over *all* held-out folds'
  predictions concatenated (`model.py:184–186`). Pooling is flattered by the
  larger/easier folds; it is **not** the generalization estimate (it sits only
  +0.016 above the mean-of-folds here). `[src: spread_v2_lofo.json/pooled_auc]`
- **Far-band (>3 km) mean-of-folds** ROC-AUC = **0.925** (n=3 fires with far-band
  positives); **pooled far-band 0.877**, mid-band (1–3 km) 0.870. The pooled
  scalars are the committed `spread_v2_lofo.json` values.
  `[pooled src: spread_v2_lofo.json/far_band_auc, mid_band_auc]`
  ⚠ On the corrected DEMs the pooled far-band reads **0.8408** — see the
  DEM-correction section below before quoting 0.877 anywhere. ⚠ The 0.925
  mean-of-folds is a pre-correction re-run that was never committed; the
  **committed** artifact (`auc_intervals.json`, corrected lineage) reads
  **0.904 ± 0.100** (n=3). Quote whichever you can point at, with its lineage.

## Cell-level recall, precision and F1 at the operating threshold (Session 18)

AUC scores a **ranking**. It does not say what the model actually flags. This
section answers the question a technical reader asks next, and the answer is
unflattering — which is why it is here rather than only in a session report.

> **At the operating threshold 0.3: pooled recall 0.138, precision 0.308,
> F1 0.190.** 412 true positives, 925 false positives, 2,577 missed, over
> 151,904 cells and 2,989 actual ignitions.

**The operating threshold is `config/default.yaml :: forward_sim_advance_threshold`
= 0.3 — a DEFAULT, not a tuned value.** It was never optimised on these
probabilities by F1, Youden's J, or any cost model. It is reported because it is
the number the forward simulation and the routing layer actually consume.

| | value |
|---|---:|
| pooled recall | **0.138** |
| pooled precision | **0.308** |
| pooled F1 | **0.190** |
| mean-of-folds recall | **0.0867** (range 0.0–0.456, sd 0.182) |
| average precision (full ranking) | **0.169** |
| prevalence (PR no-skill baseline) | **0.0197** |

**ROC-AUC 0.905 and recall 0.138 are both true and do not conflict.** AUC
measures how well the model *orders* cells; at ~2 % prevalence a well-ordered
model still flags few positives at a 0.3 cut. The honest summary of the ranking
is the average precision against its baseline: **0.169 vs 0.0197, i.e. 8.6× no
skill.**

⚠ **Mean-of-folds recall (0.0867) is far below pooled (0.138), and the reason is
structural.** Three of six folds have **exactly zero true positives** at 0.3:

| fold | rows | positives | recall | TP |
|---|---:|---:|---:|---:|
| `gangneung_2023` | 396 | 8 | **0.0** | 0 |
| `hongseong_2023` | 3,353 | 34 | **0.0** | 0 |
| `miryang_2022` | 3,019 | 24 | **0.0** | 0 |
| `uiseong_andong_2025` | 82,736 | 1,502 | 0.0226 | 34 |
| `uljin_samcheok_2022` | 41,651 | 652 | 0.0414 | 27 |
| `yeongdeok_2025` | 20,749 | 769 | **0.456** | 351 |

An unweighted mean gives the 396-row fold the same weight as the 82,736-row
fold. This is the **fold-size heterogeneity disclosed in Session 10** appearing
in a metric where it bites hard, and it means nearly all recall comes from
`yeongdeok_2025`.

⚠ F1 peaks at threshold **0.14 (F1 0.218)** on this same data. That is recorded
in the artifact as `f1_maximising_threshold_NOT_ADOPTED` and **is not adopted**:
a threshold chosen on the very probabilities it is then scored on is
optimistically biased. **No threshold was changed by this session.**

**No model was fitted to produce any of this.** The probabilities are the
committed LOGO-CV out-of-fold values (`spread_v2_lofo_oof.csv.gz`, written by
`scripts/auc_intervals.py`); refitting to add a column would mean the reported
recall came from a different run than the reported AUC. Cell identity
(`fire_id, op_from, row, col`) was attached by rebuilding the **dataset only**
and verifying the positional join row-for-row on four columns across all 151,904
rows — `scripts/oof_metrics.py` refuses to write if that check fails.

Artifacts: `data/processed/oof_classification_metrics.json` (metrics + a 51-point
PR curve), `data/processed/spread_v2_lofo_oof_cells.csv.gz` (per-cell OOF).

## Reference environment and reportable precision

**The reference environment is `wfg311`** — macOS, Apple Silicon (arm64),
Python 3.11.15, conda-forge (`docs/ENVIRONMENT.md`). **Every committed headline
value in this card was produced there.** That is not a footnote about tooling;
it bounds how precisely any of these numbers may be read.

Session 10 measured the bound directly. Arm A's own 16 columns, its seed
(20250603), its folds and its protocol were re-run on Linux/aarch64 with PyPI
manylinux wheels — same pinned versions, `make env-check` passing, dataset
identical at 151,904 rows / 2,989 positives. What moved:

| metric | reference `wfg311` | second platform | drift | registry key |
|---|---:|---:|---:|---|
| Pooled OOF AUC | 0.9053 | 0.8989 | **0.0064** | `platform_drift_pooled_auc` |
| Mid-band AUC | 0.8698 | 0.8515 | 0.0183 | `platform_drift_mid_band_auc` |
| Far-band AUC (>3 km) | 0.8766 | 0.8458 | **0.0307** | `platform_drift_far_band_auc` |

**Cause:** floating-point accumulation order, and the placement of the
early-stopping validation split, differ between the conda-forge macOS/arm64
build and the PyPI manylinux aarch64 build of
`HistGradientBoostingClassifier`. The estimator, its hyperparameters and its
seed are identical. `[src: docs/platform_drift.json]`

### The rule

> **Pooled ROC-AUC is reportable to THREE significant figures — `0.905`.**
> The fourth digit is not stable across platforms and must not be compared,
> ranked or differenced.

Two consequences, stated so neither is applied silently:

1. **Stored values keep full precision.** `NUMBERS.json` holds the artifact's
   exact float so `make verify` stays an exact check. The rule governs what may
   be written in prose, on a poster or on a slide — **nothing is silently
   rounded anywhere.**
2. **Any comparison below the floor is not a measurement.** Far-band needs more
   headroom than pooled (0.0307 vs 0.0064) because it holds fewer rows and
   fewer positives. Session 10's Arm D pooled delta of −0.0070 sat inside the
   pooled floor and was reported as unmeasurable rather than as a degradation
   (`docs/SESSION10_REPORT.md` §1.1).

⚠ These drift figures are **not Arm A values** and must never be cited as one.
They carry `arm: A_replication` in the registry precisely so that confusion
fails the isolation gate.

### Angular quantities take a different rule

Bearings and circular correlations are not AUCs, and the three-significant-figure
rule above does not transfer to them. Their precision is set by sampling spread,
not by platform drift.

> **Mean angular differences are reportable to ONE decimal place**, and
> differences smaller than **~19°** are not established.
> **Circular correlations are reportable to TWO decimals**, and **|r| below
> ~0.33** is not distinguishable from zero.

Derivation: n = 36 usable label steps with a per-step spread of ~56°, so the
standard error of a mean angular difference is ~9.3°, and 2 SE ≈ 19°. For a
circular correlation at this n the approximate standard error is
1/√36 ≈ 0.17, so 2 SE ≈ 0.33. These are **rules of thumb read off the observed
spread, not exact tests** — the appropriate reference distribution for a
circular correlation at n = 36 was not derived. The fold-level spread is wider
still (sd ≈ 47–50° across 6 fires), and it, not the pooled SE, governs any
per-fire claim. `[src: docs/direction_drivers.json]`

## Terrain is attenuated by the 500 m grid — a limitation of THIS model

**`slope_deg` in the committed baseline is a roughly 3× attenuated version of
physical slope.** This is a property of the reported model, not only of the
direction experiments that measured it.

Two smoothing steps stack. `elevation_on_grid` **averages** ~30 m SRTM into
500 m cells, and `slope_deg` then differences that already-smoothed surface over
a **500 m baseline**. Session 12 measured what the pair removes, by recomputing
slope at native resolution over 16×16 sub-cells per 500 m cell:

| fire | `slope_deg` (500 m) | native effective | attenuation |
|---|---:|---:|---:|
| `gangneung_2023` | 4.18° | 13.89° | ×3.33 |
| `hongseong_2023` | 2.49° | 9.05° | ×3.64 |
| `miryang_2022` | 9.29° | 22.24° | ×2.39 |
| `uiseong_andong_2025` | 4.70° | 16.28° | ×3.46 |
| `uljin_samcheok_2022` | 7.54° | 21.47° | ×2.85 |
| `yeongdeok_2025` | 6.21° | 20.61° | ×3.32 |
| **pooled** | **5.73°** | **17.26°** | **×3.01** |

`[src: docs/slope_resolution.json; keys slope_attenuation_500m_vs_native,
slope_native_effective_mean_deg]`

**The aggregate is the effective slope, not the mean:**
`slope_effective = arctan(sqrt(mean(tan²φ)))`. Rothermel's slope factor
`φ_s = 5.275 β^(−0.3)(tan φ)²` is **quadratic in `tan φ`**, so by Jensen's
inequality `E[tan²φ] ≥ (E[tan φ])²` — the mean slope of a heterogeneous cell
systematically **understates that cell's mean slope forcing**, and the
understatement grows with within-cell roughness. The effective slope is the
single angle whose forcing equals the cell's mean forcing, so it is the
aggregate that preserves the physics. The maximum is deliberately not used: over
256 sub-cells it is an extreme-value statistic that grows with the subdivision
count and measures the sampling rather than the terrain.

### What this means, stated plainly

- **The model's terrain representation is attenuated.** Slope enters Arm A only
  as a scalar magnitude (`slope_deg`, plus `elev_above_source_m`), and that
  magnitude is about a third of the physical slope of the same ground.
- **Calibration range moves with resolution.** Every 500 m slope sits below
  Rothermel's lowest calibrated angle (14.0°; his 12 laboratory fires were at
  14.0 / 26.6 / 36.9°). The native effective pooled mean of 17.26° does **not** —
  it is 1.23× that angle. `hongseong_2023` and `gangneung_2023` remain below it,
  and no fire's mean reaches the upper two angles. The downward extrapolation is
  **smaller, not gone.**
- **`slope_deg` has NOT been changed and Arm A has NOT been retrained.** This is
  a disclosure of a limitation in the committed model. Session 12's Arm E added
  native-resolution terrain features *beside* the frozen ones and did not
  displace them; its result is a null (see `docs/direction_findings.md`).
- **Unmeasured:** whether Arm A trained on native-resolution slope would perform
  differently. That experiment was not run.

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

<!-- collision-ok: 0.077 — permutation IMPORTANCE of days_since_rain, not wxdep_drop_days_since_rain_mean_delta (0.027), which is the mean-of-folds AUC change from DROPPING it. -->
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
| random_forest | 0.914 ± 0.044 | 0.896 |
| logistic | 0.903 ± 0.060 | 0.826 |
| **hist_gbm (ours)** | **0.894 ± 0.092** | **0.904** |

⚠ Values are the **committed artifact** `data/processed/ml_baselines.json`
(2026-08-10, corrected-DEM bundle — the only bundle this machine holds; an
earlier revision of this table carried a never-committed pre-correction run's
values, same ordering conclusions in both lineages).

Random forest actually **edges the GBM on mean-of-folds** (and is more stable);
the GBM wins pooled (0.904 vs 0.896). We keep the GBM not for a large accuracy
win — **and not for a calibration win either**: measured pooled out-of-fold
Brier / ECE (`data/processed/calibration_metrics.json`, 2026-08-10) are GBM
**0.0183 / 0.0086** vs random forest **0.0174 / 0.0068** — the baseline
calibrates at least as well, and the measurement script prints exactly that
("report it plainly, do not spin"). What the calibration claim now means: the
router consumes a genuine, well-calibrated `P(ignite)` (Brier 0.018 absolute) —
a property of the GBM, not an edge over RF. What actually keeps the GBM: the
**pooled-AUC edge**, **inference speed**, **native NaN handling**, and
**interpretability** (it yields a permutation-importance ranking at all).
⚠ **The interpretability reason used to read "produced the severity≫direction
finding"; that finding is withdrawn as not established** (see the section
above). Values regenerate via `scripts/ml_baselines.py` and
`scripts/calibration_metrics.py`. Method: `docs/baselines.md`.

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

---

## Appendix (WFG-019) — the operating point per fire, and why no threshold guarantee exists

Appended 2026-09-03. **Nothing above this line was edited.** No model was fitted,
no default was changed, and no threshold computed here is adopted anywhere. Full
document: [`docs/operating_point.md`](operating_point.md). Artifact:
`data/processed/operating_point/per_fire_recall.json`. Figure:
`docs/figures/auto/pr_curve_operating_point.png`.

### A1. Two thresholds, two surfaces

The Session 18 section above reports recall at 0.3. That 0.3 is
`time.forward_sim_advance_threshold`, applied **per simulation step** to a
per-step ignition probability. It is **not** the cut the router applies: the
router thresholds the **cumulative, survival-accumulated** hazard field at
`pedestrian.walk_cutoff_p` = **0.5**. A sentence that reads the recall above as
the routing field's miss rate is wrong in both directions — the recall bounds how
fast the simulated hazard *extent* grows, and the router then reads the
accumulated field that extent produced.

### A2. What the zero-recall folds actually say

The three folds with zero true positives fail for two different reasons, and the
distinction is stronger than "recall 0":

| fold | positives | max OOF probability over ALL cells | can 0.3 fire at all? |
|---|---:|---:|---|
| `gangneung_2023` | 8 | **0.0241** | **no** — no cell reaches 0.3 |
| `hongseong_2023` | 34 | **0.296** | **no** — no cell reaches 0.3 |
| `miryang_2022` | 24 | **0.369** | yes, on 2 non-igniting cells only |

On two of six held-out fires the operating threshold can produce neither a true
nor a false positive. The remaining folds' false-negative rates at 0.3 are
`uiseong_andong_2025` **0.977**, `uljin_samcheok_2022` **0.959**,
`yeongdeok_2025` **0.544** — so 351 of the 412 pooled true positives (85 %) come
from `yeongdeok_2025`, which is also the fold whose training set contains
same-week rows from `uiseong_andong_2025`.

### A3. The threshold-calibration negative result

Nested leave-one-fire-out: calibrate a lambda on five fires so their pooled
false-negative rate is within a **0.20** budget, then measure it on the sixth.
Convention (stated because the two Round-3 verdicts differed and got different
lambdas): strict comparison, and the **largest** feasible lambda.

| convention | target FNR on the 5 | held-out bound holds | worst held-out FNR | share of all cells flagged |
|---|---:|:--:|---:|---:|
| no finite-sample term | 0.200 | **3 of 6** | **0.750** | 0.0992 – 0.185 |
| minus `1/(n+1)`, n = 5 | 0.0333 | 6 of 6 | 0.108 | **0.260 – 0.456** |

**At six fires the correction `1/(n+1)` = 0.167 consumes 83 % of a 0.20 budget.**
That single arithmetic fact is the finding. Without it the bound breaks on the
fires the calibration never saw; with it the bound holds and a bound-satisfying
lambda paints **26 – 46 % of the map** against a **1.97 %** prevalence, which is
not a hazard field a pedestrian route can be planned on. **For this model, at
n = 6, you can have the guarantee or a usable field, not both.** The operating
point therefore stays what it already was: a ranking-driven forward simulation at
an untuned default, not a classifier carrying a guarantee.

⚠ **The two halves of that sentence rest on different evidence, and a leakage
audit of the experiment (`mandela`) flagged the conflation.** "The correction
consumes 83 % of the budget" is arithmetic in `n` alone — model-independent, true
for any model at six fires. "26 – 46 % of cells flagged" is a property of *this
model's* probability distribution: lambda has to fall to 0.0005 partly because
the budget is narrow and partly because the igniting cells of the three small
fires sit near the floor of the probability range. **The experiment does not
separate those two causes** — that would need a control with the same marginal
probability distribution and the fire-to-fire structure destroyed, which does not
exist. So the defensible claim is "this model, calibrated on these six fires,
gives an unusable threshold, and the budget arithmetic alone is about the fire
count" — not "no threshold guarantee is possible in principle". Two smaller
notes: the calibration-set FNR column is a construction check (lambda is *defined*
to meet it), not a result; and the "largest feasible lambda" convention
*minimises* the flagged fraction, so it works against this conclusion rather than
for it. Finally `uiseong_andong_2025` and `yeongdeok_2025` are one March-2025
complex with overlapping bounding boxes, so n = 5 calibration fires is itself
optimistic and the correction is if anything too small (WFG-032).

⚠ **Neither row above is a valid guarantee**, and the artifact says so. Exchangeability
breaks twice: the held-out fire's out-of-fold probabilities come from a model
trained on the very fires used to calibrate, and `1/(n+1)` is a **fire-level**
finite-sample term applied to a **cell-level** quantile. The corrected row is an
*optimistic* bound on what a real guarantee would cost. It is reported because
even the optimistic version is unusable.
