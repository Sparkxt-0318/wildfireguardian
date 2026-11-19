"""Row-level extraction of NIST TN 2135 fire-progression tables 11-32 with their Location column (word positions, pdfplumber).
Usage: python3 -I extract_nist_locations.py TN2135.pdf OUT.csv
Each row is anchored by its date token (11/8, 11/9 ...) in the date column; its observation text and its Location text are the words of those
columns whose vertical position is nearest to that anchor (rows are vertically centred on the date line). No figure is digitised."""
import csv, re, sys
import pdfplumber

pdf = pdfplumber.open(sys.argv[1])
TAB = re.compile(r"Table (\d+)\. Summary of fire progression")
rows = []
cur = None
for pi in range(88, 143):
    p = pdf.pages[pi]
    words = p.extract_words()
    # headings on this page (y of the line)
    text_lines = {}
    for w in words:
        text_lines.setdefault(round(w["top"]), []).append(w)
    heads = []
    for y, ws in text_lines.items():
        line = " ".join(w["text"] for w in sorted(ws, key=lambda w: w["x0"]))
        m = TAB.search(line)
        if m and "......" not in line:
            heads.append((y, int(m.group(1))))
    heads.sort()
    hdr = [w for w in words if w["text"] == "Location"]
    if not hdr:
        if heads:
            cur = heads[-1][1]
        continue
    loc_x0 = min(w["x0"] for w in hdr)
    srcs = [w for w in words if w["text"] == "Source" and abs(w["top"] - hdr[0]["top"]) < 3]
    src_x0 = srcs[0]["x0"] if srcs else loc_x0 + 100
    obs_x0 = [w for w in words if w["text"] == "Fire" and abs(w["top"] - hdr[0]["top"]) < 3]
    obs_x0 = obs_x0[0]["x0"] if obs_x0 else 165
    hdr_y = hdr[0]["top"]
    anchors = []
    for w in words:
        if re.fullmatch(r"11/\d{1,2}", w["text"]) and w["x0"] < 110 and w["top"] > hdr_y:
            same = [v for v in words if abs(v["top"] - w["top"]) < 2.5 and 110 <= v["x0"] < 160 and re.fullmatch(r"\d\d:\d\d", v["text"])]
            same.sort(key=lambda v: v["x0"])
            anchors.append({"y": w["top"], "date": w["text"], "start": same[0]["text"] if same else "", "end": same[1]["text"] if len(same) > 1 else ""})
    anchors.sort(key=lambda a: a["y"])
    for k, a in enumerate(anchors):
        lo = (anchors[k - 1]["y"] + a["y"]) / 2 if k else hdr_y + 8
        hi = (a["y"] + anchors[k + 1]["y"]) / 2 if k + 1 < len(anchors) else p.height - 60
        tab = cur
        for hy, hn in heads:  # a heading above this anchor on this page switches the table
            if hy < a["y"] - 5 and hy > hdr_y - 200:
                tab = hn
        loc = " ".join(w["text"] for w in sorted([w for w in words if loc_x0 - 3 <= w["x0"] < src_x0 - 12 and lo <= w["top"] < hi and not re.fullmatch(r"(TD|VTD|911)[-\d,A-Z]*", w["text"])], key=lambda w: (round(w["top"] / 3), w["x0"])))
        obs = " ".join(w["text"] for w in sorted([w for w in words if obs_x0 - 3 <= w["x0"] < loc_x0 - 3 and lo <= w["top"] < hi], key=lambda w: (round(w["top"] / 3), w["x0"])))
        rows.append({"table": tab, "page": pi + 1, "date": a["date"], "start": a["start"], "end": a["end"], "location": re.sub(r"\s+", " ", loc).strip(), "observation": re.sub(r"\s+", " ", obs)[:220]})
    if heads:
        cur = heads[-1][1]
with open(sys.argv[2], "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, list(rows[0].keys())); w.writeheader(); w.writerows(rows)
import collections
print(len(rows), "rows;", "with location:", sum(bool(r["location"]) for r in rows), "; per table:", sorted(collections.Counter(r["table"] for r in rows).items()))
