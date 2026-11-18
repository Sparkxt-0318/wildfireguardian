#!/usr/bin/env python3
"""Print every table of RESULTS.md from numbers.json.   python3 tables.py numbers.json > derived/tables.md"""
import json
import statistics
import sys

n = json.load(open(sys.argv[1]))
ORDER = ["G", "A-cal", "A25", "A30", "A+G", "A25+G", "A30+G", "A-match"]
ORDER = [r for r in ORDER if r in n["fire_set"]]


def c(x, pct=True):
    """k of n with its exact interval."""
    if x["n"] == 0:
        return "0 of 0"
    lo, hi = x["ci95"]
    return f"{x['k']} of {x['n']} ({100*lo:.0f}-{100*hi:.0f}%)"


def leads(v):
    if not v:
        return "-"
    return f"{', '.join(str(x) for x in sorted(v))} (median {statistics.median(v):g})"


def m(x):
    return "-" if x is None else f"{x['mean']:.1f} ({x['ci95'][0]:.1f}-{x['ci95'][1]:.1f})"


def table(head, rows):
    print("| " + " | ".join(head) + " |")
    print("|" + "---|" * len(head))
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")
    print()


sm = n["s_match"]
print(f"S-match: G fires on {sm['g_alarm_point_days']} burden point-days; A reaches that count at {sm['threshold_ms']} m/s "
      f"({sm['a_alarm_point_days']} point-days).\n")

print("## T1 Fire set and burden, per rule\n")
for label, key in (("all run fire-days", "full"), ("without 25 March 2025", "without_25_march")):
    print(f"**{label}**\n")
    rows = []
    for r in ORDER:
        f, b = n["fire_set"][r][key], n["burden"][r]
        rows.append([r, f"{f['run_fire_days']} / {f['fires_with_run']}", c(f["warned"]), c(f["warned_1h_ahead"]), leads(f["leads_h"]),
                     c(f["run_hours_missed"]), c(f["alarm_days_without_run"]), m(b["alarm_days_per_point_season"]),
                     m(b["false_alarm_days_per_point_season"]), m(b["days_any_point_per_season"])])
    table(["rule", "run fire-days / fires", "warned at the first run hour", "warned >= 1 h ahead", "lead times, h", "run hours missed",
           "alarm fire-days with no run", "burden: alarm days per point and season", "false-alarm days per point and season",
           "days per season with an alarm at any of ten points"], rows)

print("## T2 Every run fire-day\n")
days = {r: {(d["fire"], d["kst_day"]): d for d in n["fire_set"][r]["fire_days"] if d["run_hours"] > 0} for r in ORDER}
go = {(d["fire"], d["kst_day"]): d for d in n["gobs"]["within_50km"]["fire_days"] if d["run_hours"] > 0}


def cell(d):
    if d is None:
        return "NOT RUN"
    if not d["state_known"]:
        return "no data"
    return f"{d['lead_h']} h ({d['lead_h_since_ignition']})" if d["warned"] else "no"


rows = []
for k in sorted(days["G"]):
    d = days["G"][k]
    rows.append([d["name"], k[0], k[1], f"{d['first_run_kst_hour']:02d}", d["run_hours"]] +
                [cell(days[r][k]) for r in ORDER if r in ("G", "A-cal", "A25", "A30", "A-match")] + [cell(go.get(k))] +
                [f"{days['G'][k]['run_hours_missed']} / {days['A-cal'][k]['run_hours_missed']}"])
table(["fire", "id", "KST day", "first run hour KST", "run hours"] + [r for r in ORDER if r in ("G", "A-cal", "A25", "A30", "A-match")] +
      ["G-obs (PARTIAL)", "run hours missed G / A-cal"], rows)

print("## T3 Leave-one-fire-out: run fire-days warned\n")
fires = sorted(n["fire_set"]["G"]["leave_one_fire_out"])
rows = []
for f in fires:
    x = {r: n["fire_set"][r]["leave_one_fire_out"][f] for r in ORDER}
    rows.append([f, x["G"]["run_fire_days"]] + [f"{x[r]['warned']['k']}" for r in ORDER] +
                [f"{x['G']['alarm_days_without_run']['k']} / {x['A-cal']['alarm_days_without_run']['k']} of {x['G']['alarm_days_without_run']['n']}"])
