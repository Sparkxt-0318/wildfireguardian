"""Test A (Bunsen, plan of 2026-11-18): logged CSV -> flux per run, per distance, comparison with three curves.

    python -m field_tests.a_bunsen_analyse LOG.csv --sheet field_tests/sheets/A_plan_inputs.yaml --out OUTDIR

LOG.csv (one tidy file, one row per sample). Required columns: run_id, t_s, plate_c, air_c. Per exposure run:
distance_m (burner axis to plate face, m) and repeat. Optional: kind (exposure | cooldown; default exposure),
phase (baseline | exposure | tail; if absent, t_s = 0 is the moment the shield comes off, baseline is t_s < 0 and
the exposure is 0 <= t_s < run_s), fault (non-empty = thermocouple fault, sample dropped), gas_c (a shielded
thermocouple next to the plate, used only to bound convection). A cooldown run is the plate heated and then left alone
(gas off, burner away); it fixes the loss term.

What is computed (A_PLAN.md section 1): thin-skin energy balance  C dT/dt = alpha*q - loss(T),  C = rho*cp*d,
loss(T) = h (T-Ta) + eps*sigma*(T^4-Ta^4), h from the cool-down curves (crossing.flux.fit_cooldown). Mean flux over
the exposure window by integrating the balance (no differentiation of the noisy trace):

    q = [ C (T(t2) - T(t1)) + integral loss dt ] / (alpha (t2 - t1))  -  q_baseline

q_baseline is the apparent flux of the shielded baseline (drift, TC offset), subtracted as a constant.
A run is "unusable" if any sample >= 70 C (reported, never dropped silently, excluded from means).

Comparison (A_PLAN.md section 3). Every curve is linear in chi, so chi is not known beforehand and only SHAPE can
discriminate. For each curve m: chi_eff (the chi it would need), chi^2 of the shape after the best chi, the fitted
exponent, and a pre-registered verdict. Input that is not a measurement is labelled SIMULATED everywhere.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import bunsen_models as bm
from . import common
from crossing.flux import PlateSpec, LossModel, fit_cooldown, SIGMA, C_TO_K

DISC_MAX_C = 70.0
QUANT_C = 0.25                      # MAX31855 resolution
LHV_DEFAULT_MJ_M3 = {"methane": 33.9, "propane": 86.4}

# Pre-registered decision numbers (A_PLAN.md section 3). Changing them after data is in is not allowed.
SNR_MIN = 3.0                       # a distance enters the shape test only if q / u >= this
DELTA_CHI2_FAVOUR = 9.0             # 3 sigma between two curves' shape chi^2
CHI_PRIOR = (0.01, 0.30)            # a curve whose chi_eff leaves this range is not credible
MIN_POINTS = 3                      # distances needed for a shape verdict

# Uncertainty inputs that are ASSUMPTIONS (listed in A_PLAN.md section 5; defaults, overridable on the CLI)
DEFAULTS = dict(run_s=60.0, baseline_s=30.0, end_win_s=6.0, alpha_rel=0.03, h_rel_min=0.15, t_on_sigma_s=1.0,
                dist_sigma_m=0.002, floor_kw_m2=0.003, conv_kw_m2=0.02)


# ------------------------------------------------------------------------------------------------ input
@dataclass
class Run:
    run_id: str
    kind: str
    distance_m: float
    repeat: str
    t: np.ndarray
    plate: np.ndarray
    air: np.ndarray
    phase: Optional[np.ndarray]
    gas: Optional[np.ndarray]
    n_fault: int = 0


def read_log(path) -> List[Run]:
    rows: Dict[str, list] = {}
    with open(path, newline="") as fh:
        rd = csv.DictReader(fh)
        need = {"run_id", "t_s", "plate_c", "air_c"}
        if not need <= set(rd.fieldnames or []):
            raise ValueError("log needs columns %s, has %s" % (sorted(need), rd.fieldnames))
        for r in rd:
            rows.setdefault(r["run_id"], []).append(r)
    runs = []
    for rid, rr in rows.items():
        def col(name, cast=float, default=float("nan")):
            out = []
            for r in rr:
                v = (r.get(name) or "").strip()
                try:
                    out.append(cast(v) if v != "" else default)
                except ValueError:
                    out.append(default)
            return out
        fault = [(r.get("fault") or "").strip() for r in rr]
        t = np.array(col("t_s")); plate = np.array(col("plate_c")); air = np.array(col("air_c"))
        bad = np.array([bool(f) for f in fault]) | ~np.isfinite(t) | ~np.isfinite(plate)
        order = np.argsort(t[~bad], kind="stable")
        keep = np.where(~bad)[0][order]
        kind = (rr[0].get("kind") or "").strip().lower() or "exposure"
        dist = col("distance_m")
        phase = np.array([(rr[i].get("phase") or "").strip().lower() for i in keep]) if "phase" in rr[0] else None
        gas = np.array(col("gas_c"))[keep] if "gas_c" in rr[0] else None
        if phase is not None and not any(phase):
            phase = None
        runs.append(Run(rid, kind, float(np.nanmedian(dist)) if np.isfinite(dist).any() else float("nan"),
                        (rr[0].get("repeat") or "").strip(), t[keep], plate[keep], air[keep], phase, gas,
                        int(bad.sum())))
    return runs


# --------------------------------------------------------------------------------------------- numerics
def _linfit(t, y, t0):
    """Value and slope at t0 of a least-squares line, with their variances (residual-based, floored at the
    quantisation noise of the MAX31855)."""
    n = len(t)
    if n < 4:
        return float("nan"), float("nan"), float("nan"), float("nan")
    V = np.column_stack([np.ones(n), t - t0])
    coef, *_ = np.linalg.lstsq(V, y, rcond=None)
    rss = float(np.sum((y - V @ coef) ** 2))
    s2 = max(rss / (n - 2), QUANT_C ** 2 / 12.0)
    cov = s2 * np.linalg.inv(V.T @ V)
    return float(coef[0]), float(coef[1]), float(cov[0, 0]), float(cov[1, 1])


def _loss(model: LossModel, plate_c, air_c):
    return model.loss_w_m2(np.asarray(plate_c) + C_TO_K, np.asarray(air_c) + C_TO_K)


@dataclass
class RunResult:
    run_id: str
    distance_m: float
    repeat: str
    q_kw_m2: float = float("nan")
    u_kw_m2: float = float("nan")          # random + stated per-run terms, kW/m2
    q_raw_kw_m2: float = float("nan")      # before baseline subtraction
    q_bg_kw_m2: float = float("nan")
    loss_share: float = float("nan")       # fraction of the absorbed energy that the loss term accounts for
    dT_k: float = float("nan")
    plate_max_c: float = float("nan")
    ok: bool = False
    status: str = ""
    parts: Dict[str, float] = field(default_factory=dict)


def windows(run: Run, run_s: float, baseline_s: float):
    t = run.t
    if run.phase is not None:
        ph = run.phase
        ex = ph == "exposure"
        bs = ph == "baseline"
        if not ex.any() or not bs.any():
            return None
        t1, t2 = float(t[ex].min()), float(t[ex].max())
        return t1, t2, t[bs]
    return 0.0, run_s, t[(t >= -baseline_s) & (t < 0)]


def flux_of_run(run: Run, spec: PlateSpec, loss: LossModel, u_h_rel: float, p: dict) -> RunResult:
    res = RunResult(run.run_id, run.distance_m, run.repeat)
    t, T, Ta = run.t, run.plate, run.air
    if t.size == 0:
        res.status = "NO DATA"; return res
    res.plate_max_c = float(np.nanmax(T))
    if res.plate_max_c >= DISC_MAX_C:
        res.status = "UNUSABLE: disc reached %.1f C (>= %.0f C)" % (res.plate_max_c, DISC_MAX_C); return res
    w = windows(run, p["run_s"], p["baseline_s"])
    if w is None:
        res.status = "NO PHASE MARKS"; return res
    t1, t2, tb = w
    if tb.size < 40 or (tb.max() - tb.min()) < 0.8 * p["baseline_s"]:
        res.status = "BASELINE TOO SHORT (%d samples)" % tb.size; return res
    ex = (t >= t1 - 1e-9) & (t <= t2 + 1e-9)
    if ex.sum() < 0.8 * (t2 - t1) * 5 or (t[ex].max() - t[ex].min()) < 0.9 * (t2 - t1):
        res.status = "EXPOSURE WINDOW INCOMPLETE"; return res
    if np.max(np.diff(t[ex])) > 1.0:
        res.status = "GAP > 1 s IN EXPOSURE"; return res
    C, alpha, tau = spec.heat_capacity_j_m2_k, spec.absorptivity, t2 - t1
    ew = p["end_win_s"]
    bsel = (t >= t1 - ew) & (t < t1)
    esel = (t > t2 - ew) & (t <= t2)
    T1, _, v1, _ = _linfit(t[bsel], T[bsel], t1)
    T2, _, v2, _ = _linfit(t[esel], T[esel], t2)
    loss_int = float(np.trapezoid(_loss(loss, T[ex], Ta[ex]), t[ex]))
    q_raw = (C * (T2 - T1) + loss_int) / (alpha * tau) / 1000.0
    # baseline apparent flux
    bb = (t >= tb.min()) & (t < t1)
    Tb, sb, _, vsb = _linfit(t[bb], T[bb], float(np.mean(t[bb])))
    q_bg = (C * sb + float(np.mean(_loss(loss, T[bb], Ta[bb])))) / alpha / 1000.0
    q = q_raw - q_bg
    # per-run uncertainty terms, kW/m2
    parts = {
        "trace_noise": C * math.sqrt(v1 + v2) / (alpha * tau) / 1000.0,
        "baseline": C * math.sqrt(vsb) / alpha / 1000.0,
        "loss_model": u_h_rel * abs(loss_int) / (alpha * tau) / 1000.0,
        "timing": abs(q) * p["t_on_sigma_s"] / tau,
        "floor": p["floor_kw_m2"],
        "convection": _conv_term(run, ex, loss, p),
    }
    res.q_kw_m2, res.q_raw_kw_m2, res.q_bg_kw_m2 = q, q_raw, q_bg
    res.u_kw_m2 = math.sqrt(sum(v * v for v in parts.values()))
    res.parts = parts
    res.dT_k = T2 - T1
    absorbed = C * (T2 - T1) + loss_int
    res.loss_share = loss_int / absorbed if absorbed > 0 else float("nan")
    res.ok, res.status = True, "ok"
    return res


def _conv_term(run: Run, ex, loss: LossModel, p: dict) -> float:
    """Convection uncertainty, kW/m2: h x (mean gas - air) from the optional shielded gas thermocouple, else the
    ASSUMED --conv-kw-m2 (A_PLAN.md section 5). Not subtracted: convection is not separable from radiation here."""
    if run.gas is not None and np.isfinite(run.gas[ex]).any():
        return float(abs(loss.h * np.nanmean(run.gas[ex] - run.air[ex])) / 1000.0)
    return float(p["conv_kw_m2"])


def fit_loss(runs: Sequence[Run], spec: PlateSpec, min_h_rel: float):
    """Loss model from the cool-down runs: pooled mean of per-run h; relative uncertainty = spread of h between
    runs (std of the mean over sqrt(n), but never below min_h_rel: one still-air fit does not cover draughts)."""
    fits, notes = [], []
    for r in runs:
        if r.kind != "cooldown":
            continue
        sel = (r.t >= r.t[0])
        if r.phase is not None:
            sel = np.array([ph in ("tail", "cooldown", "") for ph in r.phase])
        try:
            fits.append(fit_cooldown(r.t[sel], r.plate[sel], r.air[sel], spec))
        except ValueError as e:
            notes.append("%s: %s" % (r.run_id, e))
    if not fits:
        return (LossModel(h=10.0, eps=spec.emissivity, note="UNFITTED DEFAULT h=10"), 0.5, fits,
                notes + ["no usable cool-down run: loss model is an UNFITTED default, u_h = 50 %"])
    hs = np.array([f.h for f in fits])
    h = float(hs.mean())
    spread = float(hs.std(ddof=1) / math.sqrt(len(hs)) / h) if len(hs) > 1 else 0.0
    lo = min(f.t_range_c[0] for f in fits); hi = max(f.t_range_c[1] for f in fits)
    model = LossModel(h=h, eps=spec.emissivity, rms_residual_w_m2=float(np.mean([f.rms_residual_w_m2 for f in fits])),
                      n=int(sum(f.n for f in fits)), t_range_c=(lo, hi), note="pooled mean of %d cool-down fits" % len(fits))
    if len(fits) < 2:
        notes.append("only one cool-down fit: spread unknown, u_h set to %.0f %%" % (100 * max(min_h_rel, 0.25)))
        return model, max(min_h_rel, 0.25), fits, notes
    return model, max(spread, min_h_rel), fits, notes


# ------------------------------------------------------------------------------------------ comparison
def per_distance(results: Sequence[RunResult], p: dict, alpha: float) -> List[dict]:
    by: Dict[float, List[RunResult]] = {}
    for r in results:
        if r.ok:
            by.setdefault(round(r.distance_m, 4), []).append(r)
    out = []
    for d in sorted(by):
        rr = by[d]
        q = np.array([r.q_kw_m2 for r in rr]); u = np.array([r.u_kw_m2 for r in rr])
        n = len(rr)
        stat = float(np.sqrt(np.sum(u ** 2)) / n)               # propagated random terms of the mean
        scat = float(q.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
        ui = max(stat, scat) if n > 1 else stat
        out.append({"distance_m": d, "n_runs": n, "q_kw_m2": float(q.mean()), "u_random_kw_m2": ui,
                    "repeat_scatter_kw_m2": scat, "snr": float(q.mean() / ui) if ui > 0 else float("inf"),
                    "plate_max_c": float(max(r.plate_max_c for r in rr)),
                    "loss_share": float(np.nanmean([r.loss_share for r in rr]))})
    return out


def _chi2_sf_approx(x: float, k: int) -> float:
    """P(chi2_k >= x), Wilson-Hilferty normal approximation (no scipy needed; fine for k >= 1 at the 5 % level)."""
    if k <= 0:
        return float("nan")
    z = ((x / k) ** (1 / 3) - (1 - 2 / (9 * k))) / math.sqrt(2 / (9 * k))
    return 0.5 * math.erfc(z / math.sqrt(2))


def compare(rows: List[dict], flame: bm.Flame, p: dict, chi_sheet: float, alpha_rel: float, q_rel: float) -> dict:
    """Shape test of each curve against the per-distance means. chi is a free factor, so
    y_i = ln(q_i / q_curve_i(chi = 1)) should be a constant ln chi_eff."""
    rs = np.array([r["distance_m"] for r in rows])
    curves = bm.curves(rs, flame)
    for i, r in enumerate(rows):
        for k, v in curves.items():
            r["curve_" + k + "_chi1"] = float(v[i])
    use = np.array([r["snr"] >= SNR_MIN and r["q_kw_m2"] > 0 for r in rows])
    out = {"n_used": int(use.sum()), "distances_used": [float(x) for x in rs[use]],
           "distances_below_floor": [float(x) for x in rs[~use]], "curves": {}}
    for name, qc in curves.items():
        y = np.full(len(rows), np.nan); sig = np.full(len(rows), np.nan)
        for i, r in enumerate(rows):
            if use[i]:
                n_loc = bm.local_exponent(bm.CURVES[name], r["distance_m"], flame)
                y[i] = math.log(r["q_kw_m2"] / qc[i])
                sig[i] = math.hypot(r["u_random_kw_m2"] / r["q_kw_m2"],
                                    n_loc * p["dist_sigma_m"] / r["distance_m"] / math.sqrt(r["n_runs"]))
        m = np.isfinite(y)
        d = {"name": name}
        if m.sum() >= 1:
            w = 1.0 / sig[m] ** 2
            c = float(np.sum(w * y[m]) / np.sum(w))
            sc = math.sqrt(1.0 / np.sum(w))
            common_rel = math.hypot(alpha_rel, q_rel)             # alpha and Q: common to all distances
            chi = math.exp(c)
            d.update(chi_eff=chi, chi_eff_u_rel=math.hypot(sc, common_rel),
                     chi2=float(np.sum(w * (y[m] - c) ** 2)), dof=int(m.sum() - 1),
                     chi_in_prior=bool(CHI_PRIOR[0] <= chi <= CHI_PRIOR[1]),
                     level_ratio_at_sheet_chi=float(np.mean([r["q_kw_m2"] / (chi_sheet * qc[i])
                                                             for i, r in enumerate(rows) if use[i]])))
            d["p_value"] = _chi2_sf_approx(d["chi2"], d["dof"]) if d["dof"] > 0 else float("nan")
        out["curves"][name] = d
    # measured exponent (weighted log-log line) beside each curve's exponent over the same distances
    if use.sum() >= 2:
        x = np.log(rs[use]); yy = np.log([r["q_kw_m2"] for r, u in zip(rows, use) if u])
        sg = np.array([r["u_random_kw_m2"] / r["q_kw_m2"] for r, u in zip(rows, use) if u])
        sg = np.hypot(sg, 2.0 * p["dist_sigma_m"] / rs[use] / 1.0)
        W = np.diag(1 / sg ** 2); V = np.column_stack([np.ones_like(x), x])
        cov = np.linalg.inv(V.T @ W @ V); beta = cov @ V.T @ W @ yy
        out["exponent"] = {"measured": float(-beta[1]), "u": float(math.sqrt(cov[1, 1])),
                           "curves": {n: float(np.mean([bm.local_exponent(bm.CURVES[n], r, flame) for r in rs[use]]))
                                      for n in curves}}
    out["verdict"] = verdict(out)
    return out


def verdict(cmp_: dict) -> dict:
    """Pre-registered rules (A_PLAN.md 3). Returns {"text": ..., "favoured": name or None, "reasons": [...]}."""
    reasons: List[str] = []
    cs = cmp_["curves"]
    scalable = ["closed_form", "voxel_sum", "point"]
    if cmp_["n_used"] < MIN_POINTS:
        return {"favoured": None, "reasons": ["only %d distances above the floor (need %d): no shape verdict"
                                              % (cmp_["n_used"], MIN_POINTS)], "text": "NO VERDICT (too few usable distances)"}
    ok = {n: cs[n] for n in scalable if "chi2" in cs[n]}
    acceptable = {n: c for n, c in ok.items() if c["dof"] > 0 and c["p_value"] >= 0.05 and c["chi_in_prior"]}
    for n, c in ok.items():
        if n not in acceptable:
            reasons.append("%s rejected: %s" % (n, "chi_eff %.3f outside prior %s" % (c["chi_eff"], CHI_PRIOR)
                                               if not c["chi_in_prior"] else "shape chi2 %.1f on %d dof (p=%.3f)" %
                                               (c["chi2"], c["dof"], c["p_value"])))
    fav = None
    if acceptable:
        best = min(acceptable, key=lambda n: acceptable[n]["chi2"])
        others = [n for n in ok if n != best]
        if all(ok[n]["chi2"] - ok[best]["chi2"] >= DELTA_CHI2_FAVOUR for n in others):
            fav = best
            reasons.append("%s fits and every other curve is worse by >= %.0f in chi2" % (best, DELTA_CHI2_FAVOUR))
        else:
            gaps = {n: ok[n]["chi2"] - ok[best]["chi2"] for n in others}
            reasons.append("best shape %s, but chi2 gaps to the others are %s (< %.0f): not distinguishable"
                           % (best, {k: round(v, 2) for k, v in gaps.items()}, DELTA_CHI2_FAVOUR))
    else:
        reasons.append("no scalable curve is acceptable: look for a measurement problem (convection, drift, "
                       "geometry) before blaming a model")
    reasons.append("fds_fit_transfer is not a scaled FDS radiometer curve and cannot be favoured; its chi2 is "
                   "reported for completeness")
    text = ("FAVOURS %s" % fav) if fav else "NO CURVE FAVOURED"
    return {"favoured": fav, "reasons": reasons, "text": text}


# ------------------------------------------------------------------------------------------------ output
def make_figure(rows, results, runs, cmp_, flame, chi_sheet, chi_range, out_png, simulated, spec):
    plt = common.pyplot()
    fig, ax = plt.subplots(1, 3, figsize=(15.5, 5.0), constrained_layout=True)
    cols = {"closed_form": "#0072B2", "voxel_sum": "#D55E00", "fds_fit_transfer": "#009E73", "point": "0.45"}
    sty = {"closed_form": "-", "voxel_sum": "--", "fds_fit_transfer": ":", "point": "-."}
    lab = {"closed_form": "closed-form line source", "voxel_sum": "voxel sum (no absorption)",
           "fds_fit_transfer": "FDS-fit absorption, transferred", "point": "point source (reference)"}
    rs = np.array([r["distance_m"] for r in rows]) if rows else np.array([0.1, 0.4])
    rg = np.geomspace(rs.min() * 0.9, rs.max() * 1.1, 60)
    cg = bm.curves(rg, flame, names=tuple(cols))
    a = ax[0]
    for n in cols:
        a.plot(rg, chi_sheet * cg[n], sty[n], color=cols[n], lw=1.8, label=lab[n])
    a.fill_between(rg, chi_range[0] * cg["closed_form"], chi_range[1] * cg["closed_form"], color=cols["closed_form"],
                   alpha=0.10, lw=0)
    if rows:
        q = np.array([r["q_kw_m2"] for r in rows]); u = np.array([r["u_random_kw_m2"] for r in rows])
        a.errorbar(rs, np.clip(q, 1e-5, None), yerr=u, fmt="o", color="k", ms=6, capsize=3, label="measured (mean of repeats, 1 sigma random)")
        for r in results:
            if r.ok:
                a.plot(r.distance_m, max(r.q_kw_m2, 1e-5), "o", mfc="none", mec="0.5", ms=4)
    a.set_xscale("log"); a.set_yscale("log"); a.set_xlabel("burner axis to plate face r (m)")
    a.set_ylabel("incident flux (kW/m$^2$)")
    a.set_title("(a) flux; curves at sheet chi=%.2f, band %.2f-%.2f" % ((chi_sheet,) + tuple(chi_range)), fontsize=9)
    a.legend(fontsize=7, loc="lower left"); a.grid(alpha=0.25, which="both")
    b = ax[1]
    for n in cols:
        if rows:
            yv = np.array([r["q_kw_m2"] / r["curve_%s_chi1" % n] for r in rows])
            uv = np.array([r["u_random_kw_m2"] / r["curve_%s_chi1" % n] for r in rows])
            off = 1.0 + 0.012 * list(cols).index(n)
            b.errorbar(rs * off, yv, yerr=uv, fmt="o" + ("" if n != "point" else ""), color=cols[n], ms=5, capsize=2,
                       label="%s: chi_eff %s" % (lab[n], ("%.3f" % cmp_["curves"][n]["chi_eff"]) if "chi_eff" in cmp_["curves"].get(n, {}) else "n/a"))
            if "chi_eff" in cmp_["curves"].get(n, {}):
                b.axhline(cmp_["curves"][n]["chi_eff"], color=cols[n], ls=sty[n], lw=0.8, alpha=0.7)
    b.axhspan(CHI_PRIOR[0], CHI_PRIOR[1], color="0.85", alpha=0.5, lw=0)
    b.set_xscale("log"); b.set_yscale("log"); b.set_xlabel("r (m)")
    b.set_ylabel("measured / curve(chi = 1)  =  chi needed")
    b.set_title("(b) shape test: a flat line means the curve's shape fits;\ngrey band = prior chi range", fontsize=9)
    b.legend(fontsize=7, loc="best"); b.grid(alpha=0.25, which="both")
    c = ax[2]
    ex = [r for r in runs if r.kind != "cooldown" and r.phase is None or r.kind == "exposure"]
    dists = sorted({round(r.distance_m, 4) for r in ex if np.isfinite(r.distance_m)})
    cm = plt.get_cmap("viridis")
    for r in ex:
        if not np.isfinite(r.distance_m) or r.t.size == 0:
            continue
        k = dists.index(round(r.distance_m, 4)) / max(1, len(dists) - 1)
        c.plot(r.t, r.plate, color=cm(k), lw=0.9, alpha=0.8)
    for d in dists:
        k = dists.index(d) / max(1, len(dists) - 1)
        c.plot([], [], color=cm(k), label="r = %.2f m" % d)
    c.axhline(DISC_MAX_C, color="r", lw=1.2); c.text(c.get_xlim()[1], DISC_MAX_C, "70 C disc limit ", color="r", va="bottom", ha="right", fontsize=8)
    c.set_xlabel("time since shield off (s)"); c.set_ylabel("plate temperature (C)")
    c.set_title("(c) plate traces (exposure runs)", fontsize=9)
    if dists:
        c.legend(fontsize=7, loc="center right")
    c.grid(alpha=0.25)
    return common.finish_figure(fig, out_png, "Test A: flux plate vs Bunsen flame, measurement beside three curves", simulated)


def _need(sheet: dict, key: str) -> float:
    v = sheet.get(key)
    if v is None:
        raise SystemExit("sheet: %s is null; measure it (photo against a scale) before analysing" % key)
    return float(v)


def run(log_path, sheet: dict, out: Path, simulated: bool, overrides: Optional[dict] = None) -> dict:
    p = dict(DEFAULTS); p.update(overrides or {})
    plate = sheet.get("plate", {})
    spec = PlateSpec(thickness_m=plate.get("thickness_m", 0.001), rho=plate.get("rho", 8960.0), cp=plate.get("cp", 385.0),
                     absorptivity=plate.get("absorptivity", 0.95), emissivity=plate.get("emissivity", 0.95),
                     area_m2=math.pi * (plate.get("diameter_m", 0.03) / 2) ** 2)
    q_kw = sheet.get("q_kw")
    if q_kw is None:
        flow = sheet.get("gas_flow_l_min")
        gas = sheet.get("gas", "methane")
        lhv = sheet.get("lhv_mj_m3") or LHV_DEFAULT_MJ_M3.get(gas)
        if flow is None or lhv is None:
            raise SystemExit("sheet needs gas_flow_l_min and lhv_mj_m3 (or q_kw): the curves need the burner power")
        q_kw = bm.power_kw(float(flow), float(lhv), float(sheet.get("combustion_efficiency", 1.0)))
    flame = bm.Flame(q_kw=q_kw, height_m=_need(sheet, "flame_height_m"),
                     diameter_m=_need(sheet, "flame_diameter_m"),
                     plate_radius_m=plate.get("diameter_m", 0.03) / 2)
    runs = read_log(log_path)
    loss, u_h, fits, notes = fit_loss(runs, spec, p["h_rel_min"])
    results = [flux_of_run(r, spec, loss, u_h, p) for r in runs if r.kind != "cooldown"]
    rows = per_distance(results, p, spec.absorptivity)
    chi_sheet = float(sheet.get("chi", 0.10)); chi_range = tuple(sheet.get("chi_range", [0.03, 0.20]))
    q_rel = float(sheet.get("q_rel_uncertainty", 0.10))
    cmp_ = compare(rows, flame, p, chi_sheet, p["alpha_rel"], q_rel)
    out = common.out_dir(out)
    common.write_csv(out / "A_bunsen_runs.csv", [
        {"run_id": r.run_id, "distance_m": r.distance_m, "repeat": r.repeat, "ok": r.ok, "status": r.status,
         "q_kw_m2": r.q_kw_m2, "u_kw_m2": r.u_kw_m2, "q_raw_kw_m2": r.q_raw_kw_m2, "q_baseline_kw_m2": r.q_bg_kw_m2,
         "dT_k": r.dT_k, "plate_max_c": r.plate_max_c, "loss_share": r.loss_share,
         **{"u_" + k: v for k, v in r.parts.items()}} for r in results], simulated=simulated)
    cols = ["distance_m", "n_runs", "q_kw_m2", "u_random_kw_m2", "repeat_scatter_kw_m2", "snr", "plate_max_c", "loss_share"] + \
           ["curve_%s_chi1" % n for n in bm.CURVES]
    common.write_csv(out / "A_bunsen_table.csv", rows, cols, simulated=simulated)
    crows = []
    for n, c in cmp_["curves"].items():
        crows.append({"curve": n, **{k: v for k, v in c.items() if k != "name"}})
    common.write_csv(out / "A_bunsen_compare.csv", crows, simulated=simulated)
    png = make_figure(rows, results, runs, cmp_, flame, chi_sheet, chi_range, out / "A_bunsen_figure.png", simulated, spec)
    lines = ["Burner power Q = %.3f kW (sheet); flame L x D = %.3f x %.3f m; plate disc %.0f mm; loss model: h = %.2f W/m2/K "
             "(%s; u_h %.0f %%; fitted over %s C), eps %.2f." % (q_kw, flame.height_m, flame.diameter_m,
             2000 * flame.plate_radius_m, loss.h, loss.note, 100 * u_h,
             "%.0f-%.0f" % loss.t_range_c if all(math.isfinite(x) for x in loss.t_range_c) else "n/a", loss.eps), ""]
    lines += [n for n in notes]
    bad = [r for r in results if not r.ok]
    if bad:
        lines += ["", "Runs not used:"] + ["- %s (r=%.2f m): %s" % (r.run_id, r.distance_m, r.status) for r in bad]
    lines += ["", common.md_table(rows, ["distance_m", "n_runs", "q_kw_m2", "u_random_kw_m2", "snr", "plate_max_c", "loss_share"],
                                  ["r (m)", "runs", "q (kW/m2)", "u random", "q/u", "peak plate C", "loss share"], 4), ""]
    lines += [common.md_table(crows, ["curve", "chi_eff", "chi_eff_u_rel", "chi2", "dof", "p_value", "chi_in_prior"],
                              ["curve", "chi_eff", "rel u (incl. alpha, Q)", "shape chi2", "dof", "p", "chi in prior"], 3), ""]
    if "exponent" in cmp_:
        e = cmp_["exponent"]
        lines += ["Exponent n in q ~ r^-n: measured %.2f +- %.2f; curves: %s." % (
            e["measured"], e["u"], ", ".join("%s %.2f" % kv for kv in e["curves"].items())), ""]
    lines += ["Distances below the SNR floor (not in the shape test): %s." % (cmp_["distances_below_floor"] or "none"), "",
              "**Verdict (pre-registered rules): %s.**" % cmp_["verdict"]["text"]] + ["- " + s for s in cmp_["verdict"]["reasons"]]
    (out / "A_bunsen_snippet.md").write_text(common.md_snippet("Test A: flux plate vs Bunsen flame", simulated, lines))
    summ = {"simulated": simulated, "q_kw": q_kw, "loss": loss.to_dict(), "u_h_rel": u_h, "distances": rows,
            "compare": cmp_, "figure": str(png)}
    common.write_json(out / "A_bunsen_summary.json", summ)
    return summ


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("log"); ap.add_argument("--sheet", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--simulated", action="store_true", help="label every output SIMULATED (synthetic input)")
    for k, v in DEFAULTS.items():
        ap.add_argument("--" + k.replace("_", "-"), type=float, default=v)
    a = ap.parse_args(argv)
    import yaml
    sheet = yaml.safe_load(Path(a.sheet).read_text())
    s = run(a.log, sheet, Path(a.out), a.simulated, {k: getattr(a, k) for k in DEFAULTS})
    print(s["compare"]["verdict"]["text"]); print(s["figure"])


if __name__ == "__main__":
    main()
