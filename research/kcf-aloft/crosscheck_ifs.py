#!/usr/bin/env python3
"""Second model (PROTOCOL.md section 5): rule A read from ECMWF IFS open data, beside GFS thinned to the same times.

    python3 crosscheck_ifs.py --ifs NWP_DIR/ifs_KOR --gfs NWP_DIR/gfs_KOR --fire derived/fire_hours.csv.gz \
        --burden derived/burden_days.csv.gz --out derived/ifs_crosscheck.json

Same cycle rule as GFS (latest 00/06/12/18 UTC cycle at least 5 h old), 3-hourly valid times inside (t, t + 8 h],
the four points of the model's own lattice cell around the place. A cross-check only: it enters no verdict.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from analyze import MARCH25, per_day, summarise
from burden import POINTS, season_days
from rules import A_CAL, GUST, U850, V850, Store, cycle_of, fires

STEPS = (6, 9, 12, 15, 18)
RULES_A = {"A-cal": (A_CAL, True), "A25": (25.0, False), "A30": (30.0, False)}
IFS_START = pd.Timestamp("2023-01-18")


class IfsStore(Store):
    def load_ifs(self, key):
        p = self.d / (key + ".npz")
        if not p.exists():
            return None
        z = np.load(p)
        return z["arr"], z["steps"], z["lat"], z["lon"], float(z["res"])


def read(ifs, gfs, cache, t, lat, lon):
    """(IFS max 850 wind, IFS max 10fg, GFS max 850 wind at the same valid times, GFS max gust at them)."""
    t = pd.Timestamp(t)
    c = cycle_of(t)
    key = c.strftime("%Y%m%d%H")
    steps = [s for s in STEPS if t < c + pd.Timedelta(hours=s) <= t + pd.Timedelta(hours=8)]
    out = [math.nan] * 4
    if key not in cache:
        cache[key] = ifs.load_ifs(key)
    z = cache[key]
    if z is not None:
        arr, st, la, lo, res = z
        i = int(math.floor((lat - la[0]) / res + 1e-9))
        j = int(math.floor((lon - lo[0]) / res + 1e-9))
        si = [int(np.flatnonzero(st == s)[0]) for s in steps]
        b = arr[si][:, :, i:i + 2, j:j + 2].astype(float)
        w = np.hypot(b[:, 0], b[:, 1])
        if not np.isnan(w).any():
            out[0] = float(w.max())
        if not np.isnan(b[:, 2]).any():
            out[1] = float(b[:, 2].max())
    g = gfs.load(key)
    if g is not None:
        arr, leads, la, lo = g
        i = int(math.floor((lat - la[0]) / 0.25 + 1e-9))
        j = int(math.floor((lon - lo[0]) / 0.25 + 1e-9))
        li = [int(np.flatnonzero(leads == s)[0]) for s in steps]
        b = arr[li][:, :, i:i + 2, j:j + 2].astype(float)
        w = np.hypot(b[:, U850], b[:, V850])
        if not np.isnan(w).any():
            out[2] = float(w.max())
        if not np.isnan(b[:, GUST]).any():
            out[3] = float(b[:, GUST].max())
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ifs", required=True)
    ap.add_argument("--gfs", required=True)
    ap.add_argument("--fire", required=True)
    ap.add_argument("--burden", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seasons", nargs="*", type=int, default=[2023, 2024, 2025])
    a = ap.parse_args()
    ifs, gfs, cache = IfsStore(a.ifs), Store(a.gfs), {}
    here = Path(a.out).parent
    out = dict(label="cross-check; enters no verdict", fire_set={}, burden={})

    # ---------------- fire set: fires from 2023-01-18 on
    fh = pd.read_csv(a.fire, low_memory=False)
    for c in ("pre", "issue", "run", "scored_abstain", "in_gap"):
        fh[c] = fh[c].astype(bool)
    fh = fh[fh.timeline == "primary"].copy()
    fh["t"] = pd.to_datetime(fh.t_utc)
    first = fh.groupby("fire").t.min()
    use = sorted(first[first >= IFS_START].index)
    out["fire_set"]["fires_with_ifs"] = use
    out["fire_set"]["fires_without_ifs"] = sorted(set(fh.fire) - set(use))
    f = fh[fh.fire.isin(use)].copy()
    v = np.array([read(ifs, gfs, cache, r.t, r.lat, r.lon) for r in f.itertuples(index=False)])
    f["ifs_w"], f["ifs_fg"], f["gfs3h_w"], f["gfs3h_g"] = v.T
    f.drop(columns="t").to_csv(here / "ifs_fire_hours.csv.gz", index=False)
    iss = f[f.issue]
    out["fire_set"]["issue_hours"] = int(len(iss))
    out["fire_set"]["issue_hours_without_ifs"] = int(iss.ifs_w.isna().sum())
    out["fire_set"]["ifs_minus_gfs_same_times_ms"] = dict(
        median=round(float((iss.ifs_w - iss.gfs3h_w).median()), 2), p05=round(float((iss.ifs_w - iss.gfs3h_w).quantile(0.05)), 2),
        p95=round(float((iss.ifs_w - iss.gfs3h_w).quantile(0.95)), 2),
        corr=round(float(np.corrcoef(iss.ifs_w.dropna(), iss.gfs3h_w[iss.ifs_w.notna()])[0, 1]), 3))
    srcs = {"IFS": "ifs_w", "GFS at the same 3-hourly times": "gfs3h_w", "GFS hourly (primary)": "w_k1"}
    for rule, (thr, strict) in RULES_A.items():
        blk = {}
        for label, col in srcs.items():
            rows = per_day(f, lambda tl, col=col: fires(tl[col].values, thr, strict))
            blk[label] = dict(full=summarise(rows), without_25_march=summarise(rows, drop_day=MARCH25),
                              run_fire_days=[dict(fire=r["fire"], kst_day=r["kst_day"], warned=r["warned"], lead_h=r["lead_h"],
                                                  first_run_kst_hour=r["first_run_kst_hour"]) for r in rows if r["run_hours"] > 0])
        si = fires(iss.ifs_w.values, thr, strict)
        sg = fires(iss.w_k1.values, thr, strict)
        ok = ~np.isnan(si) & ~np.isnan(sg)
        blk["issue_hours_state"] = dict(both_fire=int(((si == 1) & (sg == 1) & ok).sum()), ifs_only=int(((si == 1) & (sg == 0) & ok).sum()),
                                        gfs_only=int(((si == 0) & (sg == 1) & ok).sum()), neither=int(((si == 0) & (sg == 0) & ok).sum()))
        out["fire_set"][rule] = blk
    # the forecast gust: IFS 10fg (3 h maximum, any step) against GFS, 2025 fires only
    g25 = iss[iss.ifs_fg.notna()]
    rows_i = per_day(f[f.fire.isin(sorted(g25.fire.unique()))], lambda tl: fires(tl.ifs_fg.values, 20.0))
    rows_g = per_day(f[f.fire.isin(sorted(g25.fire.unique()))], lambda tl: fires(tl.g_k1.values, 20.0))
    out["fire_set"]["gust_any_step_20"] = dict(
        fires=sorted(g25.fire.unique()), note="IFS 10fg is the maximum gust of the previous 3 h; GFS GUST is hourly; k = 1 form",
        IFS=dict(full=summarise(rows_i), without_25_march=summarise(rows_i, drop_day=MARCH25)),
        GFS_hourly_k1=dict(full=summarise(rows_g), without_25_march=summarise(rows_g, drop_day=MARCH25)),
        march25_10_to_16_kst=[dict(kst_hour=int(r.kst_hour), ifs_10fg=round(r.ifs_fg, 1), gfs_gust_k1=round(r.g_k1, 1),
                                   ifs_w850=round(r.ifs_w, 1), gfs_w850=round(r.w_k1, 1))
                              for r in f[(f.fire == "KFS_01") & (f.kst_day == "2025-03-25") & f.kst_hour.between(10, 16)].itertuples()])

    # ---------------- burden set
    bd = pd.read_csv(a.burden)
    rows = []
    for year in a.seasons:
        for day in season_days(year):
            hours = [day - pd.Timedelta(hours=9) + pd.Timedelta(hours=k) for k in range(24)]
            for name, (prov, lat, lon) in POINTS.items():
                vv = np.array([read(ifs, gfs, cache, t, lat, lon) for t in hours])
                rows.append(dict(season=year, kst_day=day.strftime("%Y-%m-%d"), point=name,
                                 ifs_hours=int(np.isfinite(vv[:, 0]).sum()), gfs3h_hours=int(np.isfinite(vv[:, 2]).sum()),
                                 ifs_w=round(float(np.nanmax(vv[:, 0])), 4) if np.isfinite(vv[:, 0]).any() else math.nan,
                                 gfs3h_w=round(float(np.nanmax(vv[:, 2])), 4) if np.isfinite(vv[:, 2]).any() else math.nan))
        cache.clear()
        print("burden", year, flush=True)
    ib = pd.DataFrame(rows).merge(bd[["season", "kst_day", "point", "hours_evaluated", "w_k1"]], on=["season", "kst_day", "point"])
    ib.to_csv(here / "ifs_burden_days.csv.gz", index=False)
    ok = ib[(ib.ifs_hours == 24) & (ib.gfs3h_hours == 24) & (ib.hours_evaluated == 24)]
    out["burden"]["point_days"] = int(len(ib))
    out["burden"]["point_days_all_three_complete"] = int(len(ok))
    out["burden"]["incomplete_ifs_by_season"] = {int(s): int((g.ifs_hours < 24).sum()) for s, g in ib.groupby("season")}
    for rule, (thr, strict) in RULES_A.items():
        st = {k: (ok[c].values > thr) if strict else (ok[c].values >= thr) for k, c in srcs.items()}
        blk = dict(per_season={})
        for s in sorted(ok.season.unique()):
            m = (ok.season == s).values
            npt = ok[m].point.nunique()
            blk["per_season"][int(s)] = dict(days=int(ok[m].kst_day.nunique()),
                                             **{k: dict(alarm_point_days=int(v[m].sum()), mean_per_point=round(float(v[m].sum()) / npt, 2))
                                                for k, v in st.items()})
        i, g = st["IFS"], st["GFS hourly (primary)"]
        blk["point_days_ifs_vs_gfs_hourly"] = dict(both=int((i & g).sum()), ifs_only=int((i & ~g).sum()),
                                                   gfs_only=int((~i & g).sum()), neither=int((~i & ~g).sum()))
        g3 = st["GFS at the same 3-hourly times"]
        blk["point_days_ifs_vs_gfs_same_times"] = dict(both=int((i & g3).sum()), ifs_only=int((i & ~g3).sum()),
                                                       gfs_only=int((~i & g3).sum()), neither=int((~i & ~g3).sum()))
        out["burden"][rule] = blk
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in out["fire_set"].items() if k in ("fires_with_ifs", "issue_hours", "issue_hours_without_ifs",
                                                                         "ifs_minus_gfs_same_times_ms")}, indent=1))


if __name__ == "__main__":
    main()
