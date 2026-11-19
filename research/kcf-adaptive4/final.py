#!/usr/bin/env python3
"""Held-out stage (PROTOCOL section 8, step 6). Run once, after derived/kept.json is committed.

    python final.py ca          # CA-HELD: fit on the 16 development fires, score the 12 held-out fires
    python final.py kr i/n      # Korea leave-one-fire-out, slice i of n of the 12 fires (KFS_01's fold also scores DET)
    python final.py merge       # tables, targets, attribution for Korea, error growth, expected-error file
"""
import json
import pickle
import sys

import numpy as np
import pandas as pd

import lib4 as L
import run4 as R

D = L.HERE / "derived"
WHICH = ("FIXED", "QUANTILE", "RULE", "BASE-gust", "BASE-850", "NONE", "TARGETED", "ALL")
QS = (0.5, 0.8, 0.9, 0.95, 0.99)
TERM_NAMES = {-1: "none", 0: "wind", 1: "k", 2: "start", 3: "timing"}


def kept():
    k = json.loads((D / "kept.json").read_text())
    return k["var"], {"TARGETED": tuple(k["TARGETED"]), "ALL": tuple(k["ALL"])}


def corrected_flag(st):
    return (np.abs(st[:, 0] - 1) > 1e-9) | (st[:, 1] > 1 + 1e-9) | (st[:, 2] > 1e-9) | (st[:, 3] > 0)


def fit_expected(train, P, var, settings):
    """Conformal scales of the shortfall S - q in units of the pooled margin, per lead and correction state."""
    Lw, H = settings["TARGETED"]
    sc = {(h, s): [] for h in range(L.NL) for s in (0, 1)}
    wt = {(h, s): [] for h in range(L.NL) for s in (0, 1)}
    for f in train:
        q, st = L.correct(f, P["NONE"], var, "targeted", Lw, H, return_state=True)
        q = q * P["TARGETED"][None, :]
        qp = L.q_base(f, P["NONE"], var)
        cf = corrected_flag(st).astype(int)
        for h in range(L.NL):
            e = f.elig[:, h]
            if not e.any():
                continue
            z = (f.S[e, h] - q[e, h]) / qp[e, h]
            for s in (0, 1):
                m = cf[e] == s
                if m.any():
                    sc[(h, s)].append(z[m])
                    wt[(h, s)].append(np.full(m.sum(), 1.0 / e.sum()))
    C = np.zeros((L.NL, 2, len(QS)))
    for h in range(L.NL):
        za = np.concatenate(sc[(h, 0)] + sc[(h, 1)])
        wa = np.concatenate(wt[(h, 0)] + wt[(h, 1)])
        for s in (0, 1):
            if sum(len(x) for x in sc[(h, s)]) >= 200:
                z, w = np.concatenate(sc[(h, s)]), np.concatenate(wt[(h, s)])
            else:
                z, w = za, wa
            C[h, s] = [L.wquantile(z, w, p) for p in QS]
    return C


def expected_rows(setname, f, P, var, settings, C):
    Lw, H = settings["TARGETED"]
    q, st = L.correct(f, P["NONE"], var, "targeted", Lw, H, return_state=True)
    q = q * P["TARGETED"][None, :]
    qp = L.q_base(f, P["NONE"], var)
    cf = corrected_flag(st).astype(int)
    rec = []
    for h in range(L.NL):
        rows = np.flatnonzero(np.isfinite(q[:, h]) & f.has)
        if not len(rows):
            continue
        d = dict(set=setname, fire=f.name, product=f.product, t_utc=f.t[rows].strftime("%Y-%m-%d %H:%M:%S"),
                 lead_h=int(L.LEADS[h]), wind_kmh=L.wind_kmh(f, var)[rows], k=P["NONE"][h] * P["TARGETED"][h],
                 pooled_margin_km=qp[rows, h], margin_km=q[rows, h], corrected=cf[rows],
                 blamed_term=[TERM_NAMES[int(x)] for x in st[rows, 4]], wind_mult=st[rows, 0], k_mult=st[rows, 1],
                 start_add_km=st[rows, 2], timing_hold_h=st[rows, 3].astype(int))
        for j, p in enumerate(QS):
            d[f"err_q{int(p * 100)}_km"] = C[h, cf[rows], j] * qp[rows, h]
        d["scored"] = f.elig[rows, h].astype(int)
        d["reach_km"] = f.S[rows, h]
        rec.append(pd.DataFrame(d))
    return pd.concat(rec, ignore_index=True)


