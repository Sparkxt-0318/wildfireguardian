# Wapiti reconciliation: step list (committed before any number is computed)

**Question (external review via the orchestrator, 2026-11-12).** The preprint checkpoint (M548 = c651, sha c651f672…)
behaves differently on Wapiti in two evaluations:
- On the preprint's 25 Wapiti intervals it is **8.17% better** than the always-zero ("no new burn") forecast. This is
  Victor's exact reproduction, `S-D9/derive/M548_REPRO.*`, PR #125 at 86550a33; Hannah PASS WITH NOTES, ledger row 32.
- In the six-fire full-rectangle evaluation it is **worse** on Wapiti: per-fire difference +0.0034.

This note attributes the sign change to the differences between the two evaluations, one factor at a time. **Existing
outputs only, no new fits, exposed development fire only (Wapiti, cohort R). Verifier: Owen.**

## Inputs
- **(S) six-fire evaluation.** The stored heldout entries on Main at 6a3265a0:
  `forecast/runs/20261030_perimeter_trained/execution_v3/heldout/ID-BOF-000683_Wapiti_Wapiti.npz` (interval, row,
  col, y, p_c651_mc, t1, hours) and the matching case receipts.
- **(M) preprint set.** The owner archive (sha b9e000e8…dd65), `runs/20261013_observed_stored_validation/`:
  intervals.csv and the 25 Wapiti case directories (reference.npz, m548_prediction.npz, protocol.json, report.json).
  - Read with Daniel's remote_zip.py. The link is held only in the environment.
  - **Nothing from the archive is committed**: only hashes, counts and Brier values.
- **Definitions of (M)** are Victor's, as stated in his reproduction:
  - mask: valid in the reference at both times, valid in the prediction, and unburned at the cutoff;
  - label: NIROPS-mapped burned at the endpoint;
  - prediction: the M548 `probability` from 1,024 trajectories;
  - reference forecast: always zero.
- The (M) totals must reproduce Victor's numbers before anything else is reported: 275,961 entries, 2,525 positives,
  Brier(zero) 0.0084025, BSS 8.168%. If they do not, the note stops there.

## Forecasts compared at every step
- **c651**: p_c651_mc in (S), or the M548 probability in (M).
- **zero**: the always-zero forecast. On both masks the cells are unburned at the cutoff, so S-D9 "persistence" equals
  zero there. This is stated, not assumed: it is checked at step A0.

## Steps (fixed order; each reports n cells, positives, Brier(c651), Brier(zero), the difference and BSS)
- **A0. (S) as stored**, Wapiti rows only. It must reproduce the +0.0034 per-fire difference.
- **A1. Interval set.** Keep only the (S) intervals that match an (M) interval by identical cutoff and endpoint
  timestamps (exact, to the second). Report the matched count. The cells within each interval are unchanged.
- **A2. Cell mask.** Within the matched intervals, keep only cells that are also in the (M) mask. Cells are matched by
  cell-centre world coordinates. If the grids are not cell-aligned (different transform or origin), this and the later
  cell-level steps are reported as NOT COMPUTABLE, with the reason, and the note continues with interval-level totals
  only.
- **A3. Labels.** On the A2 cells, replace (S) labels (rebuilt NIROPS perimeter states) with (M) reference labels.
- **A4. Predictions.** On the A2 cells, replace p_c651_mc with the (M) M548 probability. Same checkpoint, but a
  different run, inputs and RNG.
- **A5. Full (M) mask** on the matched intervals, adding (M) cells that are not in (S).
- **A6. Full (M) set**, adding the unmatched (M) intervals. This must equal the (M) totals above.

**Path dependence.** Besides the fixed order, each factor (interval set, mask, labels, predictions) is also applied
**alone** to A1. The note reports the step at which the sign flips in the fixed order and the single-factor effects;
it claims an attribution only where both agree.

## Output
`WAPITI_NOTE.md` plus `RESULTS_wapiti.json` (counts and Brier only; input hashes). Until the note exists, harness
documents describe the preprint result as specific to the preprint's 25-interval cohort.
