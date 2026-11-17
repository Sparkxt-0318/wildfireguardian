"""Test B analysis: radar echo of a corner reflector with nothing / flame / smoke / mist on the line of sight.

Method (crossing.radar_flame, not re-implemented):
- Per distance, a RadarBaseline is captured from the `baseline` run (role baseline; else the first `nothing` run).
- The reflector bin is the strongest baseline bin of the boresight beam within +-0.3 m of the stated distance.
- Every run's analysis window (condition_on -> condition_off marks, or the whole baseline run) is cut into
  non-overlapping windows of `window_s` (default 3 s, the detector's window). For each window a fresh
  RadarFlameDetector evaluates the frames (near edge = flame distance, bearing 0) and the per-bin values at the
  reflector bin are taken: loss_db (baseline mean - window max, dB), flicker_amp_db (frame-to-frame linear
  amplitude flicker in dB-equivalent), flicker_phase_rad (circular std of frame-to-frame phase differences) and
  their z-scores; the detector status (FLAME_EFFECT / NO_EFFECT / UNKNOWN) is counted.
- Noise statistics come from the `nothing` trial windows (the baseline run is excluded because it was used to build
  the baseline; if no other `nothing` run exists, the baseline run's own windows are used and flagged as optimistic).
- Effect of a condition = mean over its windows - mean over the nothing windows, per metric. Each metric has one
  of three outcomes: `below` (effect and sigma finite, sigma > 0, |effect| < 3 sigma), `above` (finite, sigma > 0,
  |effect| >= 3 sigma) or `not computable` (anything else, with the reason: noise sigma NaN, e.g. fewer than 2
  finite nothing windows; effect NaN, no finite values in the condition windows; or noise sigma = 0). If all three
  metrics are below the script prints "<condition> effect below noise" (for the flame condition the exact text is
  "flame effect below noise"); if at least one is above it prints "<condition> effect above 3 sigma of the nothing
  runs (<metrics>)"; otherwise "<condition> effect vs noise NOT COMPUTABLE (<reasons>)". A not-computable metric is
  never read as an effect: `effect_below_noise` is then None and the case is listed under Problems.
- Safety gate per run (B_gate.csv, like A_gate.csv): flame and smoke runs must carry the signed risk assessment's
  SHA-256 and the supervisor; a run without them is listed as GATE MISSING (never dropped). Flame runs whose
  trial.json does not say `bunsen_burner: true` are flagged: the analysis assumes a Bunsen-size flame.
- Plan coverage: the runs are compared with the protocol plan (2, 3, 4, 5 m; per distance >= 3 nothing, 3 flame,
  2 smoke, 2 mist trial runs) and every gap is a Problem.

Assumptions: static scene and static radar during a distance block (any movement changes echo phases); the
reflector dominates its range bin; windows are treated as independent (they do not overlap, but slow drifts make
neighbouring windows correlated, which makes sigma optimistic). No fusion with the thermal camera happens here:
this test looks at the radar alone. A FLAME_EFFECT window under smoke would be a failure of the smoke assumption
and is reported as measured.
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
from field_tests.sessions import Run, find_runs  # noqa: E402
from crossing import radar_flame as rf  # noqa: E402

METRICS = ("loss_db", "flicker_amp_db", "flicker_phase_rad")
CONDITIONS = ("nothing", "flame", "smoke", "mist")
K_SIGMA = 3.0
GATED = ("flame", "smoke")                     # conditions that need the signed risk assessment + supervisor
PLAN_DISTANCES_M = (2.0, 3.0, 4.0, 5.0)        # protocols/B_radar.md
PLAN_MIN_TRIALS = {"nothing": 3, "flame": 3, "smoke": 2, "mist": 2}


def compare_to_noise(eff: float, sig: float, n_noise: int, n_cond: int, metric: str, cond: str):
    """('below' | 'above' | 'not computable', reason). Never reads a NaN or a zero sigma as an effect."""
    if not math.isfinite(sig):
        return "not computable", "noise sigma NaN (n_nothing=%d finite windows)" % n_noise
    if not math.isfinite(eff):
        return "not computable", "effect NaN (no finite %s in %s windows, n=%d)" % (metric, cond, n_cond)
    if sig <= 0:
        return "not computable", "noise sigma = 0"
    return ("below" if abs(eff) < K_SIGMA * sig else "above"), ""


def plan_coverage(runs) -> List[str]:
    """Gaps against the protocol plan, one line each."""
    have: Dict[float, Dict[str, int]] = {}
    base: Dict[float, int] = {}
    for r in runs:
        d = round(float(r.trial.get("distance_m", float("nan"))), 2)
        if r.trial.get("role") == "baseline":
            base[d] = base.get(d, 0) + 1
            continue
        c = r.trial.get("condition")
        have.setdefault(d, {})[c] = have.setdefault(d, {}).get(c, 0) + 1
    out = []
    for d in PLAN_DISTANCES_M:
        if d not in have and d not in base:
            out.append("plan: %.0f m not recorded at all" % d)
            continue
        if not base.get(d):
            out.append("plan: %.0f m has no baseline run" % d)
        for c, n in PLAN_MIN_TRIALS.items():
            got = have.get(d, {}).get(c, 0)
            if got < n:
                out.append("plan: %.0f m %s: %d of >= %d trial runs" % (d, c, got, n))
    return out


def frames_of(run: Run, t0: Optional[float] = None, t1: Optional[float] = None) -> List[rf.RadarFrame]:
    out = []
    for m in run.readings("radar"):
        t = float(m["t_mono"])
        if (t0 is not None and t < t0) or (t1 is not None and t > t1):
            continue
        d = m["data"]
        if d.get("range_res_m") is None:
            continue
        try:
            out.append(rf.frame_from_reading(d, t, sim=bool(m.get("sim"))))
        except Exception:  # noqa: BLE001 - a frame that does not decode is skipped and counted by the caller
            continue
    return out


def analysis_window(run: Run):
    if run.trial.get("role") == "baseline":
        return run.mark_t("baseline"), run.mark_t("end")
    return run.mark_t("condition_on"), run.mark_t("condition_off")


def reflector_bin(baseline: rf.RadarBaseline, distance_m: float, tol_m: float = 0.3):
    stats = baseline.stats_for("heatmap", 0.0, 2.5) or baseline.profile
    r = np.arange(baseline.n_bins) * baseline.range_res_m
    sel = np.flatnonzero(np.abs(r - distance_m) <= tol_m)
    if sel.size == 0:
        return None, float("nan"), float("nan")
    b = int(sel[np.argmax(stats.mean_db[sel])])
    return b, float(r[b]), float(stats.mean_db[b] - stats.noise_db)


def window_values(frames: List[rf.RadarFrame], baseline, bin_idx: int, near_edge_m: float, window_s: float,
                  min_frames: int = 10) -> List[dict]:
    if not frames:
        return []
    t = np.array([f.t for f in frames])
    out = []
    start = t[0]
    while start + window_s <= t[-1] + 1e-6:
        sel = [f for f in frames if start <= f.t < start + window_s]
        start += window_s
        if len(sel) < min_frames:
            out.append({"status": "UNKNOWN", "reason": "only %d frames in window" % len(sel)})
            continue
        det = rf.RadarFlameDetector(baseline, cfg=rf.RadarFlameConfig(window_s=window_s + 0.5))
        for f in sel:
            det.push(f)
        st = det.evaluate(now=sel[-1].t, near_edge_m=near_edge_m, bearing_deg=0.0)
        row = {"status": st.status, "reason": st.reason, "t_start": sel[0].t}
        pb = st.per_bin or {}
        for k in METRICS + ("loss_z", "flicker_amp_z", "flicker_phase_z"):
            arr = pb.get(k)
            row[k] = float(arr[bin_idx]) if arr is not None and arr[bin_idx] is not None else float("nan")
        out.append(row)
    return out


def analyse(runs_root, out, window_s: float = 3.0, echo=print) -> dict:
    runs = find_runs(runs_root, "B")
    if not runs:
        raise SystemExit("no test B runs under %s" % runs_root)
    out = common.out_dir(out)
    sim = common.is_simulated(*[r.simulated for r in runs])
    by_d: Dict[float, List[Run]] = {}
    for r in runs:
        by_d.setdefault(round(float(r.trial["distance_m"]), 2), []).append(r)
    window_rows, cond_rows, lines, problems = [], [], [], []
    gate_rows = []
    for r in runs:
        cond = r.trial.get("condition")
        sha, sup = r.trial.get("risk_assessment_sha256"), r.trial.get("supervisor")
        g = {"run_id": r.run_id, "distance_m": r.trial.get("distance_m"), "condition": cond,
             "risk_assessment_sha256": sha, "supervisor": sup, "flame_source": r.trial.get("flame_source") or "",
             "bunsen_burner": r.trial.get("bunsen_burner"), "gate": ""}
        if cond in GATED and not (sha and sup and str(sup).strip()):
            g["gate"] = "GATE MISSING"
            problems.append("%s: %s run without a recorded risk assessment and supervisor (GATE MISSING)"
                            % (r.run_id, cond))
        elif cond in GATED:
            g["gate"] = "ok"
        if cond == "flame" and r.trial.get("bunsen_burner") is not True:
            g["gate"] = (g["gate"] + "; " if g["gate"] else "") + "NOT BUNSEN"
            problems.append("%s: flame source not recorded as a Bunsen burner (%r, flame_kind %r); the analysis "
                            "assumes a Bunsen-size flame" % (r.run_id, r.trial.get("flame_source") or "",
                                                             r.trial.get("flame_kind")))
        gate_rows.append(g)
    coverage = plan_coverage(runs)
    problems += coverage
    for d in sorted(by_d):
        rs = by_d[d]
        base_run = next((r for r in rs if r.trial.get("role") == "baseline"), None) or \
            next((r for r in rs if r.trial.get("condition") == "nothing"), None)
        if base_run is None:
            problems.append("%.1f m: no baseline and no nothing run: distance not analysed" % d)
            continue
        t0, t1 = analysis_window(base_run)
        try:
            baseline = rf.RadarBaseline.capture(frames_of(base_run, t0, t1), meta={"run": base_run.run_id})
        except ValueError as exc:
            problems.append("%.1f m: baseline capture failed (%s)" % (d, exc))
            continue
        b, r_b, snr = reflector_bin(baseline, d)
        if b is None:
            problems.append("%.1f m: no range bin within 0.3 m of the reflector distance" % d)
            continue
        if snr < 12.0:
            problems.append("%.1f m: reflector only %.1f dB above noise in the baseline (< 12 dB)" % (d, snr))
        per_cond: Dict[str, List[dict]] = {c: [] for c in CONDITIONS}
        noise_src = "nothing trial runs"
        for r in rs:
            cond = r.trial.get("condition")
            if r is base_run:
                continue
            ta, tb = analysis_window(r)
            if ta is None or tb is None:
                problems.append("%s: missing condition marks, run skipped" % r.run_id)
                continue
            fd = float(r.trial.get("flame_distance_m") or d / 2.0)
            for w in window_values(frames_of(r, ta, tb), baseline, b, fd, window_s):
                w.update({"distance_m": d, "condition": cond, "run_id": r.run_id})
                per_cond.setdefault(cond, []).append(w)
                window_rows.append(w)
        if not per_cond["nothing"]:
            noise_src = "baseline run itself (optimistic: the baseline was built from these frames)"
            for w in window_values(frames_of(base_run, t0, t1), baseline, b, d / 2.0, window_s):
                w.update({"distance_m": d, "condition": "nothing", "run_id": base_run.run_id + " (baseline)"})
                per_cond["nothing"].append(w)
                window_rows.append(w)
        nstat = {k: common.summary([w[k] for w in per_cond["nothing"]]) for k in METRICS}
        for cond in CONDITIONS:
            ws = per_cond.get(cond) or []
            if not ws:
                continue
            row = {"distance_m": d, "condition": cond, "reflector_range_m": r_b, "reflector_snr_db": snr,
                   "n_windows": len(ws), "n_runs": len({w["run_id"] for w in ws}),
                   "frac_flame_effect": float(np.mean([w["status"] == "FLAME_EFFECT" for w in ws])),
                   "frac_unknown": float(np.mean([w["status"] == "UNKNOWN" for w in ws])),
                   "noise_source": noise_src}
            outcome: Dict[str, str] = {}
            why_nc: Dict[str, str] = {}
            for k in METRICS:
                s = common.summary([w[k] for w in ws])
                row[k + "_mean"], row[k + "_std"] = s["mean"], s["std"]
                row[k + "_noise_sigma"] = nstat[k]["std"]
                eff = s["mean"] - nstat[k]["mean"]
                row[k + "_effect"] = eff
                sig = nstat[k]["std"]
                outcome[k], why = compare_to_noise(eff, sig, nstat[k]["n"], s["n"], k, cond)
                if outcome[k] == "not computable":
                    why_nc[k] = why
                    row[k + "_vs_noise"] = "not computable: " + why
                else:
                    row[k + "_vs_noise"] = "below noise" if outcome[k] == "below" else "%.1f sigma" % (abs(eff) / sig)
            above = [k for k in METRICS if outcome[k] == "above"]
            below_all = all(outcome[k] == "below" for k in METRICS)
            if cond == "nothing":
                row["effect_below_noise"] = None
            elif below_all:
                row["effect_below_noise"] = True
            elif above:
                row["effect_below_noise"] = False
            else:
                row["effect_below_noise"] = None
            cond_rows.append(row)
            if cond != "nothing":
                msg = ("%.1f m %-6s: loss %+.2f dB, amp flicker %+.3f dB, phase flicker %+.4f rad vs nothing "
                       "(3 sigma = %.2f / %.3f / %.4f)" % (
                           d, cond, row["loss_db_effect"], row["flicker_amp_db_effect"],
                           row["flicker_phase_rad_effect"], K_SIGMA * nstat["loss_db"]["std"],
                           K_SIGMA * nstat["flicker_amp_db"]["std"], K_SIGMA * nstat["flicker_phase_rad"]["std"]))
                nc = "; ".join("%s: %s" % (k, why_nc[k]) for k in METRICS if k in why_nc)
                if below_all:
                    verdict = "%s effect below noise" % cond
                elif above:
                    verdict = "%s effect above 3 sigma of the nothing runs (%s)" % (cond, ", ".join(above))
                    if nc:
                        verdict += "; not computable: %s" % nc
                else:
                    verdict = "%s effect vs noise NOT COMPUTABLE (%s)" % (cond, nc)
                if why_nc:
                    problems.append("%.1f m %s: effect vs noise not computable for %s" % (d, cond, nc))
                echo(msg)
                echo("    -> %s" % verdict)
                lines.append("- %.1f m, %s: **%s**%s" % (d, cond, verdict,
                                                          (" (detector FLAME_EFFECT in %.0f %% of windows)"
                                                           % (100 * row["frac_flame_effect"]))))
                if cond == "smoke" and row["frac_flame_effect"] > 0:
                    problems.append("%.1f m smoke: radar effect detector fired in %.0f %% of windows (smoke is "
                                    "assumed to have no radar effect)" % (d, 100 * row["frac_flame_effect"]))
    for p in problems:
        echo("PROBLEM: " + p)
    wcols = ["distance_m", "condition", "run_id", "t_start", "status", "reason"] + list(METRICS) + \
        ["loss_z", "flicker_amp_z", "flicker_phase_z"]
    common.write_csv(out / "B_windows.csv", window_rows, wcols, sim)
    ccols = ["distance_m", "condition", "n_runs", "n_windows", "reflector_range_m", "reflector_snr_db"]
    for k in METRICS:
        ccols += [k + "_mean", k + "_std", k + "_effect", k + "_noise_sigma", k + "_vs_noise"]
    ccols += ["effect_below_noise", "frac_flame_effect", "frac_unknown", "noise_source"]
    common.write_csv(out / "B_conditions.csv", cond_rows, ccols, sim)
    common.write_csv(out / "B_gate.csv", gate_rows, ["run_id", "distance_m", "condition", "risk_assessment_sha256",
                                                     "supervisor", "flame_source", "bunsen_burner", "gate"], sim)
    _plot(out / "B_radar_conditions.png", cond_rows, sim)
    body = ["Corner reflector at %s m; window %.0f s; noise = std of the 'nothing' windows; 'below noise' = "
            "|effect| < 3 sigma for loss, amplitude flicker and phase flicker." % (
                ", ".join("%.0f" % d for d in sorted(by_d)), window_s), "",
            common.md_table(cond_rows, ["distance_m", "condition", "n_windows", "reflector_snr_db", "loss_db_effect",
                                        "loss_db_noise_sigma", "flicker_amp_db_effect", "flicker_amp_db_noise_sigma",
                                        "flicker_phase_rad_effect", "flicker_phase_rad_noise_sigma",
                                        "frac_flame_effect"],
                            ["d (m)", "condition", "windows", "SNR (dB)", "loss effect (dB)", "sigma",
                             "amp flicker effect (dB)", "sigma", "phase flicker effect (rad)", "sigma",
                             "FLAME_EFFECT frac"]), ""] + lines
    n_gated = sum(1 for g in gate_rows if g["condition"] in GATED)
    n_missing = sum(1 for g in gate_rows if "GATE MISSING" in g["gate"])
    body += ["", "Safety gate (B_gate.csv): %d flame/smoke run(s), %d without a recorded risk assessment and "
             "supervisor. Flame source: as approved in the signed risk assessment; the analysis assumes a "
             "Bunsen-size flame (non-Bunsen runs are flagged)." % (n_gated, n_missing),
             "Plan coverage (2, 3, 4, 5 m; >= 3 nothing, 3 flame, 2 smoke, 2 mist per distance): %s."
             % ("complete" if not coverage else "INCOMPLETE, %d gap(s) listed under Problems" % len(coverage))]
    if problems:
        body += ["", "Problems (as measured):"] + ["- " + p for p in problems]
    body += ["", "The radar alone never decides FLAME: the app needs the radar effect AND flame-temperature pixels "
             "at the same bearing.", "Files: B_conditions.csv, B_windows.csv, B_gate.csv, B_radar_conditions.png."]
    md = common.md_snippet("Test B - radar, corner reflector, nothing / flame / smoke / mist", sim, body)
    (out / "B_results.md").write_text(md)
    return {"simulated": sim, "conditions": cond_rows, "windows": window_rows, "problems": problems,
            "markdown": md}


def _plot(path, rows, sim):
    plt = common.pyplot()
    fig, axs = plt.subplots(3, 1, figsize=(7.5, 8), sharex=True)
    colors = {"nothing": "0.3", "flame": "tab:red", "smoke": "tab:brown", "mist": "tab:blue"}
    offs = {"nothing": -0.15, "flame": -0.05, "smoke": 0.05, "mist": 0.15}
    labels = {"loss_db": "loss (dB)", "flicker_amp_db": "amp flicker (dB)", "flicker_phase_rad": "phase flicker (rad)"}
    for ax, k in zip(axs, METRICS):
        for r in rows:
            c = r["condition"]
            x = r["distance_m"] + offs.get(c, 0)
            if c == "nothing" and math.isfinite(r[k + "_mean"]) and math.isfinite(r[k + "_noise_sigma"]):
                ax.add_patch(plt.Rectangle((r["distance_m"] - 0.3, r[k + "_mean"] - K_SIGMA * r[k + "_noise_sigma"]),
                                           0.6, 2 * K_SIGMA * r[k + "_noise_sigma"], color="0.85", zorder=0))
            ax.errorbar(x, r[k + "_mean"], yerr=0 if not math.isfinite(r[k + "_std"]) else r[k + "_std"], fmt="o",
                        color=colors.get(c, "k"), ms=5, capsize=2)
        for c, col in colors.items():
            ax.plot([], [], "o", color=col, label=c)
        ax.set_ylabel(labels[k]); ax.grid(alpha=0.3)
    axs[0].plot([], [], "s", color="0.85", ms=10, label="nothing mean +- 3 sigma")
    axs[0].legend(fontsize=7, ncol=5, loc="upper left")
    axs[-1].set_xlabel("reflector distance (m)")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test B: radar effect at the reflector bin, mean +- sd over windows", sim)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test B analysis")
    p.add_argument("--runs", default=str(common.RECORDS / "B"))
    p.add_argument("--window-s", type=float, default=3.0)
    p.add_argument("--out", default=str(common.RECORDS / "B" / "analysis"))
    a = p.parse_args(argv)
    res = analyse(a.runs, a.out, a.window_s)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
