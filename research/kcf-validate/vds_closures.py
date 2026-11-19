"""15-minute VDS volumes (KEC dataset 148, March 2025) -> closure runs, reopenings, surge ratios on 중앙선 (route 0550); comparison with the official 한국도로공사
events and the model's published bounds (PROTOCOL.md amendment 13). Usage: python3 -I vds_closures.py VDS_CSV KEC_TCS_DIR OUT_DIR
Model output / derived volumes vs records. Not what happened to people."""
import csv, json, math, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

VDS, TCS_DIR, OUT = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
H = Path(__file__).resolve().parent
DAYS6 = ["22", "23", "24", "25", "26", "27"]
ROUTE_V, ROUTE_T = "0550", "055"

# ---------------------------------------------------------------- read VDS for route 0550
vol = defaultdict(lambda: np.full((32, 96), np.nan))   # conzone -> [day, slot]
has2 = defaultdict(lambda: np.zeros((32, 96)))
for x in csv.reader(open(VDS, encoding="cp949", newline="")):
    if len(x) < 5 or not x[2].startswith(ROUTE_V + "CZ"):
        continue
    d = int(x[0][-2:]); s = int(x[1][:2]) * 4 + int(x[1][3:5]) // 15; v = int(x[4])
    if v < 0:
        continue
    a = vol[x[2]]
    a[d, s] = v if np.isnan(a[d, s]) else a[d, s] + v   # sum over lane types, readings >= 0
print("conzones read", len(vol))

# ---------------------------------------------------------------- TCS daily totals (22-27 Mar) and the mapping rule
tcs = defaultdict(lambda: dict.fromkeys(DAYS6, 0))
for d in DAYS6:
    for x in csv.reader(open(TCS_DIR / f"d{d}/tcs.csv", encoding="cp949", newline="")):
        if len(x) >= 14 and x[6] == ROUTE_T and x[12].strip():
            tcs[(x[13], int(x[10]), x[11].strip())][d] += int(x[12])


