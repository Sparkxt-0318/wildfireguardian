"""Source 4 (PROTOCOL.md amendment 3): recorded closure vs recorded fire at the same road, from the text of NIST TN 2135 and TN 2252.
Usage: python3 -I nist_lag.py TN2135.txt TN2252.txt OUT_DIR      (txt = `pdftotext -layout`; PDFs from nvlpubs.nist.gov)
Rows are parsed by text rule only (no figure digitising). Every matched row is written out so the result can be audited.
Times are the start of the report's window (resolution 15-30 min). Model output on reconstructed inputs: none here; this tests the
roadlayer assumption 'a cell closes when the fire reaches it' against records. Not what happened to people."""
import csv, json, re, sys
from pathlib import Path

t2135 = Path(sys.argv[1]).read_text().splitlines()
t2252 = Path(sys.argv[2]).read_text().splitlines()
out = Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)

ROADS = {"Pentz": ["Pentz Rd", "Pentz Road"], "Wagstaff": ["Wagstaff Rd", "Wagstaff Road"], "Bille": ["Bille Rd", "Bille Road"],
         "Elliott": ["Elliott Rd", "Elliott Road"], "Pearson": ["Pearson Rd", "Pearson Road"], "Clark": ["Clark Rd", "Clark Road"],
         "Skyway": ["Skyway"], "Neal": ["Neal Rd", "Neal Road"]}
TAB = re.compile(r"^\s*Table (\d+)\.\s+(.*)$")


def mins(hhmm):
    h, m = hhmm.split(":"); return int(h) * 60 + int(m)


def tables(lines, wanted):
    """Yield (n, title, lines) for table bodies. A heading is the LAST line starting 'Table n.' (the list of tables comes first)."""
    idx = [(i, int(m.group(1)), m.group(2)) for i, l in enumerate(lines) if (m := TAB.match(l)) and "......" not in l]
    last = {}
    for i, n, title in idx:
        last[n] = i
    order = sorted(idx)
    for k, (i, n, title) in enumerate(order):
        if n in wanted and last[n] == i:
            j = order[k + 1][0] if k + 1 < len(order) else min(len(lines), i + 400)
            yield n, title.strip(), lines[i + 1:j]


# ---- TN 2135 fire progression tables (11-32): row = date + time(s) anchors
fire_rows = []
DT = re.compile(r"\b(11/(?:8|9|10))\s+(\d\d:\d\d)(?:\s+(\d\d:\d\d))?")
for n, title, body in tables(t2135, set(range(11, 33))):
    if "fire progression" not in title.lower():
        continue
    for l in body:
        m = DT.search(l)
        if m:
            fire_rows.append({"table": n, "title": title, "date": m.group(1), "start": m.group(2), "end": m.group(3) or "",
                              "text": re.sub(r"\s+", " ", l.strip())[:140]})
# ---- TN 2252 per-road traffic tables (18-28): row starts with HH:MM [HH:MM]
TR = re.compile(r"^\s{0,12}(\d\d:\d\d)(?:\s+(\d\d:\d\d))?\s{1,}(\S.*)$")
traffic_rows = []
for n, title, body in tables(t2252, set(range(18, 29))):
    if "traffic progression" not in title.lower():
        continue
    cur = None
    for l in body:
        if re.match(r"^\s*(\d+\.\d+\.\d+|NIST TN|July 2023|Figure|Table)", l) and not l.strip().startswith("Time Range"):
            if l.strip().startswith(("NIST TN", "July 2023")) or re.match(r"^\s*\d+\s*$", l):
                continue
            break
        m = TR.match(l)
        if m:
            cur = {"table": n, "title": title, "start": m.group(1), "end": m.group(2) or "", "text": m.group(3).strip()}
            traffic_rows.append(cur)
        elif cur is not None and l.strip() and not re.match(r"^\s*\d+\s*$", l) and not l.strip().startswith(("Time Range",)):
            cur["text"] += " " + l.strip()
