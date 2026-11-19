"""Satellite detection limit for detached fire, against airborne infrared heat perimeters (PROTOCOL 2.5 (a)).

Dixie 2021 (Hatchett 2025, Zenodo 15492982): one map per flight night, date in the file name, no time of day. Flights
are taken to fall in 18:00-06:00 local (PDT) of the named night (ASSUMED; NIROPS flies at night).

An IR detached polygon: a heat-perimeter polygon at least 1.0 km from the largest polygon of the same map, at most
15 km from it, and not intersecting the previous map's heat perimeter (new fire, not an old island).
Seen by VIIRS: any VIIRS detection (S-NPP or NOAA-20, confidence not low) of the flight window within 0.5 km of the
polygon. Seen by GOFER: the GOFER perimeter at 09 UTC of the flight night, or the nearest earlier hour, within 0.5 km.

    python airir.py --ir DATA/airir/dixie --gofer DATA/gofer/x/GOFER --firms DATA/firms --out derived/airir_dixie.csv
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from run_spots import read_viirs  # noqa: E402


def heat_polys(path):
    import geopandas as gpd
    g = gpd.read_file(path)
    if "Name" in g and g.Name.astype(str).str.contains("Heat", case=False).any():
        g = g[g.Name.astype(str).str.contains("Perimeter", case=False)]
    g = g.explode(index_parts=False)
    g = g[g.geom_type == "Polygon"].to_crs(3310)
    return g.geometry.make_valid().explode(index_parts=False).pipe(lambda s: s[s.geom_type == "Polygon"]).reset_index(drop=True)


def main():
    import geopandas as gpd
    from shapely.ops import unary_union
    ap = argparse.ArgumentParser()
    ap.add_argument("--ir", required=True); ap.add_argument("--gofer", required=True)
    ap.add_argument("--firms", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--fire", default="Dixie"); ap.add_argument("--year", type=int, default=2021)
    a = ap.parse_args()
    files = sorted(Path(a.ir).glob("*.shp"))
    by_date = {}
    for f in files:
        m = re.match(r"(\d{8})_", f.name)
        if not m:
            continue
        name = f.name.lower()
        if ("intenseheat" in name or "scatteredheat" in name) and "perimeter" not in name:
            continue
        by_date.setdefault(m.group(1), []).append(f)
    gdf = gpd.read_file(Path(a.gofer) / "GOFER_Combined" / "GOFERC_fireProg.shp")
    gdf = gdf[gdf.fname == a.fire].copy()
    gdf["t"] = pd.to_datetime(gdf.tUTC)
    gdf = gdf.sort_values("t").to_crs(3310)
    vi = read_viirs(a.firms, "United_States", (a.year,))
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, 3310, always_xy=True)
    rows, prev = [], None
    for d in sorted(by_date):
        polys = pd.concat([heat_polys(f) for f in by_date[d]], ignore_index=True)
        if not len(polys):
            continue
        main_poly = polys.iloc[int(np.argmax(polys.area.values))]
        day = pd.Timestamp(d)
        w0, w1 = day + pd.Timedelta(hours=18 + 7), day + pd.Timedelta(hours=30 + 7)   # PDT = UTC - 7
        v = vi[(vi.t >= w0) & (vi.t <= w1)]
        bx = polys.total_bounds
        x, y = tr.transform(v.longitude.values, v.latitude.values)
        keep = (x > bx[0] - 20000) & (x < bx[2] + 20000) & (y > bx[1] - 20000) & (y < bx[3] + 20000)
        from shapely.geometry import MultiPoint
        vpts = MultiPoint(list(zip(x[keep], y[keep]))) if keep.any() else None
        g9 = gdf[gdf.t <= day + pd.Timedelta(hours=33)]          # 09 UTC next day = 02 PDT
        gper = g9.geometry.iloc[-1] if len(g9) else None
        gt = g9.t.iloc[-1] if len(g9) else pd.NaT
        n_viirs_window = int(keep.sum())
        for p in polys:
            dmain = p.distance(main_poly)
            if p.equals(main_poly) or dmain < 1000 or dmain > 15000:
                continue
            if prev is not None and p.intersects(prev):
                continue
            seen_v = bool(vpts is not None and p.distance(vpts) <= 500)
            seen_g = bool(gper is not None and p.distance(gper) <= 500)
            rows.append(dict(date=d, area_ha=p.area / 1e4, dist_main_km=dmain / 1000, seen_viirs=seen_v,
                             seen_gofer=seen_g, gofer_t=str(gt), viirs_dets_in_window=n_viirs_window,
                             n_polys_map=len(polys)))
        prev = unary_union(list(polys)) if prev is None else unary_union([prev] + list(polys))
        print(d, len(polys), "detached", sum(r["date"] == d for r in rows), "viirs", n_viirs_window, flush=True)
    pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
