"""Replace REPORTED rows of research/kcf-roadcut/validation_table.csv by official 재난문자 times where the frozen rule (PROTOCOL.md amendment 4)
finds a candidate. Usage: python3 -I jaenan_compare.py OUT_DIR   (reads inputs/jaenan_munja_5counties_20250322_27.csv and the roadcut table)
Model output on reconstructed inputs vs official records. Not what happened to people."""
import csv, json, re, sys
from datetime import datetime, timedelta
from pathlib import Path

H = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
M = list(csv.DictReader(open(H / "inputs/jaenan_munja_5counties_20250322_27.csv", encoding="utf-8-sig")))
for m in M:
    m["t"] = datetime.strptime(m["created_kst"], "%Y-%m-%d %H:%M:%S")
# the first line of the roadcut table is a comment line; the header is the second line
lines = open(H.parent / "kcf-roadcut/validation_table.csv", encoding="utf-8").read().splitlines()
T = list(csv.DictReader(lines[1:] if lines[0].lstrip(chr(34)).startswith("#") else lines))
ARMS = ["MEASURED", "RUNNING", "ORDINARY", "WORST", "MEASURED_GUST_KMA", "MEASURED_GUST"]
WIN = timedelta(hours=6)
ACTION_RD = re.compile(r"통제|차단|통행금지|통행제한")

# RD rows: counties and keywords, fixed here (the rule's "route or place keyword of the row")
RD = {"RD1": (["안동시", "청송군"], ["서산영덕선"]), "RD2": (["의성군", "영덕군", "안동시", "청송군"], ["서산영덕선"]),
      "RD3": (["의성군", "안동시"], ["중앙선"]), "RD4": (["의성군", "안동시"], ["중앙선"]), "RD5": (["영덕군", "의성군", "안동시", "청송군"], ["서산영덕선"]),
      "RD6": (["영덕군", "의성군", "안동시", "청송군"], ["서산영덕선"]), "RD7": (["의성군", "안동시"], ["중앙선"]), "RD8": (["의성군", "안동시"], ["중앙선"]),
      "RD9": (["영덕군", "영양군"], ["911호선", "화매리", "황장리"]), "RD10": (["영덕군"], ["황장재"]), "RD11": (["영덕군"], ["국도34호선"]),
      "RD12": (["영덕군", "영양군"], ["도계", "영양"]), "RD13": (["영덕군"], ["국도7호선", "지경삼거리"])}


def rec_time(s):
    return datetime.strptime("2025-" + s.strip(), "%Y-%m-%d %H:%M") if s and re.match(r"^\d\d-\d\d \d\d:\d\d$", s.strip()) else None


def rep_time(s):
    return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")


def mins(a, b):
    return (a - b).total_seconds() / 60.0


def candidates(row):
    rid = row["id"]; t0 = rep_time(row["recorded_kst"]) if row["recorded_kst"] else None
    if t0 is None:
        return None, []
    out = []
    if rid.startswith("EV"):
        what = row["what"]; county = what.split()[0]
        names = re.findall(r"'([^']+)'", what)
        for m in M:
            if county not in m["region"] or abs(m["t"] - t0) > WIN or "대피" not in m["text"]:
                continue
            if names and not any(n in m["text"] or n in m["region"] for n in names):
                continue
            out.append(m)
    elif rid in RD:
        counties, kws = RD[rid]
        for m in M:
            if not any(c in m["region"] for c in counties) or abs(m["t"] - t0) > WIN:
                continue
            if ACTION_RD.search(m["text"]) and any(k in m["text"] for k in kws):
                out.append(m)
    elif rid == "VA3":
        for m in M:
            if "영덕군" in m["region"] and abs(m["t"] - datetime(2025, 3, 26, 0, 7)) <= timedelta(minutes=10) and "대피" in m["text"]:
                out.append(m)
    return t0, sorted(out, key=lambda m: m["t"])


def context(row):
    """Same-section official messages outside the +-6 h window (context only)."""
    rid = row["id"]
    if rid not in RD:
        return []
    counties, kws = RD[rid]; t0 = rep_time(row["recorded_kst"])
    return [m for m in M if any(c in m["region"] for c in counties) and abs(m["t"] - t0) > WIN and ACTION_RD.search(m["text"]) and any(k in m["text"] for k in kws)]


