# E1 post hoc counterfactual (batch-1 review, 2026-11-01)

Post hoc, not pre-registered, not a leaderboard row: a batch-1 review verifier's check of finding E1-D2, run after E1's
results were known. It is E1 with no oracle use inside the 60 s budget (no calibration, no certification reserve); the
best relaxed plan is returned and the harness's untimed oracle check certifies it, as for every baseline.

* `nocert_run.py` subclasses `e1_alns` as `e1_nocert` and runs it through `evacplan.harness.run` on the 10 dev instances,
  seeds 0-4, with the evacplan worktree's venv at `18841678`, under `program/benchlock.py`, 12:16-13:14 UTC, vm boot `ff671362`.
* `e1_nocert.csv`: its 50 rows (delivered = the harness's oracle check). `nocert_run.log`: its log (scratchpad paths).
* Per-seed totals 1777/1775/1774/1799/1780; one run per seed, other review agents active: indicative only. See ../README.md.
