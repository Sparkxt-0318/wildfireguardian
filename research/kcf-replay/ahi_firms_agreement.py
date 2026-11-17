"""Diagnostic (not a rule change): for each AHI hotspot of HOTSPOT_RULE.md, the first FIRMS detection (kept by the
same rule) within 2 km of the pixel centre at ANY time from 2025-03-22 to 2025-03-26 15:00 UTC, and the lead/lag.
Usage: python3 ahi_firms_agreement.py out/fire_discs.json OUT.json"""
import json, sys
from datetime import datetime
import numpy as np
d = json.load(open(sys.argv[1]))["discs"]
ahi = [x for x in d if x["src"] == "AHI"]; fir = [x for x in d if x["src"] != "AHI"]
FX = np.array([x["x"] for x in fir]); FY = np.array([x["y"] for x in fir]); FT = np.array([datetime.fromisoformat(x["t_utc"]).timestamp() for x in fir])
rows = []
for a in ahi:
    near = np.hypot(FX - a["x"], FY - a["y"]) <= 2000
    ta = datetime.fromisoformat(a["t_utc"]).timestamp()
    if near.any():
        first = FT[near].min()
        rows.append((ta - first) / 3600)
    else:
        rows.append(None)
conf = [r for r in rows if r is not None]
res = {"ahi_hotspots": len(ahi), "with_firms_within_2km_any_time": len(conf), "never_confirmed_by_firms": rows.count(None),
       "firms_before_ahi": int(sum(r > 0 for r in conf)), "ahi_before_firms": int(sum(r <= 0 for r in conf)),
       "median_ahi_lead_h_when_ahi_first": float(np.median([-r for r in conf if r <= 0])) if any(r <= 0 for r in conf) else None,
       "firms_window_utc": "kept FIRMS rows span 2025-03-22 to 2025-03-25T17:58 UTC (last overpass in the files before 2025-03-26T00:00)"}
json.dump(res, open(sys.argv[2], "w"), indent=1); print(res)
