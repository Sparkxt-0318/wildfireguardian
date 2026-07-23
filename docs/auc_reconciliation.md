# AUC / IoU reconciliation (read-only fact-find)

> **Resolution → [`docs/MODEL_CARD.md`](MODEL_CARD.md).** Build B is canonical
> (it produced every downstream result); the two builds are **not like-for-like**
> (different fire set, 16 vs 19 features, seed 42 vs 20250603, different eval code),
> so no "B better than A" claim is made. Headline = LOFO **mean-of-folds ROC-AUC
> 0.89 ± 0.11** (range 0.68–0.97); pooled 0.905 is labeled-as-pooled; footprint
> IoU **~0.40** (the 0.874 single-step IoU is report-blocked).

> **Diagnostic only.** This document recomputes statistics from already-committed
> artifacts to explain why two AUCs are cited (repo `0.905`, project doc `0.83`). It
> **changes no reported number** and makes **no reporting decision** — that is the
> author's. No retraining, no LOFO re-run, no logic change.

## Sources read

1. `data/processed/spread_v2_lofo.json` — this branch's spread_v2 LOFO summary
   (seed 20250603, 6 fires, `n_rows`=151904, `n_positives`=2989). Holds
   `pooled_auc`=0.9053, `far_band_auc`=0.8766, `mid_band_auc`=0.8698,
   `per_fire_auc` (6 scalars), and `footprint_iou_single_step.model`=0.8742. **No raw
   out-of-fold prediction arrays, no per-fire `n_pos`/`n_total`, no per-fire far-band.**
2. `src/wildfireguardian/spread_v2/model.py::leave_one_fire_out` — the AUC code.
   Line 184–189 (quoted): `oof = pd.concat(oof_parts, ignore_index=True)`;
   `pooled = _safe_auc(oof["label"], oof["prob"])`;
   `far = oof[oof["dist_band"]=="far"]`; `far_auc = _safe_auc(far["label"], far["prob"])`.
   `_safe_auc` = `roc_auc_score(y, p)` (line 95–100). Per-fire: line 175–176
   `auc = _safe_auc(test["label"], p); per_fire_auc[held] = auc`.
   → **`pooled_auc` (0.905) concatenates every held-out fold's predictions and calls
   `roc_auc_score` ONCE — it is the POOLED out-of-fold AUC, not a mean of per-fire
   AUCs. `far_band_auc` (0.877) is likewise pooled (concat then filter to the far
   band).** The raw `oof` frame lives on `LofoResult` in memory but is **not**
   persisted to the JSON, so pooled/far-band cannot be independently recomputed here.
3. Per-fold predictions: **not stored** for this build. Only per-fire AUC *scalars*
   are committed → mean-of-folds is recomputable; pooled/far-band are confirm-as-stored
   only; per-fire `n_pos`/`n_total` and per-fire far-band require re-running LOFO
   (FIRMS bundle is git-ignored).
4. IoU sources — traced below (three different IoU statistics exist).
5. "0.83 / 0.80 / 0.32 / 0.748" — located in-repo; identified below as a *different
   model build*, not a different statistic of this one.

## === AUC / IoU RECONCILIATION ===

