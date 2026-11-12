# S-D9: multi-fire, multi-horizon probabilistic benchmark harness

Status: the **harness and its correctness check are complete**. The pre-registration addendum is still a draft, and **no new score has been produced or inspected**.

| file | contents |
|---|---|
| `INVENTORY.md` | step 1: the evaluation assets that already exist (checkpoint df5aa8e) |
| `ledger/` | fire-exposure ledger, committed before any score (checkpoint 3e2eb2d); 0 untouched fires in the repository |
| `sd9bench/` | scoring harness (input contract in `sd9bench/entries.py`) |
| `tests/` | the forecast-v2 reproduction test and unit tests |

## Interface for D1/D2 and later streams

Write one `<fire>.npz` per fire with `interval`, `y`, `hours` and `p_<predictor>`. `dist_m` and `area_samples_<predictor>` are optional. This is the same layout as `forecast/runs/20261030_perimeter_trained/execution_v3/heldout/*.npz`, so persistence, dilation and logistic can sit in the same files on identical cells.

```python
import sys; sys.path.insert(0, "research/harness-2026-11/S-D9")
from sd9bench import load, score
result = score(load(paths), mc_trajectories={"c651_mc": 1024})
```

```sh
PYTHONPATH=research/harness-2026-11/S-D9 python -m sd9bench --out RESULTS.json --mc c651_mc=1024 FIRE1.npz FIRE2.npz
```

The output contains:
- Everything forecast-v2 reports per predictor, using the same code (`forecast/wildfire/baselines.py`): pooled and per-fire Brier, BSS against persistence and against the best dilation, AP, ROC AUC, 10-bin calibration and ECE, clipped and exact NLL, exact zero-probability positives, the lowest-bin record, paired whole-fire Brier intervals, and paired BSS intervals (10,000 draws, seed 20261030).
- Additions:
  - `base_rate_bss`: an in-sample uncertainty-term diagnostic.
  - `by_horizon`: horizon bins (0,12], (12,24], (24,36], (36,48] h, with entry, fire and interval counts per bin.
  - `by_band`: distance-to-cutoff-burn bands (0,1], (1,2], (2,4], (4,8] km. Requires `dist_m`.
  - `area_crps`: exact ensemble CRPS of the new-burn cell count per interval. Requires `area_samples`; otherwise it is marked unavailable and never approximated.

## Correctness check (measured)

```sh
python3.12 -m venv V && V/bin/pip install numpy==1.26.4 scipy==1.13.1 pytest
cd research/harness-2026-11/S-D9 && ../../../V/bin/python -m pytest -q tests -p no:cacheprovider
```

The result is `24 passed`. The reproduction tests take about 66 s on this container (4 tests) and the unit tests take 0.4 s (20 tests).

`tests/test_reproduce_forecast_v2.py` recomputes the `heldout` block of `research/forecast-v2/RESULTS.json` from the committed per-fire entry files. It covers 1,705,079 entries, 8,520 positives and 6 fires. It compares **every** published field for all 16 predictors: pooled, per-fire, calibration bins, lowest bin, exact NLL, both BSS references, both paired-BSS intervals and the c651 Monte Carlo variance correction. It also compares all 30 paired whole-fire Brier intervals. Integers must match exactly; floats must agree within 1e-12 relative. All match.

## Not done yet, and not verified

- The 8.17% Wapiti preprint figure is reproduced only arithmetically, from the stored aggregate record (`INVENTORY.md` §1). The cell-level M548 exports are not in git (a request is out to Daniel).
- No per-horizon or per-band score on any cohort has been printed or inspected. This is deliberate: those strata and the primary statistic are fixed in the pre-registration addendum first.
- The arrival-time score is not implemented yet. It needs hourly cumulative marginals per cell, and its file field will be agreed with D1 and D2.
- `dist_m` is not present in the forecast-v2 files. The cutoff burn masks are referenced by hash in the case receipts but are not in git, so band strata on US2024 need the inputs rebuilt.
