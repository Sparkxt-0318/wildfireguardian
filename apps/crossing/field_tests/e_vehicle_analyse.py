"""Test E analysis: 30-minute drive with the unit on the roof and the laptop inside.

Inputs: the Pi's own record session(s) (--pi-session, repeatable: a reboot starts a new session) and the laptop copy
from e_vehicle_record.py (--laptop, for rx.jsonl.gz receipt times). Without --pi-session the laptop copy is used for
everything (thermal is then decimated to the wire rate and completeness is relative to what reached the laptop).

Reported (as measured, nothing is judged "ready"):
- Link dropouts: gaps > gap_s (default 1 s) between messages received by the laptop; count, durations, longest,
  total; disconnect events; Pi-side `dropped` events (per-client queue overflow on the Pi).
- GNSS track: fix ratio (readings with fix > 0), hdop distribution (hdop is dimensionless, not metres), satellites,
  distance driven along fixed points, map PNG of the track in local metres (no basemap).
- Power: under-voltage events (count, duration), throttling bits from vcgencmd get_throttled, input voltage if read.
- Temperatures: Pi CPU, housing thermocouple, intake-height air thermocouple (min / median / max), faults.
- Data completeness per sensor (Pi clock): readings vs nominal rate (unit.yaml rate_hz when the session config
  has it, else DESIGN defaults: thermal 25, radar 10, tc 10, imu 20, pi 1 Hz; gnss: measured median), missing seq
  numbers, gaps longer than the sensor's stale_s, fraction of time fresh, heartbeats not "ok", fault readings.
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

from field_tests import common, unitstats  # noqa: E402
from field_tests.sessions import Run, load_run  # noqa: E402

SENSORS = ("thermal", "radar", "tc_plate", "tc_housing", "tc_air", "imu", "gnss", "pi")


def _cfg_rate(info: dict, sensor: str) -> Optional[float]:
    cfg = info.get("config") or {}
    s = (cfg.get("sensors") or {}).get(sensor) or {}
    r = s.get("rate_hz")
    return float(r) if isinstance(r, (int, float)) and r > 0 else None


def _span(run: Run) -> tuple:
    a, b = run.info.get("t_mono_first"), run.info.get("t_mono_last")
    if a is None or b is None:
        ts = [m["t_mono"] for s in SENSORS for m in run.messages(s)]
        a, b = (min(ts), max(ts)) if ts else (0.0, 0.0)
    return float(a), float(b)


def gnss_summary(readings: List[dict]) -> Dict[str, object]:
    fix = np.array([int(m["data"].get("fix") or 0) for m in readings])
    hd = common.finite([m["data"].get("hdop") for m in readings if (m["data"].get("fix") or 0) > 0])
    sats = common.finite([m["data"].get("sats") for m in readings])
    pts = [(m["data"]["lat"], m["data"]["lon"], m["data"].get("fix")) for m in readings
           if (m["data"].get("fix") or 0) > 0 and m["data"].get("lat") is not None and m["data"].get("lon") is not None]
    dist = 0.0
    if len(pts) > 1:
        lat = np.array([p[0] for p in pts]); lon = np.array([p[1] for p in pts])
        x, y = unitstats.local_xy(lat, lon, float(lat.mean()), float(lon.mean()))
        step = np.hypot(np.diff(x), np.diff(y))
        dist = float(step[step < 200].sum())          # ignore jumps across no-fix stretches
    nofix = unitstats.gaps([m["t_mono"] for m in readings if (m["data"].get("fix") or 0) > 0], 2.0)
    return {"n": int(fix.size), "fix_ratio": float(np.mean(fix > 0)) if fix.size else float("nan"),
            "fix2_ratio": float(np.mean(fix == 2)) if fix.size else float("nan"),
            "hdop": common.summary(hd), "sats": common.summary(sats), "distance_km": dist / 1000.0,
            "no_fix_stretches": len(nofix), "longest_no_fix_s": max([g["gap_s"] for g in nofix], default=0.0),
            "_pts": pts, "_hdop": hd}


def temps(run: Run) -> List[dict]:
    rows = []
    for name, sensor, key in (("cpu", "pi", "cpu_c"), ("housing", "tc_housing", "temp_c"), ("air", "tc_air", "temp_c")):
        rd = run.readings(sensor)
        s = common.summary([m["data"].get(key) for m in rd])
        rows.append({"what": name, "sensor": sensor, "n": s["n"], "min_c": s["min"], "median_c": s["p50"],
                     "max_c": s["max"], "missing_or_fault": sum(1 for m in rd if m["data"].get(key) is None)})
    return rows


def analyse(out, pi_sessions: List[str], laptop: Optional[str] = None, gap_s: float = 1.0,
            rates: Optional[Dict[str, float]] = None) -> dict:
    out = common.out_dir(out)
    lap = load_run(laptop) if laptop else None
    pis = [load_run(p) for p in pi_sessions] if pi_sessions else ([lap] if lap else [])
    if not pis:
        raise SystemExit("give --pi-session DIR (and/or --laptop DIR)")
    source_note = "Pi record session(s)" if pi_sessions else "laptop copy only (thermal decimated on the wire)"
    sim = common.is_simulated(*([r.simulated for r in pis] + ([lap.simulated] if lap else [])),
                              *[r.any_sim_message() for r in pis])
    comp_rows, gn_all, pw_rows, temp_rows, pi_dropped = [], [], [], [], 0
    gnss_reads, pi_reads, ht, hous, air, cpu = [], [], [], [], [], []
    for r in pis:
        span = _span(r)
        for s in SENSORS:
            row = unitstats.completeness(s, r.readings(s), r.heartbeats(s), span,
                                         (rates or {}).get(s) or _cfg_rate(r.info, s))
            row["session"] = r.info.get("session_id") or r.dir.name
            comp_rows.append(row)
        gnss_reads += r.readings("gnss")
        pi_reads += r.readings("pi")
        temp_rows += [dict(x, session=r.info.get("session_id")) for x in temps(r)]
        if r.session is not None:
            pi_dropped += sum(1 for e in r.session.events() if e.get("kind") == "dropped")
    gn = gnss_summary(gnss_reads)
    pw = unitstats.power_summary(pi_reads)
    link = unitstats.link_dropouts(lap.rx(), gap_s) if lap else None
    drop_rows = [{"n": i + 1, "start_s": a, "duration_s": d} for i, (a, d) in
                 enumerate(zip(link["starts_s"], link["durations_s"]))] if link else []
    comp_cols = ["session", "sensor", "n_readings", "span_s", "median_rate_hz", "nominal_hz", "completeness_pct",
                 "seq_missing", "gaps_over_stale", "stale_s", "longest_gap_s", "fresh_time_pct", "hb_not_ok_pct",
                 "fault_readings"]
    common.write_csv(out / "E_completeness.csv", comp_rows, comp_cols, sim)
    common.write_csv(out / "E_link_dropouts.csv", drop_rows, ["n", "start_s", "duration_s"], sim)
    common.write_csv(out / "E_power_events.csv", pw["under_voltage_events"], ["start", "end", "duration_s", "open"], sim)
    common.write_csv(out / "E_temperatures.csv", temp_rows, ["session", "what", "sensor", "n", "min_c", "median_c",
                                                              "max_c", "missing_or_fault"], sim)
    gsum = {k: v for k, v in gn.items() if not k.startswith("_")}
    common.write_json(out / "E_summary.json", {"simulated": sim, "gnss": gsum, "power": pw, "link": link,
                                                "pi_dropped_events": pi_dropped, "sessions": [r.dir.name for r in pis]})
    _plot_track(out / "E_track.png", gn, sim)
    _plot_timeline(out / "E_timeline.png", pis, lap, link, sim)

    span_min = sum(_span(r)[1] - _span(r)[0] for r in pis) / 60.0
    body = ["Source: %s; %d Pi session(s)%s; recorded span %.1f min." % (
        source_note, len(pis), " (a second session means the unit restarted)" if len(pis) > 1 else "", span_min)]
    if link:
        body.append("Link (laptop receipt, gaps > %.1f s): %d dropout(s), longest %s s, total %s s; %d disconnect "
                    "event(s); largest gap %s s. Pi-side queue-drop events: %d." % (
                        gap_s, link["count"], common.fmt(link["longest_s"], 1), common.fmt(link["total_s"], 1),
                        link["disconnects"], common.fmt(link["max_gap_s"], 2), pi_dropped))
    else:
        body.append("Link: no laptop copy given, dropouts not analysed.")
    body.append("GNSS: %d readings, fix ratio %s (fix 2: %s), hdop median %s / p95 %s / max %s, satellites median "
                "%s, %d no-fix stretch(es) > 2 s (longest %s s), distance %s km." % (
                    gn["n"], common.fmt(gn["fix_ratio"], 3), common.fmt(gn["fix2_ratio"], 3),
                    common.fmt(gn["hdop"]["p50"], 2), common.fmt(gn["hdop"]["p95"], 2),
                    common.fmt(gn["hdop"]["max"], 2), common.fmt(gn["sats"]["p50"], 0), gn["no_fix_stretches"],
                    common.fmt(gn["longest_no_fix_s"], 1), common.fmt(gn["distance_km"], 2)))
    body.append("Power: %d under-voltage event(s), %s s in total; throttling-bit readings: %s; occurred since boot "
                "(last reading): %s; %d reading(s) without throttle data." % (
                    pw["n_under_voltage_events"], common.fmt(pw["under_voltage_s"], 1),
                    pw["readings_with_bit"] or "none", ", ".join(pw["occurred_since_boot"]) or "none",
                    pw["unknown_throttle_readings"]))
    body += ["", common.md_table(temp_rows, ["what", "n", "min_c", "median_c", "max_c", "missing_or_fault"],
                                 ["temperature", "n", "min (C)", "median (C)", "max (C)", "missing/fault"], nd=1),
             "", common.md_table(comp_rows, ["sensor", "n_readings", "median_rate_hz", "nominal_hz", "completeness_pct",
                                             "seq_missing", "gaps_over_stale", "longest_gap_s", "fresh_time_pct",
                                             "hb_not_ok_pct", "fault_readings"],
                                 ["sensor", "readings", "rate (Hz)", "nominal", "complete (%)", "seq missing",
                                  "gaps > stale", "longest gap (s)", "fresh time (%)", "hb not ok (%)", "faults"],
                                 nd=1),
             "", "Files: E_completeness.csv, E_link_dropouts.csv, E_power_events.csv, E_temperatures.csv, "
             "E_summary.json, E_track.png, E_timeline.png."]
    md = common.md_snippet("Test E - vehicle drive, unit on the roof", sim, body)
    (out / "E_results.md").write_text(md)
    return {"simulated": sim, "completeness": comp_rows, "gnss": gsum, "power": pw, "link": link,
            "temps": temp_rows, "markdown": md}


def _plot_track(path, gn, sim):
    plt = common.pyplot()
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.8), gridspec_kw={"width_ratios": [1.6, 1]})
    pts = gn["_pts"]
    if pts:
        lat = np.array([p[0] for p in pts]); lon = np.array([p[1] for p in pts])
        fx = np.array([p[2] for p in pts])
        lat0, lon0 = float(lat.mean()), float(lon.mean())
        x, y = unitstats.local_xy(lat, lon, lat0, lon0)
        for f, c, lab in ((1, "tab:orange", "fix 1 (GPS)"), (2, "tab:blue", "fix 2 (DGPS/RTK class)")):
            s = fx == f
            if s.any():
                a1.plot(x[s], y[s], ".", ms=2, color=c, label=lab)
        a1.plot(x[0], y[0], "g^", ms=8, label="start"); a1.plot(x[-1], y[-1], "rs", ms=7, label="end")
        a1.set_aspect("equal", adjustable="datalim")
        a1.set_title("track in local metres around %.5f, %.5f (no basemap)" % (lat0, lon0), fontsize=8)
    a1.set_xlabel("east (m)"); a1.set_ylabel("north (m)"); a1.grid(alpha=0.3); a1.legend(fontsize=7)
    hd = gn["_hdop"]
    if hd.size:
        a2.hist(hd, bins=np.arange(0, max(5.0, float(hd.max()) + 0.25), 0.25), color="0.4")
    a2.set_xlabel("hdop (dimensionless, fixed readings)"); a2.set_ylabel("readings")
    a2.set_title("fix ratio %s" % common.fmt(gn["fix_ratio"], 3), fontsize=9); a2.grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0.02, 1, 0.93))
    common.finish_figure(fig, path, "Test E: GNSS track and hdop", sim)


def _plot_timeline(path, pis: List[Run], lap: Optional[Run], link, sim):
    plt = common.pyplot()
    fig, axs = plt.subplots(3, 1, figsize=(9, 7.5), sharex=False)
    t0 = _span(pis[0])[0]
    for r in pis:
        for sensor, key, lab, c in (("pi", "cpu_c", "CPU", "tab:red"), ("tc_housing", "temp_c", "housing", "tab:orange"),
                                    ("tc_air", "temp_c", "air (intake height)", "tab:blue")):
            rd = r.readings(sensor)
            t = np.array([m["t_mono"] for m in rd]) - t0
            v = np.array([np.nan if m["data"].get(key) is None else m["data"][key] for m in rd], dtype=float)
            axs[0].plot(t / 60, v, lw=0.8, color=c, label=lab if r is pis[0] else None)
        for m in r.readings("pi"):
            if m["data"].get("under_voltage_now"):
                axs[0].axvline((m["t_mono"] - t0) / 60, color="purple", alpha=0.4, lw=1)
    axs[0].plot([], [], color="purple", label="under-voltage reading")
    axs[0].set_ylabel("C"); axs[0].legend(fontsize=7, ncol=4); axs[0].grid(alpha=0.3)
    axs[0].set_xlabel("minutes (Pi clock)")
    for i, s in enumerate(SENSORS):
        for r in pis:
            st = unitstats.STALE_S[s]
            span = _span(r)
            t = np.array([m["t_mono"] for m in r.readings(s)])
            for g in unitstats.gaps(np.concatenate([[span[0]], t, [span[1]]]), st):
                axs[1].plot([(g["start"] - t0) / 60, (g["end"] - t0) / 60], [i, i], color="tab:red", lw=6)
            if t.size:
                axs[1].plot([(t[0] - t0) / 60, (t[-1] - t0) / 60], [i, i], color="0.85", lw=2, zorder=0)
    axs[1].set_yticks(range(len(SENSORS))); axs[1].set_yticklabels(SENSORS, fontsize=7)
    axs[1].set_title("red: reading gaps longer than the sensor's stale_s", fontsize=8)
    axs[1].set_xlabel("minutes (Pi clock)")
    if link and lap:
        starts = np.array(link["starts_s"]) / 60
        axs[2].bar(starts, link["durations_s"], width=0.15, color="tab:red")
        axs[2].set_ylabel("dropout (s)")
        axs[2].set_title("laptop link dropouts: %d, longest %s s" % (link["count"], common.fmt(link["longest_s"], 1)),
                         fontsize=8)
    else:
        axs[2].text(0.5, 0.5, "no laptop copy: link not analysed", ha="center", transform=axs[2].transAxes)
    axs[2].set_xlabel("minutes (laptop clock, from first message)"); axs[2].grid(alpha=0.3)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    common.finish_figure(fig, path, "Test E: temperatures, data gaps, link", sim)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Test E analysis")
    p.add_argument("--pi-session", action="append", default=[], help="Pi record session dir (repeat after a reboot)")
    p.add_argument("--laptop", help="laptop copy from e_vehicle_record.py")
    p.add_argument("--gap-s", type=float, default=1.0)
    p.add_argument("--rate", action="append", default=[], help="override nominal rate, e.g. --rate gnss=5")
    p.add_argument("--out", default=str(common.RECORDS / "E" / "analysis"))
    a = p.parse_args(argv)
    rates = {}
    for r in a.rate:
        k, v = r.split("=", 1)
        rates[k.strip()] = float(v)
    res = analyse(a.out, a.pi_session, a.laptop, a.gap_s, rates)
    print(res["markdown"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
