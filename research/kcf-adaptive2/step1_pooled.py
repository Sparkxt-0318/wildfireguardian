"""Step 1(a) addendum (PROTOCOL Amendment 2): pooled-budget oracle. Writes derived/step1_pooled.json."""
import os
import json, sys
import numpy as np
from lib import *
import methods_base as mb
from step1_oracle import fire_stats


def pooled_oracle(D, idx, s, block, rng=None, ncand=61):
    fid = D.fid[idx]; S = D.S[idx]; s = np.maximum(s, S_FLOOR)
    nf = np.bincount(fid)[np.unique(fid)]
    F = len(nf)
    w_f = 1.0 / np.bincount(fid)
    blocks = []
    for f in np.unique(fid):
        rows = np.flatnonzero(fid == f)
        order = rows if rng is None else rows[rng.permutation(len(rows))]
        for b0 in range(0, len(order), block):
            blocks.append(order[b0:b0 + block])
    cand_q, cand_a, cand_m = [], [], []
    for r in blocks:
        ratio = S[r] / s[r]
        c = np.unique(np.concatenate([[0.0], np.quantile(ratio, np.linspace(0, 1, ncand))]))
        a = np.zeros(len(c)); m = np.zeros(len(c))
        for j, cj in enumerate(c):
            q = cj * s[r]
            a[j] = (D.area(idx[r], np.minimum(q, NB * CELL_KM)) * w_f[fid[r]]).sum()
            m[j] = ((S[r] > q) * w_f[fid[r]]).sum()
        cand_q.append(c); cand_a.append(a); cand_m.append(m)

    def pick(mu):
        ch = [int(np.argmin(a + mu * m)) for a, m in zip(cand_a, cand_m)]
        A = sum(a[j] for a, j in zip(cand_a, ch)) / F
        M = sum(m[j] for m, j in zip(cand_m, ch)) / F
        return ch, A, M
    lo, hi = 1e-3, 1e8
    for _ in range(60):
        mu = np.sqrt(lo * hi)
        _, A, M = pick(mu)
        if M > TARGET: lo = mu
        else: hi = mu
    ch, A, M = pick(hi)
    q = np.zeros(len(idx))
    for r, c, j in zip(blocks, cand_q, ch):
        q[r] = c[j] * s[r]
    return q


def main():
    D = Data(5, os.environ.get("KCF2_WORK", "/tmp/w/work"))
    dev_f = [f for f in D.fires if D.product[D.fire == f][0] == "GOFER"]
    folds = outer_folds(dev_f); idx = D.rows_of(dev_f)
    prev = json.load(open("derived/step1_oracle.json"))
    fixed_cal = np.array(prev["methods"]["FIXED"]["per_fire"]["area"]); fixed_front = prev["methods"]["FIXED"]["summary"]["frontier_area"]
    mref_area = np.array(prev["methods"]["M_ref"]["per_fire"]["area"])
    s_all, k_all, _ = run_outer(mb.mref(), D, folds, verbose=False)
    np.save(os.path.join(os.environ.get("KCF2_WORK", "/tmp/w/work"), "s_mref_h5.npy"), s_all); np.save(os.path.join(os.environ.get("KCF2_WORK", "/tmp/w/work"), "k_mref_h5.npy"), k_all)
    out = {}
    for sname, sarr in (("s=1", np.ones(len(D.S))), ("s=M_ref", s_all)):
        s = sarr[idx]
        for bname, block in (("O-fire", 10**9), ("O-day", 24), ("O-6h", 6)):
            for ctrl in (False, True):
                label = f"{bname}{'-random' if ctrl else ''} [{sname}] pooled"
                q = pooled_oracle(D, idx, s, block, rng=np.random.default_rng(20261121) if ctrl else None)
                mi, ar = fire_stats(D, idx, q)
                bi = boot_idx(len(ar), 2000, 20261120)
                g = 1 - ar.mean() / fixed_cal.mean(); gb = 1 - ar[bi].mean(1) / fixed_cal[bi].mean(1)
                out[label] = dict(miss=float(mi.mean()), area=float(ar.mean()), gain_vs_fixed_calibrated=float(g),
                                  gain_lo=float(np.percentile(gb, 2.5)), gain_hi=float(np.percentile(gb, 97.5)),
                                  gain_vs_fixed_frontier10=float(1 - ar.mean() / fixed_front),
                                  gain_vs_mref=float(1 - ar.mean() / mref_area.mean()))
                print(f"{label:34s} miss {mi.mean():.4f} area {ar.mean():8.1f} gain vs FIXED {g:+.3f} [{np.percentile(gb,2.5):+.3f},{np.percentile(gb,97.5):+.3f}]  vs M_ref {1-ar.mean()/mref_area.mean():+.3f}", flush=True)
    json.dump(out, open("derived/step1_pooled.json", "w"))


if __name__ == "__main__":
    main()
