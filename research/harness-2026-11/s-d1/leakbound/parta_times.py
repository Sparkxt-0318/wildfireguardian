"""Leak bound, step 1: part-a survey-time metadata (LEAK_BOUND_PLAN.md revision 1, 615ffc14, item 1).

first_utc, last_utc and the survey count are read for PART_A_ALLOWLIST_FINAL incidents ONLY, with Daniel's
allowlist-safe reader (data-fetch-3/nirops_access/nirops_access.py, ab065e85): the Incident_C column alone for all
records, then UTC by fid for allowlisted fids only (the reader refuses anything else). No other field is read.

Check, reported and never substituted: the same three quantities from the pinned part-a perimeter states
(data-fetch-3/parta_pool/perimeters/<id>/states.npz at 982eb71c, `times`), per-incident sha checked against
PERIMETER_MANIFEST.json. Output: PARTA_TIMES.csv (metadata values used by F1/F2) and PARTA_TIMES_CHECK.json.

    python parta_times.py --shp NIROPS_2020_2024_R1_R6.shp --allowlist PART_A_ALLOWLIST_FINAL.csv \
        --nirops-access <dir with nirops_access.py> --parta-pool <data-fetch-3/parta_pool> --out-dir DIR
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

NIROPS_ACCESS_SHA = None  # recorded in the output, not asserted (file identity is its commit ab065e85)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", type=Path, required=True)
    ap.add_argument("--allowlist", type=Path, required=True)
    ap.add_argument("--nirops-access", type=Path, required=True)
    ap.add_argument("--parta-pool", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    a = ap.parse_args()
    if not sha(a.allowlist).startswith("7db3cc0e"):
        raise SystemExit("not PART_A_ALLOWLIST_FINAL")
    allowed = sorted({r["Incident_C"] for r in csv.DictReader(a.allowlist.open())})
    sys.path.insert(0, str(a.nirops_access))
    import nirops_access as NA
    ids = NA.id_index(str(a.shp))
    fids = NA.allowlisted_fids(ids, allowed)
    df = NA.read_by_fid(str(a.shp), fids, ids, allowed, columns=["Incident_C", "UTC"])
    df["t"] = pd.to_datetime(df["UTC"], utc=True)
    meta = {}
    for inc, g in df.groupby("Incident_C"):
        t = g["t"].dropna()
        meta[inc] = dict(first_utc=t.min(), last_utc=t.max(), surveys=int(t.nunique()))
    manifest = json.loads((a.parta_pool / "PERIMETER_MANIFEST.json").read_text())
    check, diffs = [], []
    for inc in allowed:
        p = a.parta_pool / "perimeters" / inc / "states.npz"
        rec = manifest["events"][inc]
        if sha(p) != rec["states_sha256"]:
            raise SystemExit(f"states sha mismatch: {inc}")
        times = pd.to_datetime(np.load(p, allow_pickle=False)["times"], utc=True)
        s = dict(first_utc=times.min(), last_utc=times.max(), surveys=int(len(pd.unique(times))))
        m = meta.get(inc)
        if m is None:
            check.append(dict(incident=inc, metadata="MISSING"))
            continue
        d = dict(incident=inc, d_first_s=(m["first_utc"] - s["first_utc"]).total_seconds(),
                 d_last_s=(m["last_utc"] - s["last_utc"]).total_seconds(), d_surveys=m["surveys"] - s["surveys"])
        check.append(d)
        if d["d_first_s"] or d["d_last_s"] or d["d_surveys"]:
            diffs.append(d)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    with (a.out_dir / "PARTA_TIMES.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Incident_C", "first_utc", "last_utc", "surveys"])
        for inc in allowed:
            if inc in meta:
                m = meta[inc]
                w.writerow([inc, m["first_utc"].isoformat(), m["last_utc"].isoformat(), m["surveys"]])
    out = dict(plan="LEAK_BOUND_PLAN.md rev 1 (615ffc14) item 1", allowlist_sha256=sha(a.allowlist),
               shapefile_sha256=sha(a.shp), nirops_access_sha256=sha(a.nirops_access / "nirops_access.py"),
               perimeter_manifest_sha256=sha(a.parta_pool / "PERIMETER_MANIFEST.json"),
               parta_times_sha256=sha(a.out_dir / "PARTA_TIMES.csv"), n_allowlisted=len(allowed),
               n_with_metadata=len(meta), n_records_read=int(len(df)),
               n_differ_from_states=len(diffs),
               max_abs_d_last_s=max((abs(d["d_last_s"]) for d in diffs), default=0.0),
               max_abs_d_first_s=max((abs(d["d_first_s"]) for d in diffs), default=0.0),
               max_abs_d_surveys=max((abs(d["d_surveys"]) for d in diffs), default=0),
               differing=diffs)
    (a.out_dir / "PARTA_TIMES_CHECK.json").write_text(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "differing"}, default=str))


if __name__ == "__main__":
    main()
