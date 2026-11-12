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
