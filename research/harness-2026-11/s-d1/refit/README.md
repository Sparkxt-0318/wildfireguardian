# Refit tooling (S-D9 A1 §3.1 / §3.2)

| file | role | pinned |
|---|---|---|
| `run_pipeline_rebuilt.py` | d4_wind_rebuilt / logistic_rebuilt via the unmodified pipeline | A1 §3.1, sha256 `264deaea…` |
| `write_receipt_addendum.py` | REFIT_RECEIPT_ADDENDUM.json beside each receipt | `54b0f957…` (ab7a1f77) |
| `run_c651_recipe.py` | c651_fullvalid on/off (prepare + candidate stages) | A1 item 26, `3e99f479…` (81dc7c2e) |
| `c651_sampling_gate.py` | totals gate for the c651 sampling recipe | `153bf393…` (03b55002); Owen PASS WITH NOTES |
| `check_refit_env.py` | **mandatory preflight**: fails unless the environment equals the pins | not pinned (new) |
| `requirements-refit.txt` | the pins | |

## The pins are load-bearing

Owen (verdict on 81dc7c2): the c651 recipe smoke passes only in the pinned environment
(Python 3.12, numpy 1.26.4, pandas 2.2.3, rasterio 1.4.3, scipy 1.13.1, torch 2.5.1). Under pandas 3.1.1 /
numpy 2.5.4 the **unmodified** `forecast/wildfire/prepare.py` already fails at line 946
(`assert current_utc == expected_utc`) in the `--fullvalid off` arm, i.e. with no wrapper change at all, likely
pandas-3 timestamp resolution. A refit run elsewhere is therefore not the recorded recipe.

Rule: every refit command is preceded, with the same interpreter, by

    V/bin/python research/harness-2026-11/s-d1/refit/check_refit_env.py --out RUN_DIR

which writes `RUN_DIR/REFIT_ENV_CHECK.json` and exits non-zero on any mismatch; the wrapper runs only if it
passes (`&&`). Each REFIT_RECEIPT sent to Victor carries that file. The check is a separate script so the
pinned wrappers keep their bytes and their A1 sha256 values.

Install: `python3.12 -m venv V && V/bin/pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && V/bin/pip install -r requirements-refit.txt`
(`--index-url`, not `--extra-index-url`).

## Known property of the training data (Elena, UNVERIFIED; relayed by the orchestrator 2026-11-12)

On part a (490 events, 3,773 intervals ≤ 48 h, the same interval count as `TRAIN_EVENTS_preweather.json`; 122,640
new-burn cells), Elena's `refit/preweather_unscored.py` at b7cdc48f on claude/s-d2-next finds:
- 12,384 new-burn cells (10.1%) lie outside `crop_box(initial, MARGIN 10)`;
- `pipeline.cropped` drops them in every arm, so they never enter training;
- they are concentrated in 97 intervals (2.6%).

The largest reach events are therefore absent from training for d4_wind_rebuilt, logistic_rebuilt and the D2 arms
alike. This is a property of the frozen recipe's crop, not of a wrapper. Victor decides whether it is declared under
A1 item 22. Before weather, unscored-inside-crop is 0. The non-finite-kernel count follows once the weather pins
exist. Not verified by me.
