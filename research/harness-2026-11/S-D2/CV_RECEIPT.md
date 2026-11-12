# Receipt: part-a fire-level CV (`results/cv_part_a.json`)

**Unverified.** Development evidence on the 25 part-a fires (4 of them GOFER-matched H-dev fires), first 240 h,
covariate-free pooled homogeneous kernels. 5 folds (sorted eligible fires, i % 5); 1024 exact forward simulations per
interval; Brier score over cells within a 4 km band of each interval's initial perimeter.

**One CV.** All five folds come from the same fitters, scoring code, fold definitions and seeds: MCEM fit
424242 + fold; test fire i 77_000 + 31·fold + i.
- Fold 2 was produced at 14:56 by cv_part_a.py at eba66fc7, which had per-fold checkpoints only.
- Folds 0, 1, 3 and 4 were produced by cv_part_a.py 00244503… (cc57de0e). That version adds checkpoint and resume
  plumbing only: per fold, per estimator, per MCEM iteration (with RNG state) and per test fire.
  `test_cv_resume.py` shows that a resumed MCEM chain is bit-identical to an uninterrupted one.
- The aggregate is `cv_part_a.py` with the same arguments and no `--only-fold`. It reads the five fold checkpoints.

**Fold checkpoint sha256 (prefix):**
- fold0.json: 229a1702021135a3
- fold1.json: e8ac0fd4f991aa20
- fold2.json: bef052967edd8107
- fold3.json: 1bdee061825bbdf8
- fold4.json: e913f6c48f69444e

**Aggregate:** results/cv_part_a.json sha256 e2252120c818ec7a…

**Run losses (environment), from the restart log:**
```
# part-a CV restart log (time UTC, what was lost, stage)
2026-11-12T12:58 container restart; first relaunched CV (no checkpoints) lost
2026-11-12T15:00 2 h background limit; folds 0,1,3,4 lost mid-run (fold 2 saved 14:56)
2026-11-12T16:03 container restart; detached combined run lost (fold 2 kept)
2026-11-12T16:12 container restart; separate folds lost in fit stage (no sub-fold state yet)
2026-11-12T16:25 fold0 found dead (uptime 9.87s); last stage: 2026-11-12T16:13:31Z composite fitted
2026-11-12T16:25 fold1 found dead (uptime 9.88s); last stage: 2026-11-12T16:13:30Z plugin fitted
2026-11-12T16:25 fold3 found dead (uptime 9.89s); last stage: 2026-11-12T16:13:32Z composite fitted
2026-11-12T16:25 fold4 found dead (uptime 9.90s); last stage: 2026-11-12T16:13:32Z composite fitted
2026-11-12T16:26 container restart (idle reclaim, uptime ~10s at 16:25 check-in); folds 0,1,3,4 dead after estimators 1-2; detached setsid processes do not keep the container alive -> switching to harness-tracked background task
2026-11-12T18:26 fold0 found dead (uptime 7228.58s); last stage: 2026-11-12T17:46:38Z fire 3 scored
2026-11-12T18:26 fold1 found dead (uptime 7228.59s); last stage: 2026-11-12T17:41:20Z fire 2 scored
2026-11-12T18:26 fold3 found dead (uptime 7228.60s); last stage: 2026-11-12T17:43:21Z fire 2 scored
2026-11-12T18:26 fold4 found dead (uptime 7228.61s); last stage: 2026-11-12T18:25:09Z fire 3 scored
2026-11-12T18:26 tracked task bsnohdi35 hit 2 h limit; in-progress fires lost (fold0 fire4, fold1 fire3, fold3 fire3, fold4 fire4); relaunched as new tracked task
```

Six losses in total: 4 container reclaims while the session was idle and detached processes were running, and 2 hits on the 2 h tracked-task limit. After 16:26 the folds ran inside harness-tracked tasks, and there were no further container restarts.
