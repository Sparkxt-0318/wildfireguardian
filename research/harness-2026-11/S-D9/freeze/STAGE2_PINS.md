# FREEZE stage 2: pins collected so far (working record, NOT the freeze)

This file records inputs as they are pinned, before the stage-2 FREEZE file is generated.
- Each row says who supplied the pin and who checked it.
- Nothing here is frozen until `make_freeze.py` writes the stage-2 amendment record and Hannah verifies it.
- Part c stays closed until then (A1 §6.1, §9).

| item | value | source | status |
|---|---|---|---|
| refit `--train-events`, **pre-weather** | `TRAIN_EVENTS_preweather.txt`, sha256 `bbedca82b10ff0d7737feac78f7997bb57e26f3af6028eb10516d4cb7c42b55b` (513 = fit-23 + 490 part a) | Marcus, harness/s-d1-next e29524a4 (`s-d1/refit/train_events/`); built from Daniel's part-a pool 982eb71c (data-fetch-3) | Victor checked: the sha matches; the 490 part-a IDs equal PART_A_ALLOWLIST_FINAL (7db3cc0e…) exactly; the other 23 are the fit-23. **Pre-weather: superseded by the final list** |
| refit `--train-events`, **final** | pending | Marcus, after tonight's weather. Same rule (≥ 2 surveys, ≥ 1 interval ≤ 48 h), plus a report of incidents with no usable interval by `Environment.available_at`; nothing is replaced | pending |
| part-a pool build | daniel/data-fetch-3 982eb71c `parta_pool/` (490/490 OK) | Daniel | pin the manifest sha when it is committed |
| weather input-manifest | pending | Daniel (13 Nov) | pending |
| d2_bracket_rebuilt code | `d2_bracket.py` 98d7d6c6…, `run_d2_bracket.py` cc41cc33…, `run_d2.py` e3c0843c… (claude/s-d2-next) | Elena | final head and Owen's verification pending |
| part-a scoring table (development-only, in-sample) | **does not exist yet**: the refits have not run (weather 13–14 Nov). When produced: `PYTHONPATH=research/harness-2026-11/S-D9 python -m sd9bench --out PARTA_SCORES.json --predictors <list> --population full_rectangle --draws 10000 --seed 20261030 <per-fire .npz>`. The output is deterministic (sorted keys, indent 1, no NaN), so a byte comparison is meaningful under a pinned environment | Victor (table), Owen (independent rerun) | pending |
| part-a prediction command per refit checkpoint (replaces the retired `pipeline.py heldout`) | per-fire `.npz` in the `sd9bench/entries.py` contract (`interval`, `y`, `hours`, `p_<predictor>`, `dist_m`) | Marcus | pending |
| `d4_wind_recal` fit code | A1 §3.1: a one-feature logistic recalibration on logit(p) of `d4_wind_rebuilt`, fit on the §3.1 training data, frozen by SHA before part c. No code is committed. **Details A1 leaves open are to be pinned here before the fit:** the subsample and weights, the population, and the p clipping before the logit | Marcus writes; Owen verifies | pending |
| table pairs | for each admitted D1/D2 candidate (headline `d2_bracket_rebuilt`, fallback `d2_nll_rebuilt`, then secondaries): candidate − `persistence`, − `dilation_8h`, − `logistic_rebuilt`, − `d4_wind_recal` (§6.1 criteria 1–4), plus the lowest-bin [0, 0.1) calibration gap (criterion 5); also the comparator `d4_wind_rebuilt` − `logistic_rebuilt` | Victor | proposed |
