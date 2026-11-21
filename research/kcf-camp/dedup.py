"""PROTOCOL 2.1: read every sheet of the NIST fire-spread workbook, drop the header row, de-duplicate.
Usage: python3 -I dedup.py WORKBOOK.xlsx OUT.csv"""
import csv, re, sys
import openpyxl

wb = openpyxl.load_workbook(sys.argv[1], read_only=True, data_only=True)
COLS = ["source", "date", "time", "time_source", "window_min", "lat", "lon", "location_source", "info_source", "text", "fire_type", "residual", "ssi"]
rows, n_read = {}, 0
for ws in wb.worksheets:
    for k, r in enumerate(ws.iter_rows(values_only=True)):
        if k == 0 or all(v is None for v in r):
            continue
        n_read += 1
        d = dict(zip(COLS, list(r) + [None] * (len(COLS) - len(r))))
        t = d["time"]
        hhmm = t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[:5]
        lat = round(float(d["lat"]), 5) if d["lat"] not in (None, "") else None
        lon = round(float(d["lon"]), 5) if d["lon"] not in (None, "") else None
        text = re.sub(r"\s+", " ", str(d["text"] or "")).strip()
        key = (str(d["source"]).strip(), hhmm, lat, lon, text.lower())
        day = str(d["date"])[5:10]  # month-day; the year is mistyped 2021 in the workbook (PROTOCOL amendment 3)
        if key in rows:
            rows[key]["sheets"].append(ws.title)
            if rows[key]["day"] != day:
                raise SystemExit("duplicate key spans two days: %r" % (key,))
            continue
        rows[key] = {"obs_id": None, "day": day, "source": str(d["source"]).strip(), "time": hhmm, "time_source": d["time_source"], "window_min": d["window_min"],
                     "lat": lat, "lon": lon, "location_source": d["location_source"], "info_source": d["info_source"], "text": text,
                     "fire_type": d["fire_type"] or "", "residual": d["residual"] or "", "sheets": [ws.title]}
out = sorted(rows.values(), key=lambda r: (r["time"], r["source"], r["lat"] or 0, r["lon"] or 0, r["text"]))
for i, r in enumerate(out):
    r["obs_id"] = "W%04d" % (i + 1)
    r["n_sheets"] = len(r["sheets"]); r["sheets"] = "; ".join(r["sheets"])
with open(sys.argv[2], "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, ["obs_id", "day", "time", "window_min", "time_source", "lat", "lon", "location_source", "source", "info_source", "fire_type", "residual", "text", "n_sheets", "sheets"])
    w.writeheader(); w.writerows(out)
same_text_place = {}
for r in out:
    same_text_place.setdefault((r["time"], r["lat"], r["lon"], r["text"].lower()), []).append(r["source"])
print("rows read", n_read, "unique observations", len(out), "duplicates removed", n_read - len(out),
      "| unique rows sharing time+place+text with another source:", sum(len(v) for v in same_text_place.values() if len(v) > 1),
      "| no coordinates:", sum(1 for r in out if r["lat"] is None))