def corr(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((y - mb) ** 2 for y in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa * sb > 0 else float("nan")


def vday(c, d):
    return float(np.nansum(vol[c][int(d)]))


mapping = {}
for dcode in ("S", "E"):
    cz = sorted(c for c in vol if c[len(ROUTE_V) + 2] == dcode and not np.all(np.isnan(vol[c][22:28])))
    secs = sorted((k for k in tcs if k[0] == dcode), key=lambda k: (k[1], k[2]))
    best = None
    for orient in (1, -1):
        ordered = secs if orient == 1 else secs[::-1]
        for off in range(0, len(ordered) - len(cz) + 1):
            sub = ordered[off:off + len(cz)]
            rs, lr = [], []
            for c, k in zip(cz, sub):
                a = [vday(c, d) for d in DAYS6]; b = [tcs[k][d] for d in DAYS6]
                r = corr(a, b); rs.append(r if r == r else 0.0)
                rat = [x / y for x, y in zip(a, b) if y > 0]
                lr.append(abs(math.log(max(st.median(rat), 1e-3))) if rat else 9)
            sc = sum(rs) / len(rs) - 0.5 * sum(lr) / len(lr)
            if best is None or sc > best[0]:
                best = (sc, sub)
    for c, k in zip(cz, best[1]):
        a = [vday(c, d) for d in DAYS6]; b = [tcs[k][d] for d in DAYS6]
        r = corr(a, b); rat = st.median([x / y for x, y in zip(a, b) if y > 0] or [0])
        mapping[c] = {"dir": dcode, "section": k[2], "seq": k[1], "r": round(r, 3), "ratio": round(rat, 2), "accepted": bool(r == r and r >= 0.85 and 0.5 <= rat <= 2.0)}
print("accepted conzones", sum(m["accepted"] for m in mapping.values()), "of", len(mapping))
WANT = {"의성 -> 안동JC", "안동JC -> 남안동", "남안동 -> 서안동", "서안동 -> 예천", "예천 -> 영주", "영주 -> 풍기",
        "풍기 -> 영주", "영주 -> 예천", "예천 -> 서안동", "서안동 -> 남안동", "남안동 -> 안동JC", "안동JC -> 의성"}
sel = {c: m for c, m in mapping.items() if m["accepted"] and m["section"] in WANT}
print("conzones on the 중앙선 sections of interest", len(sel))

# ---------------------------------------------------------------- baseline, runs, surges
def slot_time(d, s):
    return datetime(2025, 3, d) + timedelta(minutes=15 * s)


runs_out, per_cz = [], {}
for c, m in sorted(sel.items(), key=lambda kv: (kv[1]["dir"], kv[1]["seq"])):
    V = vol[c]
    B = np.nanmedian(V[1:22], axis=0)               # median over 1-21 March for each slot of day
    info = B >= 15.0
    seq = [(d, s) for d in range(22, 32) for s in range(96)]
    near = []
    for d, s in seq:
        v = V[d, s]
        near.append(bool(info[s] and not np.isnan(v) and 0 <= v <= max(2.0, 0.05 * B[s])))
    runs, i = [], 0
    while i < len(seq):
        if near[i]:
            j = i
            while j + 1 < len(seq) and near[j + 1]:
                j += 1
            if j - i + 1 >= 4:
                # reopening: first slot after the run with V >= 0.25 B
                k = j + 1
                reo = None
                while k < len(seq):
                    d2, s2 = seq[k]; v2 = V[d2, s2]
                    if not np.isnan(v2) and info[s2] and v2 >= 0.25 * B[s2]:
                        reo = slot_time(d2, s2); break
                    k += 1
                on = slot_time(*seq[i])
                # surge: max V/B over the six hours before the onset
                sg, sgt = None, None
                for q in range(max(0, i - 24), i):
                    d3, s3 = seq[q]; v3 = V[d3, s3]
                    if info[s3] and not np.isnan(v3):
                        r = v3 / B[s3]
                        if sg is None or r > sg:
                            sg, sgt = r, slot_time(d3, s3)
                runs.append({"onset": on, "reopen": reo, "slots": j - i + 1, "surge_ratio": None if sg is None else round(float(sg), 2), "surge_at": sgt})
            i = j + 1
        else:
            i += 1
    per_cz[c] = runs
    for r in runs:
        runs_out.append({"conzone": c, "section": m["section"], "dir": m["dir"], "corr_with_TCS": m["r"], "onset_kst": r["onset"].strftime("%Y-%m-%d %H:%M"),
                         "reopen_kst": r["reopen"].strftime("%Y-%m-%d %H:%M") if r["reopen"] else "", "slots": r["slots"], "surge_ratio_6h_before": r["surge_ratio"],
                         "surge_at": r["surge_at"].strftime("%m-%d %H:%M") if r["surge_at"] else ""})
with open(OUT / "vds_closure_runs_route0550.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(runs_out[0].keys())); w.writeheader(); w.writerows(runs_out)
with open(OUT / "vds_mapping_route0550.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, ["conzone"] + list(next(iter(mapping.values())).keys())); w.writeheader()
    for c, m in sorted(mapping.items()):
        w.writerow({"conzone": c, **m})

# ---------------------------------------------------------------- comparison with official events
SECS = {"의성IC~남안동": ["의성 -> 안동JC", "안동JC -> 남안동", "안동JC -> 의성", "남안동 -> 안동JC"],
        "의성IC~안동JC": ["의성 -> 안동JC", "안동JC -> 의성"],
        "의성IC~예천IC": ["의성 -> 안동JC", "안동JC -> 남안동", "남안동 -> 서안동", "서안동 -> 예천", "예천 -> 서안동", "서안동 -> 남안동", "남안동 -> 안동JC", "안동JC -> 의성"],
        "의성IC~풍기IC": ["의성 -> 안동JC", "안동JC -> 남안동", "남안동 -> 서안동", "서안동 -> 예천", "예천 -> 영주", "영주 -> 풍기", "풍기 -> 영주", "영주 -> 예천", "예천 -> 서안동", "서안동 -> 남안동", "남안동 -> 안동JC", "안동JC -> 의성"],
        "풍기IC~영주IC": ["영주 -> 풍기", "풍기 -> 영주"]}
ev = list(csv.DictReader(open(H / "out/kec_official_closure_events.csv", encoding="utf-8-sig")))
cmp_rows = []
for e in ev:
    secs = [s for s in e["sections_parsed"].split(" ; ") if s.startswith("중앙선")]
    for s in secs:
        key = s.split(" ", 1)[1].replace("JCT", "JC").replace("의성IC~남안동JC", "의성IC~남안동")
        key = "의성IC~남안동" if key.startswith("의성IC~남안동") else key
        if key not in SECS:
            continue
        off = datetime.strptime(e["effective_kst"], "%Y-%m-%d %H:%M")
        diffs, nones = [], 0
        names = SECS[key]
        for c, m in sel.items():
            if m["section"] not in names:
                continue
            best = None
            for r in per_cz[c]:
                t = r["onset"] if e["action"] == "closure" else r["reopen"]
                if t is not None and abs((t - off).total_seconds()) <= 6 * 3600:
                    if best is None or abs((t - off).total_seconds()) < abs((best - off).total_seconds()):
                        best = t
            if best is None:
                nones += 1
            else:
                diffs.append((best - off).total_seconds() / 60.0)
        cmp_rows.append({"official_effective_kst": e["effective_kst"], "time_basis": e["time_basis"], "action": e["action"], "section": s, "conzone_directions": len(names) if False else sum(1 for c, m in sel.items() if m["section"] in names),
                         "with_derived_time_within_6h": len(diffs), "without": nones, "median_derived_minus_official_min": round(st.median(diffs), 1) if diffs else "",
                         "min": round(min(diffs), 1) if diffs else "", "max": round(max(diffs), 1) if diffs else ""})
with open(OUT / "vds_vs_official_events.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(cmp_rows[0].keys())); w.writeheader(); w.writerows(cmp_rows)

# ---------------------------------------------------------------- model bounds (RD rows) and surge summary
RD = {"RD3": ("의성IC~서안동 (rule: 의성→안동JC, 안동JC→남안동, 남안동→서안동)", ["의성 -> 안동JC", "안동JC -> 남안동", "남안동 -> 서안동", "서안동 -> 남안동", "남안동 -> 안동JC", "안동JC -> 의성"], datetime(2025, 3, 25, 16, 0), datetime(2025, 3, 25, 18, 0)),
      "RD4": ("의성IC~예천IC", SECS["의성IC~예천IC"], datetime(2025, 3, 25, 17, 0), datetime(2025, 3, 25, 18, 0)),
      "RD7": ("의성IC~풍기IC", SECS["의성IC~풍기IC"], datetime(2025, 3, 25, 21, 0), datetime(2025, 3, 25, 21, 26)),
      "RD8": ("의성IC~예천IC (26 Mar)", SECS["의성IC~예천IC"], datetime(2025, 3, 26, 0, 0), datetime(2025, 3, 26, 10, 0))}
rd_rows = []
for rid, (lab, names, Ti, ref) in RD.items():
    ons = []
    for c, m in sel.items():
        if m["section"] in names:
            near = [r["onset"] for r in per_cz[c] if abs((r["onset"] - ref).total_seconds()) <= 12 * 3600]
            if near:
                ons.append(min(near, key=lambda t: abs((t - ref).total_seconds())))
    if ons:
        med = sorted(ons)[len(ons) // 2]
        rd_rows.append({"row": rid, "section": lab, "model_closed_by_issue_kst": Ti.strftime("%m-%d %H:%M"), "official_or_reference_kst": ref.strftime("%m-%d %H:%M"), "n_conzones_with_onset": len(ons),
                        "median_volume_onset_kst": med.strftime("%m-%d %H:%M"), "bound_issue_minus_volume_onset_min": round((Ti - med).total_seconds() / 60.0)})
    else:
        rd_rows.append({"row": rid, "section": lab, "model_closed_by_issue_kst": Ti.strftime("%m-%d %H:%M"), "official_or_reference_kst": ref.strftime("%m-%d %H:%M"), "n_conzones_with_onset": 0})
with open(OUT / "vds_vs_model_RD.csv", "w", newline="", encoding="utf-8-sig") as f:
    keys = sorted({k for r in rd_rows for k in r}, key=lambda k: list(rd_rows[0]).index(k) if k in rd_rows[0] else 99)
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rd_rows)
surges = [r["surge_ratio"] for rs in per_cz.values() for r in rs if r["surge_ratio"] is not None]
summary = {"label": "15-minute VDS volumes vs official events. Not what happened to people.", "protocol": "PROTOCOL.md amendment 13",
           "conzones_read_route0550": len(vol), "accepted": int(sum(m["accepted"] for m in mapping.values())), "used": len(sel),
           "closure_runs": len(runs_out), "surge_ratio_before_onset": {"n": len(surges), "median": float(np.median(surges)) if surges else None, "max": float(max(surges)) if surges else None,
                                                                          "n_ge_1.5": int(sum(s >= 1.5 for s in surges))}}
(OUT / "vds_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps(summary, ensure_ascii=False))
print(open(OUT / "vds_vs_official_events.csv", encoding="utf-8-sig").read())
print(open(OUT / "vds_vs_model_RD.csv", encoding="utf-8-sig").read())
