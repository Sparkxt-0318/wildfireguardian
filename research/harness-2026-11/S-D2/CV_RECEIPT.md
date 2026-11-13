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

**Environment and invalidity note.** The CV ran in Python 3.13.18 with numpy 2.1.3 and scipy 1.14.1. The pooled
composite collapsed to the floor in folds 0, 2, 3 and 4 (Owen), so all composite numbers here are INVALID. See
results/cv_composite_rerun.json (pinned environment: Python 3.12.3, numpy 1.26.4, scipy 1.13.1). cv_baselines.py ran in
the pinned environment but read the composite p from these checkpoints.

## Pinned rerun (E3), 2026-11-12/13

Environment: `{'python': '3.12.3', 'numpy': '1.26.4', 'scipy': '1.13.1', 'pandas': '2.2.3', 'scikit-learn': '1.5.2', 'torch': '2.5.1+cpu', 'pinned': True}`
(`runenv.require_pinned()` enforced; same seeds and fold split as E1).
Command per fold: `venv312/bin/python cv_part_a.py --brackets $SP/brackets_v2 --fit results/real_bracket_fit.json --checkpoint-dir $SP/cv_ckpt_pinned --only-fold k`;
aggregate adds `--out results/cv_part_a_pinned.json`. Baselines: `cv_baselines.py --cv results/cv_part_a_pinned.json --ckpt $SP/cv_ckpt_pinned --out results/cv_baselines_pinned.json`.

```
2dc2c746ad9e42b40f42dfd2fdf8f159351a80cfbc5d61ab6a79331c46b61361  cv_ckpt_pinned/fold0.json
b72b931252de4be6364aca9b582285d2a6625936da7fe603bb59269ef5223a97  cv_ckpt_pinned/fold1.json
e4d234bf3fd65a0a91f94e428379278ee08d1b4138ccbeeea12d7da78c5cef29  cv_ckpt_pinned/fold2.json
a4f2e865e10a8949a645e0b3146452401274e04107ae098bf999185e5c64d72a  cv_ckpt_pinned/fold3.json
902156de1ab8345835f5aa6cbbb9521cf15546c0afcf32df4d8ba2554faf0543  cv_ckpt_pinned/fold4.json
cfc8cfae14fb366b031439495ac818ad66853b76a1836dd1f8eaaefd70b65b8e  results/cv_part_a_pinned.json
baa4c207bcf68785f37e85dcb327943ceca328bfbb9bc766eb2e0c27297fe708  results/cv_baselines_pinned.json
624936da0e73762023e15d14f6581a939c6947ec44b063ac9158981d5509c4af  results/check_bounds_pinned.json
54f22b475e13e89ef392508ed6bff8dcbc53bb031a85d89f78249b66c427caac  cv_part_a.py
40ba3454b499f29ada04ca32e363d080747b9a827819dfe28b4f6eec33b60e0d  check_bounds.py
d3578a8a0976997a89c7bb3cd9d2f43af587f438613df6cfe1532fb61750a187  cv_baselines.py
fede2cb775f494982a10ad129b64bbff964af9579966ba5fd655e29ec224f1bb  compare_pinned.py
```

Pinned-run losses (restart log):
```
2026-11-12T23:13 tracked task bii5kqkio (pinned E3) hit 2 h limit; in-progress fires lost (fold0 fire2, fold1 fire3, fold2 fire1, fold3 fire3, fold4 fire0); all 5 pinned fits checkpointed; relaunched as new tracked task
2026-11-13T00:22 container restart killed tracked task bg29s3qvx (pinned E3); folds 2,3 done; in-progress fires lost (fold0 after fire3, fold1 after fire3, fold4 after fire1); relaunched as new tracked task
```
Fits all checkpointed before the first loss; each loss cost only the test fires being scored (resume from per-fire checkpoints; bit-identity of resume is tested in test_cv_resume.py).
No pinned fit tripped the FitFailed guard; check_bounds_pinned.json: PASS for all 4 estimators in all 5 folds (composite share at floor 0.20–0.32).

**Cross-host reproducibility (Owen, ledger row 49).** "Pinned" fixes package versions, not bit-identity across hosts.
Owen's independent pinned rerun of folds 0 and 2 matched the composite and mean-field NLL thetas exactly (max |Δ| 0).
Plug-in and MCEM thetas differ by ≤ 5e-8 and ≤ 3e-4, and per-fire Brier by ≤ 0.24% and ≤ 0.64% relative. This is
attributed to host-level floating point (BLAS/CPU), not code. Conclusions are unchanged (10-fire MCEM − plug-in +0.01068 on both hosts).