table(["fire left out", "run fire-days left"] + ORDER + ["alarm fire-days with no run, G / A-cal"], rows)

print("## T4 Verdicts against G (frozen wording)\n")
rows = []
for r, v in n["verdicts"].items():
    f, w = v["full"], v["without_25_march"]
    lo = [x["warned_a"] - x["warned_g"] for x in v["leave_one_fire_out"].values()]
    rows.append([r, f"{f['warned_a']} vs {f['warned_g']} of {f['run_fire_days']}", f"{w['warned_a']} vs {w['warned_g']} of {w['run_fire_days']}",
                 f"{min(lo):+d} to {max(lo):+d}", f"{f['warned_by_a_only']} / {f['warned_by_g_only']} (p = {f['sign_test_p']})",
                 v["more_reliably"] + (": " + ", ".join(v["more_reliably_fails_in"]) if v["more_reliably_fails_in"] else ""),
                 ", ".join(f"{x:+d}" for x in f["lead_a_minus_g_h"]) or "-", v["earlier"]])
table(["rule", "warned, rule vs G", "without 25 March", "leave-one-fire-out: rule minus G", "warned by rule only / by G only (sign test)",
       "more reliably", "lead, rule minus G, h (days warned by both)", "earlier"], rows)

print("## T5 Burden set season by season\n")
seasons = n["burden"]["G"]["all_seasons_evaluated"]
rows = []
for r in ORDER:
    b = n["burden"][r]["per_season"]
    for s in seasons:
        x = b[str(s)]
        rows.append([r, s, f"{x['days_evaluated']} of {x['full_season_days']}", x["alarm_point_days"], f"{x['mean_alarm_days_per_point']:.1f}",
                     f"{x['min_point'][0]} {x['min_point'][1]}", f"{x['max_point'][0]} {x['max_point'][1]}", x["days_any_point"],
                     x["false_alarm_point_days"]])
table(["rule", "season", "days evaluated", "alarm point-days", "mean alarm days per point", "lowest point", "highest point",
       "days with an alarm at any point", "false-alarm point-days"], rows)
print("By point, alarm days per full season (mean):\n")
pts = list(n["burden"]["G"]["per_point"])
table(["rule"] + pts, [[r] + [f"{n['burden'][r]['per_point'][p]['mean']:.1f}" for p in pts] for r in ORDER])

print("## T6 Sensitivity\n")
rows = []
for k, v in n["sensitivity"].items():
    f, w, b = v["full"], v["without_25_march"], v["burden"]
    rows.append([k, c(f["warned"]), c(w["warned"]), leads(f["leads_h"]), c(f["run_hours_missed"]), c(f["alarm_days_without_run"]),
                 m(b["alarm_days_per_point_season"]), m(b["days_any_point_per_season"])])
table(["rule", "warned", "without 25 March", "lead times, h", "run hours missed", "alarm fire-days with no run",
       "burden: alarm days per point and season", "days per season, any point"], rows)
print("Lapsed-warning variant (fired at any hour in the 12 h up to the first run hour):\n")
table(["rule", "warned (primary)", "warned (lapsed counted)"],
      [[r, c(n["fire_set"][r]["full"]["warned"]), c(n["fire_set"][r]["full"]["warned_lapsed_12h"])] for r in ORDER])

print("## T7 Threshold sweep (descriptive)\n")
for label, key in (("forecast gust, two consecutive hours (k = 2)", "gust_k2"), ("forecast gust, any hour (k = 1)", "gust_k1"),
                   ("forecast 850 hPa wind, any hour", "w850_k1")):
    print(f"**{label}**\n")
    table(["threshold m/s", "warned of run fire-days", "without 25 March", "run hours missed", "alarm fire-days with no run",
           "burden: alarm days per point and season", "burden point-days"],
          [[x["threshold"], f"{x['warned']} of {x['run_fire_days']}", x["warned_without_25_march"], f"{x['run_hours_missed']} of {x['run_hours']}",
            f"{x['alarm_days_without_run']} of {x['no_run_fire_days']}", x["burden_alarm_days_per_point_season"], x["burden_alarm_point_days"]]
           for x in n["sweep"][key] if x["threshold"] % 2 == 0 or x["threshold"] in (15, 25)])

