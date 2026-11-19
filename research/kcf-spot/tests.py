"""Step 5, tests 1, 2 and 4 (PROTOCOL section 6), from the geometry of tests_geom.py.

Every margin is a fixed buffer c (km, 5 h lead) united with the spot zone P >= p (p = none for FIXED). c is calibrated so
that the fire-weighted miss rate on the training fires is 10% (kcf-adaptive2 rule), then scored on held-out fires.
Training: CA-HELD <- CA-DEV; each Korean fire <- 28 California + the 11 other Korean fires (kcf-adaptive4); 25 March
<- 28 California + 12 Korean fires (KFS_01 Choi hours excluded).

    python tests.py --geom WORK/geom --fit derived/fit.json --adaptive4 ../kcf-adaptive4/derived --out derived
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from tests_geom import CK, NB, P_GRID

CELL2 = CK * CK
RNG = np.random.default_rng(20261119)
NBOOT = 1000
ARMS = ["FIXED"] + [f"SPOT_p{p:g}" for p in P_GRID]


def load(geom):
    rows, curves, zones = [], [], []
    for p in sorted(Path(geom).glob("*.csv")):
        d = pd.read_csv(p)
        if not len(d):
            continue
        z = np.load(p.with_suffix(".npz"))
        rows.append(d); curves.append(z["curves"]); zones.append(z["zones"])
    d = pd.concat(rows, ignore_index=True)
    return d, np.concatenate(curves), np.concatenate(zones)


def resid(d, arm):
    return d.S.values if arm == "FIXED" else d[f"Sp_{ARMS.index(arm) - 1}"].values


def area(idx, curves, zones, arm, c):
    """Flagged area (km2) per row: buffer c (capped 60 km) union zone."""
    k = int(np.clip(np.floor(c / CK + 1e-9), 0, NB))
    base = curves[idx, k - 1] if k > 0 else np.zeros(len(idx))
    if arm == "FIXED":
        return base * CELL2
    z = zones[idx, ARMS.index(arm) - 1, k:].sum(axis=1)
    return (base + z) * CELL2


def wmiss(fires, s, c):
    df = pd.DataFrame(dict(f=fires, m=s > c + 1e-9))
    return df.groupby("f").m.mean().mean()


def calibrate(fires, s, target=0.10):
    """Smallest c with fire-weighted miss <= target."""
    cand = np.unique(np.r_[0.0, s])
    lo, hi = 0, len(cand) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if wmiss(fires, s, cand[mid]) <= target:
            hi = mid
        else:
            lo = mid + 1
    return float(cand[lo])


def fw_mean(fires, v):
    return pd.DataFrame(dict(f=fires, v=v)).groupby("f").v.mean().mean()


def score(d, curves, zones, tr_idx, te_idx, arm):
    s = resid(d, arm)
    c = calibrate(d.fire.values[tr_idx], s[tr_idx])
    ft = d.fire.values[te_idx]
    miss = wmiss(ft, s[te_idx], c)
    ar = area(te_idx, curves, zones, arm, c)
    c10 = calibrate(ft, s[te_idx])                     # read at exactly 10% held-out miss
    ar10 = area(te_idx, curves, zones, arm, c10)
    return dict(arm=arm, c_km=c, miss=miss, area=fw_mean(ft, ar), c10_km=c10, area10=fw_mean(ft, ar10),
                _rows=pd.DataFrame(dict(fire=ft, miss=s[te_idx] > c + 1e-9, area=ar, area10=ar10)))


def boot_ratio(ra, rb, col):
    """Fire bootstrap of the ratio of fire-weighted means (rb / ra) on the same held-out rows."""
    fa = ra.groupby("fire")[col].mean(); fb = rb.groupby("fire")[col].mean()
    fires = fa.index.values
    out = []
    for _ in range(NBOOT):
        pick = RNG.choice(fires, len(fires), replace=True)
        out.append(fb.loc[pick].mean() / fa.loc[pick].mean())
    return [float(np.quantile(out, 0.025)), float(np.quantile(out, 0.975))]


def boot_rate(r, col="miss"):
    f = r.groupby("fire")[col].mean()
    v = [f.loc[RNG.choice(f.index.values, len(f), replace=True)].mean() for _ in range(NBOOT)]
    return [float(np.quantile(v, 0.025)), float(np.quantile(v, 0.975))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--geom", required=True); ap.add_argument("--fit", required=True)
    ap.add_argument("--adaptive4", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fit = json.load(open(a.fit))
    d, curves, zones = load(a.geom)
    d["kst"] = d.kst_hour
    dev, held = fit["dev"], fit["held"]
    isCA = d.region.values == "CA"
    tr_ca = np.flatnonzero(isCA & d.fire.isin(dev).values)
    te_ca = np.flatnonzero(isCA & d.fire.isin(held).values)
    res = {"n_rows": {r: int((d.region == r).sum()) for r in ("CA", "KR", "DET")}}
    # ---------------- p*: smallest CA-DEV training area at 10% miss (in-sample)
    tr_area = {}
    for arm in ARMS:
        s = resid(d, arm)
        c = calibrate(d.fire.values[tr_ca], s[tr_ca])
        tr_area[arm] = float(fw_mean(d.fire.values[tr_ca], area(tr_ca, curves, zones, arm, c)))
    pstar = min((a_ for a_ in ARMS if a_ != "FIXED"), key=lambda k: tr_area[k])
    res["train_area_ca_dev"] = tr_area
    res["pstar_arm"] = pstar
    primary = "SPOT_p0.1"
    arms_rep = list(ARMS)
    # ---------------- test 2: California held-out
    out_ca = {arm: score(d, curves, zones, tr_ca, te_ca, arm) for arm in dict.fromkeys(arms_rep)}
    # ---------------- Korea leave-one-fire-out
    kr_f = sorted(d[d.region == "KR"].fire.unique())
    kr_rows = {arm: [] for arm in dict.fromkeys(arms_rep)}
    kr_c = {arm: [] for arm in dict.fromkeys(arms_rep)}
    for f in kr_f:
        tr = np.flatnonzero(isCA | ((d.region.values == "KR") & (d.fire.values != f)))
        te = np.flatnonzero((d.region.values == "KR") & (d.fire.values == f))
        for arm in kr_rows:
            s = resid(d, arm)
            c = calibrate(d.fire.values[tr], s[tr])
            kr_c[arm].append(c)
            kr_rows[arm].append(pd.DataFrame(dict(fire=f, miss=s[te] > c + 1e-9, area=area(te, curves, zones, arm, c),
                                                  s=s[te], idx=te)))
    out_kr = {}
    for arm, parts in kr_rows.items():
        r = pd.concat(parts, ignore_index=True)
        c10 = calibrate(r.fire.values, r.s.values)
        r["area10"] = area(r.idx.values, curves, zones, arm, c10)
        out_kr[arm] = dict(arm=arm, c_km_median=float(np.median(kr_c[arm])), miss=float(r.groupby("fire").miss.mean().mean()),
                           area=float(r.groupby("fire").area.mean().mean()), c10_km=c10,
                           area10=float(r.groupby("fire").area10.mean().mean()), _rows=r)
    t2 = {}
    for name, o in (("CA-HELD", out_ca), ("KR", out_kr)):
        tab = []
        for arm, v in o.items():
            row = {k: v[k] for k in v if not k.startswith("_")}
            row["miss_95"] = boot_rate(v["_rows"])
            row["ratio_area10_vs_FIXED"] = v["area10"] / o["FIXED"]["area10"]
            row["ratio_area10_95"] = boot_ratio(o["FIXED"]["_rows"], v["_rows"], "area10") if arm != "FIXED" else [1, 1]
            row["ratio_area_vs_FIXED"] = v["area"] / o["FIXED"]["area"]
            tab.append(row)
        t2[name] = tab
    res["test2"] = t2
    # ---------------- test 1: 25 March 09-20 KST
    tr = np.flatnonzero((d.region.values != "DET"))
    det = d[d.region == "DET"]
    t1 = []
    for arm in dict.fromkeys(arms_rep):
        s = resid(d, arm)
        c = calibrate(d.fire.values[tr], s[tr])
        idx = det.index.values
        held_ = s[idx] <= c + 1e-9
        ar = area(idx, curves, zones, arm, c)
        win = (det.kst.values >= 9) & (det.kst.values <= 20)
        t1.append(dict(arm=arm, c_km=c, held_9_20=int(held_[win].sum()), of=int(win.sum()),
                       mean_area_9_20=float(ar[win].mean()), held_all=int(held_.sum()), of_all=len(idx),
                       per_hour={int(k): bool(h) for k, h in zip(det.kst.values, held_)}))
    res["test1"] = t1
    # ---------------- test 4: unexplained misses of kcf-adaptive4 at 5 h
    att = []
    for f, setname in (("attribution_ca_dev.csv.gz", "CA-DEV"), ("attribution_ca_held.csv.gz", "CA-HELD"),
                       ("attribution_kr.csv.gz", "KR")):
        x = pd.read_csv(Path(a.adaptive4) / f)
        x = x[(x.lead == 5)]
        x["set"] = setname
        att.append(x)
    att = pd.concat(att, ignore_index=True)
    att["set"] = np.where(att["product"] == "DET", "DET", att["set"])
    key = d.assign(t_utc=pd.to_datetime(d.t_utc).astype(str))
    att["t_utc"] = pd.to_datetime(att.t_utc).astype(str)
    att["fire_key"] = att.fire
    m = att.merge(key, left_on=["fire_key", "t_utc"], right_on=["fire", "t_utc"], how="left", suffixes=("", "_g"))
    m = m[m.region.notna() & ((m.region == "DET") == (m["product"] == "DET"))]
    un = m[m.v_all == 0].copy()
    t4 = {}
    for setname, g in un.groupby("set"):
        row = dict(unexplained=int(len(g)), fires=int(g.fire.nunique()),
                   S_match=float(np.mean(np.isclose(g.S, g.S_g, atol=1e-3))))
        row["oracle_held_without_spot_cells"] = int((g.S_nospot <= g.q + 1e-9).sum())
        row["hours_with_spot_cells_in_reach"] = int((g.spot_cells_in_reach > 0).sum())
        for arm in (primary, pstar):
            col = f"Sp_{ARMS.index(arm) - 1}"
            row[f"held_with_{arm}"] = int((g[col] <= g.q + 1e-9).sum())
        t4[setname] = row
    pooled = un[un.set.isin(["CA-HELD", "KR", "DET"])]
    for arm in (primary, pstar):
        col = f"Sp_{ARMS.index(arm) - 1}"
        fixed = pooled.assign(h=(pooled[col] <= pooled.q + 1e-9))
        fr = fixed.groupby("fire").h.mean()
        t4[f"pooled_heldout_share_fixed_{arm}"] = float(fixed.h.mean())
        t4[f"pooled_heldout_share_fixed_{arm}_95"] = boot_rate(fixed.rename(columns={"h": "miss"})[["fire", "miss"]])
    t4["note_choi"] = ("On the Korean Choi hours the burned set is the kriged later perimeter; observed spot cells are mapped "
                       "from VIIRS onto it, which the protocol calls not measurable. Reported, not used for the verdict.")
    res["test4"] = t4
    json.dump(res, open(Path(a.out) / "tests.json", "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in res.items() if k != "test1"}, indent=1, default=float)[:8000])
    for r in res["test1"]:
        print({k: v for k, v in r.items() if k != "per_hour"})


if __name__ == "__main__":
    main()
