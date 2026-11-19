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

# RD rows (amendment 6). Expressway rows: route names + interchange names of the row's section; local-road rows: place keywords.
SEO = ["서산영덕선", "청주영덕선"]; JUNG = ["중앙선"]
COUNTIES5 = ["의성군", "안동시", "청송군", "영양군", "영덕군"]
# each section = (end A tokens, end B tokens); a token set matches if any of its tokens occurs in the text
RD_HWY = {"RD1": (SEO, [["안동JC"], ["청송IC"]]), "RD2": (SEO, [["서의성IC"], ["영덕IC", "영덕TG"]]), "RD3": (JUNG, [["의성IC"], ["서안동", "남안동"]]),
          "RD4": (JUNG, [["의성IC"], ["예천IC"]]), "RD5": (SEO, [["동상주IC"], ["영덕IC", "영덕TG"]]), "RD6": (SEO, [["동상주IC"], ["영덕IC", "영덕TG"]]),
          "RD7": (JUNG, [["의성IC"], ["풍기IC"]]), "RD8": (JUNG, [["의성IC"], ["예천IC"]])}


def ends_named(text, ends):
    return sum(any(t in text for t in toks) for toks in ends)
RD_LOCAL = {"RD9": (["영덕군", "영양군"], ["911호선", "화매리", "황장리"]), "RD10": (["영덕군"], ["황장재"]), "RD11": (["영덕군"], ["국도34호선"]),
            "RD12": (["영덕군", "영양군"], ["도계"]), "RD13": (["영덕군"], ["국도7호선", "지경삼거리"])}
RD = {**RD_HWY, **RD_LOCAL}
FIRE = re.compile(r"산불|화재|확산")
WHOLE = re.compile(r"전 ?(시민|군민)|모든 .{0,6}군민|군민께서는|전지역|전 지역")
EFF = re.compile(r"(\d{1,2}):(\d{2})\s*부로")


def official_time(m):
    """Stated effective time ('금일 15:30부로') on the message date if present and not after the creation time, else the creation time."""
    e = EFF.search(m["text"])
    if e:
        t = m["t"].replace(hour=int(e.group(1)), minute=int(e.group(2)), second=0)
        if t <= m["t"]:
            return t, True
    return m["t"], False


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
        whole = "whole county" in what
        for m in M:
            if county not in m["region"] or abs(m["t"] - t0) > WIN or "대피" not in m["text"]:
                continue
            if whole and not (WHOLE.search(m["text"]) and FIRE.search(m["text"])):
                continue
            if names and not any(n in m["text"] or n in m["region"] for n in names):
                continue
            out.append((m, m["t"], False))
    elif rid in RD_HWY:
        routes, ends = RD_HWY[rid]
        for m in M:
            if not (any(c in m["region"] for c in COUNTIES5) or "GB_ALL" == m["counties_hit"]):
                continue
            if "재개" in m["text"] or not ACTION_RD.search(m["text"]) or not any(r in m["text"] for r in routes) or ends_named(m["text"], ends) == 0:
                continue
            ot, stated = official_time(m)
            if abs(ot - t0) <= WIN:
                out.append((m, ot, stated))
        if out:  # specificity first (amendment 7): keep only the candidates naming the most ends of the section
            best = max(ends_named(c[0]["text"], ends) for c in out)
            out = [c for c in out if ends_named(c[0]["text"], ends) == best]
    elif rid in RD_LOCAL:
        counties, kws = RD_LOCAL[rid]
        for m in M:
            if not (any(c in m["region"] for c in counties) or "GB_ALL" == m["counties_hit"]) or "재개" in m["text"]:
                continue
            ot, stated = official_time(m)
            if abs(ot - t0) <= WIN and ACTION_RD.search(m["text"]) and any(k in m["text"] for k in kws):
                out.append((m, ot, stated))
    elif rid == "VA3":
        for m in M:
            if "영덕군" in m["region"] and abs(m["t"] - datetime(2025, 3, 26, 0, 7)) <= timedelta(minutes=10) and "대피" in m["text"]:
                out.append((m, m["t"], False))
    return t0, sorted(out, key=lambda c: c[1])


def context(row):
    """Same-section official closure messages outside the +-6 h window (context only, never a replacement)."""
    rid = row["id"]; t0 = rep_time(row["recorded_kst"])
    out = []
    if rid in RD_HWY:
        routes, ends = RD_HWY[rid]
        for m in M:
            if (any(c in m["region"] for c in COUNTIES5) or "GB_ALL" == m["counties_hit"]) and "재개" not in m["text"] and ACTION_RD.search(m["text"]) \
                    and any(r in m["text"] for r in routes) and ends_named(m["text"], ends) > 0:
                ot, _ = official_time(m)
                if abs(ot - t0) > WIN:
                    out.append((m, ot))
    return out


