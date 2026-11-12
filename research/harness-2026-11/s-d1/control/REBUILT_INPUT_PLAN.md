# Rebuilt-input run: frozen d4_wind_seed0 on Daniel's rebuilt covariates (plan, committed before any run)

Agreed with Victor on 2026-11-12. **Descriptive row only** (A1 §1.2 fallback: archive-trained model on rebuilt
inputs). **No pass/fail rule.** Its purpose is to measure input-induced drift against the re-execution floor
measured by the unmodified-rollout control (d4_wind ≤ 4.2e-7; Owen PASS WITH NOTES at 10ce6b93).

**Dependency, hard.** Do not start until Daniel's rebuilt US2024 **weather** is in and pinned (A1 item 14). Slope
and tree cover alone do not make a rebuilt-input run.

## Fixed before the run

- **Model.** `d4_wind_seed0`, frozen checkpoint sha 33c5b3cf…, through `survival.sample_forecast` unchanged (same
  call as `score_cohorts.predict_case`).
- **Inputs.**
  - Environment: Daniel's `rebuild_env.sh --project` output for the six fires, pinned by its `input_manifest.json`
    (sha recorded in the output header).
  - Perimeters: the same rebuilt perimeters as the control. They reproduced all 273 receipts' initial, endpoint and
    mask hashes.
- **Case set.** Exactly the 273 stored heldout cases at 6a3265a0, reported as n = 273.
  - All 273 have hours ≤ 48 (max 48.0, min 4.38), so none of the 51 US2024 intervals over 48 h is included.
  - Cases are keyed by case_id. Cells are exactly the stored (interval, row, col, y), not re-derived.
  - A case whose rebuilt environment leaves a stored cell unsupported is reported as such, never dropped silently.
- **Identity expectations.**
  - `initial_sha256`, `endpoint_sha256`, `reference_mask_sha256`, `initial_age_sha256` and `rectangle` must equal
    the stored receipt. A mismatch is reported and the case is flagged.
  - `environmental_snapshot_sha256` is expected to differ, since that is the change.
  - `residence_sha256` is reported either way: it depends on fuel layers, which may be rebuilt.
- **dist_m.** Euclidean distance between 375 m cell centres to the nearest cell of the cutoff mapped union (A1 §4),
  emitted per stored cell. The 4 km band is dist_m ≤ 4000.

## Summaries reported (all of them, whatever they show)

For p_rebuilt (this run) against p_original (stored `p_d4_wind_seed0`), on the stored cells:
1. |Δp| = |p_rebuilt − p_original|: max, median, mean and 99th percentile, pooled and per fire. Also the count of
   cells with |Δp| > 4.2e-7 (above the re-execution floor).
2. Brier score of each against y, and the delta (rebuilt − original), in the full domain and the 4 km band, pooled
   and per fire.
3. Average precision of each against y, and the delta, in the full domain and the 4 km band, pooled and per fire.
4. Tail: the share of cells, and the share of positives (y = 1), with p < 1/1024, for each predictor, in the full
   domain and the 4 km band.
5. n cases, n cells, n positives, n flagged cases (identity mismatch or unsupported cells).
No bootstrap intervals and no decision. Any later addition goes in a new dated section and does not replace these.

## Not in this run

The mean-field half-step variant is not preregistered and is not built (Victor's decision). The CA half-step on R
is development-only and is held behind Iris's ranking (items 1–3).
