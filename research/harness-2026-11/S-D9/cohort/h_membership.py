"""Short-horizon stratum H membership (A1 §2.1, revisions 14, 15 and 25). METADATA ONLY.

Inputs:
  GOFER v0.2 ignition points (GOFER_Combined/GOFERC_fireIg: fname, tUTC, location). No GOFER
  perimeter or label is read.
  The §1.3 reference fires (FIT and SELECTED_ON) as built by prepare_meta.py (ref.csv:
  Incident_C, poo_lat, poo_lon, discovery_date).
  cohort/GOFER_MATCH.csv and cohort/COHORT_FINAL.csv for the item-25 forced H-dev set F.
Rules, all fixed in A1 before this script ran:
  §1.3   A GOFER fire is excluded if any of its ignition points lies within 50 km of a reference
         fire's point of origin AND its first ignition date is within 30 days of that fire's
         discovery date. Caldor (INSPECTED) is excluded.
  item 25  F = GOFER fires with status MATCH or UNDETERMINED against an incident kept in part a.
  §2.1   n = number of survivors. Survivors in F go to H-dev. The other survivors are ordered by
         u = sha256("S-D9-A1|GOFER|" + name); H-dev also takes the first max(0, floor(n/2) - |F|)
         of them, and the rest form H-test.

  python h_membership.py --ignitions GOFERC_fireIg --ref ref.csv --match GOFER_MATCH.csv \
      --final COHORT_FINAL.csv --out H_MEMBERSHIP.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import math
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import shapefile

NEAR_KM, NEAR_DAYS = 50.0, 30
INSPECTED = {"Caldor"}


def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def u(name: str) -> str:
    return hashlib.sha256(("S-D9-A1|GOFER|" + name).encode()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    for a in ("--ignitions", "--ref", "--match", "--final", "--out"):
        ap.add_argument(a, required=True, type=Path)
    args = ap.parse_args()
    ign = defaultdict(list)
    for sr in shapefile.Reader(str(args.ignitions)).iterShapeRecords():
        r = sr.record.as_dict()
        lon, lat = sr.shape.points[0]
        ign[r["fname"]].append(((lat, lon), datetime.fromisoformat(r["tUTC"])))
    ref = [(r["Incident_C"], (float(r["poo_lat"]), float(r["poo_lon"])), date.fromisoformat(r["discovery_date"][:10]))
           for r in csv.DictReader(args.ref.open()) if r["poo_lat"] and r["discovery_date"]]
    kept_a = {r["Incident_C"] for r in csv.DictReader(args.final.open()) if r["part"] == "a" and r["status"] == "kept"}
    forced = {r["gofer"] for r in csv.DictReader(args.match.open())
              if r["status"] in ("MATCH", "UNDETERMINED") and r["Incident_C"] in kept_a}
    rows = []
    for g, pts in sorted(ign.items()):
        first = min(t for _, t in pts).date()
        hit = None
        for rid, rloc, rday in ref:
            dmin = min(km(p, rloc) for p, _ in pts)
            if dmin <= NEAR_KM and abs((first - rday).days) <= NEAR_DAYS:
                hit = f"§1.3 near {rid} ({dmin:.1f} km, {(first - rday).days:+d} d)"
                break
        if any(tok in g for tok in INSPECTED):
            hit = hit or "Caldor 2021 INSPECTED"
        rows.append(dict(gofer=g, first_ignition_date=first.isoformat(), u=u(g), forced_h_dev=g in forced,
                         status="excluded" if hit else "survivor", reason=hit or "", h=""))
    surv = [r for r in rows if r["status"] == "survivor"]
    n = len(surv)
    f_surv = [r for r in surv if r["forced_h_dev"]]
    rest = sorted((r for r in surv if not r["forced_h_dev"]), key=lambda r: r["u"])
    extra = max(0, n // 2 - len(f_surv))
    for r in f_surv:
        r["h"] = "H-dev"
        r["reason"] = "item 25 forced (GOFER fire matched to a kept part-a incident)"
    for i, r in enumerate(rest):
        r["h"] = "H-dev" if i < extra else "H-test"
        r["reason"] = f"u order rank {i + 1} of {len(rest)}"
    with args.out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(dict(gofer_fires=len(rows), survivors=n, forced_in_survivors=len(f_surv), extra_h_dev=extra,
               h_dev=sum(r["h"] == "H-dev" for r in rows), h_test=sum(r["h"] == "H-test" for r in rows)))
    for r in rows:
        print(r["h"] or "-", r["status"], r["gofer"], "|", r["reason"])


if __name__ == "__main__":
    main()