```
Model / run : this branch's spread_v2 (PR #3/#4 lineage), seed 20250603,
              written by scripts/run_routing_integration.py -> spread_v2_lofo.json
              (16-feature build; n_rows=151904, n_positives=2989)
Folds       : N=6, fires=[gangneung_2023, hongseong_2023, miryang_2022,
              uiseong_andong_2025, uljin_samcheok_2022, yeongdeok_2025]
              weather-complete = all 6 (the 0-byte-ERA5 gangneung_donghae_2022 and
              single-overpass goseong_2019 were already excluded from this build)

Per-fold:
  fire                 | n_pos | n_total | AUC    | far-band AUC
  ---------------------|-------|---------|--------|-------------
  yeongdeok_2025       |  n/s  |  n/s    | 0.9408 | n/s
  uljin_samcheok_2022  |  n/s  |  n/s    | 0.9181 | n/s
  miryang_2022         |  n/s  |  n/s    | 0.9737 | n/s
  uiseong_andong_2025  |  n/s  |  n/s    | 0.8777 | n/s
  hongseong_2023       |  n/s  |  n/s    | 0.9449 | n/s
  gangneung_2023       |  n/s  |  n/s    | 0.6820 | n/s   (tiny ~17-detection fire, flagged noisy)
  (n/s = not stored; per-fire counts + per-fire far-band require re-running LOFO)

Summary statistics:
  statistic                              | value            | definition                            | source
  pooled AUC (concat held-out preds)     | 0.9053           | one ROC over all folds' preds         | spread_v2_lofo.json/pooled_auc (confirm-as-stored; raw preds not committed)
  mean-of-folds AUC +/- sd  (min-max)    | 0.8895 +/- 0.1066 (0.682-0.974) | mean of per-fire AUCs | RECOMPUTED from spread_v2_lofo.json/per_fire_auc
  pooled - mean-of-folds                 | +0.0158          | pooling vs averaging gap              | recomputed
  pooled far-band AUC                    | 0.8766           | far band, pooled                      | spread_v2_lofo.json/far_band_auc (confirm-as-stored)
  mean-of-folds far-band AUC +/- sd      | NOT RECOMPUTABLE | per-fire far-band not stored          | requires LOFO re-run
  IoU (0.40)                             | 0.368/0.398/0.392/0.398 @ 3/6/9/12 h | FORWARD-SIM envelope IoU vs observed, Yeongdeok single fire, p_cut threshold | yeongdeok_forward_sim.json/drift
  IoU (0.87)                             | 0.8742           | SINGLE-STEP cumulative footprint IoU (this build) | spread_v2_lofo.json/footprint_iou_single_step.model
  IoU (0.32)                             | 0.32             | a DIFFERENT build's single-step top-N footprint IoU AND the brief's stated value | docs/SPREAD_MODEL_REPORT_BUILD_A_LEGACY.md:22,172 ; docs/ROUTING_INTEGRATION_REPORT.md:53

What "0.83 / 0.80 / 0.32" referred to:
  Located in-repo as a DIFFERENT model build, not a different statistic of this one:
   - 0.83  = pooled AUC of PR #2's independent spread_v2 RE-TRAIN (seed 42, 19 features:
             frp_sum_nearby, v1_alignment, ... ) = 0.834 full / 0.857 weather-complete
             [docs/SPREAD_MODEL_REPORT_BUILD_A_LEGACY.md:206,353 ; data/processed/spread_v2/*],
             which COINCIDES with the project brief's stated ~0.83
             [docs/ROUTING_INTEGRATION_REPORT.md:51 "brief states ~0.83 | we measure 0.905"].
   - 0.80  = same PR #2 build / brief far-band AUC (~0.80) [same sources, lines 25/52].
   - 0.32  = PR #2 build's single-step top-N footprint IoU (mean 0.32) + brief value
             [SPREAD_MODEL_REPORT_BUILD_A_LEGACY.md:172 ; ROUTING_INTEGRATION_REPORT.md:53].
   - 0.748 = an even earlier model: PR #1's ignition_model LOFO MEAN-of-folds AUC
             (0.748 +/- 0.033, 4 fires) [PR #1 description / SPREAD_MODEL_REPORT.md].

Hypothesis supported : NEITHER H1 nor a simple "stale". The 0.905-vs-0.83 gap is a
  DIFFERENT MODEL BUILD (two independent spread_v2 reconstructions from the same FIRMS
  data: this branch's 16-feature seed-20250603 build vs PR #2's 19-feature seed-42
  build + the brief). H1 (pooled-vs-mean of the SAME model) is REFUTED: this build's
  mean-of-folds is 0.890, only 0.016 below pooled 0.905 — both far above 0.83.
Recomputable now     : mean-of-folds AUC (overall) = 0.8895 +/- 0.1066, range
  0.682-0.974, from the committed per_fire_auc scalars.
NOT recomputable without re-run : pooled AUC from scratch (raw OOF preds not committed;
  value only confirmable as stored), per-fire far-band AUC, mean-of-folds far-band,
  per-fire n_pos/n_total. Do NOT retrain to fill these — author's follow-up decision.
```

## Verdict (evidence, not a decision)

The two cited AUCs are **two different model builds**, not two statistics of one model.
Within **this** branch's build, pooled (0.905) and mean-of-folds (0.890 ± 0.107) differ
by only **0.016**, and both sit well above 0.83 — so the gap is **not** a
pooled-vs-mean-of-folds artifact (H1 refuted), and 0.83 is **not** this build's
mean-of-folds. The `0.83 / 0.80 / 0.32` numbers are PR #2's independently-reconstructed
spread_v2 (different feature set, seed, row/positive counts) and coincide with the
project brief's stated figures; this branch's `0.905 / 0.877 / 0.40` is its own
reconstruction, explicitly framed as "we measure" vs the brief in
`docs/ROUTING_INTEGRATION_REPORT.md`.

**Honest generalization figure for this build:** the leave-one-fire-out **mean-of-folds
AUC = 0.89 ± 0.11 (range 0.68–0.97, N=6)**, dominated on the low end by the tiny
~17-detection `gangneung_2023` fold (0.68); the pooled 0.905 is marginally (+0.016)
higher because pooling weights the larger/easier folds. For heterogeneous LOFO the
mean-of-folds ± spread is the more conservative generalization estimate — **but which
number to report (and whether to align the two documents on the same build) is the
author's call; no number has been changed here.**

The three IoUs are different statistics and must not be compared as if one: **0.40** =
forward-sim envelope IoU at 3–12 h (Yeongdeok, this build); **0.87** = single-step
cumulative footprint IoU (this build); **0.32** = a *different* build's single-step
top-N footprint IoU + the brief's value. Report each with its threshold/horizon/scope.