def run_fold(setname, train, test, var, settings):
    P = R.fit_models(train, var, settings, WHICH)
    Q = R.issue(P, test, settings, WHICH)
    C = fit_expected(train, P, var, settings)
    exp = pd.concat([expected_rows(setname if f.product != "DET" else "DET", f, P, var, settings, C) for f in test],
                    ignore_index=True)
    states = {}
    for f in test:
        for arm in ("TARGETED", "ALL"):
            _, st = L.correct(f, P["NONE"], var, arm.lower(), *settings[arm], return_state=True)
            states[(f.name, f.product, arm)] = st
    params = {m: np.asarray(P[m]).tolist() for m in ("FIXED", "RULE10", "BASE-gust", "BASE-850", "NONE", "TARGETED", "ALL")}
    params["ONEK"] = float(P["ONEK"])
    return dict(fires=[(f.name, f.product) for f in test], Q=Q, exp=exp, states=states, params=params,
                ks={f.name: P["NONE"] for f in test})


def ca():
    fires, curve = L.load()
    dev, held, _ = L.ca_split(fires["CA"])
    var, settings = kept()
    out = run_fold("CA-HELD", [fires["CA"][n] for n in dev], [fires["CA"][n] for n in held], var, settings)
    pickle.dump(out, open(D / "final_ca.pkl", "wb"))
    print("CA-HELD done", len(out["fires"]))


def kr(part):
    fires, curve = L.load()
    var, settings = kept()
    i, n = (int(x) for x in part.split("/"))
    names = sorted(fires["KR"])
    for name in names[i::n]:
        train = list(fires["CA"].values()) + [fires["KR"][x] for x in names if x != name]
        test = [fires["KR"][name]] + ([fires["DET"][name]] if name in fires["DET"] else [])
        out = run_fold("KR", train, test, var, settings)
        pickle.dump(out, open(D / f"final_kr_{name}.pkl", "wb"))
        print("KR fold done", name, flush=True)


# ------------------------------------------------------------------ merge
def collect(fires, keys, files):
    order, Q, exp, states, params, ks = [], {}, [], {}, {}, {}
    for p in files:
        o = pickle.load(open(p, "rb"))
        for j, (name, prod) in enumerate(o["fires"]):
            key = {"GOFER": "CA", "CHOI": "KR", "DET": "DET"}[prod]
            if key not in keys:
                continue
            order.append(fires[key][name])
            for m, qs in o["Q"].items():
                Q.setdefault(m, []).append(qs[j])
            ks[name] = o["ks"][name]
        exp.append(o["exp"])
        states.update(o["states"])
        params[p.stem] = o["params"]
    return order, Q, pd.concat(exp, ignore_index=True), states, params, ks


def norun_table(order, Q, curve):
    """Fire-days (KST) of the Korean Choi timelines with no eligible 5 h issue hour above RUN_KM."""
    h = 4
    days = []
    for fi, f in enumerate(order):
        for d in np.unique(f.kst_day[f.elig[:, h]]):
            rows = np.flatnonzero(f.elig[:, h] & (f.kst_day == d))
            days.append((fi, d, rows, bool((f.S[rows, h] > L.RUN_KM).any())))
    out = dict(n_fire_days=len(days), n_run=sum(x[3] for x in days), n_norun=sum(not x[3] for x in days), models={})
    for m, qs in Q.items():
        a, mi, ar = [], [], []
        for fi, d, rows, run in days:
            f = order[fi]
            q = qs[fi][rows, h]
            area = L.area_of(curve, f.cidx[rows], np.minimum(q, L.NB * L.CELL_KM)).mean()
            (a if not run else ar).append(area)
            if not run:
                mi.append((f.S[rows, h] > q).mean())
        out["models"][m] = dict(area_norun=float(np.mean(a)), miss_norun=float(np.mean(mi)), area_run=float(np.mean(ar)))
    return out


