# ML baselines vs the canonical model — status, method, honest framing

*Companion to `scripts/ml_baselines.py` and
`src/wildfireguardian/validation/ml_baselines.py` (unit-tested in
`tests/test_ml_baselines.py`). Answers the 기술적 우수성 critique "you only beat a
bad physics model (~9 % Rothermel capture)": how does the canonical gradient-
boosted model compare to **standard ML baselines** on the same task?*

## TL;DR

- A **controlled LOFO comparison** is built: **logistic regression** and **random
  forest** run over the **identical 16 features, identical fold set, identical seed
  (20250603)** as the canonical gradient-boosted model — same holdout loop, no
  per-model differences, no tuning to manufacture a gap.
- The comparator is **unit-tested** on a synthetic multi-fire frame
  (`tests/test_ml_baselines.py`): all three models run on the same folds and learn
  a planted signal.
- The result below comes from the gated `scripts/ml_baselines.py` re-run on the real
  fires (it needs the **git-ignored FIRMS/ERA5/DEM bundle** to rebuild the LOFO
  dataset; a fresh clone reproduces it only with the bundle present, else exit 2 — no
  invented AUCs). Output: `data/processed/ml_baselines.json`.

> **Honesty stance:** identical features/folds/seed for all models; reasonable,
> **untuned** hyperparameters — the baselines are not handicapped and the GBM is
> not tuned further to win. If a baseline ties or beats the GBM on a fold, the
> script reports it.

## The comparators (documented, untuned defaults)

| model | pipeline / hyperparameters |
|---|---|
| `logistic` | median-impute → standardize → L2 logistic regression (`C=1.0`, `max_iter=2000`) |
| `random_forest` | median-impute → `RandomForestClassifier(n_estimators=300, min_samples_leaf=20)` |
| `hist_gbm` (reference) | the canonical `HistGradientBoosting` (log-loss, `lr=0.08`, `max_iter=300`, `max_leaf_nodes=31`, `min_samples_leaf=40`, `l2=1.0`) — produced the model card's **mean-of-folds 0.89 / pooled 0.905** |

(The GBM/RF use the tree models' native or imputed NaN handling; LR adds
standardization. The canonical estimator in `spread_v2.model` is
`HistGradientBoosting` — the build that produced every downstream number — so it is
used as the reference here.)

## Result (gated re-run; regenerate via `scripts/ml_baselines.py`)

| model | mean-of-folds AUC ± SD | pooled AUC |
|---|---|---|
| random_forest | 0.920 ± 0.036 | 0.898 |
| logistic | 0.903 ± 0.060 | 0.826 |
| hist_gbm (canonical reference) | 0.890 ± 0.107 | 0.905 |

**The verdict, given these numbers:** random forest actually **edges the GBM on
mean-of-folds** (0.920 vs 0.889) and is more stable (SD 0.036 vs 0.107); the GBM wins
**pooled** (0.905 vs 0.898) and leads logistic throughout. So we do **not** claim a
large accuracy win. We keep the GBM for what is actually true: its **calibrated
probabilities** (the router consumes a genuine `P(ignite)`; held-out Brier ~0.03
unweighted vs ~0.09 balanced), **inference speed**, and that it yields a
**permutation-importance ranking** at all.

> ⚠ **이 비율은 미확립으로 철회되었습니다.** 측정값(0.102 vs 0.0023)은 유효하나
> 결론은 지지되지 않습니다: **6개 특징 합산 대 단일 변수** 비교이고, **ERA5 0.25°
> (~28 km)** 는 이 비교가 다루는 국지풍을 해상하지 못하며, **산포를 측정하지 않은
> 단일 점추정**입니다. ⚠ **「풍향이 중요하지 않다」는 뜻이 아니라 이 장비로 볼 수
> 없다는 뜻입니다.** 전체 근거: [`MODEL_CARD.md`](MODEL_CARD.md) §"Permutation
> importance — what it measures, and what it does NOT establish".

⚠ The third reason used to read "the **severity ≫ wind-direction
interpretability** (the 44× permutation-importance ratio that surfaced the
headline finding)". With that finding withdrawn, what survives is
interpretability itself, not the conclusion drawn from it. **The first two
reasons are unaffected** and neither depended on the withdrawn claim.

The honest comparison is the deliverable: the prior "beats a ~9 % Rothermel model"
framing is replaced by "compared head-to-head with standard ML baselines on identical
data — and chosen for calibration + speed + interpretability, not a headline accuracy
gap."

## How to run (where the data is present)

```bash
unzip firms_data.zip -d data/raw/          # or: export WFG_FIRMS_DIR=/path/to/firms
python scripts/ml_baselines.py             # writes data/processed/ml_baselines.json
pytest tests/test_ml_baselines.py          # validates the comparator (no data needed)
```
