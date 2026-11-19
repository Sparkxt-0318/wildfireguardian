"""Step 1(a): oracle ceiling and the FIXED / PERSIST / M_ref baselines on DEV (PROTOCOL 4.1). Writes derived/step1_oracle.json."""
import os
import argparse, json, sys
import numpy as np
import lib
from lib import *
import methods_base as mb


def oracle_blocks(D, idx, s, block, rng=None, budget=TARGET):
    """Per fire: scale kappa_b per block (carry-over miss budget, Amendment 1). Returns q for rows idx."""
    q = np.zeros(len(idx))
    fid = D.fid[idx]
    S = D.S[idx]
    for f in np.unique(fid):
        rows = np.flatnonzero(fid == f)           # already time ordered
        order = rows if rng is None else rows[rng.permutation(len(rows))]
        N = 0; M = 0
        for b0 in range(0, len(order), block):
            r = order[b0:b0 + block]
            N += len(r)
            allowed = max(int(np.floor(budget * N + 1e-9)) - M, 0)
            ratio = S[r] / np.maximum(s[r], S_FLOOR)
            srt = np.sort(ratio)
            kap = 0.0 if allowed >= len(r) else srt[len(r) - allowed - 1]
            q[r] = kap * np.maximum(s[r], S_FLOOR)
            M += int((S[r] > q[r]).sum())
    return q


def fire_stats(D, idx, q):
    fid = D.fid[idx]
    fl = np.unique(fid)
    mi = (D.S[idx] > q).astype(float)
    ar = D.area(idx, np.minimum(q, NB * CELL_KM))
    return np.array([mi[fid == f].mean() for f in fl]), np.array([ar[fid == f].mean() for f in fl])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", default=os.environ.get("KCF2_WORK", "/tmp/w/work"))
    ap.add_argument("--h", type=int, default=5)
    ap.add_argument("--out", default="derived/step1_oracle.json")
    a = ap.parse_args()
    D = Data(a.h, a.work)
    dev_f = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    folds = outer_folds(dev_f)
    idx = D.rows_of(dev_f)
    print("DEV fires", len(dev_f), "rows", len(idx), "folds", np.bincount(list(folds.values())))
    res = {"h": a.h, "n_fires": len(dev_f), "n_hours": int(len(idx)), "methods": {}, "oracle": {}}
    sc = {}
    for m in (mb.Fixed(), mb.Persist(), mb.mref()):
        s_all, k_all, cfgs = run_outer(m, D, folds)
        sc[m.name] = (s_all, k_all)
        fl, miss, area = evaluate(D, idx, s_all, k_all)
        sm = boot_summary(miss, area)
        res["methods"][m.name] = dict(summary=sm, cfgs=cfgs, per_fire=dict(fires=fl, miss=miss[:, L1].tolist(), area=area[:, L1].tolist()),
                                      frontier_miss=miss.mean(0).tolist(), frontier_area=area.mean(0).tolist())
        print(m.name, {k: round(v, 4) if isinstance(v, float) else v for k, v in sm.items()}, flush=True)
    # reference: committed 3.75 km margin
    fl, mi, ar = None, None, None
    q375 = np.full(len(idx), 3.75)
    mi, ar = fire_stats(D, idx, q375)
    res["methods"]["FIXED_3.75km_committed"] = dict(miss=float(mi.mean()), area=float(ar.mean()), n_fires=len(mi))
    print("committed 3.75 km:", mi.mean(), ar.mean())
    zm, _ = fire_stats(D, idx, np.zeros(len(idx)))
    res["methods"]["ZERO"] = dict(miss=float(zm.mean()), area=0.0)
    # ---- oracles
    fixed_area_cal = np.array(res["methods"]["FIXED"]["per_fire"]["area"])
    fixed_front = res["methods"]["FIXED"]["summary"]["frontier_area"]
    fixed_miss = res["methods"]["FIXED"]["summary"]["miss"]
    rng = np.random.default_rng(20261121)
    shapes = {"s=1": np.ones(len(D.S)), "s=M_ref": sc["M_ref"][0]}
    for sname, sarr in shapes.items():
        s = np.maximum(sarr[idx], S_FLOOR)
        for bname, block in (("O-fire", 10**9), ("O-day", 24), ("O-6h", 6)):
            for ctrl in (False, True):
                label = f"{bname}{'-random' if ctrl else ''} [{sname}]"
                q = oracle_blocks(D, idx, s, block, rng=np.random.default_rng(20261121) if ctrl else None)
                mi, ar = fire_stats(D, idx, q)
                bi = boot_idx(len(ar), 2000, 20261120)
                gain = 1 - ar.mean() / fixed_area_cal.mean()
                g_b = 1 - ar[bi].mean(1) / fixed_area_cal[bi].mean(1)
                res["oracle"][label] = dict(miss=float(mi.mean()), area=float(ar.mean()), gain_vs_fixed_calibrated=float(gain),
                                            gain_lo=float(np.percentile(g_b, 2.5)), gain_hi=float(np.percentile(g_b, 97.5)),
                                            gain_vs_fixed_frontier10=float(1 - ar.mean() / fixed_front),
                                            area_per_fire=ar.tolist())
                print(f"{label:28s} miss {mi.mean():.4f} area {ar.mean():8.1f} gain vs FIXED(cal) {gain:+.3f} [{np.percentile(g_b,2.5):+.3f},{np.percentile(g_b,97.5):+.3f}] vs FIXED(front10) {1-ar.mean()/fixed_front:+.3f}", flush=True)
    g = res["oracle"]["O-day [s=1]"]["gain_vs_fixed_calibrated"]
    res["gate"] = dict(statistic="O-day [s=1] gain vs FIXED calibrated", gain=g, passes=bool(g >= 0.10),
                       fixed_miss=fixed_miss, fixed_area=float(fixed_area_cal.mean()), fixed_frontier_area=fixed_front)
    print("GATE", res["gate"])
    json.dump(res, open(a.out, "w"))


if __name__ == "__main__":
    main()
