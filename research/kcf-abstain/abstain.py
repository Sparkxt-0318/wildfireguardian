#!/usr/bin/env python3
"""Out-of-range score, abstention threshold, leave-one-fire-out evaluation and transfer (PROTOCOL.md sections 4-7).

    python3 abstain.py --hours derived/hours_pred.csv.gz --out-json derived/abstain_numbers.json \
                       --out-hours derived/hours.csv.gz

Everything follows the frozen protocol (commit ef50d2a). Nothing here is tuned; the only free settings are the
ones the protocol fixes (beta = 0.05, bootstrap 2,000 with seed 20261118, beta grid 0..1 step 0.01).
"""
import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
MARGIN = HERE.parent / "kcf-margin"
sys.path.insert(0, str(MARGIN))
from reach import clopper_pearson, conformal_R  # noqa: E402

PRED = ["gust_ms", "w850_ms", "rhmin_pct", "hdw", "prior3_km"]
SIGN = np.array([1.0, 1.0, -1.0, 1.0, 1.0])    # danger direction: larger signed value = more dangerous
BETA = 0.05
BETAS = np.round(np.arange(0, 1.0001, 0.01), 2)
BOOT, SEED = 2000, 20261118
DRAWS, RSEED = 2000, 20261116
R_FROZEN = {5: 3.75, 8: 5.031152949374527}     # kcf-margin numbers.json, all28, cls all, alpha 0.10
LOFO_COMMITTED = {5: 0.061555772930186714, 8: 0.0661837408575892}


# ------------------------------------------------------------------ tail fractions
def tail_fractions(Zref, Zq):
    """Per predictor: share of reference rows >= query value (ge) and <= query value (le)."""
    n = Zref.shape[0]
    ge = np.empty(Zq.shape)
    le = np.empty(Zq.shape)
    for j in range(Zq.shape[1]):
        s = np.sort(Zref[:, j])
        ge[:, j] = (n - np.searchsorted(s, Zq[:, j], side="left")) / n
        le[:, j] = np.searchsorted(s, Zq[:, j], side="right") / n
    return ge, le


def score_from(pge, ple, two_sided=False):
    if two_sided:
        p = np.minimum(1.0, 2.0 * np.minimum(pge, ple))
    else:
        p = pge
    return p.min(axis=1), p


def thresholds(scores, weights, betas):
    """tau(beta) = largest score value v with weighted share of scores <= v still <= beta; -1 if none."""
    o = np.argsort(scores, kind="mergesort")
    s, w = scores[o], weights[o]
    uniq, start = np.unique(s, return_index=True)
    cw = np.cumsum(w)
    last = np.r_[start[1:] - 1, len(s) - 1]
    cum = cw[last]
    k = np.searchsorted(cum, np.asarray(betas) + 1e-12, side="right") - 1
    return np.where(k >= 0, uniq[np.clip(k, 0, None)], -1.0)


def wauc(score, y, w):
    """Weighted AUROC of `score` (higher = predicts positive) for binary y."""
    o = np.argsort(score, kind="mergesort")
    s, yy, ww = score[o], y[o].astype(bool), w[o]
    uniq, start = np.unique(s, return_index=True)
    P = np.add.reduceat(np.where(yy, ww, 0.0), start)
    N = np.add.reduceat(np.where(~yy, ww, 0.0), start)
    Nbefore = np.cumsum(N) - N
    num = float((P * (Nbefore + 0.5 * N)).sum())
    den = float(P.sum() * N.sum())
    return num / den if den > 0 else math.nan


# ------------------------------------------------------------------ main pieces
class Calib:
    """Tail fractions of every query row against every calibration fire."""

    def __init__(self, df, cal_fires):
        self.fires = list(cal_fires)
        self.Zq = df[PRED].to_numpy(float) * SIGN
        self.ge, self.le = {}, {}
        self.rows = {}
        for f in self.fires:
            idx = np.flatnonzero((df["fire"] == f).to_numpy() & df["scored"].to_numpy() & (df["product"] == "GOFER").to_numpy())
            self.rows[f] = idx
            self.ge[f], self.le[f] = tail_fractions(self.Zq[idx], self.Zq)

    def p(self, rows, ref, two_sided=False):
        ref = list(ref)
        pge = sum(self.ge[g][rows] for g in ref) / len(ref)
        ple = sum(self.le[g][rows] for g in ref) / len(ref)
        return score_from(pge, ple, two_sided)


