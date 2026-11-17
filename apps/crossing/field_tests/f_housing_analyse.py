"""Test F analysis: did the unit keep running and keep reporting truthfully under water spray and a hot-air gun?

Inputs: the laptop run directory from f_housing_record.py (phase marks, rx receipt log, laptop copy of the stream)
and, preferably, the Pi's own record session of the same time (--pi-session). Unit-side checks use the Pi session
when given; otherwise they use the laptop copy, where a Wi-Fi loss also looks like a unit gap (stated in the output).

Checks (thresholds are placeholders from hardware/vehicle-unit/docs/HOUSING.md sections 6 and 7, to be set from
this test; each is PASS / FAIL / WARN / INFO, as measured):
- unit_heartbeat_gaps: server ("unit") heartbeats with a gap > 2 s -> FAIL (unit stalled or rebooted).
- <sensor>_heartbeat_gaps: per-sensor heartbeat gap > 2 s -> FAIL.
- reboot: more than one session id, or Pi t_mono going backwards -> FAIL.
- silent_stop_<sensor>: readings stopped for longer than stale_s while every heartbeat in the gap said "ok" -> FAIL.
- housing_temp: max tc_housing >= 60 C -> FAIL (out of envelope), >= 50 C -> WARN.
- cpu_temp: max pi.cpu_c >= 80 C (SoC soft throttle) -> FAIL; throttling or frequency capping bits -> FAIL.
- under_voltage: any under_voltage_now -> FAIL.
- link_dropouts: laptop receipt gaps > 2 s -> FAIL (a lost WebSocket fails test F per HOUSING.md).
- plate_faults / plate_step: thermocouple faults, or a step > 5 C between consecutive 10 Hz plate readings during
  hot_air_plate -> FAIL; plate falling while heated (polarity) -> FAIL if the phase ends below its start.
- air_rise: tc_air must rise during hot_air_probe -> FAIL if it does not rise by >= 5 C.
- checklist: operator answers (water inside, radar window damage, plate) reported as given.
- disc_limit: the hot air must not heat the flux disc (copper on printed PETG tabs) to 70 C (crossing.yaml
  flux.disc_max_c, user-set): any tc_plate reading >= the limit -> FAIL.
- disc_guard_stop: the record script's disc guard stopped the run (trial.json stop_reason) -> FAIL, reported as
  "STOPPED: disc 70 C" / "STOPPED: disc temperature unknown"; the run is analysed as recorded, never dropped.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from field_tests import common, unitstats  # noqa: E402
from field_tests.sessions import Run, find_runs, load_run, scalar_series, segment  # noqa: E402

SENSORS = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")
HB_GAP_S = 2.0
HOUSING_WARN_C, HOUSING_LIMIT_C = 50.0, 60.0          # PLACEHOLDERS (HOUSING.md section 6)
CPU_LIMIT_C = 80.0                                     # Pi SoC soft throttle point
PLATE_STEP_C = 5.0                                     # placeholder


def _check(rows, name, result, value=None, limit=None, detail=""):
    rows.append({"check": name, "result": result, "value": value, "limit": limit, "detail": detail})


def _phase_bounds(run: Run):
    kinds = [m for m in run.marks if m.get("pi_t_mono") is not None and m.get("kind") not in ("operator",)]
    kinds.sort(key=lambda m: m["pi_t_mono"])
    out = {}
    for i, m in enumerate(kinds):
        if m["kind"] == "end":
            continue
        end = kinds[i + 1]["pi_t_mono"] if i + 1 < len(kinds) else None
        out[m["kind"]] = (float(m["pi_t_mono"]), None if end is None else float(end))
    return out


def analyse(out, run_dir, pi_session: Optional[str] = None, gap_s: float = HB_GAP_S) -> dict:
    out = common.out_dir(out)
    lap = load_run(run_dir)
    unit = load_run(pi_session) if pi_session else lap
    sim = common.is_simulated(lap.simulated, unit.simulated, unit.any_sim_message())
    phases = _phase_bounds(lap)
    t_all = [m["t_mono"] for s in SENSORS for m in unit.messages(s)]
    if not t_all:
        raise SystemExit("no sensor messages in %s" % unit.dir)
    span = (float(min(t_all)), float(max(t_all)))
    if "baseline" in phases:
        span = (max(span[0], phases["baseline"][0]), span[1])
    checks: List[dict] = []
    src = "Pi record session" if pi_session else "laptop copy (Wi-Fi losses also appear as unit gaps)"

    sids = set(m["session_id"] for s in SENSORS for m in unit.messages(s))
    _check(checks, "reboot", "FAIL" if len(sids) > 1 else "PASS", len(sids), 1,
           "session ids: %s" % ", ".join(sorted(sids)))
    ug = unitstats.heartbeat_gaps(segment(unit.heartbeats("unit"), *span), gap_s, span)
    _check(checks, "unit_heartbeat_gaps", "FAIL" if ug else "PASS", max([g["gap_s"] for g in ug], default=0.0), gap_s,
           "%d gap(s) > %.0f s (%s)" % (len(ug), gap_s, src) if ug else "no gap > %.0f s (%s)" % (gap_s, src))
    for s in SENSORS:
        hb = segment(unit.heartbeats(s), *span)
        g = unitstats.heartbeat_gaps(hb, gap_s, span)
        _check(checks, "%s_heartbeat_gaps" % s, "FAIL" if g else "PASS", max([x["gap_s"] for x in g], default=0.0),
               gap_s, "; ".join("%.1f s at +%.0f s" % (x["gap_s"], x["start"] - span[0]) for x in g))
        ss = unitstats.silent_stops(segment(unit.readings(s), *span), hb, unitstats.STALE_S[s])
        if ss:
            _check(checks, "silent_stop_%s" % s, "FAIL", max(x["gap_s"] for x in ss), unitstats.STALE_S[s],
                   "; ".join("readings stopped %.1f s at +%.0f s while heartbeats said ok" % (x["gap_s"],
                                                                                              x["start"] - span[0])
                             for x in ss))
    _, hous = scalar_series(unit.readings("tc_housing"), "temp_c")
    hmax = float(np.nanmax(hous)) if np.isfinite(hous).any() else float("nan")
    _check(checks, "housing_temp", "FAIL" if hmax >= HOUSING_LIMIT_C else ("WARN" if hmax >= HOUSING_WARN_C else
                                                                          ("PASS" if math.isfinite(hmax) else "FAIL")),
           hmax, HOUSING_LIMIT_C, "max tc_housing; warn %.0f C, limit %.0f C (placeholders)" % (HOUSING_WARN_C,
                                                                                               HOUSING_LIMIT_C))
    _, cpu = scalar_series(unit.readings("pi"), "cpu_c")
    cmax = float(np.nanmax(cpu)) if np.isfinite(cpu).any() else float("nan")
    _check(checks, "cpu_temp", "FAIL" if not math.isfinite(cmax) or cmax >= CPU_LIMIT_C else "PASS", cmax,
           CPU_LIMIT_C, "max pi.cpu_c" if math.isfinite(cmax) else "CPU temperature not read")
    pw = unitstats.power_summary(segment(unit.readings("pi"), *span))
    thr = {k: v for k, v in pw["readings_with_bit"].items() if k != "under-voltage now"}
    _check(checks, "throttling", "FAIL" if thr else "PASS", sum(thr.values()) if thr else 0, 0, str(thr or "none"))
    _check(checks, "under_voltage", "FAIL" if pw["n_under_voltage_events"] else "PASS", pw["n_under_voltage_events"],
           0, "%.1f s in total" % pw["under_voltage_s"])
    link = unitstats.link_dropouts(lap.rx(), gap_s) if lap.rx() else None
    if link is None:
        _check(checks, "link_dropouts", "INFO", None, gap_s, "no rx log in the run directory")
    else:
        _check(checks, "link_dropouts", "FAIL" if link["count"] else "PASS", link["max_gap_s"], gap_s,
               "%d laptop receipt gap(s) > %.0f s, %d disconnect(s)" % (link["count"], gap_s, link["disconnects"]))
    if "hot_air_plate" in phases:
        a, b = phases["hot_air_plate"]
        pr = segment(unit.readings("tc_plate"), a, b)
        faults = [m["data"].get("fault") for m in pr if m["data"].get("fault")]
        t, v = scalar_series(pr, "temp_c")
        steps = np.abs(np.diff(v[np.isfinite(v)])) if np.isfinite(v).sum() > 1 else np.array([0.0])
        _check(checks, "plate_faults", "FAIL" if faults else "PASS", len(faults), 0, ", ".join(sorted(set(faults))))
        _check(checks, "plate_step", "FAIL" if steps.max() > PLATE_STEP_C else "PASS", float(steps.max()),
               PLATE_STEP_C, "largest step between consecutive plate readings in hot_air_plate")
        fin = v[np.isfinite(v)]
        if fin.size > 20:
            rise = float(np.median(fin[-10:]) - np.median(fin[:10]))
            _check(checks, "plate_rises_when_heated", "PASS" if rise > 0 else "FAIL", rise, 0.0,
                   "end minus start of hot_air_plate (negative = polarity reversed?)")
    if "hot_air_probe" in phases:
        a, b = phases["hot_air_probe"]
        t, v = scalar_series(segment(unit.readings("tc_air"), a, b), "temp_c")
        fin = v[np.isfinite(v)]
        rise = float(fin.max() - np.median(fin[:10])) if fin.size > 10 else float("nan")
        _check(checks, "air_rise", "PASS" if math.isfinite(rise) and rise >= 5.0 else "FAIL", rise, 5.0,
               "tc_air rise during hot_air_probe; the laptop must CLOSE above the vehicle intake limit (test D/app)")
    lim = float(lap.trial.get("disc_max_c") or common.disc_max_c())
    _, pv = scalar_series(segment(unit.readings("tc_plate"), *span), "temp_c")
    pmax = float(np.nanmax(pv)) if np.isfinite(pv).any() else float("nan")
    n_over = int(np.sum(pv[np.isfinite(pv)] >= lim))
    _check(checks, "disc_limit", "FAIL" if n_over or not math.isfinite(pmax) else "PASS", pmax, lim,
           ("%d tc_plate reading(s) >= %.0f C (PETG tabs)" % (n_over, lim)) if n_over else
           ("max tc_plate over the run; the hot air must not heat the disc to %.0f C (user-set)" % lim
            if math.isfinite(pmax) else "no tc_plate reading"))
    lab = common.stop_label(lap.trial)
    _check(checks, "disc_guard_stop", "FAIL" if lab else "PASS", lap.trial.get("stop_reason"), None,
           (lab + ": " + str(lap.trial.get("stop_detail") or "") + " (run kept, analysed as recorded)") if lab
           else ("not stopped by the record script's disc guard" if "stop_reason" in lap.trial
                 else "run recorded without a disc guard result (older record script)"))
    for k, v in (lap.trial.get("checklist") or {}).items():
        _check(checks, "checklist_%s" % k, "INFO", v, None, "operator answer")

    phase_rows = []
    for k, (a, b) in phases.items():
        row = {"phase": k, "start_s": a - span[0], "duration_s": None if b is None else b - a}
        for nm, s, key in (("housing_max_c", "tc_housing", "temp_c"), ("cpu_max_c", "pi", "cpu_c"),
                           ("plate_max_c", "tc_plate", "temp_c"), ("air_max_c", "tc_air", "temp_c")):
            _, v = scalar_series(segment(unit.readings(s), a, b), key)
            row[nm] = float(np.nanmax(v)) if np.isfinite(v).any() else float("nan")
        for s in ("radar", "thermal"):
            rd = segment(unit.readings(s), a, b)
            row[s + "_rate_hz"] = len(rd) / (b - a) if b and b > a else float("nan")
        phase_rows.append(row)
    common.write_csv(out / "F_checks.csv", checks, ["check", "result", "value", "limit", "detail"], sim)
    common.write_csv(out / "F_phases.csv", phase_rows, ["phase", "start_s", "duration_s", "housing_max_c", "cpu_max_c",
                                                        "plate_max_c", "air_max_c", "radar_rate_hz",
                                                        "thermal_rate_hz"], sim)
    _plot(out / "F_timeline.png", unit, phases, span, checks, sim)
    n_fail = sum(1 for c in checks if c["result"] == "FAIL")
    body = ["Unit-side source: %s. %d check(s) FAIL, %d WARN (thresholds are placeholders)." % (
        src, n_fail, sum(1 for c in checks if c["result"] == "WARN")), "",
            common.md_table(checks, ["check", "result", "value", "limit", "detail"],
                            ["check", "result", "value", "limit", "detail"], nd=2), "",
            common.md_table(phase_rows, ["phase", "duration_s", "housing_max_c", "cpu_max_c", "plate_max_c",
                                         "air_max_c", "radar_rate_hz"],
                            ["phase", "s", "housing max (C)", "CPU max (C)", "plate max (C)", "air max (C)",
                             "radar (Hz)"], nd=1), "",
            "Hot-air gun is a stand-in for radiant heat; it is not a flame and says nothing about flame exposure.",
            "Files: F_checks.csv, F_phases.csv, F_timeline.png."]
    md = common.md_snippet("Test F - housing: water spray and hot-air gun", sim, body)
    (out / "F_results.md").write_text(md)
    return {"simulated": sim, "checks": checks, "phases": phase_rows, "markdown": md}


def _plot(path, unit: Run, phases, span, checks, sim):
    plt = common.pyplot()
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 6.5), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    t0 = span[0]
    for s, key, lab, c in (("tc_housing", "temp_c", "housing", "tab:orange"), ("pi", "cpu_c", "CPU", "tab:red"),
                           ("tc_plate", "temp_c", "plate", "k"), ("tc_air", "temp_c", "air", "tab:blue")):
        t, v = scalar_series(unit.readings(s), key)
        a1.plot((t - t0) / 60, v, lw=0.8, color=c, label=lab)
    a1.axhline(HOUSING_WARN_C, color="tab:orange", ls=":", lw=1, label="housing warn 50 C (placeholder)")
    a1.axhline(CPU_LIMIT_C, color="tab:red", ls=":", lw=1, label="CPU soft throttle 80 C")
    cmap = plt.get_cmap("Pastel1")
    for i, (k, (a, b)) in enumerate(phases.items()):
        for ax in (a1, a2):
            ax.axvspan((a - t0) / 60, ((b if b else span[1]) - t0) / 60, color=cmap(i % 9), alpha=0.5, lw=0)
        a1.text((a - t0) / 60, 0.02, " " + k, transform=a1.get_xaxis_transform(), fontsize=6, va="bottom",
                rotation=90)
    a1.set_ylabel("C"); a1.legend(fontsize=6, ncol=3, loc="upper left"); a1.grid(alpha=0.3)
    for i, s in enumerate(SENSORS):
        t = np.array([m["t_mono"] for m in unit.readings(s)])
        for g in unitstats.gaps(t, unitstats.STALE_S[s]):
            a2.plot([(g["start"] - t0) / 60, (g["end"] - t0) / 60], [i, i], color="tab:red", lw=6)
        hb = [h for h in unit.heartbeats(s) if h["status"] != "ok"]
        if hb:
            a2.plot([(h["t_mono"] - t0) / 60 for h in hb], [i] * len(hb), "|", color="purple", ms=8)
    a2.set_yticks(range(len(SENSORS))); a2.set_yticklabels(SENSORS, fontsize=7)
    a2.set_xlabel("minutes"); a2.set_title("red: reading gaps > stale_s; purple: heartbeat not ok", fontsize=8)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test F: housing under spray and hot air", sim)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test F analysis")
    p.add_argument("--run", help="run directory from f_housing_record.py (default: newest under records/F)")
    p.add_argument("--pi-session", help="the Pi's own record session of the same time (recommended)")
    p.add_argument("--gap-s", type=float, default=HB_GAP_S)
    p.add_argument("--out", help="default: <run>/analysis")
    a = p.parse_args(argv)
    run = a.run
    if run is None:
        runs = find_runs(common.RECORDS / "F", "F")
        if not runs:
            raise SystemExit("no test F runs under %s" % (common.RECORDS / "F"))
        run = str(runs[-1].dir)
    res = analyse(a.out or str(Path(run) / "analysis"), run, a.pi_session, a.gap_s)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
