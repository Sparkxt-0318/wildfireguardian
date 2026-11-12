"""Synthetic censoring propriety test of the §5.2 arrival RPS (A1 amendment 1, revision 30).

The rule was committed at 6954c37a before this script first ran. It uses sd9bench.arrival.rps
unchanged. No fire data is read except survey times (labels/intervals.csv of the three part-a
pilot fires, given with --intervals).

  python rps_propriety.py --intervals Line.csv ThreeNine.csv Blue2.csv --out RPS_PROPRIETY.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sd9bench.arrival import ArrivalEntries, rps  # noqa: E402

ONE_BIN = {"stress_one_early": 3.0, "stress_two_early": 2.0}   # smallest resolvable step (amendment 1)
SEED, N_CELLS, WINDOW_H, SHIFT_H, SE_MULT = 20261112, 200_000, 48.0, 12.0, 3.0
GH_X, GH_W = np.polynomial.hermite_e.hermegauss(16)
GH_W = GH_W / GH_W.sum()


def real_patterns(paths):
    pats = []
    for p in paths:
        gaps = [float(r["dt_h"]) for r in csv.DictReader(open(p))]
        for i in range(len(gaps)):
            t, leads = 0.0, []
            for g in gaps[i:]:
                t += g
                if t > WINDOW_H:
                    break
                leads.append(t)
            if leads:
                pats.append(leads)
    return pats


def draw_cells(rng, n):
    pi = rng.beta(6, 4, n)
    lam = np.exp(rng.normal(np.log(1 / 30), 0.8, n))
    burns = rng.random(n) >= pi
    t = np.where(burns, rng.exponential(1 / lam), np.inf)
    return pi, lam, t


def cdf_truth(pi, lam, t):
    return (1 - pi)[:, None] * (1 - np.exp(-lam[:, None] * t))


def cdf_overdispersed(pi, lam, t):
    out = np.zeros((len(pi), t.shape[1]))
    for x, w in zip(GH_X, GH_W):
        out += w * (1 - np.exp(-(lam * np.exp(x))[:, None] * t))
    return (1 - pi)[:, None] * out


def score_pattern(rng, leads_list, clim_t, clim_f, one_bin=None):
    # assign each cell one censoring pattern (round-robin over the pattern list)
    pi, lam, tt = draw_cells(rng, N_CELLS)
    idx = np.arange(N_CELLS) % len(leads_list)
    j = max(len(l) for l in leads_list)
    lead = np.full((N_CELLS, j), np.nan)
    nl = np.zeros(N_CELLS, int)
    for k, l in enumerate(leads_list):
        m = idx == k
        lead[m, :len(l)] = l
        nl[m] = len(l)
    valid = np.arange(j)[None, :] < nl[:, None]
    t = np.where(valid, lead, 0.0)
    hit = tt[:, None] <= t
    ab = np.where(valid & hit, np.arange(j)[None, :], j).min(1)
    ab = np.minimum(ab, nl)
    f = dict(
        truth=cdf_truth(pi, lam, t),
        always_early=np.ones((N_CELLS, j)),
        never=np.zeros((N_CELLS, j)),
        shifted_earlier=cdf_truth(pi, lam, t + SHIFT_H),
        shifted_later=cdf_truth(pi, lam, np.maximum(t - SHIFT_H, 0.0)),
        overdispersed=cdf_overdispersed(pi, lam, t),
        climatology=np.interp(t, clim_t, clim_f),
    )
    if one_bin is not None:   # amendment 1, added before these ran (eb03856b)
        f["one_bin_earlier"] = cdf_truth(pi, lam, t + one_bin)
        f["one_bin_later"] = cdf_truth(pi, lam, np.maximum(t - one_bin, 0.0))
    f = {k: np.where(valid, v, np.nan) for k, v in f.items()}
    e = ArrivalEntries(fire=np.zeros(N_CELLS, dtype="<U1"), n_leads=nl, arrival_bin=ab, lead_hours=lead, cdf=f)
    r = {k: rps(e, k) for k in f}
    res = {"cells": N_CELLS, "patterns": len(leads_list), "share_never_mapped": float((ab == nl).mean()),
           "mean_rps": {k: float(v.mean()) for k, v in r.items()}, "excess_over_truth": {}}
    ok = True
    for k, v in r.items():
        if k == "truth":
            continue
        d = v - r["truth"]
        mean, se = float(d.mean()), float(d.std(ddof=1) / np.sqrt(len(d)))
        z = mean / se if se else 0.0
        if k.startswith("one_bin"):
            status = "pass" if z > SE_MULT else ("FAIL" if z < -SE_MULT else "resolution_limit")
            passed = status != "FAIL"
        else:
            status = "pass" if mean > SE_MULT * se else "FAIL"
            passed = status == "pass"
        ok &= passed
        res["excess_over_truth"][k] = dict(mean=mean, se=se, z=z, status=status, passed=bool(passed))
    ee, el = res["excess_over_truth"]["shifted_earlier"]["mean"], res["excess_over_truth"]["shifted_later"]["mean"]
    res["shift_asymmetry_diagnostic"] = dict(earlier=ee, later=el, ratio_earlier_to_later=ee / el if el else None)
    res["passed"] = bool(ok)
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intervals", nargs="+", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    # climatology: pooled empirical P(T <= t) on an independent training sample
    _, _, ttrain = draw_cells(rng, N_CELLS)
    clim_t = np.linspace(0, WINDOW_H + SHIFT_H, 241)
    clim_f = (ttrain[:, None] <= clim_t[None, :]).mean(0)
    patterns = {"real_part_a_gaps": real_patterns(args.intervals), "stress_one_early": [[3.0]],
                "stress_two_early": [[2.0, 5.0]]}
    out = dict(rule="A1 amendment 1 (revision 30), committed at 6954c37a before this run", seed=SEED,
               se_multiplier=SE_MULT, interval_files=[str(p.name) for p in args.intervals], results={})
    for name, pats in patterns.items():
        out["results"][name] = score_pattern(rng, pats, clim_t, clim_f, one_bin=ONE_BIN.get(name))
    out["passed"] = all(r["passed"] for r in out["results"].values())
    args.out.write_text(json.dumps(out, indent=1) + "\n")
    for name, r in out["results"].items():
        print(name, "patterns", r["patterns"], "never-mapped share", round(r["share_never_mapped"], 3), "PASS" if r["passed"] else "FAIL")
        for k, v in r["excess_over_truth"].items():
            print(f"   {k:16s} excess {v['mean']:+.6f}  z {v['z']:.1f}  {v['status']}")
        print("   asymmetry", r["shift_asymmetry_diagnostic"])
    print("OVERALL", "PASS" if out["passed"] else "FAIL")


if __name__ == "__main__":
    main()