def lofo_scores(C, fires, two_sided=False):
    """Each calibration fire scored against the other calibration fires (in `fires`)."""
    return {f: C.p(C.rows[f], [g for g in fires if g != f], two_sided)[0] for f in fires}


def fold_thresholds(C, fires, outer, betas, two_sided=False):
    """Nested: for outer fold f, each g != f scored against fires minus {f, g}; threshold over those scores."""
    inner = [g for g in fires if g != outer]
    sc, w = [], []
    for g in inner:
        s, _ = C.p(C.rows[g], [x for x in inner if x != g], two_sided)
        sc.append(s)
        w.append(np.full(s.size, 1.0 / (len(inner) * s.size)))
    return thresholds(np.concatenate(sc), np.concatenate(w), betas)


def per_fire_eval(df, C, fires, Rf, two_sided=False):
    """LOFO evaluation over `fires`: per fire and h, arrays of scores, miss flags, and abstain flags for each beta."""
    out = {}
    lofo = lofo_scores(C, fires, two_sided)
    for f in fires:
        taus = fold_thresholds(C, fires, f, BETAS, two_sided)
        rows = C.rows[f]
        s = lofo[f]
        rec = dict(score=s, taus=taus, rows=rows)
        for h in (5, 8):
            reach = df[f"reach{h}_km"].to_numpy()[rows]
            ok = np.isfinite(reach)
            rec[h] = dict(ok=ok, miss=reach[ok] > Rf[f][h], score=s[ok],
                          abst=s[ok][None, :] <= taus[:, None])   # [beta, hour]
        out[f] = rec
    return out


def summarise(ev, fires, h, bi):
    """Fire-weighted and pooled metrics at beta index bi."""
    a, m, m0, keep_n, ab_n, tot_n, miss_ret, miss_all = [], [], [], [], [], [], [], []
    excluded = []
    for f in fires:
        r = ev[f][h]
        n = r["miss"].size
        if n == 0:
            continue
        ab = r["abst"][bi]
        ret = ~ab
        a.append(ab.mean())
        m0.append(r["miss"].mean())
        tot_n.append(n)
        ab_n.append(int(ab.sum()))
        miss_all.append(int(r["miss"].sum()))
        miss_ret.append(int(r["miss"][ret].sum()))
        keep_n.append(int(ret.sum()))
        if ret.any():
            m.append(r["miss"][ret].mean())
        else:
            excluded.append(f)
    n = len(a)
    nm = len(m)
    res = dict(
        n_fires=n, abstention_rate=float(np.mean(a)), abstention_ci95=list(clopper_pearson(float(np.sum(a)), n)),
        miss_rate_retained=float(np.mean(m)) if nm else math.nan,
        miss_rate_retained_ci95=list(clopper_pearson(float(np.sum(m)), nm)) if nm else None,
        n_fires_with_retained_hours=nm, fires_all_hours_abstained=excluded,
        miss_rate_no_abstention=float(np.mean(m0)), miss_rate_no_abstention_ci95=list(clopper_pearson(float(np.sum(m0)), n)),
        hours=int(np.sum(tot_n)), hours_abstained=int(np.sum(ab_n)), misses_all=int(np.sum(miss_all)),
        misses_retained=int(np.sum(miss_ret)), misses_abstained=int(np.sum(miss_all) - np.sum(miss_ret)),
        pooled_abstention_rate=float(np.sum(ab_n) / np.sum(tot_n)),
        pooled_miss_rate_retained=float(np.sum(miss_ret) / max(1, np.sum(keep_n))),
        pooled_miss_rate_no_abstention=float(np.sum(miss_all) / np.sum(tot_n)),
        pooled_miss_rate_among_abstained=float((np.sum(miss_all) - np.sum(miss_ret)) / np.sum(ab_n)) if np.sum(ab_n) else None)
    return res


