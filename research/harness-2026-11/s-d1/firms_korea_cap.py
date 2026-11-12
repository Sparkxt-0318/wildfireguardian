"""Descriptive: advance of VIIRS active-fire detections between consecutive overpasses, Korea 2025.

No multi-perimeter product exists for the 2025 Korean fires in this environment; VIIRS I-band active-fire
pixels (375 m, the forecast grid size) are the closest public substitute. Data: FIRMS country yearly
archives (S-NPP, NOAA-20; standard processing v2), committed by Daniel on daniel/data-fetch under
research/harness-2026-11/data-fetch/small/firms/.

Box lon 128.2-129.7, lat 36.1-36.8 (Uiseong-Andong-Cheongsong-Yeongyang-Yeongdeok complex), 2025-03-21
to 03-31 UTC, confidence 'l' (low) excluded. Each satellite overpass (satellite + acq_date + acq_time) is
one observation. Detections are projected to EPSG:5179 and binned to a 375 m grid; the cumulative
detected set D_{k-1} is everything detected in earlier overpasses. For overpass k with gap g hours to the
previous overpass, each newly detected cell gets its chessboard distance d (cells) to D_{k-1};
"beyond cap" is d > 4 ceil(g).

HELD-OUT NOTE: KFS_01 (Uiseong 2025) and the other 2025 Korean fires are held out in research/forecast-v2/SPLIT.json.
This script reads only public satellite detections (no model, no forecast, no score) and was requested by the
orchestrator for sizing; it must not inform any development decision of a forecast scored on those fires.

Caveats (the result is descriptive, likely an upper bound on true jumps): clouds/smoke and the overpass
geometry cause omissions, so a cell first detected late may have burned much earlier; a new detection
far from all earlier ones may be a separate ignition (or spotting) as much as fast spread; active-fire
pixels mark flaming at overpass time, not the fire front.

    python research/harness-2026-11/s-d1/firms_korea_cap.py --firms-dir DIR
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

CELL = 375.0
BOX = (128.2, 36.1, 129.7, 36.8)


def main():
    from pyproj import Transformer
    from scipy.ndimage import distance_transform_cdt
    ap = argparse.ArgumentParser()
    ap.add_argument("--firms-dir", required=True)
    ap.add_argument("--out", default=str(Path(__file__).with_name("RESULTS_firms_korea_cap.json")))
    args = ap.parse_args()
    frames = []
    for name in ("viirs-snpp_2025_Republic_of_Korea.csv", "viirs-jpss1_2025_Republic_of_Korea.csv"):
        frames.append(pd.read_csv(Path(args.firms_dir) / name))
    df = pd.concat(frames, ignore_index=True)
    df["t"] = pd.to_datetime(df["acq_date"] + " " + df["acq_time"].astype(str).str.zfill(4), format="%Y-%m-%d %H%M")
    m = ((df.longitude >= BOX[0]) & (df.longitude <= BOX[2]) & (df.latitude >= BOX[1]) & (df.latitude <= BOX[3])
         & (df.t >= "2025-03-21") & (df.t < "2025-04-01") & (df.confidence != "l"))
    df = df[m].copy()
    x, y = Transformer.from_crs(4326, 5179, always_xy=True).transform(df.longitude.values, df.latitude.values)
    col = np.floor((x - x.min()) / CELL).astype(int) + 8
    row = np.floor((y.max() - y) / CELL).astype(int) + 8
    df["row"], df["col"] = row, col
    H, W = row.max() + 9, col.max() + 9
    passes = df.groupby(["satellite", "t"]).size().reset_index().sort_values("t")
    detected = np.zeros((H, W), bool)
    prev_t = None
    rows = []
    dists = []  # (gap_h, d_cells) per newly detected cell
    for _, p in passes.iterrows():
        sel = df[(df.satellite == p["satellite"]) & (df.t == p["t"])]
        cells = np.zeros((H, W), bool)
        cells[sel.row.values, sel.col.values] = True
        new = cells & ~detected
        if prev_t is not None and detected.any() and new.any():
            gap = (p["t"] - prev_t).total_seconds() / 3600
            d = distance_transform_cdt(~detected, metric="chessboard")[new].astype(float)
            dists.extend((gap, x) for x in d)
            rows.append(dict(satellite=p["satellite"], t=str(p["t"]), gap_h=gap, new_cells=int(d.size),
                             beyond_cap=int((d > 4 * math.ceil(gap - 1e-9)).sum()),
                             d_q50=float(np.median(d)), d_max=float(d.max()),
                             max_rate_cells_per_h=float(d.max() / gap)))
        detected |= cells
        prev_t = p["t"]
    t = pd.DataFrame(rows)
    dd = pd.DataFrame(dists, columns=["gap_h", "d_cells"])
    # Chessboard cells -> km: a chessboard distance of d cells spans d*0.375 km (axis) to d*0.53 km (diagonal);
    # the axis value is reported (lower end).
    dd["d_km"] = dd.d_cells * CELL / 1000

    def envelope(sub):
        if sub.empty:
            return None
        q = [0.5, 0.9, 0.95, 0.99, 1.0]
        return dict(new_cells=len(sub), d_km_q50_q90_q95_q99_max=[float(x) for x in np.quantile(sub.d_km, q)],
                    share_d_gt_0p5km=float((sub.d_km > 0.5).mean()), share_d_gt_1km=float((sub.d_km > 1).mean()),
                    share_d_gt_2km=float((sub.d_km > 2).mean()))
    out = dict(box=BOX, overpasses=int(len(passes)), detections=int(len(df)), cells_ever_detected=int(detected.sum()),
               pairs=len(t), new_cells=int(t.new_cells.sum()),
               share_new_cells_beyond_cap=float(t.beyond_cap.sum() / t.new_cells.sum()),
               short_gap_le_3h=dict(pairs=int((t.gap_h <= 3).sum()),
                                    new_cells=int(t[t.gap_h <= 3].new_cells.sum()),
                                    beyond_cap=int(t[t.gap_h <= 3].beyond_cap.sum())),
               jump_envelope_km=dict(
                   note="distance of each newly detected 375 m cell to all earlier detections; an UPPER envelope on "
                        "advance per overpass gap (omissions inflate it), not measured spotting or spread rate",
                   gap_le_0p5h=envelope(dd[dd.gap_h <= 0.5]), gap_0p5_to_3h=envelope(dd[(dd.gap_h > 0.5) & (dd.gap_h <= 3)]),
                   gap_3_to_13h=envelope(dd[(dd.gap_h > 3) & (dd.gap_h <= 13)]), all=envelope(dd)),
               per_overpass=rows)
    print(json.dumps({k: v for k, v in out.items() if k != "per_overpass"}, indent=1))
    print(t.to_string())
    Path(args.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
