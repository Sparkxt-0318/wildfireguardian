#!/usr/bin/env python3
"""G-obs from KMA ASOS hourly gusts for every fire and for the burden points (PROTOCOL.md section 3, amendment 2).

    python3 gobs.py --kma WORK/kma_hours.jsonl --fire derived/fire_hours.csv.gz --out-dir derived

Writes derived/kma_gust_records.csv.gz (every gust record fetched), derived/kma_hours_fetched.csv.gz (every stamp
with the number of stations that reported), derived/gobs_fire_hours.csv.gz, derived/gobs_burden_days.csv.gz and
derived/gobs_quality.json.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from burden import POINTS, season_days

RADIUS_KM = 50.0
THRESHOLD = 20.0


def km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * np.arcsin(np.sqrt(a))


def in_hour(stamp, gst_tm):
    """Is the gust time (HHMM, KST) inside (stamp - 1 h, stamp]?  (kcf-gust amendment 3)"""
    gm = str(gst_tm).zfill(4)
    try:
        gt = stamp.normalize() + pd.Timedelta(hours=int(gm[:2]), minutes=int(gm[2:]))
    except ValueError:
        return False
    if gt > stamp:
        gt -= pd.Timedelta(days=1)
    return stamp - pd.Timedelta(hours=1) < gt <= stamp


class Obs:
    def __init__(self, path, stations_csv):
        st = pd.read_csv(stations_csv)
        self.st = {int(r.stn): (float(r.lat), float(r.lon)) for r in st.itertuples()}
        self.present, self.gust, self.raw, self.failed, self.masked = {}, {}, [], set(), {}
        for l in open(path):
            r = json.loads(l)
            if r.get("failed"):
                self.failed.add(r["tm"])
                continue
            stamp = pd.Timestamp(r["tm"][:8] + "T" + r["tm"][8:10] + ":00")
            self.present[stamp] = set(r["stn"])
            g, m = {}, set()
            for stn, ws, tm in r["gust"]:
                ok = in_hour(stamp, tm)
                self.raw.append((r["tm"], stn, ws, tm, int(ok)))
                if ok:                              # a record timed outside its hour repeats an earlier gust: dropped
                    g[stn] = max(ws, g.get(stn, 0.0))
                elif ws >= THRESHOLD:               # the row shows an earlier, larger gust: the hour's own gust is hidden
                    m.add(stn)
            self.gust[stamp] = g
            self.masked[stamp] = m
        self.failed -= {s.strftime("%Y%m%d%H00") for s in self.present}
        self._near = {}

    def near(self, lat, lon):
        k = (round(lat, 4), round(lon, 4))
        if k not in self._near:
            self._near[k] = [s for s, (la, lo) in self.st.items() if km(lat, lon, la, lo) <= RADIUS_KM]
        return self._near[k]

    def at(self, stamp, lat, lon):
        """(stations within 50 km with a row, largest in-hour gust among them; 0 = no record) or (0, nan)."""
        p = self.present.get(stamp)
        if p is None:
            return 0, math.nan
        ss = [s for s in self.near(lat, lon) if s in p]
        if not ss:
            return 0, math.nan
        g = self.gust[stamp]
        return len(ss), max([g.get(s, 0.0) for s in ss])

    def hidden(self, stamp, lat, lon):
        """True if a station within 50 km shows, at this stamp, an earlier gust >= 20 m/s in place of the hour's own."""
        return bool(self.masked.get(stamp, set()) & set(self.near(lat, lon)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kma", required=True)
    ap.add_argument("--fire", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seasons", nargs="*", type=int, default=[2019, 2020, 2021, 2022, 2023, 2024, 2025])
    a = ap.parse_args()
    D = Path(a.out_dir)
    ob = Obs(a.kma, D / "kma_asos_stations.csv")
    raw = pd.DataFrame(ob.raw, columns=["tm_kst", "stn", "gst_ws", "gst_tm", "inside_hour"]).sort_values(["tm_kst", "stn"])
    raw.to_csv(D / "kma_gust_records.csv.gz", index=False)
    pd.DataFrame(sorted((s.strftime("%Y%m%d%H00"), len(p)) for s, p in ob.present.items()),
                 columns=["tm_kst", "stations_reporting"]).to_csv(D / "kma_hours_fetched.csv.gz", index=False)

    # ---- fire set (primary timeline)
    fh = pd.read_csv(a.fire, low_memory=False)
    f = fh[fh.timeline == "primary"][["fire", "t_utc", "lat", "lon"]].copy()
    v = [ob.at(pd.Timestamp(t) + pd.Timedelta(hours=9), la, lo) for t, la, lo in zip(f.t_utc, f.lat, f.lon)]
    f["stations_50km"] = [x[0] for x in v]
    f["gust_50km_ms"] = [x[1] for x in v]
    f["gobs"] = np.where(f.gust_50km_ms.isna(), np.nan, (f.gust_50km_ms >= THRESHOLD).astype(float))
    hid = np.array([ob.hidden(pd.Timestamp(t) + pd.Timedelta(hours=9), la, lo) for t, la, lo in zip(f.t_utc, f.lat, f.lon)])
    f["hidden_by_earlier_gust"] = (hid & (f.gobs == 0)).astype(int)
    f["gobs_upper"] = np.where(f.gobs.isna(), np.nan, ((f.gobs == 1) | hid).astype(float))   # hidden hours counted as firing
    f["nearest_km"] = [round(min(km(la, lo, s[0], s[1]) for s in ob.st.values()), 1) for la, lo in zip(f.lat, f.lon)]
    f.drop(columns=["lat", "lon"]).to_csv(D / "gobs_fire_hours.csv.gz", index=False)

    # ---- burden set
    rows = []
    for year in a.seasons:
        for day in season_days(year):
            stamps = [day + pd.Timedelta(hours=k) for k in range(24)]
            if not any(s in ob.present for s in stamps):
                continue                                        # season not fetched
            for name, (prov, lat, lon) in POINTS.items():
                vv = [ob.at(s, lat, lon) for s in stamps]
                g = [x[1] for x in vv if not math.isnan(x[1])]
                rows.append(dict(season=year, kst_day=day.strftime("%Y-%m-%d"), point=name, hours_evaluated=len(g),
                                 stations_50km=len(ob.near(lat, lon)), gobs_max_ms=max(g) if g else math.nan,
                                 firing_hours=int(sum(x >= THRESHOLD for x in g)),
                                 hidden_hours=int(sum(ob.hidden(s, lat, lon) for s in stamps))))
    bd = pd.DataFrame(rows)
    bd.to_csv(D / "gobs_burden_days.csv.gz", index=False)

    q = dict(
        hours_fetched=len(ob.present), hours_failed=sorted(ob.failed),
        station_hours=int(sum(len(p) for p in ob.present.values())), gust_records=int(len(raw)),
        share_of_station_hours_with_a_record=round(len(raw) / max(1, sum(len(p) for p in ob.present.values())), 4),
        smallest_recorded_gust_ms=float(raw.gst_ws.min()) if len(raw) else None,
        records_timed_outside_their_hour=int((raw.inside_hour == 0).sum()),
        records_not_whole_ms=int((raw.gst_ws % 1 != 0).sum()),
        records_20_or_more_inside_hour=int(((raw.gst_ws >= THRESHOLD) & (raw.inside_hour == 1)).sum()),
        records_20_or_more_outside_hour=int(((raw.gst_ws >= THRESHOLD) & (raw.inside_hour == 0)).sum()),
        stamp_hours_of_outside_records={k: int(v) for k, v in raw[raw.inside_hour == 0].tm_kst.astype(str).str[8:10].value_counts().sort_index().items()},
        fire_hours_hidden_by_earlier_gust=int(f.hidden_by_earlier_gust.sum()),
        burden_alarm_days_only_if_hidden_hours_count=int(((bd.gobs_max_ms < THRESHOLD) & (bd.hidden_hours > 0) & (bd.hours_evaluated == 24)).sum()) if len(bd) else 0,
        stations_within_50km_of_points={p: sorted(ob.near(la, lo)) for p, (_, la, lo) in POINTS.items()},
        fire_hours=int(len(f)), fire_hours_unknown=int(f.gobs.isna().sum()),
        fire_stations_50km_min_max=[int(f.stations_50km.min()), int(f.stations_50km.max())],
        burden_point_days=int(len(bd)), burden_point_days_complete=int((bd.hours_evaluated == 24).sum()) if len(bd) else 0,
        burden_days_by_season={int(s): int(g.kst_day.nunique()) for s, g in bd.groupby("season")} if len(bd) else {})
    json.dump(q, open(D / "gobs_quality.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in q.items() if k != "stations_within_50km_of_points"}, indent=1))
    print(q["stations_within_50km_of_points"])


if __name__ == "__main__":
    main()
