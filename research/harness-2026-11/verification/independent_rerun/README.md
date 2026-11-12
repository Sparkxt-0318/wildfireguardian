# Independent part-a rerun (Owen)

**Purpose.** This rebuilds the S-D9 part-a scoring table from raw inputs and compares hashes. It rests on no session's statement: every input is either downloaded raw and sha-checked, or read from git at a pinned commit and sha-checked. It covers `logistic_rebuilt`, `d4_wind_recal` and `d2_bracket_rebuilt`, scored as the pooled paired Brier difference in the 4 km band with a whole-fire bootstrap, seed 20261030.

It is part a only and keyed on Incident_C. NIROPS is read only through `nirops_access.py`: the ID column first, then by fid.

    research/harness-2026-11/verification/independent_rerun/parta_rerun.sh WORK_DIR [PYTHON]

`PYTHON` is the pinned environment in `requirements-rerun.txt`: the refit pins plus pyogrio 0.10.0 and geopandas 1.0.1, which the label builder needs.

Exit codes:
- **0:** every stage ran and every hash matched.
- **1:** a mismatch, a failure or a wrong environment. The harness fails closed.
- **3:** every runnable stage matched, but PENDING inputs stop the rest.

## Stages

| stage | what | status (2026-11-12) |
|---|---|---|
| S0 | 15 pinned sources, each checked by sha256 at its commit (`PINS.json`); lists PENDING inputs | runs; all 15 match |
| S0b | `check_refit_env.py` at 39cd863b, run with the same interpreter | runs; fails closed under numpy 2 / pandas 3 (tested) |
| S1 | NIROPS zip downloaded by `fetch.py` and checked (b19fb16c…), shapefile checked (a14f391a…). Every allowlisted incident (7db3cc0e…, 490) is rebuilt with `build_nirops_event_v2.py`. Its states.npz and perimeters.geojson sha256 are compared with the committed PERIMETER_MANIFEST (08f96b45…) and the committed states.npz (data-fetch-3 @adbfcda5) | **490/490 match** (states vs manifest, states vs committed file, geojson vs manifest); 12 min 45 s with 4 jobs |
| S2 | terrain, landcover, biome and weather inputs rebuilt and compared with the pinned input manifest | PENDING: weather manifest (Daniel, 13 Nov) |
| S3 | predictions on part-a entries from each refit checkpoint, checkpoints sha-checked against their receipts; `d4_wind_recal` fitted on `d4_wind_rebuilt` | PENDING: checkpoints, receipts, the prediction command, the recal code |
| S4 | `s4_score.py`, an independent numpy-only scorer that shares no code with sd9bench or wildfire.baselines. Its table sha256 is compared with the committed part-a table, and its numbers with sd9bench | scorer tested (below); the committed table is PENDING |

## S4 tests

- **Agreement.** On the 6 forecast-v2 held-out fires (1,705,079 entries; a synthetic deterministic dist_m, used only to exercise the band), `s4_score.py` agrees with the frozen sd9bench CLI (score.py 1ac8d933…) within a relative 1e-12. That covers point, interval ends, per-fire differences and model Brier for 4 pairs.
- **Mutant.** A +1e-3 change to one band entry out of about 0.8 M gives 5 differences and exit 1.
- **sd9bench limitation.** The sd9bench CLI pairs every model only against `persistence` and `dilation_best`. It cannot write the §6.1 criterion 3/4 pairs (vs `logistic_rebuilt`, vs `d4_wind_recal`). A committed table for those pairs has to come from another writer, and `s4_score.py` reports the pair as absent.

## Notes

- A part-a table from the A1 §3.1 refits is **in-sample**, because the refits train on all 490 part-a incidents. It is development-only by construction.
- A1 §3.1 item 6 does not claim bitwise equality of torch training across hosts. S3 therefore checks checkpoints by sha and rebuilds everything downstream. Re-running the refits themselves, if wanted, can only be compared within a stated tolerance.
- The pinned environment has no pyogrio/geopandas, which the label builder needs. With pyogrio 0.10.0 and geopandas 1.0.1, S1's outputs are byte-identical to the committed ones.
