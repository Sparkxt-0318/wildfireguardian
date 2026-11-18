"""KEC daily TCS section volumes, 22-27 March 2025 (PROTOCOL.md amendment 5): descriptive only, no pass/fail prediction.
Usage: python3 -I kec_daily.py KEC_DIR OUT_DIR   (KEC_DIR/d22..d27/tcs.csv, cp949; the user's gzip files decompressed)
V = sum over vehicle classes; baseline B = mean(V(22 Mar), V(23 Mar)); r = V/B. Model output: none. Not what happened to people."""
import csv, json, statistics as st, sys
from pathlib import Path

KEC, OUT = Path(sys.argv[1]), Path(sys.argv[2]); OUT.mkdir(parents=True, exist_ok=True)
DAYS = ["22", "23", "24", "25", "26", "27"]
vol = {}  # (route, seq, section, dir) -> {day: volume}
names = {}
for d in DAYS:
    r = csv.reader(open(KEC / f"d{d}/tcs.csv", encoding="cp949", newline=""))
    h = next(r)
    for x in r:
        if len(x) < 14 or not x[12].strip():
            continue
        assert x[0] == f"2025-03-{d}", (x[0], d)
        k = (x[6], int(x[10]), x[11].strip(), x[13])
        vol.setdefault(k, {}).setdefault(d, 0)
        vol[k][d] += int(x[12]); names[k] = x[9]

SEO_S = ["북의성 -> 동안동", "동안동 -> 청송", "청송 -> 동청송영양", "동청송영양 -> 영덕"]
SEO_E = ["영덕 -> 동청송영양", "동청송영양 -> 청송", "청송 -> 동안동", "동안동 -> 북의성"]
W_S = ["동상주 -> 서의성", "서의성 -> 안동JC", "안동JC -> 북의성"]
W_E = ["북의성 -> 안동JC", "안동JC -> 서의성", "서의성 -> 동상주"]
J_S = ["의성 -> 안동JC", "안동JC -> 남안동", "남안동 -> 서안동", "서안동 -> 예천"]
J_E = ["예천 -> 서안동", "서안동 -> 남안동", "남안동 -> 안동JC", "안동JC -> 의성"]
J2_S = ["예천 -> 영주", "영주 -> 풍기"]; J2_E = ["풍기 -> 영주", "영주 -> 예천"]
C0 = [("055", ["가산JC -> 군위", "군위 -> 의성"], "S"), ("055", ["의성 -> 군위", "군위 -> 가산JC"], "E"),
      ("030", ["화서 -> 남상주", "남상주 -> 낙동강JC", "낙동강JC -> 상주JC", "상주JC -> 동상주"], "S"),
      ("030", ["동상주 -> 상주JC", "상주JC -> 낙동강JC", "낙동강JC -> 남상주", "남상주 -> 화서"], "E")]
GROUPS = {"G1 route030 북의성~영덕": [("030", SEO_S, "S"), ("030", SEO_E, "E")],
          "G2 route030 동상주~북의성": [("030", W_S, "S"), ("030", W_E, "E")],
          "G3 route055 의성~예천": [("055", J_S, "S"), ("055", J_E, "E")],
          "G3b route055 예천~풍기": [("055", J2_S, "S"), ("055", J2_E, "E")],
          "G0 control": C0}
rows, gsum = [], {}
for g, parts in GROUPS.items():
    rs = {d: [] for d in DAYS}
    for route, secs, dr in parts:
        for k, v in vol.items():
            if k[0] == route and k[2] in secs and k[3] == dr:
                if not all(d in v for d in DAYS):
                    continue
                B = (v["22"] + v["23"]) / 2
                row = {"group": g, "route": route, "route_name": names[k], "seq": k[1], "section": k[2], "dir": dr}
                for d in DAYS:
                    row["V_" + d] = v[d]
                for d in DAYS:
                    row["r_" + d] = round(v[d] / B, 3) if B else ""
                    if B:
                        rs[d].append(v[d] / B)
                rows.append(row)
    gsum[g] = {"n_section_dirs": len(rs["22"]), "median_r": {d: round(st.median(rs[d]), 3) if rs[d] else None for d in DAYS},
               "min_r": {d: round(min(rs[d]), 3) if rs[d] else None for d in DAYS}, "max_r": {d: round(max(rs[d]), 3) if rs[d] else None for d in DAYS}}
# control: route 045 and 301 entire routes
extra = {}
for route in ("045", "301"):
    rs = {d: [] for d in DAYS}
    for k, v in vol.items():
        if k[0] == route and all(d in v for d in DAYS):
            B = (v["22"] + v["23"]) / 2
            if B:
                for d in DAYS:
                    rs[d].append(v[d] / B)
    extra["G0 route" + route] = {"n_section_dirs": len(rs["22"]), "median_r": {d: round(st.median(rs[d]), 3) for d in DAYS}}
res = {"label": "KEC daily TCS section volumes (dataset 512), user-supplied. Descriptive. Not what happened to people.", "baseline": "mean of 22 and 23 March (weekend; the fire began 22 Mar 11:25)",
       "groups": gsum, "extra_controls": extra, "n_rows_all_routes": len(vol)}
(OUT / "kec_daily_summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
with open(OUT / "kec_daily_sections.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print("sections kept", len(rows))
for g, v in {**gsum, **extra}.items():
    print(g, "n=%d" % v["n_section_dirs"], "median r by day 22..27:", [v["median_r"][d] for d in DAYS])
