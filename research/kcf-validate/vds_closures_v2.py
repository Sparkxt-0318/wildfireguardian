"""15-minute VDS volumes (KEC dataset 148, March 2025) with the conzone reference table (dataset 157): closure runs on 서산영덕선 (route 0300) and 중앙선 (route 0550),
compared with the official 한국도로공사 events and the model's published bounds (PROTOCOL.md amendments 13 (detection) and 15 (mapping by conzone name)).
Usage: python3 -I vds_closures_v2.py VDS_CSV CONZONE_CSV OUT_DIR     Not what happened to people."""
import csv, json, re, statistics as st, sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

VDS, CZ, OUT = sys.argv[1], sys.argv[2], Path(sys.argv[3]); OUT.mkdir(parents=True, exist_ok=True)
H = Path(__file__).resolve().parent
ROUTES = {"0300": "서산영덕선", "0550": "중앙선"}
ROUTE_OF = {"서산영덕선": "0300", "청주영덕선": "0300", "중앙선": "0550"}


def base(n):
    return re.sub(r"(IC|JCT|JC|TG|Hi|분기점)$", "", n.strip())


# ---------------------------------------------------------------- reference table -> chains and intervals
ref = [r for r in csv.DictReader(open(CZ, encoding="cp949", newline="")) if r["노선번호"] in ROUTES]
chain = {}
for route in ROUTES:
    es = sorted((r for r in ref if r["노선번호"] == route and r["기점종점방향구분코드"] == "E" and "종점" not in r["콘존명"] and "시점" not in r["콘존명"]), key=lambda r: int(r["노선구성순번"]))
    nodes = [base(es[0]["콘존명"].split("-")[0])] + [base(r["콘존명"].split("-")[1]) for r in es]
    chain[route] = nodes
cz = {}
for r in ref:
    if "종점" in r["콘존명"] or "시점" in r["콘존명"]:
        continue
    a, b = [base(x) for x in r["콘존명"].split("-")]
    pos = {n: i for i, n in enumerate(chain[r["노선번호"]])}
    if a in pos and b in pos:
        i, j = sorted((pos[a], pos[b]))
        cz[r["콘존ID"]] = {"route": r["노선번호"], "dir": r["기점종점방향구분코드"], "name": r["콘존명"], "interval": (i, j), "seq": int(r["노선구성순번"])}
print("conzones with an interval:", len(cz), {k: len(v) for k, v in chain.items()})


def select(route, A, B):
    pos = {n: i for i, n in enumerate(chain[route])}
    a, b = base(A), base(B)
    if a not in pos or b not in pos:
        return []
    lo, hi = sorted((pos[a], pos[b]))
    return [c for c, m in cz.items() if m["route"] == route and m["interval"][0] >= lo and m["interval"][1] <= hi]


# ---------------------------------------------------------------- read VDS
vol = defaultdict(lambda: np.full((32, 96), np.nan))
for x in csv.reader(open(VDS, encoding="cp949", newline="")):
    if len(x) < 5 or x[2] not in cz or int(x[4]) < 0:
        continue
    d = int(x[0][-2:]); s = int(x[1][:2]) * 4 + int(x[1][3:5]) // 15
    a = vol[x[2]]; v = int(x[4])
    a[d, s] = v if np.isnan(a[d, s]) else a[d, s] + v
print("conzones with data", len(vol))


def slot_time(d, s):
    return datetime(2025, 3, d) + timedelta(minutes=15 * s)


