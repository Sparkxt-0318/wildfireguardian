"""Iris's lag-1 persistence check on the displacement diagnostic.

Question: are a fire's interval ranks (or log observed/simulated median reach) persistent from one survey interval
to the next? That would point to a fire-level or slowly varying misfit rather than independent interval noise.

Pairs are consecutive intervals of the same fire that are adjacent in time (next.a == this.b) and neither stalled.
Statistic: Pearson correlation over all pairs, pooled across fires. Null: ranks permuted within each fire, holding
the set of pairs fixed (10 000 permutations, seeded). Reported with a one-sided p (positive persistence), a
two-sided p and the pair count. Ties in rank are broken at random, as in displacement_checks.py. A variant
leaves out detached-component intervals.

    python lag1_persistence.py --inputs results/displacement_mcem.json results/displacement_plugin.json \
        --out results/lag1_persistence.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from displacement_checks import ranks_random_ties


def series(d, rng, drop_detached):
    out = {}
    for f, rs in d["per_fire"].items():
        rs = sorted(rs, key=lambda r: r["a"])
        ok = [r for r in rs if not r["stalled"] and not (drop_detached and r.get("detached"))]
        if len(ok) < 2:
            continue
        rk = ranks_random_ties(ok, rng)
        lr = np.array([np.log(r["d_obs_m"] / np.median(r["d_sim_m"])) for r in ok])
        pairs = [(i, i + 1) for i in range(len(ok) - 1) if abs(ok[i + 1]["a"] - ok[i]["b"]) < 1e-6]
        if pairs:
            out[f] = (rk, lr, np.array(pairs))
    return out


def pooled_corr(per, which, perm=None):
    x, y = [], []
    for f, (rk, lr, pr) in per.items():
        v = rk if which == "rank" else lr
        if perm is not None:
            v = v[perm[f]]
        x.append(v[pr[:, 0]])
        y.append(v[pr[:, 1]])
    x, y = np.concatenate(x), np.concatenate(y)
    return float(np.corrcoef(x, y)[0, 1])


def test(per, which, rng, n=10_000):
    obs = pooled_corr(per, which)
    null = np.array([pooled_corr(per, which, {f: rng.permutation(len(v[0])) for f, v in per.items()})
                     for _ in range(n)])
    return dict(r=obs, null_mean=float(null.mean()), null_sd=float(null.std()),
                p_one_sided=float((1 + (null >= obs).sum()) / (n + 1)),
                p_two_sided=float((1 + (np.abs(null - null.mean()) >= abs(obs - null.mean())).sum()) / (n + 1)))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--inputs", type=Path, nargs="+", required=True)
    ap.add_argument("--perms", type=int, default=10_000)
    ap.add_argument("--seed", type=int, default=20261112)
    ap.add_argument("--out", type=Path, default=Path("results/lag1_persistence.json"))
    a = ap.parse_args(argv)
    res = {}
    for path in a.inputs:
        d = json.loads(path.read_text())
        est = d.get("estimator", path.stem)
        for drop in (False, True):
            rng = np.random.default_rng(a.seed)
            per = series(d, rng, drop)
            key = f"{est}{'_no_detached' if drop else ''}"
            res[key] = dict(pairs=int(sum(len(v[2]) for v in per.values())), fires=len(per),
                            rank=test(per, "rank", rng, a.perms), log_ratio=test(per, "log_ratio", rng, a.perms))
    a.out.write_text(json.dumps(dict(command="python lag1_persistence.py " + " ".join(argv or __import__("sys").argv[1:]),
                                     results=res), indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
