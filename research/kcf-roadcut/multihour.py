"""Family M (PROTOCOL.md §1, §2): gap = T_village - T_road on the multi-hour F-DYN HEADLINE run (no_reentry/2).

T_road from research/harness-2026-11/F-3.1/results/HEADLINE_NR2_summary.json (CERT field, prefix sets, leave_by_s) and the
not-evaluated split; T_village from the Choi 2026 TOA (kriged_mean) and variants.firms_variants (firms_early; envelope =
its earliest bracket edge = firms_early, ASSUMED), at the KFS_01 export-grid cell of the place's entry node.

Usage: python3 multihour.py OUT.json
"""
from __future__ import annotations

import json, sys, tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import tifffile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "research/harness-2026-11/F-DYN/fdyn"))
import variants as V  # noqa: E402

F31 = ROOT / "research/harness-2026-11/F-3.1/results"
T0 = datetime(2025, 3, 22, 2, 24, tzinfo=timezone.utc)
KST = timezone(timedelta(hours=9))


def arrival_rasters():
    toa = tifffile.imread(ROOT / "research/harness-2026-11/data-fetch/small/choi2026_kfs01/KFS_01_pswt_ok_toa.tif").astype(float)
    src = ROOT / "research/harness-2026-11/data-fetch/small/firms"
    with tempfile.TemporaryDirectory() as td:
        for f in V.FIRMS_FILES:
            (Path(td) / f"{f}.csv").symlink_to(src / f"{f}_2025_Republic_of_Korea.csv")
        r, c, h, s = V.load_firms(Path(td))
    constrained, early, stats = V.firms_variants(toa, r, c, h, s)
    return {"kriged_mean": toa, "firms_early": early, "envelope": early}, stats


def entry_nodes():
    out = {}
    for region in ("yeongdeok_2025", "uiseong_andong_2025"):
        raw = json.loads((ROOT / f"data/routing/graphs/{region}/graph.json").read_text())
        xy = {n["id"]: (n["x"], n["y"]) for n in raw["nodes"]}
        for f in json.loads((ROOT / f"planner/public/data/regions/{region}/places.geojson").read_text())["features"]:
            p = f["properties"]
            if p.get("role") == "origin" and p.get("checkable"):
                out[(region, p["id"])] = {"xy": xy[p["entry"]["node"]], "name": p.get("name") or "",
                                          "sigungu": (p.get("sigungu") or {}).get("ko", ""), "category": p["category"],
                                          "vulnerable": bool(p.get("vulnerable"))}
    return out


def cell_rc(x, y):
    a = V.AFFINE
    return int(np.floor((a[5] - y) / -a[4])), int(np.floor((x - a[2]) / a[0]))


def classify(T, H, leave, censored, ne_class, tv):
    """-> state, T_road (datetime|None), gap_s (exact|None), gap_lb_s (lower bound|None), tv_state."""
    if tv is not None and tv <= T or ne_class == "not_evaluated":
        return "INSIDE", None, None, None, "inside"
    tv_in = tv is not None and tv <= T + timedelta(seconds=H)
    tv_state = "within_H" if tv_in else "censored"
    if leave is None:
        lb = (tv - T).total_seconds() if tv_in else H
        return "NO_WINDOW", None, None, lb, tv_state
    tr = T + timedelta(seconds=leave)
    if censored:
        return "NOT_CUT_WITHIN_H", tr, None, None, tv_state
    if tv_in:
        return "CUT", tr, (tv - tr).total_seconds(), None, tv_state
    return "CUT", tr, None, (T + timedelta(seconds=H) - tr).total_seconds(), tv_state


def main(out):
    rasters, stats = arrival_rasters()
    nodes = entry_nodes()
    summ = json.loads((F31 / "HEADLINE_NR2_summary.json").read_text())
    split = json.loads((F31 / "HEADLINE_NR2_not_evaluated_split.json").read_text())
    cls = {(r["region"], r["start"], r["horizon_h"], r["variant"], r["origin"]): r for r in split["rows"]}
    rows = []
    for p in summ["places"]:
        region, start, Hh, origin = p["region"], p["start"], p["horizon_h"], p["origin"]
        T = datetime.strptime(start, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        H = Hh * 3600
        nd = nodes[(region, origin)]
        r_, c_ = cell_rc(*nd["xy"])
        for var, x in p["nr_cert"]["per_variant"].items():
            a = rasters[var][r_, c_]
            tv = T0 + timedelta(hours=float(a)) if np.isfinite(a) else None
            sp = cls[(region, start, Hh, var, origin)]
            leave = x.get("leave_by_s")
            state, tr, gap, lb, tvs = classify(T, H, leave, x.get("horizon_censored"), sp["class"], tv)
            rows.append({"family": "M", "region": region, "place_id": origin, "name": nd["name"], "sigungu": nd["sigungu"],
                         "category": nd["category"], "vulnerable": nd["vulnerable"], "issue_utc": T.isoformat(),
                         "arm": var, "horizon": f"{Hh}h", "state": state, "split_class": sp["class"],
                         "no_route_reason": x.get("no_route"),
                         "windows_s": [[0, leave]] if leave is not None else [], "n_windows": 1 if leave is not None else 0,
                         "hole_s": 0, "T_road_utc": tr.isoformat() if tr else None,
                         "T_village_utc": tv.isoformat() if tv else None, "T_village_state": tvs,
                         "gap_s": gap, "gap_lower_bound_s": lb, "binding": None, "cell_rc": [r_, c_]})
    Path(out).write_text(json.dumps({"rows": rows, "firms_variant_stats": stats}))
    print(len(rows), "rows")


if __name__ == "__main__":
    main(sys.argv[1])
