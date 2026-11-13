"""Reading for RULE_ablation_seed_extension.md (fixed before the run). Reporting only: no fitting, no randomness."""
import json
import sys
from pathlib import Path

import numpy as np

TRUE = 0.0718
PAIRS = (("time_varying", "baseline"), ("time_varying_contig", "baseline_contig"))


def arm_stats(rows, arm, seeds):
    out = {}
    nll = {r["seed"]: r for r in rows if r["arm"] == arm and r["estimator"] == "meanfield_nll" and r["seed"] in seeds}
    mc = {r["seed"]: r for r in rows if r["arm"] == arm and r["estimator"] == "mcem" and r["seed"] in seeds}
    void = sorted(s for s in seeds if not (nll[s]["guard"]["ok"] and mc[s]["guard"]["ok"]))
    ok = [s for s in seeds if s not in void]
    v = np.array([nll[s]["far_share"] for s in ok])
    m = np.array([mc[s]["far_share"] for s in ok])
    out = dict(n=len(ok), voided_seeds=void,
               nll=dict(median=float(np.median(v)), q25=float(np.percentile(v, 25)), q75=float(np.percentile(v, 75)),
                        mean=float(v.mean()), share_above_040=float((v > 0.40).mean()),
                        count_above_040=f"{int((v > 0.40).sum())} of {len(v)}"),
               mcem=dict(median=float(np.median(m)), mean=float(m.mean()), sd=float(m.std(ddof=1)),
                         share_within_tol=float((np.abs(m - TRUE) <= 0.05).mean()),
                         count_within_tol=f"{int((np.abs(m - TRUE) <= 0.05).sum())} of {len(m)}"),
               restart_triggers=int(sum(r["guard"]["n_flagged"] for r in rows if r["arm"] == arm and r["seed"] in ok)))
    return out


def reading(tv, base):
    if tv["nll"]["median"] > 0.40 and tv["nll"]["share_above_040"] >= 0.50 and tv["mcem"]["share_within_tol"] >= 0.80:
        return "STABLE"
    if tv["nll"]["share_above_040"] - base["nll"]["share_above_040"] >= 0.10:
        return "INTERMITTENT"
    return "NOT REPRODUCED"


def main(path="results/feature_ablation_seeds30.json", out="results/ablation_seed_reading.json"):
    d = json.loads(Path(path).read_text())
    rows = d["rows"]
    res = {}
    for name, seeds in (("seeds_0_29", list(range(30))), ("seeds_5_29", list(range(5, 30)))):
        st = {a: arm_stats(rows, a, seeds) for p in PAIRS for a in p}
        res[name] = dict(stats=st, reading={tv: reading(st[tv], st[b]) for tv, b in PAIRS})
    res["headline"] = res["seeds_0_29"]["reading"]
    res["agree_0_29_vs_5_29"] = res["seeds_0_29"]["reading"] == res["seeds_5_29"]["reading"]
    res["real_reference"] = dict(nll_share_above_040=0.72, nll_count_above_040="18 of 25", nll_median=0.679,
                                 mcem_share_within_005_of_synthetic_reference_0072=0.88, mcem_count="22 of 25",
                                 note=("Real fires have no known kernel. The MCEM figure compares real per-fire fits "
                                       "with the synthetic generator's setting 0.072; it is not evidence that 0.072 "
                                       "is right for real fires."),
                                 source="results/real_far_share.json (25 per-fire fits)")
    res["rule"] = "RULE_ablation_seed_extension.md"
    Path(out).write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:])
