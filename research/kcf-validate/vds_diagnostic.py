"""EXPLORATORY (not in PROTOCOL.md; made after the first run of vds_closures.py): V/B for the 12 mapped 중앙선 conzones in two windows after the official 25 Mar 18:00 closure.
Usage: python3 -I vds_diagnostic.py VDS_CSV MAPPING_CSV OUT.csv"""
import csv, sys
import numpy as np
vol = {}
for x in csv.reader(open(sys.argv[1], encoding="cp949", newline="")):
    if len(x) < 5 or not x[2].startswith("0550CZ") or int(x[4]) < 0:
        continue
    a = vol.setdefault(x[2], np.full((32, 96), np.nan)); d = int(x[0][-2:]); s = int(x[1][:2]) * 4 + int(x[1][3:5]) // 15
    a[d, s] = int(x[4]) if np.isnan(a[d, s]) else a[d, s] + int(x[4])
rows = []
WANT = {"의성 -> 안동JC", "안동JC -> 남안동", "남안동 -> 서안동", "서안동 -> 예천", "예천 -> 영주", "영주 -> 풍기", "풍기 -> 영주", "영주 -> 예천", "예천 -> 서안동", "서안동 -> 남안동", "남안동 -> 안동JC", "안동JC -> 의성"}
for m in csv.DictReader(open(sys.argv[2], encoding="utf-8-sig")):
    if m["accepted"] != "True" or m["section"] not in WANT:
        continue
    V = vol[m["conzone"]]; B = np.nanmedian(V[1:22], axis=0)
    def ratio(d, s0, s1):
        sl = [V[d, s] / B[s] for s in range(s0, s1) if B[s] >= 15 and not np.isnan(V[d, s])]
        return round(float(np.median(sl)), 2) if sl else ""
    rows.append({"conzone": m["conzone"], "dir": m["dir"], "section_mapped": m["section"], "r_with_TCS": m["r"],
                 "median_V_over_B_25Mar_18:30-23:45": ratio(25, 74, 96), "median_V_over_B_26Mar_08:00-20:00": ratio(26, 32, 80), "median_V_over_B_27Mar_08:00-20:00": ratio(27, 32, 80),
                 "median_V_over_B_23Mar_08:00-20:00_(before)": ratio(23, 32, 80)})
with open(sys.argv[3], "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
for r in sorted(rows, key=lambda r: (r["dir"], r["conzone"])): print(r["conzone"], r["dir"], r["section_mapped"].ljust(12), "r=%s" % r["r_with_TCS"], "| 23Mar", r["median_V_over_B_23Mar_08:00-20:00_(before)"], "| 25Mar eve", r["median_V_over_B_25Mar_18:30-23:45"], "| 26Mar day", r["median_V_over_B_26Mar_08:00-20:00"], "| 27Mar day", r["median_V_over_B_27Mar_08:00-20:00"])
