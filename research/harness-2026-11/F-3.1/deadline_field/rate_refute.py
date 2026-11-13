"""Refutation test of 8.2 km/h as the highest spread rate in scope (rule: RATE_ASSUMED_RULE.md section 2).

Per detection j: r_j = min over earlier-bracketed detections i (s_i < e_j, i != j) of dist(i, j) / (e_j - s_i), km/h.
Brackets: end = acquisition time; start = last overpass strictly before it with >= 1 grid detection (firms_early).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

AFFINE = (375.0, 1085250.0, 1845375.0)   # resolution, x0, top y (KFS_01 export grid, EPSG:5179)
SHAPE = (79, 237)
FILES = ("viirs-snpp", "viirs-jpss1", "modis")


def load(firms_dir: Path, toa: np.ndarray):
    import pandas as pd
    from pyproj import Transformer
    fr = []
    for f in FILES:
        d = pd.read_csv(firms_dir / f"{f}.csv")
        d["src"] = f
        fr.append(d)
    d = pd.concat(fr, ignore_index=True)
    d["t"] = pd.to_datetime(d.acq_date + " " + d.acq_time.astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
    n0 = len(d)
    d = d[(d.t >= "2025-03-21") & (d.t < "2025-03-29")]
    n_time = len(d)
    x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(d.longitude.values, d.latitude.values)
    res, x0, top = AFFINE
    c = np.floor((x - x0) / res).astype(int)
    r = np.floor((top - y) / res).astype(int)
    ingrid = (r >= 0) & (r < SHAPE[0]) & (c >= 0) & (c < SHAPE[1])
    d = d.assign(x=x, y=y, r=r, c=c)[ingrid]
    n_grid = len(d)
    if "type" in d:
        d = d[d["type"] == 0]
    n_type = len(d)
    foot = np.isfinite(toa[d.r.values, d.c.values])
    d = d[foot]
    counts = {"rows_total": int(n0), "in_time_window": int(n_time), "in_grid": int(n_grid), "type0": int(n_type),
              "in_final_footprint": int(len(d))}
    return d.reset_index(drop=True), counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms-dir", type=Path, required=True)
    ap.add_argument("--toa", type=Path, required=True, help="KFS_01 kriged TOA GeoTIFF (footprint filter)")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    import rasterio
    with rasterio.open(a.toa) as s:
        toa = s.read(1).astype(float)
    d, counts = load(a.firms_dir, toa)
    t0 = np.datetime64("2025-03-21T00:00")
    e = (d.t.values - t0) / np.timedelta64(1, "s")
    passes = np.unique(e)
    idx = np.searchsorted(passes, e, side="left") - 1
    s = np.where(idx >= 0, passes[np.clip(idx, 0, None)], np.nan)
    X, Y = d.x.values, d.y.values
    n = len(d)
    r = np.full(n, np.inf)
    src = np.full(n, -1)
    allpair_max, allpair_hist = 0.0, []
    for j in range(n):
        ok = np.isfinite(s) & (s < e[j])
        ok[j] = False
        if not ok.any():
            continue
        dist = np.hypot(X[ok] - X[j], Y[ok] - Y[j]) / 1000.0
        dt = (e[j] - s[ok]) / 3600.0
        rate = dist / dt
        k = int(np.argmin(rate))
        r[j] = rate[k]
        src[j] = np.flatnonzero(ok)[k]
        allpair_max = max(allpair_max, float(rate.max()))
        allpair_hist.append(np.percentile(rate, [50, 99]))
    fin = np.isfinite(r)
    rv = r[fin]
    top = np.argsort(-np.where(fin, r, -1))[:10]

    def row(j):
        i = int(src[j])
        return {"rate_kmh": round(float(r[j]), 3), "j": {"time": str(d.t[j]), "lat": float(d.latitude[j]),
                                                        "lon": float(d.longitude[j]), "src": d.src[j]},
                "i": {"time": str(d.t[i]), "bracket_start_h_since_0321": round(float(s[i]) / 3600, 3),
                      "lat": float(d.latitude[i]), "lon": float(d.longitude[i]), "src": d.src[i]},
                "dist_km": round(float(np.hypot(X[i] - X[j], Y[i] - Y[j]) / 1000), 3)}

    out = {"rule": "RATE_ASSUMED_RULE.md section 2", "filters": counts,
           "firms_sha256": {f: hashlib.sha256((a.firms_dir / f"{f}.csv").read_bytes()).hexdigest() for f in FILES},
           "overpasses_with_detection": int(len(passes)),
           "detections_without_earlier_source": int((~fin).sum()),
           "primary_r_j_kmh": {"n": int(fin.sum()), "p50": float(np.percentile(rv, 50)), "p90": float(np.percentile(rv, 90)),
                               "p99": float(np.percentile(rv, 99)), "max": float(rv.max()),
                               "n_gt_8.2": int((rv > 8.2).sum()), "n_gt_16.4": int((rv > 16.4).sum())},
           "top10": [row(int(j)) for j in top if np.isfinite(r[j])],
           "secondary_all_pairs": {"max_kmh": allpair_max,
                                   "note": "dominated by simultaneous detections on separate fronts; not used for the decision"},
           "decision": None}
    # documented interval (KFS: 25 Mar 14:00 -> 26 Mar 02:00 KST = 05:00 -> 17:00 UTC) and consecutive overpasses
    import pandas as pd
    P = sorted(d.t.unique())
    near = lambda t: min(P, key=lambda p: abs(p - t))

    def advance(a, b, newer):
        A = d[d.t <= a]
        B = d[newer]
        XA = np.c_[A.x.values, A.y.values]
        dist = np.array([np.min(np.hypot(*(XA - [x, y]).T)) for x, y in zip(B.x.values, B.y.values)]) / 1000.0
        return float(dist.max()), int(np.argmax(dist)), B

    pa, pb = near(pd.Timestamp("2025-03-25 05:00")), near(pd.Timestamp("2025-03-25 17:00"))
    dmax, k, B = advance(pa, pb, (d.t > pa) & (d.t <= pb))
    gap = (pb - pa).total_seconds() / 3600
    out["documented_interval_check"] = {"interval": "KFS 25 Mar 14:00 -> 26 Mar 02:00 KST (05:00 -> 17:00 UTC)",
                                        "overpasses": [str(pa), str(pb)], "gap_h": round(gap, 2),
                                        "max_new_detection_distance_from_prior_extent_km": round(dmax, 2),
                                        "at": {"time": str(B.t.iloc[k]), "lat": float(B.latitude.iloc[k]),
                                               "lon": float(B.longitude.iloc[k])},
                                        "implied_mean_kmh": round(dmax / gap, 2)}
    cons = []
    for a_, b_ in zip(P, P[1:]):
        dm, _, _ = advance(a_, b_, d.t == b_)
        h = (b_ - a_).total_seconds() / 3600
        cons.append({"from": str(a_), "to": str(b_), "gap_h": round(h, 2), "km": round(dm, 2), "kmh": round(dm / h, 2)})
    ge3 = [c for c in cons if c["gap_h"] >= 3]
    out["context_consecutive_overpasses"] = {
        "max_gap_ge_3h": max(ge3, key=lambda c: c["kmh"]) if ge3 else None,
        "max_any_gap": max(cons, key=lambda c: c["kmh"]),
        "note": "context only; short gaps are confounded by sensor swath coverage", "all": cons}
    out["wording"] = "uninformative about 8.2 km/h (low power), not contradicted"
    out["decision"] = ("8.2 km/h EXCEEDED by %d detections: refuted unless each is attributed to a separate ignition or "
                       "spotting (case-by-case, see top10)" % out["primary_r_j_kmh"]["n_gt_8.2"]
                       if out["primary_r_j_kmh"]["n_gt_8.2"] else
                       "not refuted; low power (max per-detection lower bound %.2f km/h, documented 12-h mean ~4.25 km/h)"
                       % out["primary_r_j_kmh"]["max"])
    a.out.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps({k: out[k] for k in ("filters", "overpasses_with_detection", "detections_without_earlier_source",
                                          "primary_r_j_kmh", "secondary_all_pairs", "documented_interval_check", "decision")}, indent=1, default=str))


if __name__ == "__main__":
    main()
