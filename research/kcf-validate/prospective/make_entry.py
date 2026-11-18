"""Make one PROSPECTIVE_LOG entry: a prediction fixed before its outcome, with hashes. Usage:

  python3 make_entry.py --fire-id ID --since-utc 2026-11-20T00:00:00Z --issue-utc 2026-11-20T03:00:00Z --retrieved-utc 2026-11-20T02:50:00Z \\
      --firms-csv viirs.csv [--firms-csv modis.csv ...] --bbox LON0 LAT0 LON1 LAT1 --out predictions/ID/20261120T030000Z [--dry-run]

Inputs the operator supplies: FIRMS-format CSVs (latitude, longitude, acq_date, acq_time, satellite, instrument, confidence, type)
that were retrieved BEFORE the issue time. The known fire area follows research/kcf-replay/HOTSPOT_RULE.md (VIIRS confidence n/h,
radius 375 m; MODIS confidence >= 30, radius 1000 m; type 0; only rows with acquisition time strictly before the issue time). The
prediction is the replay's MEASURED arm unchanged: class by prior-3 h spread, R5/R8 from research/kcf-margin, closure time of every
375 m lattice cell. Himawari AHI hotspots are NOT used by this script (add them as extra --discs-json entries if retrieved).
Output files: prediction.json (claims + hashes), arrival_minutes.tif (roadlayer input format), inputs/ (copies, hashed).
--dry-run only changes the label. The entry is committed AND PUSHED by the operator before the earliest outcome time (see the log).
"""
from __future__ import annotations

import argparse, csv, hashlib, json, math, shutil, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from pyproj import Transformer

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "research/kcf-replay")); sys.path.insert(0, str(REPO / "product/wfg-roadlayer"))
import measured_arms as MA  # noqa: E402
from wfg_roadlayer import geotiff  # noqa: E402

