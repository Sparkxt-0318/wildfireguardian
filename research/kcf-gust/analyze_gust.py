"""Apply research/kcf-gust/PROTOCOL.md (frozen). ERA5 only -> PROVISIONAL. Writes work/gust_hours.json and gust_hours.csv."""
import json, csv
from datetime import datetime, timedelta
E = json.load(open("work/era5_gusts.json"))
N = json.load(open("../kcf-margin/numbers.json"))
PTS = list(E)
D0 = datetime(2025, 3, 25)  # KST midnight
def stamp(H):  # KST stamp H on 25 March -> UTC iso hour string
    return (D0 + timedelta(hours=H - 9)).strftime("%Y-%m-%dT%H:00")
idx = {p: {t: g for t, g in zip(E[p]["time_utc"], E[p]["gust_ms"])} for p in PTS}
def g(p, H): return idx[p][stamp(H)]
def cls(x): return "<10" if x < 10 else "10-20" if x < 20 else ">=20"
FR = {"<10": (2.6, 3.0), "10-20": (4.7, 5.9), ">=20": (8.6, 12.0)}  # frozen, PROTOCOL
# check against numbers.json
for r in N["table"]:
    if r["fire_set"] == "all28" and abs(r["alpha"] - .1) < 1e-9 and r["cls"].startswith("gust"):
        c = {"gust<10": "<10", "gust10-20": "10-20", "gust>=20": ">=20"}.get(r["cls"].replace(" ", "").replace("m/s", "").replace("_", ""), None)
        print("numbers.json", r["cls"], r["h"], round(r["R_km"], 2), "n_fires", r.get("n_fires"))
hy = {(x["kst_hour"], x["h"]): x for x in N["gyeongbuk_stress"]["hourly"]}
rows = []
for H in range(25):
    r = dict(kst_stamp=H, **{p: g(p, H) for p in PTS})
    r["fire_wide_max"] = max(r[p] for p in PTS); r["class_at_stamp"] = cls(r["fire_wide_max"])
    r["point_classes"] = {p: cls(r[p]) for p in PTS}
    for h in (5, 8):
        if H < 24 and H + h <= 24 + 9:  # stamps up to 33 exist? data to 26 Mar 23 UTC = 25 Mar... guard below
            pass
        try:
            m = {p: max(g(p, k) for k in range(H + 1, H + h + 1)) for p in PTS}
        except KeyError:
            m = None
        if m is None or H == 24:
            r[f"fwd{h}"] = None; continue
        fw = max(m.values()); c = cls(fw); R = FR[c][0 if h == 5 else 1]
        x = hy.get((H, h)); reach = x["reach_km"] if x else None
        r[f"fwd{h}"] = dict(max_by_point=m, fire_wide_max=fw, cls=c, R_km=R, reach_km=reach, complete=bool(x and x["complete"]),
                            held=(None if not (x and x["complete"]) else reach <= R),
                            prior_class=x["prior_class"] if x else None, R_prior_class_0_1=x["R_class_0.1"] if x else None,
                            held_prior_class=(None if not (x and x["complete"]) else not x["miss_class_0.1"]))
    rows.append(r)
json.dump(rows, open("work/gust_hours.json", "w"), indent=1)
for r in rows:
    f5, f8 = r["fwd5"], r["fwd8"]
    print(f'{r["kst_stamp"]:02d} stamp {r["fire_wide_max"]:5.1f} {r["class_at_stamp"]:>6} | ' + " ".join(f"{r[p]:5.1f}" for p in PTS) +
          (f' | 5h {f5["fire_wide_max"]:5.1f} {f5["cls"]:>5} R{f5["R_km"]:4.1f} reach {f5["reach_km"]} cmp={f5["complete"]} held={f5["held"]}' if f5 else " | -") +
          (f' | 8h {f8["fire_wide_max"]:5.1f} {f8["cls"]:>5} R{f8["R_km"]:4.1f} reach {f8["reach_km"]:.1f} cmp={f8["complete"]} held={f8["held"]}' if f8 else ""))
