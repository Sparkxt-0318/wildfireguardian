"""Per-cell NIROPS survey brackets for part-a training fires (raw-bracket arm input).

Reads ONLY incidents listed in S-D9's PART_A_ALLOWLIST_FINAL.csv (sha256 801acdd8...; each incident is
read with an attribute filter, nothing else is opened). Selection rule, fixed before any perimeter is
read: allowlisted incidents with ``surveys >= 20``, in Incident_C order.

For each incident:

* perimeters are reprojected to EPSG:5070 and rasterized on a 375 m grid snapped to multiples of 375 m;
  the grid covers the union of all surveys plus a 3-cell margin;
* a cell counts as mapped when its centre is inside the polygon (rasterio's default rule, the same as
  ``observed_evaluation.survey_reference``);
* the mapped extent is made monotone with a cumulative union, because NIROPS extents can shrink between
  surveys through mapping differences;
* each cell gets the index of the first survey containing it (``-1`` if never mapped), so its arrival
  bracket is ``(survey[k-1], survey[k]]``; cells mapped at the first survey are the initial burned state.

Survey times come from the ``UTC`` field. Output: one ``<incident>.npz`` per fire plus ``index.json``.
Access is logged in ``index.json`` (part-a use, per S-D9 ledger rules).

    python nirops_brackets.py --shp <NIROPS .shp> --allowlist PART_A_ALLOWLIST_FINAL.csv --out DIR
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

CELL = 375.0
MARGIN = 3


def main(argv=None):
    import pyogrio
    import shapely
    from pyproj import Transformer
    from rasterio import features
    from rasterio.transform import from_origin

    ap = argparse.ArgumentParser()
    ap.add_argument("--shp", type=Path, required=True)
    ap.add_argument("--allowlist", type=Path, required=True)
    ap.add_argument("--min-surveys", type=int, default=20)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    allow_sha = hashlib.sha256(a.allowlist.read_bytes()).hexdigest()
    al = pd.read_csv(a.allowlist)
    chosen = sorted(al.loc[al.surveys >= a.min_surveys, "Incident_C"])
    a.out.mkdir(parents=True, exist_ok=True)
    to5070 = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    index = dict(allowlist=str(a.allowlist.name), allowlist_sha256=allow_sha, rule=f"surveys >= {a.min_surveys}",
                 part="a", fires={})
    for inc in chosen:
        assert "'" not in inc
        meta, _, geom, fields = pyogrio.raw.read(a.shp, where=f"Incident_C = '{inc}'")
        df = pd.DataFrame({n: v for n, v in zip(meta["fields"], fields)})
        assert (df["Incident_C"] == inc).all()
        polys = shapely.from_wkb(geom)
        polys = shapely.transform(polys, lambda xy: np.column_stack(to5070.transform(xy[:, 0], xy[:, 1])))
        times = pd.to_datetime(df["UTC"], utc=True)
        order = np.argsort(times.to_numpy(), kind="stable")
        polys, times = polys[order], times.iloc[order].reset_index(drop=True)
        # Merge surveys with identical timestamps.
        uniq = times.drop_duplicates().index.to_numpy()
        merged = [shapely.union_all(polys[(times == times[i]).to_numpy()]) for i in uniq]
        times = times[uniq].reset_index(drop=True)
        xmin, ymin, xmax, ymax = shapely.total_bounds(np.array(merged))
        x0 = np.floor(xmin / CELL) * CELL - MARGIN * CELL
        y1 = np.ceil(ymax / CELL) * CELL + MARGIN * CELL
        w = int(np.ceil((xmax - x0) / CELL)) + MARGIN
        h = int(np.ceil((y1 - ymin) / CELL)) + MARGIN
        tr = from_origin(x0, y1, CELL, CELL)
        first = np.full((h, w), -1, np.int32)
        cum = np.zeros((h, w), bool)
        for k, poly in enumerate(merged):
            if poly.is_empty:
                continue
            m = features.rasterize([(poly, 1)], out_shape=(h, w), transform=tr, fill=0, dtype="uint8").astype(bool)
            new = m & ~cum
            first[new] = k
            cum |= m
        hours = ((times - times[0]).dt.total_seconds() / 3600).to_numpy()
        np.savez_compressed(a.out / f"{inc}.npz", first_survey=first, survey_hours=hours,
                            survey_utc=times.dt.strftime("%Y-%m-%dT%H:%M:%SZ").to_numpy().astype("U20"),
                            transform=np.array(tuple(tr)[:6]), epsg=5070)
        rec = dict(surveys=int(len(hours)), shape=[h, w], initial_cells=int((first == 0).sum()),
                   newly_mapped_cells=int((first > 0).sum()), span_hours=float(hours[-1]),
                   median_gap_hours=float(np.median(np.diff(hours))) if len(hours) > 1 else None)
        index["fires"][inc] = rec
        print(inc, json.dumps(rec))
    (a.out / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