res, summ = [], {"rows_total": 0, "replaced": 0, "stay_reported": [], "replaced_ids": []}
for row in T:
    rid = row["id"]
    if not re.match(r"^(RD|VA|EV)\d+$", rid):
        continue
    summ["rows_total"] += 1
    t0, cand = candidates(row)
    ctx = context(row)
    rec = {"id": rid, "kind": row["kind"], "what": row["what"], "reported_kst": row["recorded_kst"], "n_candidates": len(cand),
           "official_kst": "", "official_seq": "", "official_text": "", "official_minus_reported_min": "", "all_candidates": " | ".join(ot.strftime("%m-%d %H:%M") + ("(stated)" if st else "(created)") + " " + m["text"][:48] for m, ot, st in cand),
           "context_outside_window": " | ".join(ot.strftime("%m-%d %H:%M") + " " + m["text"][:56] for m, ot in ctx[:5])}
    if cand:
        o, ot, stated = cand[0]
        o = dict(o, t=ot)  # official time = stated effective time if any, else creation time
        rec.update(official_kst=ot.strftime("%Y-%m-%d %H:%M:%S"), official_time_basis="stated effective time" if stated else "message creation time",
                   official_created_kst=cand[0][0]["created_kst"], official_seq=cand[0][0]["seq"], official_text=cand[0][0]["text"][:140],
                   official_minus_reported_min=round(mins(ot, t0), 1))
        summ["replaced"] += 1; summ["replaced_ids"].append(rid)
        # recomputation
        if rid.startswith("RD"):
            issue = rep_time("2025-" + row["issue_used_kst"]) if row.get("issue_used_kst") else None
            if issue is not None:  # the roadcut rule: latest issue hour <= t - 1 h, issue hours 25 Mar 12:00 .. 26 Mar 00:00 (KST)
                under = min(max((ot - timedelta(hours=1)).replace(minute=0, second=0), datetime(2025, 3, 25, 12, 0)), datetime(2025, 3, 26, 0, 0))
                rec["issue_hour_used_in_published_model_value"] = issue.strftime("%m-%d %H:%M")
                rec["issue_hour_roadcut_rule_would_pick"] = under.strftime("%m-%d %H:%M")
                rec["same_issue_hour"] = issue == under
                rec["lead_min_used"] = round(mins(ot, issue))
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


# ---- official expressway closure / reopening timeline (amendment 6), parsed by regex from the 한국도로공사 messages
SEC = re.compile(r"([가-힣]+선(?:\([가-힣]+\))?)\s*([가-힣A-Z0-9]+(?:IC|JC|JCT|TG|분기점|TG))\s*~\s*([가-힣A-Z0-9]+(?:IC|JC|JCT|TG|분기점))")
events = []
for m in sorted(M, key=lambda m: m["t"]):
    if "한국도로공사" not in m["text"]:
        continue
    ot, stated = official_time(m)
    action = "reopen" if "재개" in m["text"] else ("closure" if re.search(r"차단|통제", m["text"]) else "other")
    secs = ["%s %s~%s" % x for x in SEC.findall(m["text"])]
    events.append({"effective_kst": ot.strftime("%Y-%m-%d %H:%M"), "time_basis": "stated" if stated else "created (no stated time)", "created_kst": m["created_kst"], "seq": m["seq"],
                   "action": action, "sections_parsed": " ; ".join(secs), "direction": "양방향" if "양방향" in m["text"] else ("상주방향" if "상주방향" in m["text"] else ("서울방향" if "서울방향" in m["text"] else "")), "text": m["text"][:200]})
with open(OUT / "kec_official_closure_events.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(events[0].keys())); w.writeheader(); w.writerows(events)
summ["kec_official_events"] = len(events)

keys = sorted({k for r in res for k in r}, key=lambda k: (k not in ("id", "kind", "what", "reported_kst", "official_kst", "official_minus_reported_min", "n_candidates"), k))
with open(OUT / "jaenan_replacement.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(res)
# first 대피 message per county
first = {}
for c in ["의성군", "안동시", "청송군", "영양군", "영덕군"]:
    ms = sorted((m for m in M if c in m["region"] and "대피" in m["text"] and m["disaster"] == "산불"), key=lambda m: m["t"])
    first[c] = {"definition": "first message with 대피 in the text and the record's 재해구분명 = 산불", "first_대피_msg": ms[0]["created_kst"] if ms else None, "n_대피_msgs": len(ms), "text": ms[0]["text"][:100] if ms else None}
summ["first_evacuation_message_per_county"] = first
summ["label"] = "Official 재난문자 vs REPORTED rows. Model output on reconstructed inputs. Not what happened to people."
(OUT / "jaenan_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
print(json.dumps({k: summ[k] for k in ("rows_total", "replaced", "replaced_ids", "stay_reported")}, ensure_ascii=False))
for r in res:
    print(r["id"], "|", r["reported_kst"], "->", r["official_kst"][5:16] if r["official_kst"] else "-", "|", r["official_minus_reported_min"], "|", "n=%d" % r["n_candidates"], "|", (r["official_text"] or r["context_outside_window"])[:90])
