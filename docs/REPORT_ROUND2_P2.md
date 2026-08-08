# Round 2 — Phase 2: measuring the spread model's probability calibration

> ⚠ **제출 시점(2026-07) 기록입니다. 본문은 그대로 둡니다.**
> 이 보고서는 Round 2 제출 시점의 상태를 기록한 문서이며, 당시의 판단과 표현을
> 보존하는 것이 목적입니다. 이후 Round 3 에서 바뀐 것 중 이 문서에 영향을 주는
> 항목은 하나입니다: 모델 채택 근거로 인용된 **"severity ≫ direction"(44배) 발견이
> 미확립으로 철회**되었습니다 — 6개 특징 합산 대 단일 변수, ERA5 0.25°(~28 km)의
> 국지풍 미해상, 산포 미측정 단일 점추정. ⚠ **「풍향이 중요하지 않다」는 뜻이
> 아닙니다.** 근거: [`MODEL_CARD.md`](MODEL_CARD.md) §"Permutation importance".
> **이 문서가 실제로 측정한 것(확률 보정 — Brier·ECE·신뢰도 곡선)은 영향받지
> 않습니다.** 제출 시점 상태 전체는 태그 `round2-submitted` (`4e9dfe3`).

**Scope of this pass (honest, up front).** The Round-1 문서 adopted the
gradient-boosted spread model (`spread_v2`, `HistGradientBoostingClassifier`,
seed `20250603`) partly for **확률 보정** (probability calibration) — but
calibration was *never measured*. This pass turns that claim into evidence: it
adds a **measurement-only** pipeline that scores calibration — Brier score,
Expected Calibration Error (ECE), and reliability curves — on the
**leave-one-fire-out (LOFO) out-of-fold** predictions of the canonical GBM and
its two controlled baselines (random forest, logistic regression), on the
**identical 16 features, identical folds, identical seed** — the same machinery
as `scripts/ml_baselines.py`.

Nothing here modifies the model, the forward-sim, or the routing pipeline. Every
metric is computed on **out-of-fold** rows only (each fire scored by a model that
never saw it).

> ### ⚠️ STATUS — numbers pending the FIRMS/ERA5/DEM bundle
>
> The out-of-fold predictions are rebuilt from the **git-ignored
> `firms_data.zip` bundle** (NASA FIRMS detections + ESA WorldCover fuel + SRTM
> DEM + ERA5 weather). That bundle is **not present in this environment and
> cannot be fetched here** (no `.env`, no NASA FIRMS / Copernicus CDS
> credentials) — the same blocker documented for the hazard surface in
> `docs/REPORT_ROUND2_P1.md`. Per the task's hard guardrail — *"if regeneration
> is impossible, STOP and report"* — **no calibration numbers are fabricated or
> approximated**. `scripts/calibration_metrics.py` therefore **STOPs (exit 2)**
> in this environment instead of writing placeholder numbers.
>
> **What ships in this PR** is the complete, deterministic, unit-tested
> measurement pipeline plus this report. The moment the bundle is present, a
> **single command** produces every deliverable — the committed
> `data/processed/calibration_metrics.json`, the three OOF frames, and
> `docs/figures/calibration_reliability.png`:
>
> ```bash
> unzip firms_data.zip -d data/raw/        # or: export WFG_FIRMS_DIR=/path/to/firms
> python scripts/calibration_metrics.py
> ```
>
> The result tables in §4 below give the **exact schema** that command fills in;
> the cells read `— (pending regeneration)` until then. When the numbers land,
> §5's reading rule applies verbatim: **report whichever way it falls — if the
> random forest or logistic model calibrates better than the GBM, say so; do not
> spin.**

---

## 1. Why calibration matters *here* (not a generic ML nicety)

The evacuation/rescue router does not consume a hard fire mask — it integrates
the hazard as an **exposure dose**

```
exposure = ∫ P(ignition) dt          # routing/evacuation.py: exposure += h * dt
```

i.e. it sums the per-cell ignition **probability** `P` along a candidate path,
weighted by dwell time `dt`, and then minimises that integral to choose a route
(`future_aware_route` / the rescue variants). If `P` is **miscalibrated** — say
the model systematically says 0.30 where the true frequency is 0.10 — then every
`P·dt` term, and therefore the whole exposure integral, is off by exactly that
miscalibration, at every step of every route. A path ranked "low exposure" may
not actually be low-exposure, and the responder/resident exposure numbers that
Phase 1 reports (`resident_exposure`, `responder_exposure`) inherit the error.
**Calibrated `P` is precisely what makes the ∫P·dt exposure metric physically
meaningful** — so calibration is a load-bearing property of this system, not
cosmetic. That is why it deserves to be measured rather than asserted.

---

## 2. What was built (measurement infrastructure)