RES = 375.0


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def read_discs(paths, T, bbox, since):
    to5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    out = []
    for p in paths:
        for r in csv.DictReader(open(p, encoding="utf-8-sig")):
            lat, lon = float(r["latitude"]), float(r["longitude"])
            if not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
                continue
            t = datetime.strptime(r["acq_date"] + r["acq_time"].zfill(4), "%Y-%m-%d%H%M").replace(tzinfo=timezone.utc)
            if t >= T or t < since or r.get("type", "0") not in ("0", ""):
                continue
            viirs = "VIIRS" in r["instrument"].upper()
            if viirs and r["confidence"] not in ("n", "h"):
                continue
            if not viirs and int(r["confidence"]) < 30:
                continue
            x, y = to5179.transform(lon, lat)
            out.append({"src": "FIRMS-" + r["satellite"], "t": t, "x": x, "y": y, "r_m": 375.0 if viirs else 1000.0})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fire-id", required=True); ap.add_argument("--since-utc", required=True, help="ignition / first detection of THIS fire, so older detections in the box are excluded"); ap.add_argument("--issue-utc", required=True); ap.add_argument("--retrieved-utc", required=True)
    ap.add_argument("--firms-csv", action="append", required=True); ap.add_argument("--bbox", nargs=4, type=float, required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    T, ret = utc(a.issue_utc), utc(a.retrieved_utc)
    if ret > T:
        raise SystemExit("REFUSED: inputs were retrieved after the issue time; a prediction cannot use them")
    out = Path(a.out); (out / "inputs").mkdir(parents=True, exist_ok=False)
    for p in a.firms_csv:
        shutil.copy(p, out / "inputs" / Path(p).name)
    discs = read_discs(a.firms_csv, T, a.bbox, utc(a.since_utc))
    if not discs:
        raise SystemExit("REFUSED: no detection before the issue time inside the box; nothing to predict from")
    r5, r8, cls, info = MA.curve("MEASURED", discs, T, 8)
    X = np.array([d["x"] for d in discs]); Y = np.array([d["y"] for d in discs]); R = np.array([d["r_m"] for d in discs])
    pad = r8 + 2000
    x0 = math.floor((X - R).min() - pad) // 375 * 375.0; x1 = math.ceil((X + R).max() + pad)
    y0 = math.floor((Y - R).min() - pad) // 375 * 375.0; y1 = math.ceil((Y + R).max() + pad)
    Wc = int(math.ceil((x1 - x0) / RES)); Hc = int(math.ceil((y1 - y0) / RES))
    cx = x0 + (np.arange(Wc) + 0.5) * RES; cy = y0 + (np.arange(Hc) + 0.5) * RES
    CX, CY = np.meshgrid(cx, cy)
    d = np.full(CX.shape, np.inf)
    for i in range(0, len(discs), 500):
        dd = np.sqrt((CX[..., None] - X[None, None, i:i + 500]) ** 2 + (CY[..., None] - Y[None, None, i:i + 500]) ** 2) - R[None, None, i:i + 500]
        d = np.minimum(d, np.maximum(dd, 0).min(-1))
    mins = np.full(CX.shape, np.inf)
    ok = np.isfinite(d) & (d <= r8)
    for k in zip(*np.where(ok)):
        s = MA.closure_s(r5, r8, float(d[k]))
        mins[k] = int(math.ceil(s)) / 60.0
    md = {"WFG_ISSUE_TIME": T.strftime("%Y-%m-%dT%H:%M:%SZ"), "WFG_HORIZON_MIN": "480", "WFG_UNITS": "minutes",
          "WFG_SOURCE": "kcf-validate prospective entry %s, MEASURED arm class %s" % (a.fire_id, cls)}
    geotiff.write(out / "arrival_minutes.tif", mins[::-1], (RES, 0.0, x0, 0.0, -RES, y0 + RES * Hc), 5179, nodata=float("nan"), metadata=md)
    pred = {
        "label": "DRY RUN (retrospective, NOT a prospective entry)" if a.dry_run else "PROSPECTIVE ENTRY",
        "notice": "Model output on detections only. Advisory. Not an order. Not what happened to people.",
        "fire_id": a.fire_id, "issue_utc": T.strftime("%Y-%m-%dT%H:%M:%SZ"), "inputs_retrieved_utc": ret.strftime("%Y-%m-%dT%H:%M:%SZ"), "detections_since_utc": utc(a.since_utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code_commit": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(),
        "rule": "research/kcf-replay HOTSPOT_RULE.md + MEASURED_RULE.md (unchanged); research/kcf-validate/PROTOCOL.md section 4",
        "known_area": {"n_discs": len(discs), "latest_detection_utc": max(x["t"] for x in discs).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "class": cls, "prior3h_spread_km": info, "R5_km": r5 / 1000, "R8_km": r8 / 1000},
        "claims": {
            "C1_zone_5h": "every lattice cell with closure <= 5 h (distance <= R5 from the known area) may be reached by fire before issue + 5 h; cells beyond are claimed NOT reached in that time",
            "C2_zone_8h": "same for 8 h with R8",
            "C3_per_cell_closure_minutes": "arrival_minutes.tif (value = minutes from issue time to closure; inf = not reached within 8 h)",
            "scoring": "after issue + 8 h: coverage of cells newly burned (FIRMS detections acquired in (issue, issue + 8 h] and, where a scene exists, Sentinel-2 dNBR) by the 5 h / 8 h zones, reported with misses, by research/kcf-validate/satellite_extent.py's rules"},
        "lattice": {"epsg": 5179, "x0": x0, "y0_south": y0, "res": RES, "cols": Wc, "rows": Hc, "cells_closed_within_8h": int(ok.sum()), "cells_closed_within_5h": int((mins <= 300).sum())},
        "files_sha256": {str(p.relative_to(out)): sha(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name != "prediction.json"},
    }
    (out / "prediction.json").write_text(json.dumps(pred, indent=1))
    print("prediction.json sha256", sha(out / "prediction.json"))
    print(json.dumps({k: pred[k] for k in ("label", "issue_utc", "known_area", "lattice")}, indent=1))


if __name__ == "__main__":
    main()