# ---------------------------------------------------------------- closure runs (amendment 13)
SEQ = [(d, s) for d in range(22, 32) for s in range(96)]
runs = {}
baseline = {}
for c in cz:
    if c not in vol:
        continue
    V = vol[c]; B = np.nanmedian(V[1:22], axis=0); baseline[c] = B
    info = B >= 15.0
    near = [bool(info[s] and not np.isnan(V[d, s]) and 0 <= V[d, s] <= max(2.0, 0.05 * B[s])) for d, s in SEQ]
    out, i = [], 0
    while i < len(SEQ):
        if near[i]:
            j = i
            while j + 1 < len(SEQ) and near[j + 1]:
                j += 1
            if j - i + 1 >= 4:
                reo = None
                for k in range(j + 1, len(SEQ)):
                    d2, s2 = SEQ[k]; v2 = V[d2, s2]
                    if not np.isnan(v2) and info[s2] and v2 >= 0.25 * B[s2]:
                        reo = slot_time(d2, s2); break
                sg, sgt = None, None
                for q in range(max(0, i - 24), i):
                    d3, s3 = SEQ[q]; v3 = V[d3, s3]
                    if info[s3] and not np.isnan(v3):
                        r = v3 / B[s3]
                        if sg is None or r > sg:
                            sg, sgt = float(r), slot_time(d3, s3)
                out.append({"onset": slot_time(*SEQ[i]), "reopen": reo, "slots": j - i + 1, "surge": sg, "surge_at": sgt})
            i = j + 1
        else:
            i += 1
    runs[c] = out
rows = []
for c, rs in sorted(runs.items(), key=lambda kv: (cz[kv[0]]["route"], cz[kv[0]]["dir"], cz[kv[0]]["seq"])):
    for r in rs:
        rows.append({"conzone": c, "route": ROUTES[cz[c]["route"]], "name": cz[c]["name"], "dir": cz[c]["dir"], "onset_kst": r["onset"].strftime("%Y-%m-%d %H:%M"),
                     "reopen_kst": r["reopen"].strftime("%Y-%m-%d %H:%M") if r["reopen"] else "", "slots": r["slots"],
                     "surge_ratio_6h_before": None if r["surge"] is None else round(r["surge"], 2),
                     "surge_at_kst": r["surge_at"].strftime("%m-%d %H:%M") if r["surge_at"] else ""})
