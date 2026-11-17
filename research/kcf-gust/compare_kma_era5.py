"""Side-by-side: KMA ASOS daily max instantaneous gust (data.go.kr) vs ERA5 daily max (KST day), 22-26 March 2025. Writes work/kma_vs_era5.md"""
import json
from datetime import datetime, timedelta
K = json.load(open("work/kma_datagokr.json")); E = json.load(open("work/era5_gusts.json"))
PTS = ["Uiseong", "Andong", "Cheongsong", "Yeongyang", "Yeongdeok"]
DAYS = ["2025-03-22", "2025-03-23", "2025-03-24", "2025-03-25", "2025-03-26"]
def era5_day(p):
    out = {}
    for t, g in zip(E[p]["time_utc"], E[p]["gust_ms"]):
        k = datetime.fromisoformat(t) + timedelta(hours=9)      # KST stamp (end of the hour)
        d = (k - timedelta(hours=1)).strftime("%Y-%m-%d")       # stamp 01:00..24:00 -> that KST day
        if d not in out or g > out[d][0]: out[d] = (g, k.strftime("%H:%M"))
    return out
rows = ["| point | KMA ASOS station | day | KMA max instantaneous gust m/s (time KST) | ERA5 max gust m/s (stamp KST) | ERA5 minus KMA |", "|---|---|---|---|---|---|"]
for p in PTS:
    e = era5_day(p); k = K[p]
    for d in DAYS:
        if not k.get("daily"):
            rows.append(f"| {p} | none assumed (no ASOS id; AWS needs apihub) | {d} | - | {e[d][0]:.1f} ({e[d][1]}) | - |"); continue
        r = next(x for x in k["daily"] if x["tm"] == d); v = float(r["maxInsWs"]); h = r["maxInsWsHrmt"]
        rows.append(f"| {p} | {r['stnNm']} ({k['stn']}) | {d} | {v:.1f} ({h[:2]}:{h[2:]}) | {e[d][0]:.1f} ({e[d][1]}) | {e[d][0]-v:+.1f} |")
open("work/kma_vs_era5.md", "w").write("\n".join(rows))
hr = ["| KST hour | " + " | ".join(p for p in PTS if K[p].get("hourly")) + " |", "|---|" + "---|" * sum(1 for p in PTS if K[p].get("hourly"))]
for H in range(24):
    cells = []
    for p in PTS:
        if not K[p].get("hourly"): continue
        r = next((x for x in K[p]["hourly"] if x["tm"].endswith(f" {H:02d}:00")), None)
        cells.append((r["ws"] or "n/a") if r else "n/a")
    hr.append(f"| {H:02d}:00 | " + " | ".join(cells) + " |")
open("work/kma_hourly_ws.md", "w").write("\n".join(hr))
print("\n".join(rows)); 