CLOSE = re.compile(r"clos(ed|ure)|blocked|impassable", re.I)
FIRE = re.compile(r"fire|burn|flame|smoke|BO\b", re.I)
for r in traffic_rows:
    r["closure_match"] = bool(CLOSE.search(r["text"]) and FIRE.search(r["text"]))
# ---- TN 2135 Table 33 burnovers
bo = []
tab33 = next(tables(t2135, {33}))[2][:60]
for l in tab33:
    m = re.match(r"^\s*(\d{1,2})\s{2,}(\S.*?)\s{2,}(\d\d:\d\d)([a-z]?)\s+(\d)\s*$", l)
    m2 = re.match(r"^\s*(\d{1,2})\s{10,}(\d\d:\d\d)([a-z]?)\s+(\d)\s*$", l)
    if m:
        bo.append({"id": int(m.group(1)), "place": m.group(2).strip(), "time": m.group(3), "flag": m.group(4), "category": int(m.group(5))})
    elif m2:  # wrapped place name; completed from the two continuation lines of the same table (manual completion, stated)
        bo.append({"id": int(m2.group(1)), "place": "(wrapped in PDF)", "time": m2.group(2), "flag": m2.group(3), "category": int(m2.group(4))})
WRAP = {4: "Skyway (upper, between Clark Rd and Wagstaff Rd)", 12: "Skyway (lower, west of Princeton Way)"}
for b in bo:
    if b["place"] == "(wrapped in PDF)":
        b["place"] = WRAP[b["id"]] + " [place text completed by hand from the wrapped lines]"


def road_of(text):
    """The road named FIRST in the title (titles like 'Skyway between Coutolenc Rd and Bille Rd' name other roads as limits)."""
    best = (10 ** 9, None)
    for r, keys in ROADS.items():
        for k in keys:
            p = text.lower().find(k.lower())
            if p >= 0 and p < best[0]:
                best = (p, r)
    return best[1]


for r in fire_rows: r["road"] = road_of(r["title"])
for r in traffic_rows: r["road"] = road_of(r["title"])
for b in bo: b["road"] = road_of(b["place"])

res = {"label": "Model output on reconstructed inputs: none. Records vs the roadlayer assumption. Not what happened to people.",
       "protocol": "PROTOCOL.md amendment 3", "counts": {"fire_rows": len(fire_rows), "traffic_rows": len(traffic_rows),
       "traffic_closure_rows": sum(r["closure_match"] for r in traffic_rows), "burnovers": len(bo)}, "roads": {}}
for road in ROADS:
    f = [mins(r["start"]) for r in fire_rows if r["road"] == road and r["date"] == "11/8"]
    c = [mins(r["start"]) for r in traffic_rows if r["road"] == road and r["closure_match"]]
    b = [mins(x["time"]) for x in bo if x["road"] == road and not x["flag"] == "b"]
    ent = {"fire_rows_11_8": len(f), "F_first_fire": min(f) if f else None, "closure_rows": len(c), "C_first_closure": min(c) if c else None,
           "burnovers_same_day_8Nov": len(b), "B_first_burnover": min(b) if b else None}
    ent["C_minus_F_min"] = (ent["C_first_closure"] - ent["F_first_fire"]) if f and c else None
    ent["B_minus_F_min"] = (ent["B_first_burnover"] - ent["F_first_fire"]) if f and b else None
    ent["C_minus_B_min"] = (ent["C_first_closure"] - ent["B_first_burnover"]) if c and b else None
    res["roads"][road] = ent
for k in ("fire_rows", "traffic_rows"):
    rows = fire_rows if k == "fire_rows" else traffic_rows
    with open(out / f"nist_{k}.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
with open(out / "nist_burnovers.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, list(bo[0].keys())); w.writeheader(); w.writerows(bo)
(out / "nist_lag.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res["counts"]))
for r, e in res["roads"].items():
    print(r, {k: v for k, v in e.items()})