res, summ = [], {"rows_total": 0, "replaced": 0, "stay_reported": [], "replaced_ids": []}
for row in T:
    rid = row["id"]
    if not re.match(r"^(RD|VA|EV)\d+$", rid):
        continue
    summ["rows_total"] += 1
    t0, cand = candidates(row)
    ctx = context(row)
    rec = {"id": rid, "kind": row["kind"], "what": row["what"], "reported_kst": row["recorded_kst"], "n_candidates": len(cand),
           "official_kst": "", "official_seq": "", "official_text": "", "official_minus_reported_min": "", "all_candidates": " | ".join(m["created_kst"][5:16] + " " + m["region"].split(",")[0][:14] for m in cand),
           "context_outside_window": " | ".join(m["created_kst"][5:16] + " " + m["text"][:60] for m in ctx[:4])}
    if cand:
        o = cand[0]
        rec.update(official_kst=o["created_kst"], official_seq=o["seq"], official_text=o["text"][:140],
                   official_minus_reported_min=round(mins(o["t"], t0), 1))
        summ["replaced"] += 1; summ["replaced_ids"].append(rid)
        # recomputation
        if rid.startswith("RD"):
            issue = rep_time("2025-" + row["issue_used_kst"]) if row.get("issue_used_kst") else None
            for a in ARMS:
                mk, ek = row.get(a + "_model_kst", ""), row.get(a + "_error_min_or_status", "")
                mt = rec_time(mk)
                if ek.startswith("closed at issue") and issue is not None:
                    rec[a + "_new"] = "closed at issue (bound <= %d min)" % round(mins(issue, o["t"]))
                elif mt is not None:
                    rec[a + "_new"] = round(mins(mt, o["t"]))
                else:
                    rec[a + "_new"] = ek[:40]
                rec[a + "_old"] = ek[:40]
        elif rid.startswith("EV"):
            d = mins(o["t"], t0)
            for a in ("MEASURED", "RUNNING"):
                ek = row.get(a + "_error_min_or_status", "")
                m = re.search(r"= (-?\d+) min \(n cut (\d+)\)", ek)
                rec[a + "_old"] = ek[:60]
                used = rep_time("2025-" + row["issue_used_kst"]) if row.get("issue_used_kst") else None
                new_issue = max(o["t"].replace(minute=0, second=0), datetime(2025, 3, 25, 12, 0)) if used and used.day == 25 and o["t"].day == 25 else o["t"].replace(minute=0, second=0)
                if used is not None and new_issue != used:
                    rec[a + "_new"] = "not recomputed: issue hour would change (%s -> %s)" % (used.strftime("%H:%M"), new_issue.strftime("%d %H:%M"))
                    continue
                if m:
                    rec[a + "_new"] = "order - median T_road = %d min (n cut %s)" % (round(int(m.group(1)) + d), m.group(2))
                else:
                    rec[a + "_new"] = "no cut-off to compare (unchanged)"
    else:
        summ["stay_reported"].append(rid)
    res.append(rec)

keys = sorted({k for r in res for k in r}, key=lambda k: (k not in ("id", "kind", "what", "reported_kst", "official_kst", "official_minus_reported_min", "n_candidates"), k))
with open(OUT / "jaenan_replacement.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(res)
# first 대피 message per county
first = {}
for c in ["의성군", "안동시", "청송군", "영양군", "영덕군"]:
    ms = sorted((m for m in M if c in m["region"] and "대피" in m["text"]), key=lambda m: m["t"])
    first[c] = {"first_대피_msg": ms[0]["created_kst"] if ms else None, "n_대피_msgs": len(ms), "text": ms[0]["text"][:100] if ms else None}
summ["first_evacuation_message_per_county"] = first
summ["label"] = "Official 재난문자 vs REPORTED rows. Model output on reconstructed inputs. Not what happened to people."
(OUT / "jaenan_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
print(json.dumps({k: summ[k] for k in ("rows_total", "replaced", "replaced_ids", "stay_reported")}, ensure_ascii=False))
for r in res:
    print(r["id"], "|", r["reported_kst"], "->", r["official_kst"][5:16] if r["official_kst"] else "-", "|", r["official_minus_reported_min"], "|", "n=%d" % r["n_candidates"], "|", (r["official_text"] or r["context_outside_window"])[:90])
