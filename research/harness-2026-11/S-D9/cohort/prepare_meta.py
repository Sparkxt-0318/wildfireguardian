"""Adapt Daniel's incident_metadata.csv to apply_filters.py input (metadata only).

Writes meta.csv (all incidents) and ref.csv (FIT fires plus the SELECTED_ON fire
Wapiti), with columns Incident_C, poo_lat, poo_lon, discovery_date, first_utc, last_utc.
discovery_date is the UTC date of WFIGS FireDiscoveryDateTime.
  python prepare_meta.py --raw incident_metadata.csv --outdir DIR
"""
import argparse
import csv
import hashlib
from pathlib import Path

PINNED = "5246ce8f18f8923060490593849ad7e171f403e3e1e9b43fa2ba564f394fcb62"
SELECTED_ON = {"ID-BOF-000683_Wapiti_Wapiti"}

ap = argparse.ArgumentParser()
ap.add_argument("--raw", required=True, type=Path)
ap.add_argument("--outdir", required=True, type=Path)
a = ap.parse_args()
digest = hashlib.sha256(a.raw.read_bytes()).hexdigest()
if digest != PINNED:
    raise SystemExit(f"metadata sha256 {digest} != pinned {PINNED}")
rows = list(csv.DictReader(a.raw.open()))
cols = ["Incident_C", "poo_lat", "poo_lon", "discovery_date", "first_utc", "last_utc"]
a.outdir.mkdir(parents=True, exist_ok=True)
for name, keep in (("meta.csv", lambda r: True),
                   ("ref.csv", lambda r: r["group"] == "forecast_v2_fit" or r["Incident_C"] in SELECTED_ON)):
    with (a.outdir / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, lineterminator="\n")
        w.writeheader()
        for r in rows:
            if keep(r):
                w.writerow(dict(Incident_C=r["Incident_C"], poo_lat=r["poo_lat"], poo_lon=r["poo_lon"],
                                discovery_date=r["discovery_utc"][:10], first_utc=r["first_utc"], last_utc=r["last_utc"]))
print("ok", digest)
