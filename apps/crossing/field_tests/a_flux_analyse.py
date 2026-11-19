"""Test A analysis: flux plate vs Bunsen burner, measured flux beside three models.

Measurement: crossing.flux (thin-skin calorimeter). The loss model is fitted with crossing.flux.fit_cooldown on the
cool-down runs (plate heated, burner removed, q_inc = 0 assumed during the record). For each exposure run the
incident flux q(t) = (rho*cp*d*dT/dt + loss(T)) / absorptivity is computed with crossing.flux.FluxEstimator; the run
value is mean q over the exposure phase (after `settle_s`) minus the background flux (burner shielded; from a
least-squares slope of plate temperature, see background_flux), which removes a constant bias of the loss model.
Standard errors: batch means for the exposure mean, slope SE for the background. Units: kW/m2, m, s.

Models drawn beside the measurement (inputs from the sheet; all ASSUMED, none fitted to the measurement):
1. Point source: q = chi * Q / (4 pi r^2), r = burner axis to plate face, Q = flow x LHV x efficiency. Assumes an
   isotropic radiator at the flame centre, the plate facing it at flame mid-height, no absorption by the air.
2. Closed-form line-source law (crossing.heat.closed_form_line_flux -> research/kcf-heat law.line_flux_s) with the
   Bunsen flame mapped onto a finite front: depth D = flame width, half-width a = D/2, line intensity I = Q / D, so
   that I * 2a = Q; receiver at d = r - D/2 ahead of the leading edge, i.e. s = r. For r >> D this tends to the
   point source exactly (chi*I*a/(2 pi s^2) = chi*Q/(4 pi r^2)); near the flame it is lower.
3. FDS C064 reference (crossing.heat.fds_reference): radiometer curve of a 4473 kW/m grass-fire FDS run, scaled
   linearly by I/4473 with the same I = Q/D, at d = r - D/2. A wildland line fire is NOT a Bunsen flame; the curve
   is drawn because the comparison was asked for, and is labelled "FDS C064 reference, not a measurement".

Failures are reported as measured: a run with missing phase marks, thermocouple faults, < 80 % valid flux samples
or no air temperature is flagged and left out of the per-distance means (listed in the snippet).

Flux-disc limit (copper disc on printed PETG tabs; 70 C, crossing.yaml flux.disc_max_c, user-set): a run the record
script's disc guard stopped (trial.json stop_reason) is KEPT and reported as "STOPPED: disc 70 C" (or "STOPPED: disc
temperature unknown"), and this analysis also checks the recorded disc temperature itself: every run with any sample
>= the limit is flagged ("N samples >= 70 C") and left out of the means and of the pooled loss fit (the tabs may have
moved the disc), but listed with its numbers.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common  # noqa: E402
from field_tests.sessions import Run, find_runs, scalar_series  # noqa: E402
from crossing import flux, heat  # noqa: E402

LHV_DEFAULT_MJ_M3 = {"methane": 33.9, "propane": 86.4}     # 15 C, 101.325 kPa (50.0 MJ/kg x 0.678; 46.35 x 1.864)
MIN_VALID_FRAC = 0.8


# ---------------------------------------------------------------------------------------------- models
def heat_release_kw(sheet: dict) -> Dict[str, object]:
    """Q [kW] = flow [L/min] / 60000 [m3/s per L/min] * LHV [MJ/m3] * 1000 [kJ/MJ] * efficiency."""
    flow = sheet.get("gas_flow_l_min")
    lhv = sheet.get("lhv_mj_m3")
    gas = str(sheet.get("gas", "")).lower()
    note = ""
    if lhv is None:
        lhv = LHV_DEFAULT_MJ_M3.get(gas)
        note = "LHV default for %s (%.1f MJ/m3 at 15 C, 1 atm)" % (gas, lhv) if lhv else ""
    eff = float(sheet.get("combustion_efficiency", 1.0) or 1.0)
    if flow is None or lhv is None or not (float(flow) > 0 and float(lhv) > 0):
        return {"q_kw": float("nan"), "note": "gas flow or LHV missing on the sheet: models not drawn"}
    q = float(flow) / 60000.0 * float(lhv) * 1000.0 * eff
    return {"q_kw": q, "note": note or "LHV from sheet", "flow_l_min": float(flow), "lhv_mj_m3": float(lhv),
            "efficiency": eff}


def point_source(r_m, chi: float, q_kw: float):
    r = np.asarray(r_m, dtype=float)
    return chi * q_kw / (4.0 * math.pi * r ** 2)


def closed_form_bunsen(r_m: float, q_kw: float, chi: float, flame_d_m: float) -> float:
    d = max(float(r_m) - flame_d_m / 2.0, 0.0)
    return heat.closed_form_line_flux(d, flame_d_m, q_kw / flame_d_m, chi, half_width_m=flame_d_m / 2.0)


def fds_bunsen(r_m: float, q_kw: float, flame_d_m: float) -> heat.FdsReference:
    d = max(float(r_m) - flame_d_m / 2.0, 0.0)
    return heat.fds_reference(d, q_kw / flame_d_m)


# ---------------------------------------------------------------------------------------------- per run
def plate_spec(sheet: dict) -> flux.PlateSpec:
    p = dict(sheet.get("plate") or {})
    base = flux.PlateSpec()
    return flux.PlateSpec(thickness_m=float(p.get("thickness_m", base.thickness_m)), rho=float(p.get("rho", base.rho)),
                          cp=float(p.get("cp", base.cp)), absorptivity=float(p.get("absorptivity", base.absorptivity)),
                          emissivity=float(p.get("emissivity", base.emissivity)))


def plate_air(run: Run):
    """(t, plate_c with faults as NaN, faults list, air_t, air_c)."""
    pr = run.readings("tc_plate")
    ar = run.readings("tc_air")
    t, plate = scalar_series(pr, "temp_c")
    faults = [m["data"].get("fault") for m in pr]
    plate = np.where(np.array([f is None for f in faults], dtype=bool), plate, np.nan)
    at, air = scalar_series(ar, "temp_c")
    air = np.where(np.array([m["data"].get("fault") is None for m in ar], dtype=bool), air, np.nan)
    return t, plate, faults, at, air


def air_at(at: np.ndarray, air: np.ndarray, t: float) -> Optional[float]:
    """Last finite air reading at or before t (no look-ahead), None if none within 2 s."""
    i = int(np.searchsorted(at, t, side="right")) - 1
    while i >= 0 and not np.isfinite(air[i]):
        i -= 1
    if i < 0 or t - at[i] > 2.0:
        return None
    return float(air[i])


def flux_series(run: Run, loss: flux.LossModel, spec: flux.PlateSpec) -> Dict[str, np.ndarray]:
    t, plate, faults, at, air = plate_air(run)
    est = flux.FluxEstimator(spec, loss)
    ts, qs, ok, temps = [], [], [], []
    for ti, pi, fi in zip(t, plate, faults):
        s = est.update(ti, None if not np.isfinite(pi) else float(pi), air_at(at, air, ti), fault=fi)
        ts.append(s.t); qs.append(s.q_kw_m2); ok.append(s.valid); temps.append(pi)
    return {"t": np.asarray(ts, float), "q": np.asarray(qs, float), "valid": np.asarray(ok, bool),
            "t_raw": t, "plate_c": plate, "n_faults": int(sum(1 for f in faults if f))}


def disc_check(run: Run, plate_c: np.ndarray, limit_c: float) -> Dict[str, object]:
    """Stop reason recorded by the disc guard and the recorded disc samples at or above the limit (flags)."""
    lim = float(run.trial.get("disc_max_c") or limit_c)
    n_over = int(np.sum(plate_c[np.isfinite(plate_c)] >= lim))
    flags = []
    lab = common.stop_label(run.trial)
    if lab:
        flags.append(lab + (" (%s)" % run.trial["stop_detail"] if run.trial.get("stop_detail") else ""))
    if n_over:
        flags.append("%d disc sample(s) >= %.0f C (disc limit, PETG tabs)" % (n_over, lim))
    return {"stop_reason": run.trial.get("stop_reason"), "stopped": lab, "disc_max_c": lim,
            "n_disc_over_limit": n_over, "disc_flags": flags}


def fit_cooldown_run(run: Run, spec: flux.PlateSpec, limit_c: float = common.DISC_MAX_C_DEFAULT) -> Dict[str, object]:
    t, plate, faults, at, air = plate_air(run)
    t0 = run.mark_t("cooldown")
    t1 = run.mark_t("end")
    dc = disc_check(run, plate, limit_c)
    row = {"run_id": run.run_id, "kind": run.trial.get("kind"), "ok": False, "reason": "",
           "stop_reason": dc["stop_reason"], "n_disc_over_limit": dc["n_disc_over_limit"],
           "flag": "; ".join(dc["disc_flags"])}
    if t0 is None:
        row["reason"] = "no cooldown mark"
        return row
    sel = (t >= t0 + 5.0) & ((t <= t1) if t1 is not None else True) & np.isfinite(plate)
    if sel.sum() < 50:
        row["reason"] = "too few cool-down samples (%d)" % int(sel.sum())
        return row
    air_i = np.interp(t[sel], at[np.isfinite(air)], air[np.isfinite(air)]) if np.isfinite(air).sum() else None
    if air_i is None:
        row["reason"] = "no air temperature"
        return row
    try:
        lm = flux.fit_cooldown(t[sel], plate[sel], air_i, spec)
    except ValueError as exc:
        row["reason"] = str(exc)
        return row
    row.update({"ok": True, "h_w_m2k": lm.h, "eps": lm.eps, "rms_residual_w_m2": lm.rms_residual_w_m2, "n": lm.n,
                "t_min_c": lm.t_range_c[0], "t_max_c": lm.t_range_c[1], "_model": lm,
                "_t": t[sel], "_plate": plate[sel], "_air": air_i})
    return row


def pooled_loss(fits: List[dict], spec: flux.PlateSpec) -> flux.LossModel:
    clean_fits = [f for f in fits if not f.get("flag")]          # disc-limit flags: left out of the pooled fit
    good = [f for f in clean_fits if f.get("ok") and f.get("kind") == "cooldown"] or \
        [f for f in clean_fits if f.get("ok")]
    if not good:
        return flux.LossModel(h=10.0, eps=spec.emissivity, note="UNFITTED default h = 10 W/m2K (no usable cool-down)")
    h = float(np.median([f["h_w_m2k"] for f in good]))
    return flux.LossModel(h=h, eps=spec.emissivity, rms_residual_w_m2=float(np.median([f["rms_residual_w_m2"]
                                                                                        for f in good])),
                          n=int(sum(f["n"] for f in good)),
                          t_range_c=(min(f["t_min_c"] for f in good), max(f["t_max_c"] for f in good)),
                          note="median of %d cool-down fit(s), eps fixed at %.2f" % (len(good), spec.emissivity))


def background_flux(run: Run, loss: flux.LossModel, spec: flux.PlateSpec, t0: float, t1: float):
    """Background (burner shielded) flux from a least-squares line through the plate temperature over the window:
    q_bg = (rho*cp*d * slope + mean loss(T, Ta)) / absorptivity [kW/m2], with its standard error from the slope.
    Averaging FluxEstimator samples instead would be dominated by the noise of the two end temperatures (the mean of
    a derivative telescopes to (T_end - T_start) / duration), which is large for a 60 s window."""
    t, plate, faults, at, air = plate_air(run)
    sel = (t >= t0) & (t <= t1) & np.isfinite(plate)
    if sel.sum() < 20 or not np.isfinite(air).any():
        return float("nan"), float("nan")
    tt = t[sel] - t[sel].mean()
    T = plate[sel] + flux.C_TO_K
    A = np.column_stack([tt, np.ones_like(tt)])
    coef, *_ = np.linalg.lstsq(A, T, rcond=None)
    resid = T - A @ coef
    se_slope = math.sqrt(float(np.sum(resid ** 2)) / max(T.size - 2, 1) / float(np.sum(tt ** 2)))
    ta = np.interp(t[sel], at[np.isfinite(air)], air[np.isfinite(air)]) + flux.C_TO_K
    m = spec.heat_capacity_j_m2_k
    q = (m * coef[0] + float(np.mean(loss.loss_w_m2(T, ta)))) / spec.absorptivity / 1000.0
    return float(q), float(m * se_slope / spec.absorptivity / 1000.0)


def batch_se(x: np.ndarray, k: int = 5) -> float:
    """Standard error of the mean of a serially correlated series by batch means (k contiguous blocks)."""
    x = np.asarray(x, dtype=float)
    if x.size < 2 * k:
        return float("nan")
    means = [b.mean() for b in np.array_split(x, k)]
    return float(np.std(means, ddof=1) / math.sqrt(k))


def analyse_exposure(run: Run, loss: flux.LossModel, spec: flux.PlateSpec, settle_s: float = 10.0,
                     limit_c: float = common.DISC_MAX_C_DEFAULT) -> dict:
    row = {"run_id": run.run_id, "distance_m": run.trial.get("distance_m"), "repeat": run.trial.get("repeat"),
           "flag": ""}
    _, plate_raw, _, _, _ = plate_air(run)
    dc = disc_check(run, plate_raw, limit_c)
    row.update(stop_reason=dc["stop_reason"], n_disc_over_limit=dc["n_disc_over_limit"],
               plate_max_c=float(np.nanmax(plate_raw)) if np.isfinite(plate_raw).any() else float("nan"))
    tb, te, tc, tend = (run.mark_t("background"), run.mark_t("exposure"), run.mark_t("cooldown"), run.mark_t("end"))
    if None in (tb, te, tc):
        row["flag"] = "; ".join(dc["disc_flags"] + ["missing phase marks (background/exposure/cooldown)"])
        return row
    fs = flux_series(run, loss, spec)
    t, q, v = fs["t"], fs["q"], fs["valid"]
    ex = (t >= te + settle_s) & (t <= tc - 1.0)
    n_ex = int(ex.sum())
    vx = v & ex
    q_bg, se_bg = background_flux(run, loss, spec, tb + 5.0, te - 1.0)
    row.update({"n_exposure_samples": n_ex, "valid_frac": float(vx.sum() / n_ex) if n_ex else 0.0,
                "q_background_kw_m2": q_bg, "q_background_se_kw_m2": se_bg,
                "q_exposure_kw_m2": float(np.mean(q[vx])) if vx.any() else float("nan"),
                "q_exposure_std_kw_m2": float(np.std(q[vx], ddof=1)) if vx.sum() > 1 else float("nan"),
                "n_faults": fs["n_faults"],
                "plate_max_c": float(np.nanmax(fs["plate_c"])) if np.isfinite(fs["plate_c"]).any() else float("nan")})
    row["q_net_kw_m2"] = row["q_exposure_kw_m2"] - (row["q_background_kw_m2"]
                                                     if math.isfinite(row["q_background_kw_m2"]) else 0.0)
    # q samples are serially correlated (1 s derivative window): standard error by batch means.
    se_ex = batch_se(q[vx])
    row["q_net_se_kw_m2"] = math.sqrt(se_ex ** 2 + (se_bg if math.isfinite(se_bg) else 0.0) ** 2) \
        if math.isfinite(se_ex) else float("nan")
    flags = list(dc["disc_flags"])
    if n_ex == 0:
        flags.append("no samples in exposure phase")
    elif row["valid_frac"] < MIN_VALID_FRAC:
        flags.append("only %.0f %% valid flux samples" % (100 * row["valid_frac"]))
    if fs["n_faults"]:
        flags.append("%d thermocouple fault readings" % fs["n_faults"])
    if not math.isfinite(q_bg):
        flags.append("no usable background phase")
    row["flag"] = "; ".join(flags)
    row["_series"] = fs
    row["_marks"] = (tb, te, tc, tend)
    return row


# ---------------------------------------------------------------------------------------------- main analysis
def plan_coverage(exp_rows: List[dict], sheet: dict) -> List[str]:
    """Gaps against the sheet plan (distances_m x repeats exposure runs), one line each; [] when complete or when
    the sheet has no plan (then one line says so)."""
    dists = sheet.get("distances_m")
    reps = sheet.get("repeats")
    if not dists or not reps:
        return ["plan: the sheet has no distances_m / repeats, coverage not checked"]
    have: Dict[float, int] = {}
    for r in exp_rows:
        if r.get("distance_m") is not None:
            k = round(float(r["distance_m"]), 4)
            have[k] = have.get(k, 0) + 1
    out = []
    for d in dists:
        got = have.get(round(float(d), 4), 0)
        if got < int(reps):
            out.append("plan: %.3f m: %d of %d exposure runs" % (float(d), got, int(reps)))
    extra = sorted(set(have) - {round(float(d), 4) for d in dists})
    if extra:
        out.append("plan: exposure runs at distances not in the sheet: %s m" % ", ".join("%.3f" % x for x in extra))
    return out


def analyse(runs_root, out, sheet: Optional[dict] = None, settle_s: float = 10.0) -> dict:
    runs = find_runs(runs_root, "A")
    if not runs:
        raise SystemExit("no test A runs (trial.json with test 'A') under %s" % runs_root)
    if sheet is None:
        sheet = runs[0].trial.get("sheet") or {}
    out = common.out_dir(out)
    sim = common.is_simulated(*[r.simulated for r in runs])
    spec = plate_spec(sheet)
    limit_c = common.disc_max_c()
    fits = [fit_cooldown_run(r, spec, limit_c) for r in runs]
    loss = pooled_loss(fits, spec)
    loss.save(out / "plate_loss.json")
    exp_rows = [analyse_exposure(r, loss, spec, settle_s, limit_c) for r in runs if r.trial.get("kind") == "exposure"]
    gate_rows = [{"run_id": r.run_id, "supervisor": r.trial.get("supervisor"),
                  "risk_assessment_sha256": r.trial.get("risk_assessment_sha256")} for r in runs]

    qinfo = heat_release_kw(sheet)
    q_kw = float(qinfo["q_kw"])
    chi = float(sheet.get("chi", 0.1))
    chi_lo, chi_hi = (sheet.get("chi_range") or [chi, chi])[:2]
    dflame = float(sheet.get("flame_diameter_m", 0.02))

    by_d: Dict[float, List[dict]] = {}
    for r in exp_rows:
        if r.get("distance_m") is not None:
            by_d.setdefault(round(float(r["distance_m"]), 4), []).append(r)
    dist_rows = []
    for d in sorted(by_d):
        rs = by_d[d]
        good = [r for r in rs if not r["flag"] and math.isfinite(r.get("q_net_kw_m2", float("nan")))]
        vals = [r["q_net_kw_m2"] for r in good]
        row = {"distance_m": d, "n_runs": len(rs), "n_used": len(good),
               "q_meas_mean_kw_m2": float(np.mean(vals)) if vals else float("nan"),
               "q_meas_std_kw_m2": float(np.std(vals, ddof=1)) if len(vals) > 1 else float("nan"),
               "q_meas_runs": [round(v, 4) for v in vals]}
        if math.isfinite(q_kw):
            row["q_point_kw_m2"] = float(point_source(d, chi, q_kw))
            row["q_point_lo_kw_m2"] = float(point_source(d, float(chi_lo), q_kw))
            row["q_point_hi_kw_m2"] = float(point_source(d, float(chi_hi), q_kw))
            row["q_closed_form_kw_m2"] = closed_form_bunsen(d, q_kw, chi, dflame)
            ref = fds_bunsen(d, q_kw, dflame)
            row["q_fds_ref_kw_m2"] = ref.q_kw_m2
            row["ratio_meas_to_point"] = row["q_meas_mean_kw_m2"] / row["q_point_kw_m2"]
            row["ratio_meas_to_closed_form"] = row["q_meas_mean_kw_m2"] / row["q_closed_form_kw_m2"]
            # radiant fraction implied by the measurement under the point-source model (diagnostic only)
            row["chi_implied_point"] = row["q_meas_mean_kw_m2"] * 4 * math.pi * d ** 2 / q_kw
        dist_rows.append(row)

    run_cols = ["run_id", "distance_m", "repeat", "q_background_kw_m2", "q_background_se_kw_m2", "q_exposure_kw_m2", "q_exposure_std_kw_m2",
                "q_net_kw_m2", "q_net_se_kw_m2", "valid_frac", "n_exposure_samples", "n_faults", "plate_max_c",
                "n_disc_over_limit", "stop_reason", "flag"]
    common.write_csv(out / "A_runs.csv", exp_rows, run_cols, sim)
    fit_cols = ["run_id", "kind", "ok", "h_w_m2k", "eps", "rms_residual_w_m2", "n", "t_min_c", "t_max_c", "reason",
                "n_disc_over_limit", "stop_reason", "flag"]
    common.write_csv(out / "A_cooldown_fits.csv", fits, fit_cols, sim)
    dist_cols = ["distance_m", "n_runs", "n_used", "q_meas_mean_kw_m2", "q_meas_std_kw_m2", "q_point_kw_m2",
                 "q_point_lo_kw_m2", "q_point_hi_kw_m2", "q_closed_form_kw_m2", "q_fds_ref_kw_m2",
                 "ratio_meas_to_point", "ratio_meas_to_closed_form", "chi_implied_point", "q_meas_runs"]
    common.write_csv(out / "A_by_distance.csv", dist_rows, dist_cols, sim)
    common.write_csv(out / "A_gate.csv", gate_rows, ["run_id", "supervisor", "risk_assessment_sha256"], sim)

    _plot_vs_distance(out / "A_flux_vs_distance.png", exp_rows, dist_rows, q_kw, chi, chi_lo, chi_hi, dflame, sim)
    _plot_series(out / "A_flux_timeseries.png", exp_rows, sim)
    _plot_cooldown(out / "A_cooldown_fit.png", fits, loss, spec, sim)

    flagged = [r for r in exp_rows if r["flag"]]
    body = ["Heat source: Bunsen burner only. Gas: %s, Q = %s kW (%s). chi assumed %.2f (band %.2f-%.2f), flame "
            "width %.3f m." % (sheet.get("gas"), common.fmt(q_kw, 3), qinfo["note"], chi, float(chi_lo),
                               float(chi_hi), dflame),
            "Plate loss model: h = %.2f W/m2K, eps = %.2f (%s; fit rms %s W/m2)."
            % (loss.h, loss.eps, loss.note, common.fmt(loss.rms_residual_w_m2, 1)),
            "Runs: %d exposure, %d cool-down; %d exposure run(s) flagged and left out of the means."
            % (len(exp_rows), sum(1 for r in runs if r.trial.get("kind") == "cooldown"), len(flagged)),
            "Supervisors recorded: %s." % ", ".join(sorted({str(g["supervisor"]) for g in gate_rows})), "",
            common.md_table(dist_rows, ["distance_m", "n_used", "q_meas_mean_kw_m2", "q_meas_std_kw_m2",
                                        "q_point_kw_m2", "q_closed_form_kw_m2", "q_fds_ref_kw_m2",
                                        "ratio_meas_to_point", "chi_implied_point"],
                            ["r (m)", "n", "measured (kW/m2)", "sd", "point source", "closed form",
                             "FDS C064 ref*", "meas/point", "implied chi"]),
            "",
            "*FDS C064 reference, not a measurement: a 4473 kW/m grass-fire radiometer curve scaled by I/4473 with "
            "I = Q / flame width. A Bunsen flame is not a line fire; this column is a scale check only.",
            "The closed form maps the flame onto a front of depth = half-width x 2 = flame width; it tends to the "
            "point source for r >> flame width."]
    if flagged:
        body += ["", "Flagged runs (as measured):"] + ["- %s: %s" % (r["run_id"], r["flag"]) for r in flagged]
    stopped = common.stopped_lines(runs)
    over = [r for r in list(exp_rows) + list(fits) if r.get("n_disc_over_limit")]
    body += ["", "Flux-disc limit %.0f C (copper disc on PETG tabs; user-set): %d run(s) stopped by the record script's "
             "disc guard, %d run(s) with recorded disc samples >= the limit (left out of the means and the loss fit, "
             "listed here as measured)." % (limit_c, len(stopped), len(over))]
    body += stopped
    body += ["- %s: %d disc sample(s) >= %.0f C" % (r["run_id"], r["n_disc_over_limit"], limit_c) for r in over]
    flagged_fits = [f for f in fits if f.get("flag")]
    if flagged_fits:
        body += ["Cool-down fits flagged (not pooled): " + ", ".join("%s (%s)" % (f["run_id"], f["flag"])
                                                                      for f in flagged_fits)]
    coverage = plan_coverage(exp_rows, sheet)
    body += ["", "Plan coverage (sheet: %s m x %s repeats): %s." % (
        ", ".join("%g" % float(x) for x in (sheet.get("distances_m") or [])) or "?", sheet.get("repeats", "?"),
        "complete" if not coverage else "INCOMPLETE, protocol not completed")]
    if coverage:
        body += ["PROBLEM: " + c for c in coverage]
    body += ["", "Files: A_by_distance.csv, A_runs.csv, A_cooldown_fits.csv, plate_loss.json, "
             "A_flux_vs_distance.png, A_flux_timeseries.png, A_cooldown_fit.png."]
    md = common.md_snippet("Test A - flux plate vs Bunsen burner", sim, body)
    (out / "A_results.md").write_text(md)
    return {"simulated": sim, "loss": loss, "fits": fits, "runs": exp_rows, "by_distance": dist_rows,
            "q_kw": q_kw, "markdown": md, "plan_problems": coverage}


def _plot_vs_distance(path, exp_rows, dist_rows, q_kw, chi, chi_lo, chi_hi, dflame, sim):
    plt = common.pyplot()
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    ds = [r["distance_m"] for r in dist_rows]
    if ds:
        r = np.geomspace(min(ds) * 0.8, max(ds) * 1.25, 80)
        if math.isfinite(q_kw):
            ax.fill_between(r, point_source(r, float(chi_lo), q_kw), point_source(r, float(chi_hi), q_kw),
                            color="tab:blue", alpha=0.12, label="point source, chi %.2f-%.2f" % (chi_lo, chi_hi))
            ax.plot(r, point_source(r, chi, q_kw), color="tab:blue", lw=2.5,
                    label="point source chi*Q/(4 pi r^2), chi %.2f" % chi)
            ax.plot(r, [closed_form_bunsen(x, q_kw, chi, dflame) for x in r], color="tab:green", ls="-.", lw=1.3,
                    label="closed form (kcf-heat line law, finite front; = point source for r >> width)")
            ax.plot(r, [fds_bunsen(x, q_kw, dflame).q_kw_m2 for x in r], color="tab:gray", ls="--",
                    label="FDS C064 reference x I/4473 (not a measurement)")
    for row in exp_rows:
        if row.get("distance_m") and math.isfinite(row.get("q_net_kw_m2", float("nan"))):
            ax.plot(row["distance_m"], max(row["q_net_kw_m2"], 1e-4), "o", ms=3,
                    color="tab:red" if row["flag"] else "k", alpha=0.45)
    good = [x for x in dist_rows if math.isfinite(x["q_meas_mean_kw_m2"])]
    if good:
        ax.errorbar([x["distance_m"] for x in good], [max(x["q_meas_mean_kw_m2"], 1e-4) for x in good],
                    yerr=[0 if not math.isfinite(x["q_meas_std_kw_m2"]) else x["q_meas_std_kw_m2"] for x in good],
                    fmt="s", color="k", ms=6, capsize=3, label="measured, mean +- sd of repeats")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlabel("distance burner axis -> plate face r (m)")
    ax.set_ylabel("incident flux (kW/m2)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend(fontsize=7, loc="lower left")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test A: flux plate vs Bunsen burner", sim)


def _plot_series(path, exp_rows, sim):
    plt = common.pyplot()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
    ds = sorted({r["distance_m"] for r in exp_rows if r.get("distance_m")})
    cmap = plt.get_cmap("viridis")
    for r in exp_rows:
        if "_series" not in r:
            continue
        fs = r["_series"]
        te = r["_marks"][1]
        c = cmap(ds.index(r["distance_m"]) / max(len(ds) - 1, 1)) if r["distance_m"] in ds else "k"
        q = np.where(fs["valid"], fs["q"], np.nan)
        a1.plot(fs["t"] - te, q, lw=0.6, color=c, alpha=0.7)
        a2.plot(fs["t_raw"] - te, fs["plate_c"], lw=0.8, color=c, alpha=0.8)
    for d in ds:
        a2.plot([], [], color=cmap(ds.index(d) / max(len(ds) - 1, 1)), label="r = %.3f m" % d)
    a1.axvline(0, color="k", lw=0.8); a2.axvline(0, color="k", lw=0.8)
    a1.set_ylabel("q incident (kW/m2)"); a2.set_ylabel("plate (C)"); a2.set_xlabel("time from exposure mark (s)")
    a1.grid(alpha=0.3); a2.grid(alpha=0.3); a2.legend(fontsize=7)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test A: flux time series (all exposure runs)", sim)


def _plot_cooldown(path, fits, loss, spec, sim):
    plt = common.pyplot()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    m = spec.heat_capacity_j_m2_k
    for f in fits:
        if not f.get("ok"):
            continue
        dTdt = flux.derivative(f["_t"], f["_plate"] + flux.C_TO_K, window_s=5.0)
        ok = np.isfinite(dTdt)
        ax.plot(f["_plate"][ok], -m * dTdt[ok], ".", ms=1.5, alpha=0.4, label="%s (h %.1f)" % (f["run_id"][:28],
                                                                                              f["h_w_m2k"]))
    good = [f for f in fits if f.get("ok")]
    if good:
        ta = float(np.median(np.concatenate([np.atleast_1d(f["_air"]) for f in good])))
        tt = np.linspace(ta + 1, max(f["t_max_c"] for f in good), 100)
        ax.plot(tt, loss.loss_w_m2(tt + flux.C_TO_K, ta + flux.C_TO_K), "k-", lw=1.5,
                label="pooled loss(T), h %.2f W/m2K" % loss.h)
    ax.set_xlabel("plate temperature (C)"); ax.set_ylabel("-rho cp d dT/dt (W/m2)")
    ax.grid(alpha=0.3); ax.legend(fontsize=7)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test A: plate cool-down loss fit", sim)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test A analysis")
    p.add_argument("--runs", default=str(common.RECORDS / "A"), help="folder holding the A run directories")
    p.add_argument("--sheet", help="A_inputs.yaml (default: the copy stored in the first run)")
    p.add_argument("--settle-s", type=float, default=10.0)
    p.add_argument("--out", default=str(common.RECORDS / "A" / "analysis"))
    a = p.parse_args(argv)
    sheet = None
    if a.sheet:
        import yaml
        sheet = yaml.safe_load(Path(a.sheet).read_text())
    res = analyse(a.runs, a.out, sheet, a.settle_s)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
