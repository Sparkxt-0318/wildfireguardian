# Unmodified-rollout control: six US2024 fires, original inputs

Script: `unmodified_rollout_control.py`. It calls the frozen `pipeline.py` (88d376d2…) and `score_cohorts.py`
(88bb3839…) functions unchanged.

Stored reference: `forecast/runs/20261030_perimeter_trained/execution_v3/heldout/` on Main, last changed at 6a3265a0.
It has 273 SCORED case receipts plus their npz entry files.

## Inputs (outside git)

1. **Environment.** Owner archive (sha256 b9e000e8…dd65, DATA_PROVENANCE.md), read with Daniel's
   `research/harness-2026-11/data-fetch-3/remote_zip.py` (daniel/data-fetch-3 @ dd154036). The link is held only in
   the `REMOTE_ZIP_URL` environment variable and is never recorded. Members extracted (CRC-32 checked; 2,264 members):

       'wildfire/data/environment/*.json' 'wildfire/data/environment/*.csv'
       'wildfire/data/environment/regions/<EVENT>/*'   for the six EVENTs in the script

   Here `*` also matches `/`, so the JSON pattern pulls nested JSON as well. The script pins every file present under
   the data root (2,222 files, `inputs_digest` in each output header). Data root: `<dest>/wildfire/data/environment`.
2. **Perimeters.** Run the unmodified `research/forecast-v2/scripts/prepare_perimeters.py --shapefile
   NIROPS_2020_2024_R1_R6.shp --zenodo <unzipped Choi archive> --out PERIM`. The NIROPS zip has sha b19fb16c… and the
   Choi zip has sha 612edf5f… (daniel/data-fetch fetch scripts). The manifest embeds `created_utc`, so its sha differs
   on every run. Identity is checked per case instead (below).
3. **Environment preflight:** `refit/check_refit_env.py` passed (`REFIT_ENV_CHECK.json`).

## Commands

    V=<py3.12 venv per refit/requirements-refit.txt + torch 2.5.1 cpu>
    $V research/harness-2026-11/s-d1/control/unmodified_rollout_control.py --stage identity \
        --data-root ARCH/wildfire/data/environment --perimeters PERIM --heldout HELDOUT --work W --out identity.jsonl
    ... --stage d4_wind --threads 4 ...   (same arguments)
    ... --stage c651 --threads 2 --shard 0/20 ...  and  --shard 10/20   (every 10th case; see below)

`HELDOUT` is a checkout of the stored heldout directory at 6a3265a0
(`git archive origin/Main <dir> | tar -x`).

## Claims

- `RESULTS_identity.jsonl` (Owen PASS WITH NOTES at 10ce6b93): all 273 cases have `identity_mismatch == []` and `entries_match`. The receipt fields
  compared are the full `score_cohorts.source_identity`: `initial_sha256`, `endpoint_sha256`,
  `environmental_snapshot_sha256`, `reference_mask_sha256`, `initial_age_sha256`, `residence_sha256`, `rectangle`,
  `reference_cells` and `weather_hour`. `entries_match` means the stored `y` equals the rebuilt endpoint at the stored
  (row, col), every stored cell is in the score mask, and none is initially burned.
- `RESULTS_d4_wind.jsonl` (Owen PASS WITH NOTES; reproduces to 4.2e-7, not identical): `sample_forecast(d4_wind_seed0)` compared with the stored `p_d4_wind_seed0` over all
  1,705,079 stored cells. 471,597 cells (27.7%) are bit-identical in float32; max |Δ| = 4.2e-7; all cells valid.
- c651_mc (1024 trajectories, seed 0, batch 32, `pipeline.c651_monte_carlo` unchanged): **34 of 273 cases run;
  bit-identical to the stored `p_c651_mc` (max |Δ| = 0) on every case run.** This is not a claim about all 273 cases.
  The orchestrator decided the subset stands as the control.
  - **Owen, PASS WITH NOTES (cc34b18a):** bit-identical on every case run, **40 of 273**. That is the 34 run here
    plus 6 that Owen chose by a spacing rule fixed before any result (script-order indices 7→8, 53, 99, 145, 191,
    237; one per fire, none in the 34). He also reran 2 of the 34. Over his reruns, 66,311 of 66,311 cells are
    bit-identical.
  - 233 of 273 cases have not been run by anyone. The claim stays "on every case run (40 of 273)".
  - `RESULTS_c651_every10.jsonl` (b6db989f…): fixed subset, every 10th case in the script's case order (shards 0/20
    and 10/20). 28 cases covering all six fires (Wapiti 6, Lava 5, Pioneer 5, Goat 4, RedRock 4, FishCreek 4);
    175,773 cells, all bit-identical; all valid; all identity checks pass.
  - The subset was chosen AFTER seeing the first 7 Wapiti cases of a full run, which were also all bit-identical
    (`RESULTS_c651_first7_prior_to_subset.jsonl`, 5bb407e7…; 81,331 cells). That run was stopped because the full set
    would take about 10 h here. One case appears in both files.
  - Not run: the other 239 cases. The claim is for the 34 distinct cases run, not for the full 273.
  - Cost on this host (x86-64, 2 processes × 2 threads at once): 6,768 s of model time for the 28 cases, against
    1,698 s stored for the same cases on the original host (arm64, 2 threads), so about 4.0× slower per case here.
    This is a host-specific end-to-end figure, including kernel evaluation.

Runtimes on this host (x86-64, 4 cores): identity rebuild of 273 cases took 2 min 37 s wall. d4_wind stage took
3 min 40 s wall (4 threads), of which 64 s is model time.

Coverage in both directions (Owen's note): `check_case_coverage.py --results RESULTS_identity.jsonl --heldout HELDOUT`
reports 273 rebuilt case_ids, all unique, equal to the 273 stored receipts, with none stored-not-rebuilt and none
rebuilt-not-stored. The same holds for RESULTS_d4_wind.jsonl.

## Rebuilt-input run and channel diagnostic (2026-11-13)

**Rebuilt-input run.**
- Descriptive row per REBUILT_INPUT_PLAN. Scripts were committed before the run (c0d1836e); results are at 2fe48893.
- RESULTS_rebuilt_input.jsonl and RESULTS_rebuilt_input_summary.json: 273/273 cases, max |Δp| 3.58e-7, 0 cells above
  the 4.2e-7 floor.

**One-case diagnostic.**
- `diag_env_channels_one_case.py` with DIAG_env_channels_one_case.txt.
- It was **committed together with its output at 2fe48893, NOT before it**: it was an ad-hoc check, run after the
  summaries (Owen's note).

**All-case diagnostic.**
- `diag_env_channels.py`. Its rule is fixed in its docstring and was committed before running, at 6b5f2268. The
  result is DIAG_env_channels.json at f3f07aed.
- 18/19 channels equal on 273/273 cases. terrain.slope_degrees differs on every case: max 7.63e-6 deg, on ≤ 14.6% of
  cells.
- Owen independently confirmed the per-fire slope differences and the value-identity of the other sources from raster
  comparisons.
- Wording: reproduction of the inputs, not evidence of model insensitivity.
- Owen's side note: several fuel and vegetation rasters differ at byte level with identical values, so byte-level pins
  on those files cannot match across rebuilds.