def mar25(fires, Q_det, states, curve):
    f = fires["DET"]["KFS_01"]
    h = 4
    rows = np.flatnonzero(f.has)
    d = pd.DataFrame(dict(t_utc=f.t[rows].astype(str), kst=f.kst_hour[rows], reach5_km=f.S[rows, h],
                          sreach5_km=f.Ss[rows, h], fc_gust_ms=f.X["gust_ms"][rows], fc_w850_ms=f.X["w850_ms"][rows],
                          era5_gust_ms=[f.obs_window("gust_ms", int(i)) for i in rows]))
    for m, qs in Q_det.items():
        d[m] = qs[0][rows, h]
        d[m + "_area"] = L.area_of(curve, f.cidx[rows], np.minimum(np.nan_to_num(qs[0][rows, h]), L.NB * L.CELL_KM))
    st = states[("KFS_01", "DET", "TARGETED")]
    d["T_blamed"] = [TERM_NAMES[int(x)] for x in st[rows, 4]]
    d["T_wind_mult"], d["T_k_mult"], d["T_hold_h"], d["T_matured_misses"] = st[rows, 0], st[rows, 1], st[rows, 3], st[rows, 5]
    return d


def merge():
    fires, curve = L.load()
    var, settings = kept()
    N = {"var": var, "settings": {k: list(v) for k, v in settings.items()}}
    o_ca, Q_ca, e_ca, s_ca, p_ca, ks_ca = collect(fires, ("CA",), [D / "final_ca.pkl"])
    kfiles = sorted(D.glob("final_kr_KFS_*.pkl"))
    assert len(kfiles) == 12, len(kfiles)
    o_kr, Q_kr, e_kr, s_kr, p_kr, ks_kr = collect(fires, ("KR",), kfiles)
    o_det, Q_det, _, s_det, _, _ = collect(fires, ("DET",), kfiles)
    res_ca, pf_ca = R.summarise(o_ca, Q_ca, curve)
    res_kr, pf_kr = R.summarise(o_kr, Q_kr, curve)
    N["CA-HELD"], N["KR"] = res_ca, res_kr
    N["params"] = {"CA-HELD": p_ca, "KR": p_kr}

    # ---- target A
    d = mar25(fires, Q_det, s_det, curve)
    d.to_csv(D / "mar25.csv", index=False)
    win = d[(d.t_utc >= "2025-03-25 00:00:00") & (d.t_utc <= "2025-03-25 11:00:00")]
    A = {}
    for m in Q_det:
        held = int((win.reach5_km <= win[m]).sum())
        A[m] = dict(held=held, of=int(len(win)), missed=int(len(win) - held), max_margin_km=float(win[m].max()),
                    mean_area_km2=float(win[m + "_area"].mean()),
                    held_all_day=int((d.reach5_km <= d[m]).sum()), of_all_day=int(d.reach5_km.notna().sum()))
    N["A"] = dict(models=A, passed=bool(A["TARGETED"]["held"] > 1))

    # ---- target B
    b = res_kr["TARGETED"][4]
    N["B"] = dict(miss=b["miss"], lo=b["miss_lo"], hi=b["miss_hi"], passed=bool(b["miss"] <= 0.10 + 1e-12))

    # ---- target C and error growth
    C, G = {}, {}
    for name, pfs in (("CA-HELD", [pf_ca]), ("KR", [pf_kr]), ("POOLED", [pf_ca, pf_kr])):
        col = lambda m, h, c: np.concatenate([p[m][h][:, c] for p in pfs])      # noqa: E731
        C[name] = {}
        for a, bb in (("TARGETED", "NONE"), ("ALL", "NONE"), ("TARGETED", "ALL")):
            C[name][f"{a}-{bb}"] = {int(L.LEADS[h]): dict(zip(("diff", "lo", "hi"), L.diff_ci(col(a, h, 2), col(bb, h, 2))))
                                    for h in range(L.NL)}
            C[name][f"{a}-{bb}"]["rel5"] = float((np.nanmean(col(a, 4, 2)) - np.nanmean(col(bb, 4, 2)))
                                                 / np.nanmean(col(bb, 4, 2)))
        G[name] = {}
        mats = {}
        for m in pfs[0]:
            M = np.column_stack([col(m, h, 2) for h in range(L.NL)])
            mats[m] = M
            G[name][m] = dict(slope_km_per_h=float(np.polyfit(L.LEADS, np.nanmean(M, 0), 1)[0]),
                              pinball_by_lead=np.nanmean(M, 0).tolist(),
                              miss_by_lead=[float(np.nanmean(col(m, h, 0))) for h in range(L.NL)],
                              shortfall_by_lead=[float(np.nanmean(col(m, h, 3))) for h in range(L.NL)],
                              excess_by_lead=[float(np.nanmean(col(m, h, 4))) for h in range(L.NL)])
        for a in ("TARGETED", "ALL"):
            G[name][f"change_{a}_vs_NONE"] = dict(zip(("rel", "lo", "hi", "slope_corrected", "slope_uncorrected"),
                                                      R.growth_change(mats[a], mats["NONE"])))
    N["C"] = C
    c = C["POOLED"]["TARGETED-NONE"][5]
    N["C"]["passed"] = bool(c["hi"] < 0)
    N["growth"] = G

    # ---- target D
    N["D"] = dict(norun=norun_table(o_kr, Q_kr, curve))

    # ---- attribution, Korea (Choi hours and the 25 March detection hours)
    att = R.attribute(o_kr + o_det, {**ks_kr}, var, curve)
    att.to_csv(D / "attribution_kr.csv.gz", index=False)
    N["attribution_kr"] = dict(choi=R.attribution_table(att[att["product"] == "CHOI"]),
                               det=R.attribution_table(att[att["product"] == "DET"]) if (att["product"] == "DET").any() else {},
                               both=R.attribution_table(att))
    # held-out California attribution as a check of the development shares
    att_ca = R.attribute(o_ca, ks_ca, var, curve)
    att_ca.to_csv(D / "attribution_ca_held.csv.gz", index=False)
    N["attribution_ca_held"] = R.attribution_table(att_ca)

    # ---- which term the online loop blamed
    def blame(states, keys):
        cnt = {t: 0 for t in TERM_NAMES.values()}
        for k in keys:
            st = states[k]
            for x in st[:, 4]:
                cnt[TERM_NAMES[int(x)]] += 1
        return cnt
    N["online_blame"] = dict(CA=blame(s_ca, [(f.name, f.product, "TARGETED") for f in o_ca]),
                             KR=blame(s_kr, [(f.name, f.product, "TARGETED") for f in o_kr]),
                             DET=blame(s_det, [("KFS_01", "DET", "TARGETED")]))

    # ---- expected-error file and its calibration
    exp = pd.concat([e_ca, e_kr], ignore_index=True).drop_duplicates(["set", "fire", "product", "t_utc", "lead_h"])
    exp.to_csv(D / "expected_error.csv.gz", index=False, float_format="%.4f")
    cal = {}
    sc = exp[exp.scored == 1]
    for setname, g in sc.groupby("set"):
        cal[setname] = {}
        for p in QS:
            col = f"err_q{int(p * 100)}_km"
            g = g.assign(ex=(g.reach_km - g.margin_km > g[col]).astype(float))
            per = g.groupby(["lead_h", "fire"]).ex.mean().reset_index()
            cal[setname][col] = {int(h): dict(zip(("exceed", "lo", "hi"), L.ci(x.ex.values))) for h, x in per.groupby("lead_h")}
            cal[setname][col]["all_leads"] = dict(zip(("exceed", "lo", "hi"), L.ci(g.groupby("fire").ex.mean().values)))
            cal[setname][col]["nominal"] = 1 - p
    N["expected_error_calibration"] = cal
    (D / "numbers_final.json").write_text(json.dumps(N, indent=1, default=float))
    print("A", N["A"]["models"]["TARGETED"], "passed", N["A"]["passed"])
    print("B", N["B"])
    print("C pooled 5h", c, "passed", N["C"]["passed"])
    for s in ("CA-HELD", "KR"):
        for m in N[s]:
            r = N[s][m][4]
            print(f"{s:8s} {m:10s} miss {r['miss']:.3f} area {r['area']:.1f} ratio {r.get('area_ratio', 1):.3f} "
                  f"pinball {r['pinball']:.3f} area@10 {r['area_at_10']:.1f}")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ca":
        ca()
    elif cmd == "kr":
        kr(sys.argv[2])
    elif cmd == "merge":
        merge()