with open(OUT / "vds2_closure_runs.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)

# ---------------------------------------------------------------- (a) official events
ev = list(csv.DictReader(open(H / "out/kec_official_closure_events.csv", encoding="utf-8-sig")))
cmp_rows, covered = [], set()
for e in ev:
    if e["action"] not in ("closure", "reopen"):
        continue
    off = datetime.strptime(e["effective_kst"], "%Y-%m-%d %H:%M")
    for s in e["sections_parsed"].split(" ; "):
        if not s.strip():
            continue
        rt, ab = s.split(" ", 1)
        if rt not in ROUTE_OF or "~" not in ab:
            continue
        A, B = ab.split("~")
        sel = [c for c in select(ROUTE_OF[rt], A, B) if c in runs]
        if e["action"] == "closure":
            covered |= set(sel)
        diffs, inf = [], []
        for c in sel:
            Bc = baseline[c]
            ss = [(off + timedelta(minutes=15 * k)) for k in range(-4, 5)]
            inf.append(np.mean([Bc[(t.hour * 4 + t.minute // 15)] >= 15 for t in ss]))
            best = None
            for r in runs[c]:
                t = r["onset"] if e["action"] == "closure" else r["reopen"]
                if t is not None and abs((t - off).total_seconds()) <= 6 * 3600 and (best is None or abs((t - off).total_seconds()) < abs((best - off).total_seconds())):
                    best = t
            if best is not None:
                diffs.append((best - off).total_seconds() / 60.0)
        cmp_rows.append({"official_effective_kst": e["effective_kst"], "time_basis": e["time_basis"], "action": e["action"], "section": s, "conzone_directions": len(sel),
                         "with_derived_time_within_6h": len(diffs), "without": len(sel) - len(diffs), "median_derived_minus_official_min": round(st.median(diffs), 1) if diffs else "",
                         "min": round(min(diffs), 1) if diffs else "", "max": round(max(diffs), 1) if diffs else "",
                         "share_of_slots_within_1h_with_informative_baseline": round(float(np.mean(inf)), 2) if inf else ""})
with open(OUT / "vds2_vs_official_events.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(cmp_rows[0].keys())); w.writeheader(); w.writerows(cmp_rows)

# ---------------------------------------------------------------- (b) model bounds
RD = {"RD1": ("0300", "안동JC", "청송IC", datetime(2025, 3, 25, 15, 30), datetime(2025, 3, 25, 14, 0)), "RD2": ("0300", "서의성IC", "영덕IC", datetime(2025, 3, 25, 15, 58), datetime(2025, 3, 25, 16, 0)),
      "RD3": ("0550", "의성IC", "서안동IC", datetime(2025, 3, 25, 18, 0), datetime(2025, 3, 25, 16, 0)), "RD4": ("0550", "의성IC", "예천IC", datetime(2025, 3, 25, 18, 0), datetime(2025, 3, 25, 17, 0)),
      "RD5": ("0300", "동상주IC", "영덕IC", datetime(2025, 3, 25, 18, 0), datetime(2025, 3, 25, 17, 0)), "RD6": ("0300", "동상주IC", "영덕IC", datetime(2025, 3, 25, 22, 0), datetime(2025, 3, 25, 21, 0)),
      "RD7": ("0550", "의성IC", "풍기IC", datetime(2025, 3, 25, 21, 26), datetime(2025, 3, 25, 21, 0)), "RD8": ("0550", "의성IC", "예천IC", datetime(2025, 3, 26, 10, 0), datetime(2025, 3, 26, 0, 0))}
rd_rows = []
for rid, (rt, A, B, ref_t, Ti) in RD.items():
    sel = [c for c in select(rt, A, B) if c in runs]
    ons = []
    for c in sel:
        near = [r["onset"] for r in runs[c] if abs((r["onset"] - ref_t).total_seconds()) <= 12 * 3600]
        if near:
            ons.append(min(near, key=lambda t: abs((t - ref_t).total_seconds())))
    row = {"row": rid, "section": "%s %s~%s" % (ROUTES[rt], A, B), "reference_time_kst": ref_t.strftime("%m-%d %H:%M"), "model_closed_by_issue_kst": Ti.strftime("%m-%d %H:%M"),
           "conzone_directions": len(sel), "with_onset_within_12h": len(ons)}
    if ons:
        ons.sort(); med = ons[len(ons) // 2]
        row.update(median_onset_kst=med.strftime("%m-%d %H:%M"), onset_range=ons[0].strftime("%m-%d %H:%M") + " .. " + ons[-1].strftime("%m-%d %H:%M"),
                   bound_issue_minus_median_onset_min=round((Ti - med).total_seconds() / 60.0))
    rd_rows.append(row)
with open(OUT / "vds2_vs_model_RD.csv", "w", newline="", encoding="utf-8-sig") as f:
    keys = []
    for r in rd_rows:
        keys += [k for k in r if k not in keys]
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rd_rows)

# ---------------------------------------------------------------- (c) controls, surge
def has_run(c):
    return any(datetime(2025, 3, 22) <= r["onset"] < datetime(2025, 3, 28) for r in runs.get(c, []))
cov = [c for c in runs if c in covered]; unc = [c for c in runs if c not in covered]
surges = [r["surge"] for c in cov for r in runs[c] if r["surge"] is not None]
summary = {"label": "15-minute VDS volumes with the KEC conzone table. Not what happened to people.", "protocol": "PROTOCOL.md amendments 13 (detection) and 15 (mapping)",
           "conzones_with_interval": len(cz), "conzones_with_data": len(vol), "closure_runs": len(rows),
           "covered_by_an_official_closure_section": {"n_conzone_directions": len(cov), "with_a_run_22_27_Mar": int(sum(has_run(c) for c in cov))},
           "not_covered_(controls)": {"n_conzone_directions": len(unc), "with_a_run_22_27_Mar": int(sum(has_run(c) for c in unc))},
           "surge_ratio_before_onset_covered": {"n": len(surges), "median": float(np.median(surges)) if surges else None, "max": float(max(surges)) if surges else None,
                                                  "n_ge_1.5": int(sum(s >= 1.5 for s in surges))}}
(OUT / "vds2_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))
print(json.dumps(summary, ensure_ascii=False))
for fn in ("vds2_vs_official_events.csv", "vds2_vs_model_RD.csv"):
    print(open(OUT / fn, encoding="utf-8-sig").read())
