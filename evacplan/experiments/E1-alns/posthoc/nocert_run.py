# Batch-1 review verifier's counterfactual (finding E1-D2), 2026-11-01: post hoc, not pre-registered, not a leaderboard row.
# It was run from the evacplan worktree (its .venv, commit 18841678, clean) under the bench lock; see README.md here.
# Kept as a record: a rerun writes cache/ and results/ next to this file, so run a copy from a scratch directory.
"""verify-e1 (skeptic of E1-D2). E1 with NO in-budget oracle use: no calibration check, no time reserved for
certification, and every "certification" accepts the relaxed plan, so the plan returned is E1's best relaxed plan.
It is run through evacplan.harness.run itself, so the timed window (solve only) and the final oracle check (outside
the budget, one Oracle per instance) are exactly the harness's, as for every baseline.
Writes only under this script's directory (instance cache copy, result rows, plans). Dev split entries only.
Launch under the bench lock (lock="no" here because the parent benchlock.py holds it)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent

from evacplan import harness  # noqa: E402
from evacplan.methods import register  # noqa: E402
from evacplan.methods import e1_alns as E  # noqa: E402


class _NoCertRun(E._Run):
    def _estimate(self, st):            # nothing reserved for certification
        return 0.0

    def _check(self, v, d, hard, prefix=False):   # the only oracle call site of E1: never reached
        return None

    def certify(self, st, hard):        # accept the relaxed plan as the incumbent
        self.certifications += 1
        return st.copy(), self.F(st), 0, self.planned(st)


class E1NoCert(E.E1ALNS):
    name = "e1_nocert"

    def solve(self, instance, scenario_set, *, budget_s, seed, deadline):
        run = _NoCertRun(self.cfg, self.name, instance, scenario_set, float(budget_s), int(seed), float(deadline))
        res = run.run()
        assert run.oracle_checks == 0 and run.t_oracle == 0.0, "an oracle call happened inside the budget"
        return res


register("e1_nocert", E1NoCert)

if __name__ == "__main__":
    argv = sys.argv[1:]
    k = argv.index("--seeds")
    ids, seeds = argv[:k], [int(s) for s in argv[k + 1:]]
    print("boot", Path("/proc/sys/kernel/random/boot_id").read_text()[:8], "start", time.strftime("%H:%M:%S", time.gmtime()),
          flush=True)
    harness.run("e1_nocert", "dev", 60.0, seeds=seeds, instances=ids, lock="no", cache_dir=HERE / "cache",
                results_dir=HERE / "results", leaderboard_path=None, save_plans=True,
                log=lambda s: print(time.strftime("%H:%M:%S", time.gmtime()), s, flush=True))
    print("end", time.strftime("%H:%M:%S", time.gmtime()), flush=True)
