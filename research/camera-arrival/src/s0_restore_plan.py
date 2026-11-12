#!/usr/bin/env python3
"""Step 0 add-on: which HPWREN 3 h video blocks would a restore request need?

For the Bobcat fire (GOFER v0.2 Combined hourly perimeters) and the Mount Wilson fixed
cameras, rasterise every hourly cumulative perimeter onto the camera-centred 30 m grid
saved by s0_feasibility.py, and count the NEW burned area per hour that is (a) inside the
camera's horizontal FOV and (b) terrain-visible from the camera (ground-surface line of sight).
Hours are grouped into HPWREN 3 h blocks (Q1..Q8, Pacific local time; GOFER hour (T-1h, T]
is assigned to the block containing T-30 min).

Output: outputs/restore_plan_bobcat_wilson.csv (+ printed ranking).
Credits: HPWREN (hpwren.ucsd.edu), UC San Diego; GOFER v0.2 Liu et al. doi:10.5281/zenodo.14642378;
DEM AWS Terrain Tiles skadi 1-arcsec. Visibility = terrain line of sight only (not flame detection).
Run: python3 -I src/s0_restore_plan.py
"""
import pathlib
import numpy as np, pandas as pd, geopandas as gpd
import rasterio.features
from affine import Affine
from pyproj import CRS

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIRE, SITE = "Bobcat", "wilson"
CAMS = {"wilson-n-mobo-c": (0, 90), "wilson-e-mobo-c": (90, 90), "wilson-s-mobo-c": (180, 90),
        "wilson-w-mobo-c": (270, 90)}  # azimuth, HFOV from outputs/hpwren_cameras.csv


def main():
    z = np.load(ROOT / f"cache/feasibility/{FIRE}__{SITE}.npz", allow_pickle=True)
    tr = Affine(*z["transform"])
    crs = CRS.from_proj4(str(z["crs"]))
    H, W = z["burned"].shape
    rows, cols, vis, az = z["rows"], z["cols"], z["vis0"], z["az"]
    idx = np.full((H, W), -1, int)
    idx[rows, cols] = np.arange(len(rows))
    p = gpd.read_file(ROOT / "cache/gofer/x/GOFER/GOFER_Combined/GOFERC_fireProg.shp")
    p = p[p.fname == FIRE].sort_values("timestep").to_crs(crs)
    first_hour = np.full(len(rows), -1, int)
    times = []
    for k, (_, r) in enumerate(p.iterrows()):
        m = rasterio.features.rasterize([(r.geometry, 1)], out_shape=(H, W), transform=tr, dtype="uint8").astype(bool)
        ii = idx[m]
        ii = ii[ii >= 0]
        new = ii[first_hour[ii] < 0]
        first_hour[new] = k
        times.append(pd.Timestamp(r.tUTC, tz="UTC"))
    cell_km2 = 0.03 * 0.03
    out = []
    for k, t in enumerate(times):
        sel = first_hour == k
        tp = (t - pd.Timedelta(minutes=30)).tz_convert("America/Los_Angeles")
        row = dict(t_end_utc=t.strftime("%Y-%m-%d %H:%M"), pacific_date=tp.strftime("%Y-%m-%d"),
                   hpwren_block=f"Q{tp.hour // 3 + 1}", new_burned_km2=round(sel.sum() * cell_km2, 3))
        for cam, (a, h) in CAMS.items():
            dd = (az - a + 180) % 360 - 180
            fov = np.abs(dd) <= h / 2
            row[f"{cam}_new_visible_km2"] = round((sel & fov & vis).sum() * cell_km2, 3)
        out.append(row)
    D = pd.DataFrame(out)
    B = D.groupby(["pacific_date", "hpwren_block"]).sum(numeric_only=True).reset_index()
    B = B.sort_values("wilson-e-mobo-c_new_visible_km2", ascending=False)
    with open(ROOT / "outputs/restore_plan_bobcat_wilson.csv", "w") as f:
        f.write("# HPWREN (hpwren.ucsd.edu), UC San Diego; GOFER v0.2 (doi:10.5281/zenodo.14642378); "
                "terrain line of sight only; GOFER hourly times are nominal.\n")
        B.to_csv(f, index=False)
    D.to_csv(ROOT / "cache/feasibility/bobcat_wilson_hourly.csv", index=False)
    print("cells never covered by an hourly perimeter:", int((first_hour < 0).sum()))
    print(B.head(15).to_string(index=False))
    tot = B.sum(numeric_only=True)
    print("totals km2:", tot.to_dict())


if __name__ == "__main__":
    main()