def separation(ev, fires, h, bi, rng):
    """Weighted AUROC of -score for misses and Delta risk at beta index bi, with fire-bootstrap intervals."""
    per = []
    for f in fires:
        r = ev[f][h]
        if r["miss"].size:
            ab = r["abst"][bi]
            per.append((-r["score"], r["miss"], ab))

    def stats(sample):
        F = len(sample)
        sc = np.concatenate([p[0] for p in sample])
        y = np.concatenate([p[1] for p in sample])
        w = np.concatenate([np.full(p[0].size, 1.0 / (F * p[0].size)) for p in sample])
        auc = wauc(sc, y, w)
        ret = [p[1][~p[2]].mean() for p in sample if (~p[2]).any()]
        m0 = [p[1].mean() for p in sample]
        return auc, (np.mean(ret) - np.mean(m0)) if ret else math.nan

    auc, delta = stats(per)
    B = []
    for _ in range(BOOT):
        idx = rng.integers(0, len(per), len(per))
        B.append(stats([per[i] for i in idx]))
    B = np.array(B, float)
    ci = lambda v: [float(np.nanquantile(v, 0.025)), float(np.nanquantile(v, 0.975))]  # noqa: E731
    auc_ci, d_ci = ci(B[:, 0]), ci(B[:, 1])
    if auc_ci[0] > 0.5 and d_ci[1] < 0:
        verdict = "separates"
    elif auc_ci[0] <= 0.5 <= auc_ci[1]:
        verdict = "does not separate"
    else:
        verdict = "partial"
    return dict(auroc=auc, auroc_ci95=auc_ci, delta_risk=delta, delta_risk_ci95=d_ci, verdict=verdict,
                bootstrap=dict(resamples=BOOT, seed=SEED, unit="fire"))


def risk_coverage(ev, fires, h):
    cov, risk, pcov, prisk, orc = [], [], [], [], []
    for bi, _ in enumerate(BETAS):
        a, m, kept, missk, tot = [], [], 0, 0, 0
        for f in fires:
            r = ev[f][h]
            if not r["miss"].size:
                continue
            ab = r["abst"][bi]
            a.append(ab.mean())
            if (~ab).any():
                m.append(r["miss"][~ab].mean())
            kept += int((~ab).sum())
            missk += int(r["miss"][~ab].sum())
            tot += r["miss"].size
        cov.append(1 - float(np.mean(a)))
        risk.append(float(np.mean(m)) if m else None)
        pcov.append(kept / tot)
        prisk.append(missk / kept if kept else None)
    # oracle: at retained share c in every fire, abstain on misses first
    grid = np.round(np.arange(0.01, 1.0001, 0.01), 2)
    for c in grid:
        rs = []
        for f in fires:
            r = ev[f][h]
            n = r["miss"].size
            if not n:
                continue
            k = r["miss"].sum()
            keep = c * n
            rs.append(max(0.0, k - (1 - c) * n) / keep)
        orc.append(float(np.mean(rs)))
    m0 = float(np.mean([ev[f][h]["miss"].mean() for f in fires if ev[f][h]["miss"].size]))
    return dict(beta=BETAS.tolist(), coverage=cov, risk=risk, pooled_coverage=pcov, pooled_risk=prisk,
                oracle_coverage=grid.tolist(), oracle_risk=orc, random_risk=m0)


def lofo_margins(gofer_reach, fires):
    """kcf-margin LOFO R per held-out fire and horizon, recomputed with its own conformal_R."""
    Rf, check = {f: {} for f in fires}, {}
    for h in (5, 8):
        sc = {f: g.reach_km.to_numpy() for f, g in gofer_reach[gofer_reach.h == h].groupby("fire")}
        fs = sorted(sc)
        miss = []
        for f in fs:
            R, _, _ = conformal_R([sc[g] for g in fs if g != f], 0.10, DRAWS, RSEED)
            Rf[f][h] = R
            miss.append(float(np.mean(sc[f] > R)))
        check[h] = float(np.mean(miss))
    return Rf, check