| Artifact | Role |
|---|---|
| `src/wildfireguardian/validation/calibration.py` | Pure calibration metrics — Brier, ECE (15 equal-count bins), reliability curve, per-fold aggregation, per-fold **isotonic** recalibration of the GBM, deterministic rounded-JSON assembly, and the bilingual reliability figure. No model / forward-sim / routing code touched. |
| `validation/ml_baselines.lofo_oof_predictions()` | Additive: returns per-model **OOF prediction frames** on the *identical* folds / features / seed as the existing `lofo_compare` (which only returned AUC summaries). |
| `scripts/calibration_metrics.py` | Orchestrator: rebuilds the LOFO dataset, regenerates OOF for GBM (via the canonical `leave_one_fire_out`) + RF/logistic (via `ml_baselines`), computes all metrics, writes `calibration_metrics.json` + the figure. STOPs (exit 2) if the bundle is absent. |
| `tests/test_calibration_metrics.py` | 11 pure/synthetic unit tests (always run) + 1 **skip-if-absent** test asserting `calibration_metrics.json` regenerates **deterministically under the fixed seed**. |

All three models share one holdout loop (hold out a whole fire, train on the
rest), so the comparison is controlled — no per-model feature/fold/seed
differences, no tuning. Internal consistency is guarded two ways: the
regenerated GBM pooled AUC is checked against the committed reference
(`0.9053277489374548`, `data/processed/spread_v2_lofo.json`), and the isotonic
step's raw branch is verified row-for-row against that same canonical OOF.

---

## 3. Methodology (exact definitions)

- **Models (controlled comparison).** `hist_gbm` = the canonical
  `HistGradientBoostingClassifier(loss="log_loss", learning_rate=0.08,
  max_iter=300, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
  early_stopping=True, validation_fraction=0.15, random_state=20250603)`;
  `random_forest` = median-impute → 300-tree RF (`min_samples_leaf=20`);
  `logistic` = median-impute → standardize → L2 logistic. Baselines are the
  documented, **untuned** defaults from `validation/ml_baselines.default_models`.
- **Folds.** Leave-one-fire-out over the six fires in the bundle
  (`gangneung_2023`, `hongseong_2023`, `miryang_2022`, `uiseong_andong_2025`,
  `uljin_samcheok_2022`, `yeongdeok_2025`); a fold is skipped only if its
  training split has a single class.
- **Out-of-fold only.** Each fire's rows are scored by a model trained on the
  *other* fires. Pooled metrics use all OOF rows; per-fold metrics group by the
  held-out fire.
- **Brier score.** `mean((p − y)²)` over the OOF rows (0 = perfect).
- **ECE — binning stated explicitly: 15 equal-count (equal-mass) bins.** Rows
  are ranked by predicted probability and split into 15 contiguous groups of
  ~`N/15` rows each (a stable rank split, so it is robust to the ties that the
  ~2 % ignition base rate produces — equal-*width* bins would leave the
  high-probability bins nearly empty and noise-dominated). ECE is the
  count-weighted mean gap `Σ_b (n_b/N)·|obs_freq_b − mean_pred_b|`.
- **Reliability curve.** Per bin: mean predicted probability (x) vs observed
  frequency (y), plus the bin's count and probability span — the data drawn in
  `calibration_reliability.png` against the `y = x` diagonal.
- **Supplementary — per-fold isotonic (bounded).** Within each LOFO fold the GBM
  is wrapped in `CalibratedClassifierCV(method="isotonic")` whose isotonic map is
  learned by **internal `StratifiedKFold` CV on the training fires only** (no
  leakage from the held-out fire) and then applied to the held-out fire.
  Post-calibration Brier/ECE are reported next to raw.

---

## 4. Results (schema — cells filled by regeneration)

**Pooled out-of-fold (lower Brier / ECE = better calibrated):**

| Model | Pooled Brier | Pooled ECE (15 eq-count) | Per-fold Brier µ±σ | Per-fold ECE µ±σ |
|---|---|---|---|---|
| `hist_gbm` (canonical) | — (pending) | — (pending) | — (pending) | — (pending) |
| `random_forest` | — (pending) | — (pending) | — (pending) | — (pending) |
| `logistic` | — (pending) | — (pending) | — (pending) | — (pending) |

**Supplementary — GBM isotonic recalibration (raw → post):**

| Metric | Raw GBM | Post-isotonic | Δ |
|---|---|---|---|
| Pooled Brier | — (pending) | — (pending) | — |
| Pooled ECE | — (pending) | — (pending) | — |