print("## T8 Secondary timelines and hour sets\n")
rows = []
for label, key in (("S1 KFS_01 from the Choi raster on every day", "fire_set_choi_timeline"), ("S6 kcf-abstain's scored hours only", "fire_set_abstain_hours")):
    for r in ORDER:
        f, w = n[key][r]["full"], n[key][r]["without_25_march"]
        rows.append([label, r, f["run_fire_days"], c(f["warned"]), c(w["warned"]), leads(f["leads_h"]), c(f["run_hours_missed"]),
                     c(f["alarm_days_without_run"])])
table(["variant", "rule", "run fire-days", "warned", "without 25 March", "lead times, h", "run hours missed", "alarm fire-days with no run"], rows)
print("S4 pooled issue hours (counts):\n")
table(["rule", "fires and run hour", "fires, no run", "silent and run hour", "silent, no run"],
      [[r, p["fires_and_run"], p["fires_no_run"], p["silent_and_run"], p["silent_no_run"]] for r, p in n["pooled_hours"].items()])

print("## T9 G-obs, KFS_01 only (PARTIAL: four stations, 22-26 March 2025)\n")
rows = []
for label in ("within_50km", "all_four_stations"):
    f, w, p = n["gobs"][label]["full"], n["gobs"][label]["without_25_march"], n["gobs"][label]["pooled_hours"]
    rows.append([f"G-obs, {label.replace('_', ' ')}", f["run_fire_days"], c(f["warned"]), c(w["warned"]), c(f["warned_lapsed_12h"]),
                 c(f["run_hours_missed"]), c(f["alarm_days_without_run"]), f"{p['fires_and_run']} / {p['fires_no_run']}", p["state_unknown"]])
for r in ORDER:
    f, w = n["gobs"]["same_fire_other_rules"][r]["full"], n["gobs"]["same_fire_other_rules"][r]["without_25_march"]
    rows.append([r + " (same fire)", f["run_fire_days"], c(f["warned"]), c(w["warned"]), c(f["warned_lapsed_12h"]), c(f["run_hours_missed"]),
                 c(f["alarm_days_without_run"]), "", ""])
table(["rule", "run fire-days", "warned", "without 25 March", "warned, lapsed counted", "run hours missed", "alarm fire-days with no run",
       "issue hours firing: run / no run", "issue hours with no station data"], rows)

x = n.get("second_model_ifs")
if isinstance(x, dict):
    print("## T10 Second model: ECMWF IFS\n")
    fs = x["fire_set"]
    print(f"Fires with IFS: {', '.join(fs['fires_with_ifs'])}. Without: {', '.join(fs['fires_without_ifs'])}. Issue hours {fs['issue_hours']}, "
          f"without IFS {fs['issue_hours_without_ifs']}. IFS minus GFS at the same times: median {fs['ifs_minus_gfs_same_times_ms']['median']} m/s, "
          f"5th-95th percentile {fs['ifs_minus_gfs_same_times_ms']['p05']} to {fs['ifs_minus_gfs_same_times_ms']['p95']}, correlation {fs['ifs_minus_gfs_same_times_ms']['corr']}.\n")
    rows = []
    for r in ("A-cal", "A25", "A30"):
        for src in ("IFS", "GFS at the same 3-hourly times", "GFS hourly (primary)"):
            f, w = fs[r][src]["full"], fs[r][src]["without_25_march"]
            rows.append([r, src, c(f["warned"]), c(w["warned"]), leads(f["leads_h"]), c(f["run_hours_missed"]), c(f["alarm_days_without_run"])])
    table(["rule", "source", "warned", "without 25 March", "lead times, h", "run hours missed", "alarm fire-days with no run"], rows)
    table(["rule", "issue hours: both fire", "IFS only", "GFS hourly only", "neither"],
          [[r] + [fs[r]["issue_hours_state"][k] for k in ("both_fire", "ifs_only", "gfs_only", "neither")] for r in ("A-cal", "A25", "A30")])
    g = fs["gust_any_step_20"]
    print(f"Forecast gust >= 20 m/s at any step, fires {', '.join(g['fires'])}: IFS warned {c(g['IFS']['full']['warned'])}, "
          f"GFS hourly (k = 1) {c(g['GFS_hourly_k1']['full']['warned'])}; without 25 March {c(g['IFS']['without_25_march']['warned'])} and "
          f"{c(g['GFS_hourly_k1']['without_25_march']['warned'])}.\n")
    table(["25 March KST", "IFS 10fg m/s", "GFS gust m/s", "IFS 850 hPa m/s", "GFS 850 hPa m/s"],
          [[f"{h['kst_hour']:02d}", h["ifs_10fg"], h["gfs_gust_k1"], h["ifs_w850"], h["gfs_w850"]] for h in g["march25_10_to_16_kst"]])
    b = x["burden"]
    print(f"Burden: {b['point_days_all_three_complete']} of {b['point_days']} point-days complete in all three readings; "
          f"incomplete IFS point-days by season {b['incomplete_ifs_by_season']}.\n")
    rows = []
    for r in ("A-cal", "A25", "A30"):
        for s, v in b[r]["per_season"].items():
            rows.append([r, s, v["days"]] + [f"{v[k]['mean_per_point']:.1f}" for k in ("IFS", "GFS at the same 3-hourly times", "GFS hourly (primary)")])
    table(["rule", "season", "days", "IFS: alarm days per point", "GFS at the same times", "GFS hourly"], rows)
    table(["rule", "point-days: both", "IFS only", "GFS hourly only", "neither"],
          [[r] + [b[r]["point_days_ifs_vs_gfs_hourly"][k] for k in ("both", "ifs_only", "gfs_only", "neither")] for r in ("A-cal", "A25", "A30")])

