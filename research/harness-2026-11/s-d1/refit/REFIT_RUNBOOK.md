# Refit runbook (A1 §3.1 d4_wind_rebuilt and logistic_rebuilt): orchestrator-approved 2026-11-12, before any run

**Environment fact (Elena's diagnosis).** The container is reclaimed when the session goes idle. Detached processes
die with it. Harness-tracked background tasks keep it alive for at most 2 h each.

## Fit command
- **Byte-identical to A1 §3.1**, through the unchanged wrapper `run_pipeline_rebuilt.py` (264deaea…). pipeline.py
  (88d376d2…) is untouched.
- It is preceded by `check_refit_env.py --out RUN_DIR`.
- d4_wind_rebuilt: `final --variant d4_wind --seed 0 --epochs 3 --hidden 16 --lr 0.003 --samples-per-step 1
  --threads 2 --n-samples 1024 --balance --max-fit-intervals-per-fire 0 --intervals-per-epoch 0`, with
  `--input-manifest <Daniel's pins>` and `--train-events train_events/TRAIN_EVENTS_final.txt`.
- logistic_rebuilt: `pipeline.py baselines` per A1 §3.1, same pins and train events.

## Keeping it alive (no change to the fit process)
1. The fit runs detached: `nohup … > RUN_DIR/fit.log 2>&1 &`.
2. A separate heartbeat shell loop appends `date, pid alive, RSS` every 60 s to `RUN_DIR/HEARTBEAT.log`. It reads
   /proc only.
3. **Chained tracked waiters**, each ≤ 110 min. A waiter polls the pid and heartbeat and exits when the fit ends or
   when its limit is reached. Its completion wakes the session, and the next waiter starts at once.
4. **Backstop:** a self check-in scheduled about every 10 minutes (send_later, re-armed on each check-in) while a fit
   runs.
5. **Staggering:** the logistic refit (cheap) runs first. d4_wind_rebuilt starts after it finishes, so one container
   loss cannot kill both late in their runs. Peak RSS of each is recorded to decide whether parallel runs are safe
   later.
6. **Loss:** relaunch the IDENTICAL command and append (UTC time, reason, attempt n) to `RUN_DIR/RESTARTS.log`, which
   goes into the receipt. **After two consecutive attempts lost to reclaim: stop and report to the orchestrator**,
   since that is an environment limit to raise with the owner.

## Timing first (declared before running; not used for any decision)
- Subset: `train_events/TIMING_SUBSET.txt`, the first 3 fit-23 fires and the first 5 part-a incidents, each sorted
  by id.
- Command: the same command with `--epochs 1` and `--train-events train_events/TIMING_SUBSET.txt`, in a scratch
  run directory.
- Report: the wall time per training interval, extrapolated to 3 epochs over the final list's interval count.
  **If the extrapolation exceeds ~4 h, flag it before launching.**

## Declared deviation, 2026-11-13 01:30 UTC (orchestrator ruling), recorded before any timing run
- **Run.** The one-epoch timing runs now on the **5 part-a events of TIMING_SUBSET only**, as a tracked task. The 3
  fit-23 fires are omitted because their weather lands on day 2.
- **Use.** The timing is an estimate only. No loss or score from it is read for any decision or reported as a result.
- **Re-timing.** The declared subset (3 fit-23 + 5 part-a) is re-timed after day 2 if the estimate matters for
  scheduling.
- **Gate.** No refit starts before TRAIN_EVENTS_final and Victor's check.
- **Status at recording: BLOCKED on inputs.** The part-a environment files behind Daniel's pins (f70e52b0) are not
  in this container. The options (a/b/c) are with the orchestrator.

## Executor instructions (verbatim-runnable by someone other than Marcus), 2026-11-13

Orchestrator ruling, 01:31 UTC:
- Daniel runs the timing in his container and reports wall time only.
- If the environment fits there, the refits also run there, as tracked, checkpointed tasks. Marcus owns the commands,
  the receipts and the reading of committed outputs. The executor changes no model code.

**0. Checkout and pins.**
- `git fetch origin harness/s-d1-next && git checkout <COMMIT>`. COMMIT is the commit that contains this section; it is
  named in Marcus's message. All paths below are relative to that checkout's root.
- `PINS` = daniel/data-fetch-3 @ 748afe70 `research/harness-2026-11/data-fetch-3/weather/pins/parta_input_manifest_night1.json`.
  Verify that `sha256sum PINS` = `f70e52b00bfd8eaf12743cd60599238e72abefca80cbc0802c51a52a8ea2005a`.
- `WS` = the part-a workspace the pins were made from. It must hold `data/environment/` (events.json, regions/<490>,
  …) and `data/perimeters/{<490>/states.npz, PERIMETER_MANIFEST.json}` (parta_pool/README.md layout). PINS paths are
  relative to `$WS/data`.

**1. Interpreter (pinned; mandatory).**
- `python3.12 -m venv V && V/bin/pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu && V/bin/pip install -r research/harness-2026-11/s-d1/refit/requirements-refit.txt`
- `--index-url`, not `--extra-index-url`.

**2. Timing: 5 part-a events, 1 epoch.**
- This is the declared deviation above. It is an estimate only: report wall time, nothing else.
- `TE = research/harness-2026-11/s-d1/refit/train_events/TIMING_SUBSET_PARTA5.txt`,
  sha256 `b4ea06690a3e1c58fdf1f6caab1edf055ab01dc8cd15d3ec3a58039d8f401a2d`.

```
RUN=$SCRATCH/timing_parta5; mkdir -p $RUN
V/bin/python research/harness-2026-11/s-d1/refit/check_refit_env.py --out $RUN && \
nohup V/bin/python research/harness-2026-11/s-d1/refit/run_pipeline_rebuilt.py \
  --input-manifest PINS --train-events TE -- final \
  --data-root $WS/data/environment --perimeters $WS/data/perimeters --work $RUN/work --run $RUN \
  --variant d4_wind --seed 0 --epochs 1 --hidden 16 --lr 0.003 --samples-per-step 1 --threads 2 \
  --n-samples 1024 --balance --max-fit-intervals-per-fire 0 --intervals-per-epoch 0 > $RUN/fit.log 2>&1 &
```

- Run it as a harness-tracked task. Use the heartbeat loop of "Keeping it alive" (`date`, pid alive, RSS from /proc
  every 60 s → `$RUN/HEARTBEAT.log`).
- Expected outputs:
  - `$RUN/REFIT_ENV_CHECK.json`, which must say pass;
  - `$RUN/REFIT_RECEIPT_final.json`, carrying `wall_seconds`, `train_events` and the shas;
  - `result.json` and `checkpoint.pt` under `$RUN/<intended_phase result dir>/` (pipeline.command_final), with
    `result.json` carrying `fit_seconds`, `train_samples` and `train_events`.
- **Report:** `fit_seconds`, `train_samples`, `wall_seconds` and peak RSS from HEARTBEAT.log, plus the shas of the
  receipt and of REFIT_ENV_CHECK.json.
- Do NOT report or read the loss in `result.json["fit"]`.
- Marcus extrapolates: (fit_seconds / train_samples) × 3 epochs × the final list's sample count. If that exceeds
  ~4 h, it is flagged before any refit.

**3. Refits.** NOT before TRAIN_EVENTS_final.txt (after fit-23 weather, day 2) and Victor's check. Same form as step 2:
- `--train-events research/harness-2026-11/s-d1/refit/train_events/TRAIN_EVENTS_final.txt`;
- `--epochs 3`;
- PINS = the combined pins file Daniel issues for fit-23 + part a (sha named then);
- `--data-root` / `--perimeters` = the workspace holding all 513 events.
Order: logistic_rebuilt first (`-- baselines` with the same data/perimeters/work/run arguments **and `--max-fit-intervals-per-fire 0`**, per A1 §3.1; the archived logistic run a03_baselines ended its argv with `--max-fit-intervals-per-fire 0`, which argparse keeps), then
d4_wind_rebuilt. Each gets its own `RUN`.

**Checkpoint and resume (stated honestly).**
- pipeline.command_final writes `checkpoint.pt` only at the END of a fit. There is no mid-fit checkpoint, and adding
  one would change the frozen pipeline.
- A lost run is therefore relaunched with the IDENTICAL command into a fresh `RUN`. Append (UTC, reason, attempt n) to
  `RESTARTS.log`.
- After two consecutive losses: stop and report.

## Timing result (declared deviation; estimate only), 2026-11-13
- **Run:** by Daniel @7b810e66 on the 5 part-a events, 1 epoch, 01:38:43–01:39:54Z, exit 0. REFIT_ENV_CHECK ok
  (56bf3784…); receipt b1569c23….
- **Numbers:** fit_seconds 2.738; train_samples 25, all 5 events used; wall_seconds 68.8; peak RSS ≥ 334 MB (only 2
  heartbeat samples). No loss was read.
- **Extrapolation to d4_wind_rebuilt, 3 epochs, part a (3,773 samples):**
  - uniform per sample: ≈ 21 min of fit;
  - size-weighted (intervals × final_mapped_cells; a hypothesis), where the subset is 333× smaller than part a: ≈ 46 min;
  - load and verification scaled linearly to 513 events: ≤ ~1.9 h.
  - Under the ~4 h flag, but unreliable: the subset has small fires only and fit-23 is missing.
- **Re-timing:** the declared subset (3 fit-23 + 5 part-a) is re-timed after day 2, with a 5 s heartbeat for peak RSS.