Every number that appears in the figure or in these tables is persisted, keyed,
in `data/processed/calibration_metrics.json` (per-model `pooled` + `per_fold`
{folds, µ, σ} + `reliability` rows, plus `supplementary_isotonic_gbm`). The
figure `docs/figures/calibration_reliability.png` is the three reliability curves
+ the diagonal, bilingual labels in the repo's figure style, with a pooled
Brier/ECE annotation box.

The pipeline is verified end-to-end on a synthetic multi-fire frame (the
`tests/` suite and a scratch dry-run): it produces a well-formed JSON and PNG and
is **byte-identical across runs** under the fixed seed. Those synthetic numbers
are *not* committed — they say nothing about the real model's calibration, and
publishing them as results is exactly the approximation the guardrail forbids.

---

## 5. How to read the results once regenerated (the reading rule)

Calibration is a *different axis* from discrimination (AUC). The Round-1 AUC
story is unchanged; this measures whether the probabilities are trustworthy as
probabilities. Read it plainly:

- **If the GBM has the lowest pooled/per-fold ECE and Brier**, the "확률 보정"
  claim is supported — state it, and note it is *why* the ∫P·dt exposure metric
  is trustworthy.
- **If the random forest or logistic model calibrates as well or better**, say
  so without spin. The honest pivot (already anticipated in
  `scripts/ml_baselines.py`) is that the GBM's case rests on the *combination* of
  native-NaN handling, speed, and severity≫direction interpretability — not on a
  calibration monopoly — and that a cheap post-hoc isotonic step (§3, measured in
  the supplementary block) can close a calibration gap if one exists.
- **The isotonic supplementary** shows the *headroom*: how much better-calibrated
  the GBM could be with a per-fold isotonic wrapper. It is reported for evidence
  only.

The committed `calibration_metrics.json` is the single source of truth; the
prose in a future revision of this section should quote it, not restate it.

---

## 6. Out of scope this round (future work)

The isotonic-calibrated probabilities are **not** wired into the forward-sim or
the router this round — deliberately. Swapping raw `P` for isotonic `P` inside
`∫P·dt` would change **every** routing/exposure number in Phase 1 (resident and
responder exposure, refuge reachability, the four-way counts), which is a
re-baselining exercise that belongs in its own PR with its own before/after
verification. Recommended future work: (1) regenerate the numbers with the
bundle; (2) if the GBM shows a material calibration gap, evaluate wiring the
per-fold isotonic map into the hazard surface and re-running the full routing
verification, reporting the exposure deltas explicitly.

---

## 7. Exact regeneration commands

```bash
# 0. Python deps (already in requirements.txt): numpy scipy pandas scikit-learn
#    matplotlib pyarrow, plus the geospatial stack for the dataset rebuild
#    (pyproj rasterio xarray h5netcdf shapely geopandas).

# 1. Provide the git-ignored data bundle (NASA FIRMS + ESA WorldCover + SRTM + ERA5)
unzip firms_data.zip -d data/raw/            # or: export WFG_FIRMS_DIR=/path/to/firms

# 2. Regenerate OOF + calibration metrics + figure (writes all committed artifacts)
python scripts/calibration_metrics.py
#   → data/processed/spread_v2_lofo_oof.csv.gz        (canonical GBM OOF)
#   → data/processed/lofo_oof_random_forest.csv.gz    (RF OOF, identical folds)
#   → data/processed/lofo_oof_logistic.csv.gz         (logistic OOF, identical folds)
#   → data/processed/calibration_metrics.json         (every number in fig/report)
#   → docs/figures/calibration_reliability.png        (reliability diagram)

# 3. Determinism check (skips automatically if the bundle/JSON are absent)
python -m pytest tests/test_calibration_metrics.py -v
```

Reproducibility knobs: `--seed` (default `20250603`, the canonical seed),
`--n-bins` (default `15`, the equal-count bin count), `--isotonic-splits`
(default `5`, the internal CV folds for the isotonic wrapper), `--no-fig`.

---

## 8. Provenance / files changed

- **New** — `src/wildfireguardian/validation/calibration.py`,
  `scripts/calibration_metrics.py`, `tests/test_calibration_metrics.py`,
  `docs/REPORT_ROUND2_P2.md`.
- **Edited (additive)** — `validation/ml_baselines.py` (new
  `lofo_oof_predictions()` + `OOF_COLUMNS`; existing `lofo_compare` unchanged),
  `.gitignore` (whitelist the three new `data/processed/` result artifacts so
  they are git-trackable once produced).
- **Generated only with the bundle present** (absent in a fresh clone, hence not
  in this PR) — `data/processed/calibration_metrics.json`, the three
  `*_oof.csv.gz` frames, `docs/figures/calibration_reliability.png`.

Full test suite at time of writing: **388 passed, 8 skipped, 0 failed** (the 8
skips are all git-ignored-data skip-if-absent guards, including this pass's
regeneration-determinism test).
