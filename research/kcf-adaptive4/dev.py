#!/usr/bin/env python3
"""CA-DEV stage (PROTOCOL section 8, step 4): base models, wind-term choice, attribution, correction settings.

    python dev.py base          # models cross-validated by fire on the 16 development fires; chooses the wind term
    python dev.py attribution   # the four-term attribution of every missed (t, h) of the primary BASE
    python dev.py grid ARM i/n  # correction settings grid (ARM = TARGETED | ALL), slice i of n
    python dev.py choose        # pick (L, H) per arm from the grid outputs and write derived/kept.json
"""
import json
import sys
from pathlib import Path

import numpy as np

import lib4 as L
import run4 as R

D = L.HERE / "derived"
GRID = [(Lw, H) for Lw in (6, 12, 24) for H in (3, 6, 12)]


def folds():
    fires, curve = L.load()
    dev, held, fold = L.ca_split(fires["CA"])
    return fires, curve, dev, fold


def cv(fires, dev, fold, fn):
    """fn(train, test) -> dict model -> list of q; returns the test fires in order and the merged dict."""
    order, Q = [], {}
    for k in L.CA_DEV_FOLDS:
        te = [fires["CA"][n] for n in dev if fold[n] == k]
        tr = [fires["CA"][n] for n in dev if fold[n] != k]
        out = fn(tr, te, k)
        order += te
        for m, qs in out.items():
            Q.setdefault(m, []).extend(qs)
    return order, Q


def base():
    fires, curve, dev, fold = folds()
    params = {}

    def fn(tr, te, k):
        which = ("FIXED", "QUANTILE", "RULE", "BASE-gust", "BASE-850")
        P = R.fit_models(tr, "gust_ms", {}, which)
        params[k] = {m: np.asarray(P[m]).tolist() for m in ("FIXED", "BASE-gust", "BASE-850", "RULE10")}
        Q = R.issue(P, te, {}, which)
        P2 = dict(P, var="w850_ms", NONE=P["BASE-850"], ONEK=L.fit_base_onek(tr, "w850_ms"))
        Q["ONEK-gust"] = [L.q_base(f, np.full(L.NL, L.fit_base_onek(tr, "gust_ms")), "gust_ms") for f in te]
        Q["ONEK-850"] = [L.q_base(f, np.full(L.NL, P2["ONEK"]), "w850_ms") for f in te]
        return Q
    order, Q = cv(fires, dev, fold, fn)
    res, pf = R.summarise(order, Q, curve)
    a_g, a_8 = res["BASE-gust"][4]["area"], res["BASE-850"][4]["area"]
    var = "gust_ms" if a_g <= a_8 else "w850_ms"
    out = dict(set="CA-DEV, 4-fold by fire", fires=[f.name for f in order], summary=res, params=params,
               wind_choice=dict(area5_gust=a_g, area5_w850=a_8, chosen=var))
    (D / "dev_base.json").write_text(json.dumps(out, indent=1))
    print("wind choice:", out["wind_choice"])
    for m in res:
        r = res[m][4]
        print(f"{m:10s} 5h miss {r['miss']:.3f} ({r['miss_lo']:.3f}-{r['miss_hi']:.3f}) area {r['area']:.1f} "
              f"ratio {r.get('area_ratio', 1):.3f} pinball {r['pinball']:.3f} area@10 {r['area_at_10']:.1f}")
    for m in ("BASE-gust", "BASE-850"):
        print(m, "k_h by fold:", {k: np.round(v[m], 4).tolist() for k, v in params.items()})


def chosen_var():
    return json.loads((D / "dev_base.json").read_text())["wind_choice"]["chosen"]


def attribution():
    fires, curve, dev, fold = folds()
    var = chosen_var()
    ks_of = {}
    for k in L.CA_DEV_FOLDS:
        tr = [fires["CA"][n] for n in dev if fold[n] != k]
        ks = L.fit_base(tr, var)
        for n in dev:
            if fold[n] == k:
                ks_of[n] = ks
    d = R.attribute([fires["CA"][n] for n in dev], ks_of, var, curve)
    d.to_csv(D / "attribution_ca_dev.csv.gz", index=False)
    tab = R.attribution_table(d)
    (D / "attribution_ca_dev.json").write_text(json.dumps(tab, indent=1))
    for key in (5, "all"):
        t = tab[key]
        print(key, "misses", t["n_misses"], "wind truth available", round(t["wind_truth_share"], 3))
        for name in ("share_of_misses", "share_of_missed_area", "single_swap_fix_rate"):
            print("  ", name, {k: f"{v['value']:.3f} ({v['lo']:.3f}-{v['hi']:.3f})" for k, v in t[name].items()})


def grid(arm, part):
    fires, curve, dev, fold = folds()
    var = chosen_var()
    i, n = (int(x) for x in part.split("/"))
    out = {}
    for (Lw, H) in GRID[i::n]:
        def fn(tr, te, k):
            P = R.fit_models(tr, var, {arm: (Lw, H)}, (arm,))
            return R.issue(P, te, {arm: (Lw, H)}, (arm,))
        order, Q = cv(fires, dev, fold, fn)
        pf = L.per_fire(order, Q[arm], curve, 4)
        out[f"{Lw},{H}"] = dict(pinball5=float(np.nanmean(pf[:, 2])), miss5=float(np.nanmean(pf[:, 0])),
                                area5=float(np.nanmean(pf[:, 1])))
        print(arm, Lw, H, out[f"{Lw},{H}"], flush=True)
        (D / f"dev_grid_{arm}_{i}of{n}.json").write_text(json.dumps(out, indent=1))


def choose():
    kept = {"var": chosen_var()}
    allg = {}
    for arm in ("TARGETED", "ALL"):
        g = {}
        for p in sorted(D.glob(f"dev_grid_{arm}_*.json")):
            g.update(json.loads(p.read_text()))
        assert len(g) == len(GRID), (arm, len(g))
        best = min(g, key=lambda s: g[s]["pinball5"])
        kept[arm] = [int(x) for x in best.split(",")]
        allg[arm] = g
        print(arm, "chosen", best, g[best])
    (D / "dev_grid.json").write_text(json.dumps(allg, indent=1))
    (D / "kept.json").write_text(json.dumps(kept, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "base":
        base()
    elif cmd == "attribution":
        attribution()
    elif cmd == "grid":
        grid(sys.argv[2], sys.argv[3])
    elif cmd == "choose":
        choose()
