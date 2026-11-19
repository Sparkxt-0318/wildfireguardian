"""EXPLORATORY (not in PROTOCOL.md): is the V/B >= 1.5 in the six hours before two closure runs just the usual weekend/weekday pattern? Compare the same slots on earlier same-weekday dates of March.
Usage: python3 -I vds_surge_check.py VDS_CSV OUT.csv"""
import csv, sys
import numpy as np
want = {"0300CZS230": (23, 13, 0, "Sun 23 Mar 13:00 (official closure 13:44)"), "0300CZS240": (24, 12, 0, "Mon 24 Mar 12:00 (official closure 13:20)")}
vol = {}
for x in csv.reader(open(sys.argv[1], encoding="cp949", newline="")):
    if len(x) < 5 or x[2] not in want or int(x[4]) < 0:
        continue
    a = vol.setdefault(x[2], np.full((32, 96), np.nan)); d = int(x[0][-2:]); s = int(x[1][:2]) * 4 + int(x[1][3:5]) // 15
    a[d, s] = int(x[4]) if np.isnan(a[d, s]) else a[d, s] + int(x[4])
rows = []
for c, (d0, h, m, lab) in want.items():
    V = vol[c]; s = h * 4 + m // 15
    B = np.nanmedian(V[1:22], axis=0)[s]
    same = [d for d in range(1, 22) if (d - d0) % 7 == 0 and d != d0]
    rows.append({"conzone": c, "slot": lab, "baseline_median_1_21Mar": round(float(B), 1), "V_on_the_day": V[d0, s], "V_over_B_on_the_day": round(float(V[d0, s] / B), 2),
                 "same_weekday_earlier": ";".join("%02d Mar: V=%s V/B=%.2f" % (d, V[d, s], V[d, s] / B) for d in same)})
with open(sys.argv[2], "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in rows: print(r)
