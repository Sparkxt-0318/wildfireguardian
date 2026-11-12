"""Descriptive test: does the hourly 4-cell reach cap bind between consecutive NIROPS survey perimeters?

Data: NIROPS 2020-2024 (Magstadt et al., Mendeley 10.17632/95rj5d379g.1, CC-BY-4.0), archive sha256
b19fb16c...5615, one shapefile of 12,706 airborne-IR perimeters. Fetch with Daniel's fetch.py
(`python fetch.py get nirops_2020_2024_perimeters`), unzip into its own directory, pass the .shp path.

Per incident: perimeters are sorted by UTC, projected to the incident's UTM zone, rasterised onto a
375 m grid (cell-centre inclusion) and accumulated (B_k = B_{k-1} | raster_k). For each consecutive
survey pair with gap g hours (0 < g <= --max-gap), the newly burned cells N = B_k & ~B_{k-1} get their
chessboard distance d (cells) to B_{k-1}. A cell is beyond the hourly CA's reach after ceil(g) hourly
steps when d > 4 ceil(g). The implied minimum mean advance d / g (cells/h) is also reported.

Incidents used: ONLY the S-D9 D1 training pool, i.e. the part-a allowlist
(research/harness-2026-11/S-D9/cohort/PART_A_ALLOWLIST.csv at bba8d00d, branch
claude/s-d9-forecast-benchmark; 586 incidents) plus the 23 forecast-v2 US fit fires
(research/forecast-v2/SPLIT.json "fit.us_perimeter_and_kriged"). Parts b-d and all held-out fires are
never read. The two groups are reported separately.

    python research/harness-2026-11/s-d1/nirops_cap.py --shp .../NIROPS_2020_2024_R1_R6.shp --allowlist PART_A_ALLOWLIST.csv
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

CELL = 375.0
HELD_OUT = {"ID-BOF-000683_Wapiti_Wapiti", "ID-BOF-000904_Goat", "ID-BOF-001080_Lava",
            "ID-SCF-240202_RedRock", "WA-SES-000173_Pioneer", "WY-BTF-002416_FishCreek"}
REPO = Path(__file__).resolve().parents[3]


def main():
    import pyogrio
    from rasterio.features import rasterize
    from rasterio.transform import from_origin
    from scipy.ndimage import distance_transform_cdt
    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", required=True)
    ap.add_argument("--allowlist", required=True, help="S-D9 PART_A_ALLOWLIST.csv")
    ap.add_argument("--max-gap", type=float, default=48.0)
    ap.add_argument("--out", default=str(Path(__file__).with_name("RESULTS_nirops_cap.json")))
    args = ap.parse_args()
    part_a = set(pd.read_csv(args.allowlist)["Incident_C"])
    fit = set(json.loads((REPO / "research/forecast-v2/SPLIT.json").read_text())["fit"]["us_perimeter_and_kriged"])
    allowed = part_a | fit
    attrs = pyogrio.read_dataframe(args.shp, read_geometry=False)
    attrs["fid"] = np.arange(len(attrs))
    attrs["t"] = pd.to_datetime(attrs["UTC"])
    pairs = []
    per_inc = {}
    for inc, a in attrs.groupby("Incident_C", sort=True):
        if inc not in allowed or inc in HELD_OUT or len(a) < 2:
            continue
        g = pyogrio.read_dataframe(args.shp, fids=a["fid"].to_numpy())
        g["t"] = pd.to_datetime(g["UTC"])
        g = g[g.geometry.notna() & ~g.geometry.is_empty].sort_values("t").reset_index(drop=True)
        if len(g) < 2:
            continue
        g = g.to_crs(g.estimate_utm_crs())
        minx, miny, maxx, maxy = g.total_bounds
        pad = 8 * CELL
        x0 = math.floor((minx - pad) / CELL) * CELL
        y1 = math.ceil((maxy + pad) / CELL) * CELL
        w = int(math.ceil((maxx + pad - x0) / CELL))
        h = int(math.ceil((y1 - (miny - pad)) / CELL))
        if w * h > 4_000_000:
            continue
        tf = from_origin(x0, y1, CELL, CELL)
        burned = None
        rows = []
        for k in range(len(g)):
            r = rasterize([(g.geometry.iloc[k], 1)], out_shape=(h, w), transform=tf, fill=0,
                          dtype="uint8").astype(bool)
            if burned is None:
                burned = r
                continue
            gap = (g.loc[k, "t"] - g.loc[k - 1, "t"]).total_seconds() / 3600
            new = r & ~burned
            if 0 < gap <= args.max_gap and new.any() and burned.any():
                d = distance_transform_cdt(~burned, metric="chessboard")[new].astype(float)
                steps = math.ceil(gap - 1e-9)
                rows.append(dict(incident=inc, t=str(g.loc[k, "t"]), gap_h=gap, new_cells=int(d.size),
                                 beyond_cap=int((d > 4 * steps).sum()),
                                 max_d=float(d.max()), max_rate=float(d.max() / gap),
                                 q90_rate=float(np.quantile(d, 0.9) / gap)))
            burned |= r
        if rows:
            pairs.extend(rows)
            nc = sum(x["new_cells"] for x in rows)
            bc = sum(x["beyond_cap"] for x in rows)
            per_inc[inc] = dict(pairs=len(rows), new_cells=nc, beyond_cap=bc, group="fit23" if inc in fit else "part_a",
                                max_rate_cells_per_h=max(x["max_rate"] for x in rows))
    df = pd.DataFrame(pairs)

    def summary(sub):
        if sub.empty:
            return None
        return dict(incidents=int(sub["incident"].nunique()), pairs=len(sub), new_cells=int(sub["new_cells"].sum()),
                    share_cells_beyond_cap=float(sub["beyond_cap"].sum() / sub["new_cells"].sum()),
                    pairs_with_any_beyond_cap=int((sub["beyond_cap"] > 0).sum()),
                    gap_h_q10_q50_q90=[float(x) for x in np.quantile(sub["gap_h"], [0.1, 0.5, 0.9])],
                    pair_max_rate_cells_per_h_q50_q90_q99_max=[
                        float(x) for x in np.quantile(sub["max_rate"], [0.5, 0.9, 0.99, 1.0])])

    in_fit = df["incident"].isin(fit)
    result = dict(
        source="NIROPS 2020-2024 R1-R6 (Mendeley 10.17632/95rj5d379g.1), archive sha256 b19fb16ce2792d9a9c01f1768d09962566b0f3cada8d1f23a9851ab3fce75615",
        grid="incident UTM, 375 m, cell-centre inclusion, cumulative",
        cap="chessboard distance > 4 * ceil(gap_hours)", max_gap_h=args.max_gap,
        incidents_allowed=dict(part_a=len(part_a), fit23=len(fit)),
        all_pairs=summary(df), fit23=summary(df[in_fit]), part_a=summary(df[~in_fit]),
        short_gaps_le_12h=summary(df[df["gap_h"] <= 12]),
        per_incident=per_inc)
    print(json.dumps({k: v for k, v in result.items() if k != "per_incident"}, indent=1))
    Path(args.out).write_text(json.dumps(result, indent=1))
    df.to_csv(Path(args.out).with_suffix(".pairs.csv.gz"), index=False)


if __name__ == "__main__":
    main()
