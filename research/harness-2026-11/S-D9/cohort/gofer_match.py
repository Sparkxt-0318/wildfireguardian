"""Systematic GOFER -> NIROPS incident matching (A1 §1.1; orchestrator request after Hannah's Devil finding).

Inputs, metadata only:
  GOFER v0.2 (Zenodo 14642378, GOFER.zip sha256 96eca2e1...): GOFER_Combined/GOFERC_fireIg ignition
  points (fname, tUTC, location) and fireData.csv. No GOFER perimeter is read.
  NIROPS incident metadata (daniel/data-fetch 259ef5b4 incident_metadata.csv, sha256 5246ce8f...):
  WFIGS point of origin (POO) and discovery time.
Rule, stated before results:
  A NIROPS incident matches GOFER fire g if BOTH hold:
    1. the incident POO lies within 30 km of ANY ignition point of g;
    2. the incident's discovery date is within [first ignition of g - 3 d, last ignition of g + 3 d].
  If the POO or the discovery time is missing, the incident is listed as UNDETERMINED (a name-only check is given).
  Name-token matches are listed as a cross-check; they never decide alone.
  python gofer_match.py --ignitions GOFERC_fireIg --meta incident_metadata.csv --split COHORT_SPLIT.csv --out GOFER_MATCH.csv
"""
import argparse
import csv
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import shapefile

KM, DAYS = 30.0, 3


def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", s).lower())
            if t not in {"complex", "fire", "lightning", "and", "cx"} and len(t) > 2}


ap = argparse.ArgumentParser()
for a in ("--ignitions", "--meta", "--split", "--out"):
    ap.add_argument(a, required=True, type=Path)
args = ap.parse_args()
ign = defaultdict(list)
for sr in shapefile.Reader(str(args.ignitions)).iterShapeRecords():
    r = sr.record.as_dict()
    lon, lat = sr.shape.points[0]
    ign[r["fname"]].append(((lat, lon), datetime.fromisoformat(r["tUTC"])))
part = {r["Incident_C"]: r["part"] for r in csv.DictReader(args.split.open())}
rows = []
for m in csv.DictReader(args.meta.open()):
    inc = m["Incident_C"]
    poo = (float(m["poo_lat"]), float(m["poo_lon"])) if m["poo_lat"] and m["poo_lon"] else None
    disc = datetime.fromisoformat(m["discovery_utc"][:19]) if m["discovery_utc"] else None
    name_tok = tokens(inc.split("_", 1)[1] if "_" in inc else inc)
    for g, pts in ign.items():
        t0, t1 = min(t for _, t in pts), max(t for _, t in pts)
        dmin = min(km(poo, p) for p, _ in pts) if poo else None
        in_time = disc is not None and t0 - timedelta(days=DAYS) <= disc <= t1 + timedelta(days=DAYS)
        name_hit = bool(name_tok & tokens(g))
        if poo is None or disc is None:
            status = "UNDETERMINED" if name_hit else None
        else:
            status = "MATCH" if (dmin <= KM and in_time) else None
        if status or (name_hit and dmin is not None and dmin <= 200):
            rows.append(dict(Incident_C=inc, group=m["group"], part=part.get(inc, ""), gofer=g,
                             status=status or "name_only", min_km=None if dmin is None else round(dmin, 1),
                             discovery_utc=m["discovery_utc"], gofer_first_ign=t0.isoformat(),
                             gofer_last_ign=t1.isoformat(), name_token_match=name_hit))
rows.sort(key=lambda r: (r["status"] != "MATCH", r["gofer"], r["Incident_C"]))
with args.out.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
for r in rows:
    if r["status"] in ("MATCH", "UNDETERMINED") or r["part"] in ("b", "c", "d"):
        print(r["status"], r["part"] or r["group"], r["Incident_C"], "->", r["gofer"], r["min_km"], "km")
