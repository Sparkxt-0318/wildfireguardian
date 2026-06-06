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
- The **per-fold DeLong CIs, the significance test vs 0.5, the pooled bootstrap
  CI, and the far-band mean-of-folds CANNOT be computed in this sandbox**: they
  need the per-fold *prediction arrays*, which are not stored, so they require
  re-running LOFO — and the raw **FIRMS/ERA5/DEM bundle is git-ignored and absent
  here**. `scripts/auc_intervals.py` performs that re-run, **gates** it against
  the canonical numbers, and computes everything — it STOPs cleanly (exit 2) when
  the data is absent rather than fabricating numbers. Run it where the bundle is
  present to fill in the remaining intervals.

> **Honesty stance:** no model change, no retuning, no feature change. Reporting
> CIs that were never computed would be fabrication; instead this documents
> exactly what is and is not reproducible here, and ships the ready, gated,
> unit-tested code to produce the rest.

## What IS reported now (from the committed per-fire scalars)

Mean-of-folds ROC-AUC over the 6 LOFO fires (`spread_v2_lofo.json/per_fire_auc`,
computed by `auc_stats.mean_of_folds_interval`):

| set | mean ± SD | 95 % CI (t, small-sample) | n |
|---|---|---|---|
| all 6 fires | **0.890 ± 0.107** | **[0.778, 1.000]** (width 0.22) | 6 |
| excl. `gangneung_2023` (~17 detections) | 0.931 ± 0.036 | [0.887, 0.976] | 5 |

**Read this with the n=6 caveat.** The all-fires interval is **very wide**
(±0.11) because six fires is a tiny sample and the noisy 0.68 `gangneung_2023`
fold inflates the SD; the t-interval's upper limit is the AUC ceiling (1.0). This
is exactly why the per-fold DeLong CIs below are the *stronger* evidence — each
fold has thousands of cells, so its analytic CI is well-powered, unlike this
6-point mean. Do **not** present the mean-of-folds interval as a tight bound, and
never present the pooled AUC as the generalization figure.

## What REQUIRES the re-run (script ready; not run here — data absent)

These need the per-fold `(y_true, y_score)` arrays, which are **not** stored in
`spread_v2_lofo.json` (only per-fire AUC scalars + pooled). `auc_intervals.py`
re-runs the canonical LOFO once, persists the out-of-fold predictions, gates, and
computes:

1. **Per-fire AUC [95 % DeLong CI]** — well-powered (thousands of cells/fold).
2. **Significance vs AUC = 0.5** — a DeLong z-test per fold (+ a label-permutation
   cross-check). *This is the test hypothesis H1 requires.* Expectation given the
   per-fire AUCs (0.68–0.97 on ≥hundreds of positives): the five non-gangneung
   folds will be strongly significant; `gangneung_2023` (~17 detections) may not
   reach significance on its own — which is the honest finding, not a failure.
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