def which_min(p):
    return np.array(PRED)[np.argmin(p, axis=1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-hours", required=True)
    ap.add_argument("--meta", default=str(HERE / "derived/hours_base.meta.json"))
    a = ap.parse_args()
    df = pd.read_csv(a.hours, low_memory=False)
    df["scored"] = np.isfinite(df[PRED].to_numpy(float)).all(axis=1)
    gr = pd.read_csv(MARGIN / "derived/gofer_reach.csv.gz")
    cal = sorted(df[df["product"] == "GOFER"].fire.unique())
    assert len(cal) == 28, len(cal)
    Rf, check = lofo_margins(gr, cal)
    for h in (5, 8):
        if abs(check[h] - LOFO_COMMITTED[h]) > 1e-12:
            raise SystemExit(f"STOP: LOFO miss h={h} recomputed {check[h]!r} != committed {LOFO_COMMITTED[h]!r}")
    print("kcf-margin LOFO reproduced:", check, flush=True)

    C = Calib(df, cal)
    gfs11 = sorted(df[(df["product"] == "GOFER") & (df.model == "gfs")].fire.unique())
    rng = np.random.default_rng(SEED)
    bi = int(np.flatnonzero(np.isclose(BETAS, BETA))[0])
    res = dict(meta=dict(protocol_commit="ef50d2a", beta=BETA, R_frozen_km=R_FROZEN,
                         lofo_margin_reproduced=check, calibration_fires=cal, gfs_only_fires=gfs11))

    # ---------------- primary, S1 (two-sided), S2 (GFS-only) leave-one-fire-out
    arms = {"primary": (cal, False), "S1_two_sided": (cal, True), "S2_gfs_only": (gfs11, False)}
    evs = {}
    for arm, (fires, two) in arms.items():
        ev = per_fire_eval(df, C, fires, Rf, two)
        evs[arm] = ev
        block = {}
        for h in (5, 8):
            block[f"h{h}"] = dict(at_beta_0_05=summarise(ev, fires, h, bi), separation=separation(ev, fires, h, bi, rng),
                                  risk_coverage=risk_coverage(ev, fires, h))
            s = block[f"h{h}"]
            print(arm, h, {k: s["at_beta_0_05"][k] for k in ("abstention_rate", "miss_rate_retained",
                                                              "miss_rate_no_abstention")},
                  {k: s["separation"][k] for k in ("auroc", "auroc_ci95", "delta_risk", "delta_risk_ci95", "verdict")},
                  flush=True)
        res[f"calibration_lofo_{arm}"] = block

    # which predictor gave the minimum, abstained calibration hours (primary, beta = 0.05)
    mins = {}
    for f in cal:
        rows = C.rows[f]
        s, p = C.p(rows, [g for g in cal if g != f])
        taus = evs["primary"][f]["taus"]
        ab = s <= taus[bi]
        for k, v in zip(*np.unique(which_min(p[ab]), return_counts=True)):
            mins[k] = mins.get(k, 0) + int(v)
    res["calibration_lofo_primary"]["abstained_hours_by_min_predictor"] = mins

    # ---------------- per-hour columns for calibration rows
    df["score"] = np.nan
    df["abstain"] = pd.NA
    df["min_predictor"] = ""
    for j, n in enumerate(PRED):
        df[f"p_{n}"] = np.nan
    df["score_two_sided"] = np.nan
    df["abstain_two_sided"] = pd.NA
    df["score_gfs_only"] = np.nan
    df["abstain_gfs_only"] = pd.NA
    df["R_km_5"] = np.nan
    df["R_km_8"] = np.nan
    for f in cal:
        rows = C.rows[f]
        s, p = C.p(rows, [g for g in cal if g != f])
        df.loc[rows, "score"] = s
        df.loc[rows, "abstain"] = s <= evs["primary"][f]["taus"][bi]
        df.loc[rows, "min_predictor"] = which_min(p)
        for j, n in enumerate(PRED):
            df.loc[rows, f"p_{n}"] = p[:, j]
        s2, _ = C.p(rows, [g for g in cal if g != f], True)
        df.loc[rows, "score_two_sided"] = s2
        df.loc[rows, "abstain_two_sided"] = s2 <= evs["S1_two_sided"][f]["taus"][bi]
        if f in gfs11:
            s3, _ = C.p(rows, [g for g in gfs11 if g != f])
            df.loc[rows, "score_gfs_only"] = s3
            df.loc[rows, "abstain_gfs_only"] = s3 <= evs["S2_gfs_only"][f]["taus"][bi]
        df.loc[df.fire == f, "R_km_5"] = Rf[f][5]
        df.loc[df.fire == f, "R_km_8"] = Rf[f][8]

    # ---------------- transfer: thresholds from all calibration fires (LOFO scores)
    def tau_all(fires, two):
        ls = lofo_scores(C, fires, two)
        sc = np.concatenate([ls[f] for f in fires])
        w = np.concatenate([np.full(ls[f].size, 1.0 / (len(fires) * ls[f].size)) for f in fires])
        return float(thresholds(sc, w, [BETA])[0])

    tau = dict(primary=tau_all(cal, False), S1_two_sided=tau_all(cal, True), S2_gfs_only=tau_all(gfs11, False))
    res["thresholds_for_test_fires"] = tau
    test = np.flatnonzero((df["role"] == "test").to_numpy() & df["scored"].to_numpy())
    s, p = C.p(test, cal)
    df.loc[test, "score"] = s
    df.loc[test, "abstain"] = s <= tau["primary"]
    df.loc[test, "min_predictor"] = which_min(p)
    for j, n in enumerate(PRED):
        df.loc[test, f"p_{n}"] = p[:, j]
    s2, _ = C.p(test, cal, True)
    df.loc[test, "score_two_sided"] = s2
    df.loc[test, "abstain_two_sided"] = s2 <= tau["S1_two_sided"]
    gfs_test = test[(df.model.to_numpy()[test] == "gfs")]
    s3, _ = C.p(gfs_test, gfs11)
    df.loc[gfs_test, "score_gfs_only"] = s3
    df.loc[gfs_test, "abstain_gfs_only"] = s3 <= tau["S2_gfs_only"]
    tst = df["role"] == "test"
    df.loc[tst, "R_km_5"] = R_FROZEN[5]
    df.loc[tst, "R_km_8"] = R_FROZEN[8]
    for h in (5, 8):
        ok = np.isfinite(df[f"reach{h}_km"]) & np.isfinite(df[f"R_km_{h}"])
        df[f"held{h}"] = np.where(ok, df[f"reach{h}_km"] <= df[f"R_km_{h}"], np.nan)

    # ---------------- per test fire counts
    per_fire = {}
    for (fire, prod), g in df[tst].groupby(["fire", "product"]):
        rec = dict(product=prod, country=g.country.iloc[0], model=g.model.iloc[0], issue_hours=int(len(g)),
                   not_scored=dict(g[~g.scored].fc_note.fillna("").replace("", "prior3_undefined_or_other")
                                   .value_counts().to_dict()) if (~g.scored).any() else {})
        for h in (5, 8):
            gg = g[g.scored & np.isfinite(g[f"reach{h}_km"])]
            ab = gg.abstain.astype(bool)
            held = gg[f"reach{h}_km"] <= R_FROZEN[h]
            rec[f"h{h}"] = dict(scored_hours=int(len(gg)), abstained_held=int((ab & held).sum()),
                                abstained_missed=int((ab & ~held).sum()), kept_held=int((~ab & held).sum()),
                                kept_missed=int((~ab & ~held).sum()))
        per_fire[f"{fire}|{prod}"] = rec
    res["test_fires"] = per_fire
    no_hours = {}
    for eid, m in json.load(open(a.meta))["choi"].items():
        if m["hours"] == 0 and m["role"] == "test":
            no_hours[eid] = f"no eligible issue hour (arrival span {m['first']} .. {m['last']} UTC is shorter than 5 h + 1)"
    res["test_fires_not_tested"] = no_hours

    # group summaries: US Choi test fires (rates if >= 10 fires with scored hours), US2024 and Korea counts only
    us24 = {"ID-BOF-000683_Wapiti_Wapiti", "ID-BOF-000904_Goat", "ID-BOF-001080_Lava", "ID-SCF-240202_RedRock",
            "WA-SES-000173_Pioneer", "WY-BTF-002416_FishCreek"}
    groups = {}
    for name, sel in {"US_choi_19": (tst & (df.country == "US") & (df["product"] == "CHOI")),
                      "US2024": (tst & df.fire.isin(us24)),
                      "Korea_choi": (tst & (df.country == "KR") & (df["product"] == "CHOI")),
                      "Korea_25March_DET": (tst & (df["product"] == "DET"))}.items():
        gsel = df[sel]
        blk = {}
        for h in (5, 8):
            gg = gsel[gsel.scored & np.isfinite(gsel[f"reach{h}_km"])]
            ab = gg.abstain.astype(bool)
            held = gg[f"reach{h}_km"] <= R_FROZEN[h]
            counts = dict(fires=int(gg.fire.nunique()), scored_hours=int(len(gg)), abstained=int(ab.sum()),
                          missed=int((~held).sum()), abstained_missed=int((ab & ~held).sum()),
                          abstained_held=int((ab & held).sum()), kept_missed=int((~ab & ~held).sum()),
                          kept_held=int((~ab & held).sum()))
            if name == "US_choi_19" and counts["fires"] >= 10:
                a_f, m_f, m0_f = [], [], []
                for _, q in gg.groupby("fire"):
                    qa = q.abstain.astype(bool).to_numpy()
                    qm = (q[f"reach{h}_km"] > R_FROZEN[h]).to_numpy()
                    a_f.append(qa.mean())
                    m0_f.append(qm.mean())
                    if (~qa).any():
                        m_f.append(qm[~qa].mean())
                counts.update(abstention_rate=float(np.mean(a_f)),
                              abstention_ci95=list(clopper_pearson(float(np.sum(a_f)), len(a_f))),
                              miss_rate_retained=float(np.mean(m_f)) if m_f else None,
                              miss_rate_retained_ci95=list(clopper_pearson(float(np.sum(m_f)), len(m_f))) if m_f else None,
                              miss_rate_no_abstention=float(np.mean(m0_f)),
                              miss_rate_no_abstention_ci95=list(clopper_pearson(float(np.sum(m0_f)), len(m0_f))),
                              rates_label="fire-weighted, MEASURED on Choi kriged rasters")
            blk[f"h{h}"] = counts
        groups[name] = blk
    res["test_groups"] = groups

    # ---------------- S3: product cross-check on the 10 fires with both GOFER and a Choi raster
    s3 = {}
    sub = df[(df.role == "s3")]
    for h in (5, 8):
        rows, fr_g, fr_c = [], [], []
        for eid, q in sub.groupby("fire"):
            gname = q.gofer_name.iloc[0]
            gq = df[(df["product"] == "GOFER") & (df.fire == gname)]
            m = pd.merge(gq[["t_utc", f"reach{h}_km"]], q[["t_utc", f"reach{h}_km"]], on="t_utc", suffixes=("_gofer", "_choi"))
            m = m[np.isfinite(m[f"reach{h}_km_gofer"]) & np.isfinite(m[f"reach{h}_km_choi"])]
            if not len(m):
                continue
            mg = float((m[f"reach{h}_km_gofer"] > R_FROZEN[h]).mean())
            mc = float((m[f"reach{h}_km_choi"] > R_FROZEN[h]).mean())
            fr_g.append(mg)
            fr_c.append(mc)
            rows.append(dict(fire=gname, hours=int(len(m)), miss_gofer=mg, miss_choi=mc,
                             median_reach_gofer=float(m[f"reach{h}_km_gofer"].median()),
                             median_reach_choi=float(m[f"reach{h}_km_choi"].median())))
        n = len(fr_g)
        s3[f"h{h}"] = dict(n_fires=n, per_fire=rows,
                           miss_rate_gofer=float(np.mean(fr_g)) if n else None,
                           miss_rate_gofer_ci95=list(clopper_pearson(float(np.sum(fr_g)), n)) if n >= 10 else None,
                           miss_rate_choi=float(np.mean(fr_c)) if n else None,
                           miss_rate_choi_ci95=list(clopper_pearson(float(np.sum(fr_c)), n)) if n >= 10 else None)
    res["S3_product_crosscheck"] = s3

    # ---------------- 25 March 2025 explicit hours
    d = df[(df["product"] == "DET")].sort_values("kst_hour")
    cols = ["kst_hour", "t_utc", "cycle_utc", "viirs_cells", "lat", "lon"] + PRED + [f"p_{n}" for n in PRED] + [
        "score", "abstain", "min_predictor", "score_two_sided", "abstain_two_sided", "score_gfs_only", "abstain_gfs_only",
        "reach5_km", "reach8_km", "held5", "held8", "complete5", "complete8"]
    res["march25_hours"] = json.loads(d[cols].to_json(orient="records"))
    res["march25_choi_hours"] = json.loads(df[(df.fire == "KFS_01") & (df["product"] == "CHOI")
                                              & (df.t_utc >= "2025-03-24 15:00") & (df.t_utc <= "2025-03-25 14:00")]
                                           [["t_utc", "score", "abstain", "reach5_km", "reach8_km", "held5", "held8",
                                             "prior3_km"]].to_json(orient="records"))
    # not-scored summary for calibration
    c = df[df["product"] == "GOFER"]
    res["calibration_not_scored"] = dict(
        issue_hours=int(len(c)), scored=int(c.scored.sum()),
        prior3_undefined=int((~np.isfinite(c.prior3_km)).sum()),
        forecast_missing=int((c.fc_note.fillna("") != "").sum()),
        by_note=c.fc_note.fillna("").replace("", "ok").value_counts().to_dict())

    df.to_csv(a.out_hours, index=False)
    json.dump(res, open(a.out_json, "w"), indent=1, default=float)
    print("thresholds:", tau)


if __name__ == "__main__":
    main()
