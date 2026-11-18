"""Build the worked-example fire-arrival GeoTIFF for 25 March 2025 from research/kcf-replay (no new science).

For every 375 m cell of the KFS_01 lattice covering both regions (의성·안동 and 영덕), fire arrival after the issue
time T is the kcf-replay closure time of that cell, exactly as research/kcf-replay/replay.py::run_one computes it:

  * known fire area at T = union of the discs in research/kcf-replay/fire_discs.json with t < T (FIRMS + AHI,
    HOTSPOT_RULE.md);
  * distance d = min over discs of max(0, |cell centre - disc centre| - radius);
  * R(h) = the MEASURED arm (research/kcf-replay/MEASURED_RULE.md, frozen R(5 h), R(8 h) of research/kcf-margin
    picked by the prior-3 h spread class); closure second = ceil(measured_arms.closure_s(R5, R8, d)) if <= 8 h.

The raster stores closure_s / 60 (minutes, float64); +inf where the cell is not reached within 8 h. Metadata:
WFG_ISSUE_TIME, WFG_HORIZON_MIN = 480, WFG_UNITS = minutes, WFG_SOURCE.

Usage: python3 examples/build_example_raster.py [--issue 2025-03-25T09:00:00Z] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PRODUCT = HERE.parent
REPO = PRODUCT.parents[1]
sys.path.insert(0, str(PRODUCT))
sys.path.insert(0, str(REPO / "research/kcf-replay"))
import measured_arms as MA  # noqa: E402
from wfg_roadlayer import geotiff  # noqa: E402

# KFS_01 375 m lattice; covers yeongdeok_2025 (x0 1147500, 71 x 67) and uiseong_andong_2025 (x0 1093875, 73 x 65)
X0, Y0, RES, W, H = 1093875.0, 1815750.0, 375.0, 214, 67
HORIZON_S = 8 * 3600


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", default="2025-03-25T09:00:00Z")
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    T = datetime.fromisoformat(a.issue.replace("Z", "+00:00")).astimezone(timezone.utc)
    out = a.out or HERE / ("fire_arrival_%s_MEASURED_8h.tif" % T.strftime("%Y%m%dT%H%MZ"))
    discs = [dict(x, t=datetime.fromisoformat(x["t_utc"])) for x in
             json.loads((REPO / "research/kcf-replay/fire_discs.json").read_text())["discs"]]
    r5, r8, cls, info = MA.curve("MEASURED", discs, T, HORIZON_S // 3600)
    sel = [x for x in discs if x["t"] < T]
    cols = np.arange(W)
    rows = np.arange(H)  # south-up router rows
    cx = (X0 + (cols + 0.5) * RES)[None, :].repeat(H, 0).ravel()
    cy = (Y0 + (rows + 0.5) * RES)[:, None].repeat(W, 1).ravel()
    d = np.full(cx.shape, np.inf)
    if sel:
        Xd = np.array([x["x"] for x in sel]); Yd = np.array([x["y"] for x in sel]); Rd = np.array([x["r_m"] for x in sel])
        for i in range(0, len(sel), 2000):
            dd = np.sqrt((cx[:, None] - Xd[None, i:i + 2000]) ** 2 + (cy[:, None] - Yd[None, i:i + 2000]) ** 2) - Rd[None, i:i + 2000]
            d = np.minimum(d, np.maximum(dd, 0).min(1))
    minutes = np.full(cx.shape, np.inf)
    for k in range(cx.size):
        if np.isfinite(d[k]):
            s = MA.closure_s(r5, r8, float(d[k]))
            if s <= HORIZON_S:
                minutes[k] = int(math.ceil(s)) / 60.0
    grid = minutes.reshape(H, W)[::-1]  # north-up for the GeoTIFF
    md = {"WFG_ISSUE_TIME": T.strftime("%Y-%m-%dT%H:%M:%SZ"), "WFG_HORIZON_MIN": "480", "WFG_UNITS": "minutes",
          "WFG_SOURCE": "research/kcf-replay MEASURED arm, class %s (R5 %.1f km, R8 %.1f km), known fire area from "
                        "fire_discs.json before the issue time; worked example, not a forecast" % (cls, r5 / 1000, r8 / 1000)}
    geotiff.write(out, grid, (RES, 0.0, X0, 0.0, -RES, Y0 + RES * H), 5179, nodata=float("nan"), metadata=md)
    n = int(np.isfinite(minutes).sum())
    print("%s: class %s, R5 %.1f km, R8 %.1f km, %d discs before T, %d of %d cells reached within 8 h" %
          (out.name, cls, r5 / 1000, r8 / 1000, len(sel), n, minutes.size))


if __name__ == "__main__":
    main()
