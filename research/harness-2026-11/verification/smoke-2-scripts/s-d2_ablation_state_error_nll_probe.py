"""Owen: does the state_error arm of feature_ablation.py actually reach the mean-field NLL fit?

R.fit_meanfield builds its survey states from problem.tau (the TRUE arrival times), not from obs. The state_error
feature perturbs obs only, so the committed NLL rows of state_error / state_error_contig are bit-identical to
baseline / baseline_contig. This probe is diagnostic, not part of the rule. For each seed it refits mean-field NLL
with problem.tau replaced by the OBSERVED (perturbed) bracket upper ends, so (tau_obs <= a) is the reported burned
state at survey a. It does the same on the unperturbed obs as a control, where the fit must reproduce the committed
baseline row, because the hi ends lie on the survey grid.

    cd research/harness-2026-11/S-D2 && python .../s-d2_ablation_state_error_nll_probe.py RESULTS_JSON
"""
import json
import sys

import numpy as np

import feature_ablation as FA
import run_shape_recovery as X
import synthetic as S
import synthetic_robust as R


def nll_on_obs(p, obs):
    tau_obs = np.where(obs["burned"], obs["hi"], S.INF)
    tau_obs[p.seeds] = 0.0
    q = p
    saved = q.tau
    q.tau = tau_obs
    try:
        th = R.fit_meanfield(q, obs, loss="nll")
    finally:
        q.tau = saved
    return X.far_share(th, p.offs)


def main(res_path):
    ref = json.load(open(res_path))
    k0c = ref["k0_contig"]
    rows = {(r["arm"], r["seed"], r["estimator"]): r for r in ref["rows"]}
    out = {}
    for arm, k0 in (("state_error", FA.K0_BASE), ("state_error_contig", k0c)):
        ctl, pert = [], []
        for s in range(5):
            p, obs, _ = FA.generate("state_error", s, None, k0)
            pert.append(nll_on_obs(p, obs))
            p0, obs0, _ = FA.generate("baseline", s, None, k0)
            ctl.append(nll_on_obs(p0, obs0))
            base = rows[(arm.replace("state_error", "baseline"), s, "meanfield_nll")]["far_share"]
            print(f"{arm} seed {s}: NLL far share on perturbed obs {pert[-1]:.3f}; control on clean obs {ctl[-1]:.3f} "
                  f"(committed baseline {base:.3f}; committed {arm} {rows[(arm, s, 'meanfield_nll')]['far_share']:.3f})",
                  flush=True)
        out[arm] = dict(perturbed=pert, control=ctl, mean=float(np.mean(pert)), sd=float(np.std(pert, ddof=1)))
        print(arm, "mean", round(out[arm]["mean"], 3), "sd", round(out[arm]["sd"], 3), flush=True)
    print(json.dumps(out))


if __name__ == "__main__":
    main(sys.argv[1])
