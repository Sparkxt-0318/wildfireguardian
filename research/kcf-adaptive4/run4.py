"""Fit on training fires, issue margins on test fires, summarise (PROTOCOL sections 2, 4, 5)."""
import numpy as np

import lib4 as L

RULE_K = 0.10


def fit_models(train, var, settings, which=("FIXED", "QUANTILE", "RULE", "BASE-gust", "BASE-850", "NONE",
                                            "TARGETED", "ALL")):
    """Returns dict of fitted parameters. settings: {'TARGETED': (L, H), 'ALL': (L, H)}."""
    P = {"var": var}
    if "FIXED" in which:
        P["FIXED"] = L.fit_fixed(train)
    if "QUANTILE" in which:
        P["QUANTILE"] = L.fit_quantile(train)
    if "RULE" in which:
        P["RULE10"] = np.array([RULE_K * L.kappa_for(train, lambda f: RULE_K * L.wind_kmh(f, "gust_ms") * L.LEADS[h], h)
                                for h in range(L.NL)])
    for v in ("gust_ms", "w850_ms"):
        name = "BASE-gust" if v == "gust_ms" else "BASE-850"
        if name in which or v == var:
            P[name] = L.fit_base(train, v)
    P["NONE"] = P["BASE-gust" if var == "gust_ms" else "BASE-850"]
    P["ONEK"] = L.fit_base_onek(train, var)
    for arm in ("TARGETED", "ALL"):
        if arm in which:
            Lw, H = settings[arm]
            qs = {id(f): L.correct(f, P["NONE"], var, arm.lower(), Lw, H) for f in train}
            P[arm] = np.array([L.kappa_for(train, lambda f: qs[id(f)][:, h], h) for h in range(L.NL)])
    return P


def issue(P, test, settings, which):
    """dict model -> list of q[T, 8] per test fire."""
    var = P["var"]
    out = {}
    for m in which:
        if m == "FIXED":
            out[m] = [L.q_fixed(f, P["FIXED"]) for f in test]
        elif m == "QUANTILE":
            out[m] = [L.q_quantile(f, P["QUANTILE"]) for f in test]
        elif m == "RULE":
            out[m] = [L.q_base(f, np.full(L.NL, RULE_K), "gust_ms") for f in test]
            out["RULE10"] = [L.q_base(f, P["RULE10"], "gust_ms") for f in test]
        elif m == "BASE-gust":
            out[m] = [L.q_base(f, P[m], "gust_ms") for f in test]
        elif m == "BASE-850":
            out[m] = [L.q_base(f, P[m], "w850_ms") for f in test]
        elif m == "NONE":
            out[m] = [L.q_base(f, P["NONE"], var) for f in test]
            out["ONEK"] = [L.q_base(f, np.full(L.NL, P["ONEK"]), var) for f in test]
        elif m in ("TARGETED", "ALL"):
            Lw, H = settings[m]
            out[m] = [L.correct(f, P["NONE"], var, m.lower(), Lw, H) * P[m][None, :] for f in test]
    return out


def summarise(test, Q, curve, ref="FIXED"):
    """Per model and lead: fire-weighted miss, area, pinball and friends with fire-bootstrap intervals."""
    res, pf = {}, {}
    for m, qs in Q.items():
        pf[m] = [L.per_fire(test, qs, curve, h) for h in range(L.NL)]
    for m, qs in Q.items():
        rows = []
        for h in range(L.NL):
            a = pf[m][h]
            miss = L.ci(a[:, 0])
            area = L.ci(a[:, 1])
            pin = L.ci(a[:, 2])
            row = dict(lead=int(L.LEADS[h]), n_fires=int(np.isfinite(a[:, 0]).sum()), n_hours=int(a[:, 5].sum()),
                       miss=miss[0], miss_lo=miss[1], miss_hi=miss[2], area=area[0], area_lo=area[1], area_hi=area[2],
                       pinball=pin[0], pinball_lo=pin[1], pinball_hi=pin[2],
                       shortfall=float(np.nanmean(a[:, 3])), excess=float(np.nanmean(a[:, 4])))
            if ref in pf and m != ref:
                r = L.ratio_ci(a[:, 1], pf[ref][h][:, 1])
                row.update(area_ratio=r[0], area_ratio_lo=r[1], area_ratio_hi=r[2])
            if h == 4:
                row["area_at_10"] = L.frontier_area(test, qs, curve, h)
            rows.append(row)
        res[m] = rows
    return res, pf


def growth(pf_model, col=2):
    """Slope (per hour of lead) of the fire-weighted mean of a per-fire column against lead 1..8, with the
    per-fire [F, 8] matrix returned for paired bootstraps."""
    M = np.column_stack([pf_model[h][:, col] for h in range(L.NL)])     # [F, 8]
    y = np.nanmean(M, axis=0)
    return float(np.polyfit(L.LEADS, y, 1)[0]), M


def growth_change(Ma, Mb):
    """(slope_a - slope_b) / slope_b with a paired fire bootstrap; a = corrected, b = uncorrected."""
    ok = np.isfinite(Ma).all(1) & np.isfinite(Mb).all(1)
    Ma, Mb = Ma[ok], Mb[ok]
    sl = lambda M: np.polyfit(L.LEADS, M.mean(0), 1)[0]     # noqa: E731
    point = (sl(Ma) - sl(Mb)) / sl(Mb)
    b = L.boot(len(Ma), seed=L.SEED + 3)
    v = np.array([(sl(Ma[i]) - sl(Mb[i])) / sl(Mb[i]) for i in b])
    return float(point), float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), float(sl(Ma)), float(sl(Mb))
