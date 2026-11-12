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

- `RESULTS_identity.jsonl`: all 273 cases have `identity_mismatch == []` and `entries_match`. The receipt fields
  compared are the full `score_cohorts.source_identity`: `initial_sha256`, `endpoint_sha256`,
  `environmental_snapshot_sha256`, `reference_mask_sha256`, `initial_age_sha256`, `residence_sha256`, `rectangle`,
  `reference_cells` and `weather_hour`. `entries_match` means the stored `y` equals the rebuilt endpoint at the stored
  (row, col), every stored cell is in the score mask, and none is initially burned.
- `RESULTS_d4_wind.jsonl`: `sample_forecast(d4_wind_seed0)` compared with the stored `p_d4_wind_seed0` over all
  1,705,079 stored cells. 471,597 cells (27.7%) are bit-identical in float32; max |Δ| = 4.2e-7; all cells valid.
- c651_mc: run on a fixed subset, every 10th case in the script's case order. This was chosen after seeing 7
  Wapiti cases, all bit-identical. A full run would take about 10 h on this host, about 4.6× slower per case than
  the original host. Results will be in `RESULTS_c651_every10.jsonl`, plus the 7 early cases kept separately.

Runtimes on this host (x86-64, 4 cores): identity rebuild of 273 cases took 2 min 37 s wall. d4_wind stage took
3 min 40 s wall (4 threads), of which 64 s is model time.
