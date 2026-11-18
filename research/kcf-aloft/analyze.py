#!/usr/bin/env python3
"""All counts of kcf-aloft (PROTOCOL.md sections 3, 4 and 6) from the derived hour and day tables.

    python3 analyze.py --fire derived/fire_hours.csv.gz --burden derived/burden_days.csv.gz --out derived/analysis.json
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from rules import (A_CAL, COMBOS, RULES, SENS, clopper_pearson, either, fire_metrics, fires, garwood, sign_test)

HERE = Path(__file__).resolve().parent
KMA = HERE.parent / "kcf-gust" / "work" / "kma_asos_hourly.json"
STATIONS = {278: ("Uiseong", 36.3561, 128.6886), 136: ("Andong", 36.5729, 128.7073),
            276: ("Cheongsong", 36.4351, 129.0401), 277: ("Yeongdeok", 36.5333, 129.4094)}   # PROTOCOL section 3
MARCH25 = ("KFS_01", "2025-03-25")
FULL_SEASON_DAYS = {2019: 104, 2020: 105, 2021: 104, 2022: 104, 2023: 104, 2024: 105, 2025: 104}


def km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


# ------------------------------------------------------------------ rule states on a timeline
def spec_state(spec):
    col, thr, strict = spec
    return lambda tl: fires(tl[col].values, thr, strict)


def combo_state(a, b):
    return lambda tl: either(spec_state(RULES[a])(tl), spec_state(RULES[b])(tl))


class GObs:
    """Observed gust >= 20 m/s in the hour ending at t at a committed KMA station within `radius` km of the fire
    (kcf-gust amendment 3 conventions). NaN outside the committed stamps or with no station in range."""

    def __init__(self, radius=50.0):
        self.radius = radius
        self.g = {}
        for r in json.load(open(KMA)):
            v = float(r["gst_ws"])
            stamp = pd.Timestamp(r["tm"][:8] + "T" + r["tm"][8:10] + ":00")          # KST
            if v < 0:
                val = 0.0
            else:
                gm = r["gst_tm"].zfill(4)
                gt = stamp.normalize() + pd.Timedelta(hours=int(gm[:2]), minutes=int(gm[2:]))
                if gt > stamp:                                                       # a time just before midnight
                    gt -= pd.Timedelta(days=1)
                val = v if stamp - pd.Timedelta(hours=1) < gt <= stamp else 0.0      # a repeat of an earlier gust: dropped
            self.g[(stamp, int(r["stn"]))] = val

    def __call__(self, tl):
        out = []
        for t, lat, lon in zip(pd.to_datetime(tl.t_utc), tl.lat, tl.lon):
            stamp = t + pd.Timedelta(hours=9)
            vals = [self.g.get((stamp, s)) for s, (_, la, lo) in STATIONS.items()
                    if self.radius is None or km(lat, lon, la, lo) <= self.radius]
            vals = [v for v in vals if v is not None]
            out.append(math.nan if not vals else float(max(vals) >= 20.0))
        return np.array(out)


# ------------------------------------------------------------------ fire set
def per_day(fh, state_fn, timeline="primary", hours="all"):
    rows = []
    for fire, tl in fh[fh.timeline == timeline].groupby("fire", sort=True):
        tl = tl.sort_values("t_utc").reset_index(drop=True)
        if hours == "abstain":                      # S6: kcf-abstain's scored hours only
            tl["issue"] = tl.issue & tl.scored_abstain
            tl["run"] = tl.run & tl.issue
        if not tl.issue.any():
            continue
        for r in fire_metrics(tl, state_fn(tl)):
            r.update(fire=fire, name=tl.name.iloc[0])
            rows.append(r)
    return rows


def ci(k, n):
    lo, hi = clopper_pearson(k, n)
    return dict(k=int(k), n=int(n), ci95=[None if math.isnan(lo) else round(lo, 3), None if math.isnan(hi) else round(hi, 3)])


def summarise(rows, drop_day=None, drop_fire=None):
    rows = [r for r in rows if (r["fire"], r["kst_day"]) != drop_day and r["fire"] != drop_fire]
    run = [r for r in rows if r["run_hours"] > 0]
    ev = [r for r in run if r["state_known"]]
    norun = [r for r in rows if r["run_hours"] == 0]
    rh = sum(r["run_hours"] for r in run)
    unk = sum(r["run_hours_unknown"] for r in run)
    return dict(
        fires=len({r["fire"] for r in rows}), fire_days=len(rows),
        run_fire_days=len(run), fires_with_run=len({r["fire"] for r in run}),
        run_fire_days_state_unknown=len(run) - len(ev),
        warned=ci(sum(r["warned"] for r in ev), len(ev)),
        warned_1h_ahead=ci(sum(bool(r["warned"] and r["lead_h"] >= 1) for r in ev), len(ev)),
        warned_lapsed_12h=ci(sum(r["warned_lapsed"] for r in ev), len(ev)),
        leads_h=[r["lead_h"] for r in ev if r["warned"]],
        leads_h_since_ignition=[r["lead_h_since_ignition"] for r in ev if r["warned"]],
        run_hours=rh, run_hours_state_unknown=unk,
        run_hours_missed=ci(sum(r["run_hours_missed"] for r in run) - unk, rh - unk),
        alarm_days_without_run=ci(sum(r["alarm_no_run"] for r in norun), len(norun)),
        fires_all_run_days_warned=sum(all(r["warned"] for r in ev if r["fire"] == f) for f in {r["fire"] for r in ev}))


def compare(rows_a, rows_g, drop_day=None, drop_fire=None):
    """A against G on run fire-days: discordant counts, sign test, lead comparison on days warned by both."""
    key = lambda r: (r["fire"], r["kst_day"])
    keep = lambda r: r["run_hours"] > 0 and key(r) != drop_day and r["fire"] != drop_fire and r["state_known"]
    a = {key(r): r for r in rows_a if keep(r)}
    g = {key(r): r for r in rows_g if keep(r)}
    ks = sorted(set(a) & set(g))
    only_a = sum(a[k]["warned"] and not g[k]["warned"] for k in ks)
    only_g = sum(g[k]["warned"] and not a[k]["warned"] for k in ks)
    both = [k for k in ks if a[k]["warned"] and g[k]["warned"]]
    d = [a[k]["lead_h"] - g[k]["lead_h"] for k in both]
    capped = sum(a[k]["lead_h"] == 24 and g[k]["lead_h"] == 24 for k in both)
    return dict(run_fire_days=len(ks), warned_a=sum(a[k]["warned"] for k in ks), warned_g=sum(g[k]["warned"] for k in ks),
                warned_by_a_only=only_a, warned_by_g_only=only_g, warned_by_both=len(both),
                warned_by_neither=len(ks) - only_a - only_g - len(both), sign_test_p=round(sign_test(only_a, only_g), 4),
                lead_a_minus_g_h=d, a_earlier=sum(x > 0 for x in d), same=sum(x == 0 for x in d), g_earlier=sum(x < 0 for x in d),
                both_at_24h_cap=capped)


def verdicts(fh, name_a, fn_a, fn_g, timeline="primary", hours="all", against="G"):
    ra, rg = per_day(fh, fn_a, timeline, hours), per_day(fh, fn_g, timeline, hours)
    fires_ = sorted({r["fire"] for r in ra})
    full = compare(ra, rg)
    wo = compare(ra, rg, drop_day=MARCH25)
    lofo = {f: compare(ra, rg, drop_fire=f) for f in fires_}
    more = lambda c: c["warned_a"] > c["warned_g"]
    if full["warned_a"] <= full["warned_g"]:
        rel = "no better"
        dep = []
    elif more(wo) and all(more(c) for c in lofo.values()):
        rel, dep = "A warned more run fire-days than G", []
    else:
        dep = (["without 25 March"] if not more(wo) else []) + [f"without {f}" for f, c in lofo.items() if not more(c)]
        rel = "not robust"

    def earlier(c):
        d = c["lead_a_minus_g_h"]
        if not d:
            return "no run fire-day warned by both"
        if all(x >= 0 for x in d) and any(x > 0 for x in d):
            return "A earlier"
        if all(x <= 0 for x in d):
            return "no earlier"
        return "mixed"
    e_full, e_wo = earlier(full), earlier(wo)
    early = e_full if e_full == e_wo else f"depends on 25 March (with: {e_full}; without: {e_wo})"
    return dict(rule=name_a, against=against, full=full, without_25_march=wo, leave_one_fire_out=lofo,
                more_reliably=rel, more_reliably_fails_in=dep, earlier=early)


def pooled_hours(fh, state_fn, timeline="primary"):
    a = b = c = d = u = 0
    for _, tl in fh[fh.timeline == timeline].groupby("fire", sort=True):
        tl = tl.sort_values("t_utc").reset_index(drop=True)
        s = state_fn(tl)
        m = tl.issue.values
        run = tl.run.values[m]
        s = s[m]
        u += int(np.isnan(s).sum())
        a += int(((s == 1) & run).sum()); b += int(((s == 1) & ~run).sum())
        c += int(((s == 0) & run).sum()); d += int(((s == 0) & ~run).sum())
    return dict(fires_and_run=a, fires_no_run=b, silent_and_run=c, silent_no_run=d, state_unknown=u)


# ------------------------------------------------------------------ burden set
def burden_alarm(bd, spec):
    col, thr, strict = spec
    return (bd[col].values > thr) if strict else (bd[col].values >= thr)


def burden_counts(bd, alarm, excluded, mean_seasons=None):
    """bd: complete point-days. alarm: bool per row. excluded: set of (point, kst_day) with a fire-set run within 100 km."""
    d = bd.assign(alarm=alarm)
    d["false_alarm"] = d.alarm & ~d.apply(lambda r: (r.point, r.kst_day) in excluded, axis=1)
    out = dict(per_season={}, per_point={})
    for s, g in d.groupby("season"):
        days = g.groupby("kst_day").alarm.any()
        pp = g.groupby("point").alarm.sum()
        out["per_season"][int(s)] = dict(
            days_evaluated=int(g.kst_day.nunique()), full_season_days=FULL_SEASON_DAYS[int(s)],
            alarm_point_days=int(g.alarm.sum()), false_alarm_point_days=int(g.false_alarm.sum()),
            mean_alarm_days_per_point=round(float(g.alarm.sum()) / g.point.nunique(), 2),
            mean_false_alarm_days_per_point=round(float(g.false_alarm.sum()) / g.point.nunique(), 2),
            min_point=[pp.idxmin(), int(pp.min())], max_point=[pp.idxmax(), int(pp.max())],
            days_any_point=int(days.sum()), by_point={p: int(v) for p, v in pp.items()})
    seasons = sorted(out["per_season"])
    full = [s for s in seasons if out["per_season"][s]["days_evaluated"] == FULL_SEASON_DAYS[s]
            and (mean_seasons is None or s in mean_seasons)]
    out["complete_seasons"] = [s for s in seasons if out["per_season"][s]["days_evaluated"] == FULL_SEASON_DAYS[s]]
    npt = d.point.nunique()

    def mean_ci(total, units):
        lo, hi = garwood(total)
        return dict(total=int(total), units=units, mean=round(total / units, 2), ci95=[round(lo / units, 2), round(hi / units, 2)])
    f = d[d.season.isin(full)]
    out["full_seasons"] = full
    out["all_seasons_evaluated"] = seasons
    out["alarm_days_per_point_season"] = mean_ci(int(f.alarm.sum()), npt * len(full)) if full else None
    out["false_alarm_days_per_point_season"] = mean_ci(int(f.false_alarm.sum()), npt * len(full)) if full else None
    out["days_any_point_per_season"] = mean_ci(int(f.groupby(["season", "kst_day"]).alarm.any().sum()), len(full)) if full else None
    out["alarm_point_days_all_evaluated"] = int(d.alarm.sum())
    out["false_alarm_point_days_all_evaluated"] = int(d.false_alarm.sum())
    out["point_days_evaluated"] = int(len(d))
    for p, g in f.groupby("point"):
        out["per_point"][p] = mean_ci(int(g.alarm.sum()), len(full))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire", required=True)
    ap.add_argument("--burden", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    fh = pd.read_csv(a.fire, low_memory=False)
    for c in ("pre", "issue", "run", "scored_abstain", "in_gap"):
        fh[c] = fh[c].astype(bool)
    gpath = Path(a.fire).parent / "gobs_fire_hours.csv.gz"
    have_gobs = gpath.exists()
    if have_gobs:                                  # G-obs from KMA stations (amendment 2), primary timeline only
        g = pd.read_csv(gpath)[["fire", "t_utc", "gobs", "gobs_upper"]].rename(columns={"gobs": "gobs_kma"})
        g["timeline"] = "primary"
        fh = fh.merge(g, on=["fire", "t_utc", "timeline"], how="left")
    bd_all = pd.read_csv(a.burden)
    bd = bd_all[bd_all.hours_evaluated == 24].reset_index(drop=True)

    # burden point-days that are not false alarms: a fire-set run hour that KST day within 100 km of the point
    from burden import POINTS
    runs = fh[(fh.timeline == "primary") & fh.run]
    excluded = set()
    for r in runs.itertuples(index=False):
        for p, (_, la, lo) in POINTS.items():
            if km(r.lat, r.lon, la, lo) <= 100.0:
                excluded.add((p, r.kst_day))

    # S-match: the 850 hPa threshold at which A fires on as many burden point-days as G (0.1 m/s grid)
    n_g = int(burden_alarm(bd, RULES["G"]).sum())
    match = None
    if n_g > 0:
        for thr in np.round(np.arange(5.0, 60.0001, 0.1), 1):
            if int((bd.w_k1.values >= thr).sum()) <= n_g:
                match = float(thr)
                break
    fns = {n: spec_state(s) for n, s in RULES.items()}
    fns.update({n: combo_state(x, y) for n, (x, y) in COMBOS.items()})
    specs = dict(RULES)
    if match is not None:
        specs["A-match"] = ("w_k1", match, False)
        fns["A-match"] = spec_state(specs["A-match"])
    gobs, gobs4 = GObs(50.0), GObs(None)
    if have_gobs:
        fns = {"G": fns["G"], "G-obs": (lambda tl: tl.gobs_kma.values.astype(float)), **{k: v for k, v in fns.items() if k != "G"}}

    out = dict(s_match=dict(g_alarm_point_days=n_g, threshold_ms=match,
                            a_alarm_point_days=None if match is None else int((bd.w_k1.values >= match).sum())),
               excluded_point_days=sorted([list(x) for x in excluded]), fire_set={}, burden={}, verdicts={},
               sensitivity={}, sweep={}, pooled_hours={}, gobs={})

    def block(fn, timeline="primary", hours="all"):
        rows = per_day(fh, fn, timeline, hours)
        fires_ = sorted({r["fire"] for r in rows})
        return dict(full=summarise(rows), without_25_march=summarise(rows, drop_day=MARCH25),
                    leave_one_fire_out={f: summarise(rows, drop_fire=f) for f in fires_}, fire_days=rows)

    for n, fn in fns.items():
        out["fire_set"][n] = block(fn)
        out["pooled_hours"][n] = pooled_hours(fh, fn)
        if n == "G-obs":
            try:
                gb = pd.read_csv(Path(a.fire).parent / "gobs_burden_days.csv.gz")
                gb = gb[gb.hours_evaluated == 24].reset_index(drop=True)
            except pd.errors.EmptyDataError:
                gb = pd.DataFrame()
            if len(gb):
                out["burden"][n] = burden_counts(gb, gb.gobs_max_ms.values >= 20.0, excluded, mean_seasons=out["burden"]["G"]["full_seasons"])
            else:                                   # burden not fetched yet: NOT RUN
                out["burden"][n] = dict(per_season={}, per_point={}, full_seasons=[], all_seasons_evaluated=[], complete_seasons=[],
                                        alarm_days_per_point_season=None, false_alarm_days_per_point_season=None,
                                        days_any_point_per_season=None, alarm_point_days_all_evaluated=0,
                                        false_alarm_point_days_all_evaluated=0, point_days_evaluated=0)
            continue
        alarm = (burden_alarm(bd, specs[n]) if n in specs else
                 burden_alarm(bd, RULES[COMBOS[n][0]]) | burden_alarm(bd, RULES[COMBOS[n][1]]))
        out["burden"][n] = burden_counts(bd, alarm, excluded)
    out["fire_set_choi_timeline"] = {n: {k: v for k, v in block(fn, timeline="choi").items() if k != "leave_one_fire_out"}
                                     for n, fn in fns.items() if n != "G-obs"}
    out["fire_set_abstain_hours"] = {n: {k: v for k, v in block(fn, hours="abstain").items() if k != "leave_one_fire_out"}
                                     for n, fn in fns.items()}
    for n in fns:
        if n not in ("G", "G-obs"):
            out["verdicts"][n] = verdicts(fh, n, fns[n], fns["G"])
    if have_gobs:                                  # descriptive (amendment 2): every forecast rule against G-obs
        out["against_gobs"] = {n: verdicts(fh, n, fns[n], fns["G-obs"], against="G-obs") for n in fns if n != "G-obs"}
        up = lambda tl: tl.gobs_upper.values.astype(float)      # post hoc bound: hours hidden by an earlier gust count as firing
        out["gobs_upper_bound"] = dict(block(up), pooled_hours=pooled_hours(fh, up),
                                       against=dict(G=verdicts(fh, "G", fns["G"], up, against="G-obs upper bound")))
    # G-obs: KFS_01 only, PARTIAL (four committed stations, 22-26 March 2025)
    k1 = fh[fh.fire == "KFS_01"]
    for label, fn in (("within_50km", gobs), ("all_four_stations", gobs4)):
        rows = per_day(k1, fn)
        out["gobs"][label] = dict(full=summarise(rows), without_25_march=summarise(rows, drop_day=MARCH25), fire_days=rows,
                                  pooled_hours=pooled_hours(k1, fn))
    out["gobs"]["same_fire_other_rules"] = {n: dict(full=summarise(per_day(k1, fn)),
                                                    without_25_march=summarise(per_day(k1, fn), drop_day=MARCH25))
                                            for n, fn in fns.items()}
    # sensitivity table
    for n, s in SENS.items():
        fn = spec_state(s)
        rows = per_day(fh, fn)
        out["sensitivity"][n] = dict(spec=dict(level=s[0], threshold=s[1], strict=s[2]), full=summarise(rows),
                                     without_25_march=summarise(rows, drop_day=MARCH25),
                                     burden=burden_counts(bd, burden_alarm(bd, s), excluded))
    # threshold sweep (descriptive)
    for label, col, lo, hi in (("gust_k2", "g_k2", 10, 30), ("gust_k1", "g_k1", 10, 30), ("w850_k1", "w_k1", 10, 40)):
        sw = []
        for thr in range(lo, hi + 1):
            s = (col, float(thr), False)
            f = summarise(per_day(fh, spec_state(s)))
            w = summarise(per_day(fh, spec_state(s)), drop_day=MARCH25)
            b = burden_counts(bd, burden_alarm(bd, s), excluded)
            sw.append(dict(threshold=thr, warned=f["warned"]["k"], run_fire_days=f["warned"]["n"],
                           warned_without_25_march=w["warned"]["k"], run_hours_missed=f["run_hours_missed"]["k"],
                           run_hours=f["run_hours_missed"]["n"], alarm_days_without_run=f["alarm_days_without_run"]["k"],
                           no_run_fire_days=f["alarm_days_without_run"]["n"],
                           burden_alarm_days_per_point_season=b["alarm_days_per_point_season"]["mean"] if b["alarm_days_per_point_season"] else None,
                           burden_alarm_point_days=b["alarm_point_days_all_evaluated"]))
        out["sweep"][label] = sw
    # 25 March 2025, hour by hour (KFS_01, primary timeline)
    d = fh[(fh.fire == "KFS_01") & (fh.timeline == "primary")].sort_values("t_utc").reset_index(drop=True)
    go = gobs(d)
    st = {n: fns[n](d) for n in ("G", "A-cal", "A25", "A30")}
    gk = fns["G-obs"](d) if have_gobs else np.full(len(d), np.nan)
    out["march25_hours"] = [
        dict(kst_hour=int(r.kst_hour), cycle_utc=r.cycle_utc, gust_any_hour_ms=round(r.g_k1, 1), gust_two_hours_ms=round(r.g_k2, 1),
             w850_ms=round(r.w_k1, 1), G=int(st["G"][i]), A_cal=int(st["A-cal"][i]), A25=int(st["A25"][i]), A30=int(st["A30"][i]),
             G_obs=None if math.isnan(go[i]) else int(go[i]), G_obs_all_stations=None if math.isnan(gk[i]) else int(gk[i]), reach5_km=None if pd.isna(r.reach5_km) else round(r.reach5_km, 1),
             run=bool(r.run))
        for i, r in enumerate(d.itertuples(index=False)) if r.kst_day == "2025-03-25"]
    out["burden_meta"] = dict(
        point_days_total=int(len(bd_all)), point_days_complete=int(len(bd)),
        incomplete_by_season={int(s): int(((g.hours_evaluated < 24)).sum()) for s, g in bd_all.groupby("season")},
        first_complete_day_by_season={int(s): g[g.hours_evaluated == 24].kst_day.min() for s, g in bd_all.groupby("season")},
        days_complete_by_season={int(s): int(g[g.hours_evaluated == 24].kst_day.nunique()) for s, g in bd_all.groupby("season")})
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    print("S-match:", out["s_match"])
    for n in fns:
        f = out["fire_set"][n]["full"]
        b = out["burden"][n]["alarm_days_per_point_season"]
        print(f"{n:8s} warned {f['warned']['k']}/{f['warned']['n']}  >=1h {f['warned_1h_ahead']['k']}  leads {f['leads_h']}  "
              f"missed run hours {f['run_hours_missed']['k']}/{f['run_hours_missed']['n']}  alarm no-run days "
              f"{f['alarm_days_without_run']['k']}/{f['alarm_days_without_run']['n']}  burden/point-season {b['mean'] if b else None}")


if __name__ == "__main__":
    main()
