"""Covariate-free real-data test of plug-in bias on NIROPS part-a brackets.

For each part-a fire from ``nirops_brackets.py``, fit the homogeneous spatial hazard model
``lambda_i(t) = k0 + sum_d k_d 1{tau_(i-d) <= t}`` (5x5 offsets) over its first ``--hours`` hours after
the first survey:

* the cells mapped at the first survey are the initial burned state (sources from t = 0);
* a cell first mapped at survey k with ``hours[k] <= H`` has arrival bracket ``(hours[k-1], hours[k]]``;
* other cells are censored at ``T`` = the last survey time ``<= H``.

The four estimators are those of the synthetic study: plug-in at the first observation time (Ganguly-style),
independent-bracket composite likelihood, mean-field endpoint NLL (the forecast-v2 perimeter regime with
an NLL loss), and MCEM. There are no environmental covariates. This tests how much the estimated spread rate
depends on the treatment of censoring on real survey data. It is not a forecast and has no skill claim.

The rectangular grid is padded to a square with never-burned cells. The 3-cell margin is wider than the
kernel radius, so padding changes only the background exposure.

    python real_bracket_fit.py --brackets DIR --hours 240 --workers 4 --out results/real_bracket_fit.json
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

import synthetic as S
import synthetic_robust as R


def load_fire(path: Path, hours: float, seed: int):
    z = np.load(path)
    first, sh = z["first_survey"], z["survey_hours"]
    keep = np.flatnonzero(sh <= hours)
    K = int(keep.max())
    surveys = sh[: K + 1]
    h, w = first.shape
    n = max(h, w)
    f = np.full((n, n), -1, np.int64)
    f[:h, :w] = first
    f = f.ravel()
    burned = (f >= 0) & (f <= K)
    seeds = np.flatnonzero(f == 0)
    lo = np.where(burned & (f > 0), surveys[np.clip(f - 1, 0, K)], np.nan)
    hi = np.where(burned & (f > 0), surveys[np.clip(f, 0, K)], np.nan)
    lo[seeds] = hi[seeds] = 0.0
    T = float(surveys[-1])
    offs = S.offsets(2)
    p = S.Problem(n=n, offs=offs, k=np.full(len(offs), np.nan), k0=np.nan, T=T, seeds=seeds)
    p.tau = np.where(burned, hi, S.INF)        # states at survey times are exact functions of the brackets
    obs = dict(kind="perimeter", lo=lo, hi=hi, burned=burned, surveys=surveys)
    return p, obs


def summarise_theta(theta, offs):
    dist = np.hypot(offs[:, 0], offs[:, 1])
    k = theta[1:]
    return dict(total=float(k.sum()), near=float(k[dist < 1.5].sum()), far=float(k[dist >= 1.5].sum()),
                k0=float(theta[0]), theta=[float(v) for v in theta])


def fit_fire(args):
    path, hours, seed = args
    p, obs = load_fire(Path(path), hours, seed)
    rng = np.random.default_rng(seed)
    src, _ = S._neighbour_table(p.n, p.offs)
    point = np.where(obs["burned"], obs["hi"], S.INF)
    out = dict(fire=Path(path).stem, grid=p.n, T=p.T, surveys=int(len(obs["surveys"])),
               seeds=int(len(p.seeds)), arrivals=int(obs["burned"].sum() - len(p.seeds)),
               median_gap_hours=float(np.median(np.diff(obs["surveys"]))), estimators={})
    fits = {
        "plugin": lambda: S.fit_complete([S.sufficient_stats(p, point, src)]),
        "bracket_composite": lambda: R.fit_bracket_composite(p, obs),
        "meanfield_nll": lambda: R.fit_meanfield(p, obs, loss="nll"),
        "mcem": lambda: S.mcem(p, obs, rng, **R.MCEM_SHORT)[0],
    }
    for name, fn in fits.items():
        t0 = time.perf_counter()
        theta = fn()
        out["estimators"][name] = summarise_theta(theta, p.offs) | dict(seconds=time.perf_counter() - t0)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--brackets", type=Path, required=True)
    ap.add_argument("--hours", type=float, default=240.0)
    ap.add_argument("--min-arrivals", type=int, default=100)
    ap.add_argument("--max-grid", type=int, default=140)
    ap.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    ap.add_argument("--out", type=Path, default=Path("results/real_bracket_fit.json"))
    a = ap.parse_args(argv)
    index = json.loads((a.brackets / "index.json").read_text())
    eligible, excluded = [], {}
    for fire in sorted(index["fires"]):
        p, obs = load_fire(a.brackets / f"{fire}.npz", a.hours, 0)
        arrivals = int(obs["burned"].sum() - len(p.seeds))
        if arrivals < a.min_arrivals:
            excluded[fire] = f"{arrivals} arrivals < {a.min_arrivals}"
        elif p.n > a.max_grid:
            excluded[fire] = f"grid {p.n} > {a.max_grid}"
        elif len(p.seeds) == 0:
            excluded[fire] = "no initial burned cells"
        else:
            eligible.append(fire)
    print(f"{len(eligible)} eligible fires; excluded: {excluded}")
    t0 = time.time()
    jobs = [(str(a.brackets / f"{f}.npz"), a.hours, 20261112 + i) for i, f in enumerate(eligible)]
    with ProcessPoolExecutor(a.workers) as pool:
        fires = list(pool.map(fit_fire, jobs))
    ratios = {}
    for name in ("plugin", "bracket_composite", "meanfield_nll"):
        r = np.array([f["estimators"][name]["total"] / f["estimators"]["mcem"]["total"] for f in fires])
        ratios[name] = dict(per_fire=[float(x) for x in r], geometric_mean=float(np.exp(np.log(r).mean())),
                            min=float(r.min()), max=float(r.max()), below_one=f"{int((r < 1).sum())}/{len(r)}")
    for f in fires:
        e = f["estimators"]
        print(f["fire"], f["arrivals"], " ".join(f"{k}={v['total']:.4f}" for k, v in e.items()))
    print(json.dumps(ratios, indent=1))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(
        data="NIROPS part a (S-D9 PART_A_ALLOWLIST_FINAL.csv, sha256 " + index["allowlist_sha256"] + "), rule " + index["rule"],
        hours=a.hours, min_arrivals=a.min_arrivals, max_grid=a.max_grid, mcem=R.MCEM_SHORT,
        eligible=eligible, excluded=excluded, wall_seconds=time.time() - t0,
        total_rate_ratio_to_mcem=ratios, fires=fires), indent=1))


if __name__ == "__main__":
    main()
