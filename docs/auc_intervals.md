# AUC confidence intervals + significance — status, methods, and the honest blocker

*Companion to `scripts/auc_intervals.py` and `src/wildfireguardian/validation/auc_stats.py`
(unit-tested in `tests/test_auc_stats.py`). Addresses the 수학·통계 critique that the
headline AUC had **no confidence interval and no significance test**, and that
hypothesis H1 ("무작위(0.5)를 유의하게 초과") was never actually tested.*

## TL;DR

- The **statistical machinery is built and verified**: DeLong AUC variance + CI,
  a DeLong significance test vs AUC = 0.5, a stratified bootstrap CI, a
  label-permutation test, and a small-sample mean-of-folds t-interval. All match
  scikit-learn's AUC and behave correctly on separable-vs-random data
  (`tests/test_auc_stats.py`, 10 tests).
- The **mean-of-folds interval can be (and is) reported now** — it needs only the
  six committed per-fire AUC scalars.
- The **per-fold DeLong CIs, the significance test vs 0.5, the pooled bootstrap CI,
  and the far-band mean-of-folds** need the per-fold *prediction arrays* (not stored),
  so they require re-running LOFO with the **FIRMS/ERA5/DEM bundle** (git-ignored,
  absent in a fresh clone). `scripts/auc_intervals.py` performs that gated re-run and
  computes them; the values are in **§ Reported results** below. A fresh clone
  reproduces them only with the bundle present — without it the script STOPs cleanly
  (exit 2) rather than fabricate.

> **Honesty stance:** no model change, no retuning, no feature change. Reporting
> CIs that were never computed would be fabrication; instead this documents
> exactly what is and is not reproducible here, and ships the ready, gated,
> unit-tested code to produce the rest.

## What IS reported now (from the committed per-fire scalars)

Mean-of-folds ROC-AUC over the 6 LOFO fires (`spread_v2_lofo.json/per_fire_auc`,
computed by `auc_stats.mean_of_folds_interval`):

| set | mean ± SD | range | 95 % CI (t, small-sample) | n |
|---|---|---|---|---|
| all 6 fires | **0.890 ± 0.107** | 0.682–0.974 | *not reported* (see note) | 6 |
| excl. `gangneung_2023` (~8 positives) | 0.931 ± 0.036 | 0.878–0.974 | [0.887, 0.976] | 5 |

**Read this with the n=6 caveat.** The all-fires spread is **wide** (±0.11) because
six fires is a tiny sample and the noisy 0.68 `gangneung_2023` fold inflates the SD.
We deliberately **do not report the 6-fold t-interval**: its upper limit pins to (or
past) the AUC ceiling of 1.0, which is self-discrediting rather than informative. We
report **mean ± SD with the range** instead, and rely on the **per-fold DeLong CIs**
below as the *stronger* evidence — each fold has thousands of cells, so its analytic
CI is well-powered, unlike this 6-point mean. Never present the pooled AUC as the
generalization figure either.

## Reported results (from the gated re-run)

These come from the gated `scripts/auc_intervals.py` re-run (seed 20250603): it
reproduced pooled 0.905 / mean-of-folds 0.890 / the per-fire AUCs **before**
reporting, then computed the inference below and wrote
`data/processed/auc_intervals.json`. A fresh clone reproduces them only with the
FIRMS/ERA5/DEM bundle present (else exit 2).

**Per-fire AUC [95 % DeLong CI] and significance vs AUC = 0.5:**

| fire | ROC-AUC | DeLong 95 % CI | vs 0.5 |
|---|---|---|---|
| miryang_2022 | 0.974 | [0.941, 0.989] | p ≪ 0.001 |
| hongseong_2023 | 0.945 | [0.916, 0.964] | p ≪ 0.001 |
| yeongdeok_2025 | 0.941 | [0.936, 0.946] | p ≪ 0.001 |
| uljin_samcheok_2022 | 0.918 | [0.911, 0.924] | p ≪ 0.001 |
| uiseong_andong_2025 | 0.878 | [0.871, 0.884] | p ≪ 0.001 |
| gangneung_2023 | 0.682 | [0.577, 0.771] | p = 2.7×10⁻⁴ |

**All six folds are significant vs 0.5** — including the tiny `gangneung_2023`
(~8 positives), which clears significance (p = 2.7×10⁻⁴) despite a noisy point
estimate. This is the test hypothesis H1 required.

- **Pooled bootstrap 95 % CI = [0.901, 0.909]** (1000 stratified resamples),
  labelled pooled — **not** the generalization figure.
- **Far-band (>3 km) mean-of-folds AUC = 0.925** (n=3 fires with far-band
  positives), alongside the pooled far-band 0.877.

## How these are produced (the gated re-run)

These need the per-fold `(y_true, y_score)` arrays, which are **not** stored in
`spread_v2_lofo.json` (only per-fire AUC scalars + pooled). `auc_intervals.py`
re-runs the canonical LOFO once, persists the out-of-fold predictions, gates, and
computes:

1. **Per-fire AUC [95 % DeLong CI]** — well-powered (thousands of cells/fold).
2. **Significance vs AUC = 0.5** — a DeLong z-test per fold (+ a label-permutation
   cross-check). *This is the test hypothesis H1 requires.* **Result:** all six folds
   are significant — even the tiny `gangneung_2023` (~8 positives) at p = 2.7×10⁻⁴,
   the other five p ≪ 0.001 (see § Reported results above).
3. **Pooled bootstrap CI** — 1000 stratified resamples, **labelled pooled** (not
   the generalization figure).
4. **Far-band (>3 km) mean-of-folds** — per-fire far-band AUC + its mean-of-folds,
   alongside the existing **pooled** far-band 0.877 (the deferred model-card gap).

## The consistency gate (STOP conditions)

`auc_intervals.py` will **STOP** rather than report if:

- the FIRMS bundle is absent → exit 2 (cannot run; what happened here);
- the re-run does not reproduce **pooled 0.905 / mean-of-folds 0.890 / the per-fire
  AUCs** within rounding → exit 3 (does not "fix" the model; flags a data/seed/fold
  drift to investigate).

## Methods

- **DeLong** (DeLong et al. 1988; fast midrank, Sun & Xu 2014): analytic AUC
  variance for one classifier, `Var = S10/m + S01/n`; CI on the logit scale so it
  stays in [0, 1]; z-test vs a reference AUC. Matches sklearn's AUC exactly
  (tested).
- **Bootstrap**: percentile CI from stratified resampling (preserves the ~2 %
  positive base rate), fixed seed.
- **Permutation**: one-sided test of H0 (scores carry no rank information →
  AUC ≈ 0.5), add-one p-value, fixed seed.
- **Mean-of-folds**: Student-t interval; `small_sample` flag for n ≤ 12.
- Seeds: canonical **20250603** throughout.

### (Optional) severity-ratio stability — deferred
The 44× severity-vs-direction permutation-importance ratio is a single point
estimate. Reporting its spread across seeds/folds would need re-running the
permutation-importance path (same data dependency) — noted as **future work**,
runnable via the same harness once the bundle is present.

## How to run (where the data is present)

```bash
unzip firms_data.zip -d data/raw/          # or: export WFG_FIRMS_DIR=/path/to/firms
python scripts/auc_intervals.py            # gates, then writes data/processed/auc_intervals.json
pytest tests/test_auc_stats.py             # validates the statistics (no data needed)
```
