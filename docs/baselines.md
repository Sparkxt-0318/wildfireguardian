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
- It was **not run on the real fires here**: like the AUC-interval re-run, it needs
  the **git-ignored FIRMS/ERA5/DEM bundle** to rebuild the LOFO dataset.
  `scripts/ml_baselines.py` STOPs cleanly (exit 2) when the data is absent rather
  than report invented AUCs. Run it where the bundle is present to fill in the
  table.

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
standardization. The model card labels the canonical estimator "XGBoost"; the
actual canonical estimator in `spread_v2.model` is `HistGradientBoosting` — the
build that produced every downstream number — so it is used as the reference here.)

## What the run will report (table to fill where data is present)

| model | mean-of-folds AUC ± SD | pooled AUC |
|---|---|---|
| hist_gbm (canonical reference) | 0.890 ± 0.107 | 0.905 |
| random_forest | _run `scripts/ml_baselines.py`_ | — |
| logistic | _run `scripts/ml_baselines.py`_ | — |

The script prints the **GBM − RF mean-of-folds margin** and an automatic verdict:

- **If the margin is small (< 0.03):** say so plainly and pivot the technical-
  excellence claim to what is actually true — the GBM's **calibrated
  probabilities** (the router consumes genuine `P(ignite)`; held-out Brier ~0.03
  unweighted vs ~0.09 balanced), **speed**, and the **severity ≫ wind-direction
  interpretability** (44× permutation-importance ratio) — *not* a large accuracy
  win over random forest.
- **If the margin is clear:** report it as a clear lead, still alongside the
  calibration/interpretability story.

Either way the honest comparison is the deliverable; the prior "beats a ~9 %
Rothermel model" framing is replaced by "compared head-to-head with standard ML
baselines on identical data."

## How to run (where the data is present)

```bash
unzip firms_data.zip -d data/raw/          # or: export WFG_FIRMS_DIR=/path/to/firms
python scripts/ml_baselines.py             # writes data/processed/ml_baselines.json
pytest tests/test_ml_baselines.py          # validates the comparator (no data needed)
```