x = n.get("height")
if isinstance(x, dict):
    print("## T11 Height of 850 hPa against the local ridge (m)\n")
    rows = [[v["name"], k, v["ridge_10km_m"], v["ridge_25km_m"], f"{v['hgt850_median_m']} ({v['hgt850_min_m']}-{v['hgt850_max_m']})",
             v["gap_to_ridge_10km_m"], v["gap_to_ridge_25km_m"], v["smallest_gap_25km_m"], "-".join(str(z) for z in (min(v["model_terrain_4pts_m"]), max(v["model_terrain_4pts_m"])))]
            for k, v in x["fires"].items()]
    rows += [[k, "burden point", v["ridge_10km_m"], v["ridge_25km_m"], f"{v['hgt850_median_m']} ({v['hgt850_min_m']}-{v['hgt850_max_m']})",
              v["gap_to_ridge_10km_m"], v["gap_to_ridge_25km_m"], v["smallest_gap_25km_m"], "-".join(str(z) for z in (min(v["model_terrain_4pts_m"]), max(v["model_terrain_4pts_m"])))]
             for k, v in x["points"].items()]
    table(["place", "id", "highest ground within 10 km", "within 25 km", "850 hPa height, median (range)", "850 hPa above the 10 km ridge",
           "above the 25 km ridge", "smallest gap, 25 km", "GFS model terrain at the 4 points"], rows)

x = n.get("S5_coarse")
if isinstance(x, dict):
    print("## T12 S5, COARSE: seasons 2019 and 2020 (GEFS control, 1 deg, leads 6/12/18 h)\n")
    g = x["gefs_2019_2020"]
    print(f"Point-days {g['point_days']}; wind complete {g['point_days_wind_complete']}; gust complete {g['point_days_gust_complete']}.\n")
    rows = []
    for r, per in g["wind_rules"].items():
        if r.startswith("G"):
            per = g["gust_rule_on_days_with_gust"]
        for s, v in per.items():
            rows.append([r, s, v["days"], v["alarm_point_days"], f"{v['mean_per_point']:.1f}", v["days_any_point"]])
    table(["rule (coarse)", "season", "days", "alarm point-days", "alarm days per point", "days with an alarm at any point"], rows)
    b = x["bridge_gfs_2021_2025"]
    print(f"Bridge: GFS 2021-2025 on the same {b['point_days']} point-days, coarse sampling against full resolution (alarm days per point):\n")
    rows = []
    for r in b["coarse"]:
        for s in b["coarse"][r]:
            rows.append([r, s, b["coarse"][r][s]["days"], f"{b['coarse'][r][s]['mean_per_point']:.1f}", f"{b['full_resolution'][r][s]['mean_per_point']:.1f}"])
    table(["rule", "season", "days", "coarse sampling", "full resolution (hourly, 0.25 deg)"], rows)

print("## Fetch\n")
for k, v in n["meta"]["fetch"].items():
    print(f"- {k}: {v}")
print("- reproduction check:", n["meta"]["reproduction_check"])
print("- burden:", n["burden_meta"])
