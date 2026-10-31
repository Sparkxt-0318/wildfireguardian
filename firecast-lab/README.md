# firecast-lab (Track A)

Calibrated probabilistic fire-hazard generator; side project of the program (rules: `CLAUDE.md`). Splits:
`SPLITS.json`. Data caveats: `docs/DATA_NOTES.md`. Metric definitions and the scoring domain: `METRICS.md`.

## Phase 0 baselines on the real data (Mac)

The real data root is not in the repo; every command refuses to run without it and never falls back.

```bash
export FIRECAST_DATA_ROOT=/path/to/data/environment        # events.json + regions/
python program/benchlock.py --label fl-dilation -- firecast-lab run --baseline dilation --split dev
#   -> firecast-lab/results/dilation.csv: one row per dev window, with commit, seed, config and host
python program/benchlock.py --label fl-c651-timing -- firecast-lab time-c651 --fire KFS_02 --members 256
#   time c651 on one fire BEFORE any full c651 run (needs torch 2.5.1); it extrapolates the dev run
```

Baselines (`--baseline`): `persistence`, `dilation` (k tuned by least pooled Brier), `calibrated_dilation`
(per-lead isotonic map of the Chebyshev distance to the front; the bar to beat), `logistic` (distance, wind
alignment, slope), `c651` (frozen checkpoint; in-sample on 25 dev fires). Dev scores are cross-fitted by leaving out
one SPLITS fold of whole fires. Every baseline gives K coherent members (`--members`, default 64, matched across
baselines) and is scored on identical cells, next to persistence and calibrated dilation in the same row. Rows hold
sums: pool by summing, resample whole fires with `metrics.fire_bootstrap`. `--split test` needs `--allow-test`
(milestones only, after Siyeong approves).

## Members, couplings and scenario sets

- `members.coherent_members(cum, K, seed=..., coupling=...)`: member k has burned a cell by lead l iff
  `U_k <= cum[l]`, one uniform field per member for every lead. Marginals are exact up to Monte Carlo error.
  - `shared` (default): one uniform per member, nested members; the least conservative coupling for
    "every member clear".
  - `copula --length-cells L`: Gaussian copula with declared correlation `exp(-r^2 / 2L^2)`.
  - The coupling is a modelling choice to calibrate on dev (backlog L8), not a fact.
- `producer.from_window(window, hours, model=..., seed=..., config=...)` writes hazard_contract v1 sets:
  - `source="model"`, the repo packet heat source, horizon = lead, provenance = commit, seed, config, host.
  - Unknown cells are NaN and unsupported.
  - Cells outside the reconstruction domain stay supported with the model's forecast (`producer` docstring).

## Open questions (for Siyeong)

1. Which coupling (and correlation length) should the decision metric use by default?
2. Present fire uses each cell's reconstructed arrival age ("exact"); hazard_contract's packet default is the
   router's `R_max` enclosure. Keep "exact"?
