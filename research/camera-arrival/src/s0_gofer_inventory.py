#!/usr/bin/env python3
"""Step 0: GOFER archive inventory.
Downloads GOFER (Zenodo 14642378, v0.2), verifies md5, extracts, and writes
outputs/gofer_fires.csv, outputs/gofer_layout.md, cache/gofer/final_perimeters.gpkg.
Archive contents are untrusted data: only read with geopandas/pandas, nothing executed.
Run:  python3 -I src/s0_gofer_inventory.py
Data: GOFER, Liu et al. (2024) ESSD 16, 1395; doi:10.5281/zenodo.8327264 (v0.2: 10.5281/zenodo.14642378).
Camera context: HPWREN (hpwren.ucsd.edu), UC San Diego (no HPWREN data used in this step).
"""
import hashlib, json, os, sys, time, urllib.request, zipfile
import pandas as pd, geopandas as gpd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "cache", "gofer")
OUT = os.path.join(ROOT, "outputs")
REC = "https://zenodo.org/api/records/14642378"
MD5 = "8d495af1e4a0ed77df35b5a15d5ebb04"
ZIP = os.path.join(CACHE, "GOFER.zip")
EXT = os.path.join(CACHE, "x")
D = os.path.join(EXT, "GOFER")
CREDIT = "HPWREN (hpwren.ucsd.edu), UC San Diego; GOFER: Liu et al. 2024, doi:10.5281/zenodo.8327264"

def md5(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def fetch():
    os.makedirs(CACHE, exist_ok=True)
    if not (os.path.exists(ZIP) and md5(ZIP) == MD5):
        req = urllib.request.Request(REC, headers={"User-Agent": "research-poc-camera-arrival/0.1"})
        rec = json.load(urllib.request.urlopen(req))
        f = [x for x in rec["files"] if x["key"] == "GOFER.zip"][0]
        assert f["checksum"] == "md5:" + MD5
        req = urllib.request.Request(f["links"]["self"], headers={"User-Agent": "research-poc-camera-arrival/0.1"})
        with urllib.request.urlopen(req) as r, open(ZIP, "wb") as o:
            while (b := r.read(1 << 20)):
                o.write(b)
    assert md5(ZIP) == MD5, "md5 mismatch"
    if not os.path.isdir(D):
        os.makedirs(EXT, exist_ok=True)
        with zipfile.ZipFile(ZIP) as z:  # path-traversal safe: check names
            for n in z.namelist():
                assert not n.startswith("/") and ".." not in n.split("/"), n
            z.extractall(EXT)

def tree():
    lines = []
    for dp, dn, fn in sorted(os.walk(D)):
        dn.sort()
        rel = os.path.relpath(dp, D)
        lines.append(("GOFER/" + rel if rel != "." else "GOFER/"))
        for n in sorted(fn):
            if n == ".DS_Store":
                continue
            lines.append("    %s/%s  (%d bytes)" % (rel if rel != "." else "", n, os.path.getsize(os.path.join(dp, n))))
    return "\n".join(lines)

def main():
    fetch()
    comb = os.path.join(D, "GOFER_Combined")
    prog = gpd.read_file(os.path.join(comb, "GOFERC_fireProg.shp"))
    fd = pd.read_csv(os.path.join(D, "fireData.csv"))
    prog["t"] = pd.to_datetime(prog.tUTC)
    prog = prog.sort_values(["fyear", "fname", "timestep"]).reset_index(drop=True)
    fd["ig"] = pd.to_datetime(fd.GOESIg_UTC, format="%Y-%m-%d %H")

    # consistency checks used in the layout doc
    m = prog.merge(fd[["fname", "fyear", "ig"]], on=["fname", "fyear"])
    off = ((m.t - m.ig).dt.total_seconds() / 3600 - m.timestep)
    chk_ts = bool((off == 0).all())
    gaps = int(prog.groupby("fname").timestep.apply(lambda s: (s.diff().dropna() != 1).sum()).sum())
    shrink = int(prog.groupby("fname").farea.apply(lambda s: (s.diff() < 0).sum()).sum())

    rows, fin = [], []
    for (fy, fn), g in prog.groupby(["fyear", "fname"], sort=True):
        g = g.sort_values("timestep")
        last = g.iloc[-1]
        # bbox/centroid of the union of all hourly perimeters (full extent ever burned = final, cumulative)
        b = gpd.GeoSeries(g.geometry.values, crs=4326).total_bounds
        c = last.geometry.centroid
        ac = float(fd[(fd.fname == fn) & (fd.fyear == fy)].acres_official.iloc[0])
        rows.append(dict(name=fn, year=int(fy),
                         first_utc=g.t.min().strftime("%Y-%m-%d %H:%M"), last_utc=g.t.max().strftime("%Y-%m-%d %H:%M"),
                         n_hourly_steps=len(g), first_timestep=int(g.timestep.min()), last_timestep=int(g.timestep.max()),
                         ignition_utc_goes=fd[(fd.fname == fn) & (fd.fyear == fy)].ig.iloc[0].strftime("%Y-%m-%d %H:00"),
                         final_area_km2=round(float(last.farea), 2), official_acres=ac,
                         official_km2=round(ac * 0.00404686, 1),
                         lon_min=round(b[0], 4), lat_min=round(b[1], 4), lon_max=round(b[2], 4), lat_max=round(b[3], 4),
                         centroid_lon=round(c.x, 4), centroid_lat=round(c.y, 4)))
        fin.append(last)
    df = pd.DataFrame(rows)
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "gofer_fires.csv"), "w") as f:
        f.write("# Source: GOFER-Combined v0.2 (Liu et al. 2024, doi:10.5281/zenodo.8327264). Timestamps = END of hourly interval, UTC. Credit: HPWREN (hpwren.ucsd.edu), UC San Diego (camera data used in later steps).\n")
        df.to_csv(f, index=False)
    fp = gpd.GeoDataFrame(pd.DataFrame(fin).drop(columns=["t"]), geometry="geometry", crs=4326)
    fp = fp.merge(df[["name", "year"]].rename(columns={"name": "fname", "year": "fyear"}), on=["fname", "fyear"]) if False else fp
    gp = os.path.join(CACHE, "final_perimeters.gpkg")
    if os.path.exists(gp):
        os.remove(gp)
    fp.to_file(gp, layer="final_perimeters", driver="GPKG")

    # schemas for layout doc
    schema = []
    for v, pre in [("Combined", "C"), ("East", "E"), ("West", "W")]:
        for n in ["fireProg", "fireIg", "cfireLine", "rfireLine"]:
            p = os.path.join(D, "GOFER_" + v, "GOFER%s_%s.shp" % (pre, n))
            g = gpd.read_file(p)
            schema.append("| GOFER_%s/GOFER%s_%s.shp | %d | %s | %s | %s |" % (
                v, pre, n, len(g), ",".join(sorted(set(g.geom_type))), g.crs.to_string(),
                ", ".join(c for c in g.columns if c != "geometry")))
    summ = pd.read_csv(os.path.join(comb, "GOFERC_summary.csv"), nrows=1)
    rec = json.load(open(os.path.join(CACHE, "record.json"))) if os.path.exists(os.path.join(CACHE, "record.json")) else {}
    doc = open(os.path.join(CACHE, "docs", "README.md")).read() if os.path.exists(os.path.join(CACHE, "docs", "README.md")) else ""
    md = f"""# GOFER archive layout

Credit: {CREDIT}. Generated by `src/s0_gofer_inventory.py`.

## Provenance
- Zenodo record 14642378 (GOFER v0.2), file `GOFER.zip`, 75,711,678 bytes, md5 `{MD5}` (verified).
- Publisher docs: README of https://github.com/tianjialiu/GOFER (fetched from raw.githubusercontent.com; copy in `cache/gofer/docs/README.md`, not committed) and the ESSD paper Liu et al. 2024, doi:10.5194/essd-16-1395-2024. **The zip itself contains no README or metadata file** (only `fireData.csv` and per-variant `*_summary.csv`, `*_scaleVal.csv`); the repository only mentions GOFER. Quotes below are from the GitHub README.
- Version note from the README: v0.2 "revise fire confidence for saturated fire pixels from 0.9 to 1.0, fix rfline in instances for multipolygons ...".

## Folder tree (zip also contains a macOS `__MACOSX/` resource-fork folder and `.DS_Store`, ignored)
```
{tree()}
```

## Vector layers (shapefiles, all EPSG:4326 / WGS84 lon-lat degrees, `GCS_WGS_1984`)
| file | features | geometry | CRS | attribute columns |
|---|---|---|---|---|
""" + "\n".join(schema) + f"""

Attribute meaning (README "Product Description"): `fname` fire name; `fyear` year; `timestep` "Hours after ignition, end of hour" (hours); `tUTC` "UTC time"; `tLocal` "Local time, with daylight savings"; `tLocalGMT` "Local time, without daylight savings"; `farea` "Area within fire perimeter" km2; `fareaPer` area as % of final area; `fperim` perimeter length km; `cflinelen`/`rflinelen` concurrent/retrospective active fire line length km; `fstate` "0 = dormant, 1 = active"; `fconf` fire detection confidence of the cfireLine definition (0.05 ... 0.9); `ignitions` count in fireIg.

- `fireProg`: one (Multi)Polygon per fire per hourly step = **cumulative** burned-area perimeter (farea never decreases in any fire: {shrink} decreases found). `cfireLine` has several rows per step (one per confidence threshold `fconf`).
- `fireIg`: MultiPoint ignition locations; `timestep` there is when the ignition was first detected (can be 0 or later; 82 rows in Combined).
- `GOFERx_summary.csv` columns: {", ".join(summ.columns)}; the half-hour variables (`timestep_hh`, `dfarea`, `maefspread`, `awefspread`) are growth/spread between consecutive end-of-hour perimeters, labelled at t = 0.5, 1.5, ...
- `GOFERx_scaleVal.csv`: fname, fyear, timestep, scaleVal (early-perimeter scaling factors; ~1.0 mostly).
- `fireData.csv`: fname, fyear, acres_official, GOESIg_UTC (first GOES detection / ignition hour, format `YYYY-MM-DD HH`, UTC), local_tz, local_tzGMT (`America/Los_Angeles`, `Etc/GMT+8`).

## Time stamps
- `tUTC` is a string `YYYY-MM-DD HH:MM:SS` in **UTC** (no zone suffix), always on the hour. `tLocal` is America/Los_Angeles with DST (UTC-7 in summer, UTC-8 in winter); `tLocalGMT` is fixed UTC-8.
- **Meaning: end of the hour.** README: "Hours after ignition, end of hour (t=1,2,3...)"; table header "End-of-hour variables (t=1,2,3...)" for the perimeter, fire line, area and state; "Half-hour variables (t=0.5,1.5,2.5...)" for growth/spread. So a perimeter with `tUTC` = T is the cumulative burned area as of the end of the hour (T-1h, T], i.e. a cell inside perimeter T but outside perimeter T-1h has a nominal GOFER arrival interval of (T-1h, T]. This is **nominal**: GOES scans every 10-15 min with a ~2 km pixel and parallax/smoothing, so the actual timing uncertainty is not defined by the label.
- Check performed: for all {len(prog)} Combined perimeters, `tUTC == GOESIg_UTC + timestep hours` exactly: **{chk_ts}**. `GOESIg_UTC` is the ignition hour (e.g. Kincade 2019-10-24 04 -> first perimeter 05:00 = timestep 1). Steps are contiguous (hourly gaps in timestep sequences: {gaps}). Some fires start at timestep > 1 (e.g. Antelope 4, CZU 10, Walker): earlier steps do not exist in the shapefile.

## Which variant to use
README: "GOFER-Combined uses both GOES-East and GOES-West observations, while GOFER-East and GOFER-West use only GOES-East and only GOES-West observations". Combined is the full product (same 4 layers + summary) and is used here as the recommended default. Fire-line default per README: "cflinelen5 should be used as the default fire line as it incorporates most active fire pixels along the perimeter and most closely matches FEDS" (cfireLine rows with fconf = 0.05). Perimeters (`fireProg`) have no confidence/parallax variants in the files: the confidence threshold and parallax correction are already applied in the published perimeter (README steps 1b, 2, 4); the confidence variants exist only in `cfireLine` (`fconf` and `cflinelen5..90` in summary).

## Fires
See `gofer_fires.csv` ({len(df)} fires). `final_perimeters.gpkg` (cache, EPSG:4326, layer `final_perimeters`) holds the last hourly cumulative perimeter per fire from Combined.
- `first_utc` / `last_utc`: first and last end-of-hour `tUTC` in fireProg. `bbox` columns = bounds of all hourly perimeters (= extent of the final cumulative perimeter, since perimeters only grow). `final_area_km2` = `farea` at the last step; `official_km2` from `acres_official` for comparison.
"""
    open(os.path.join(OUT, "gofer_layout.md"), "w").write(md)
    print(df.to_string())
    print("ts check", chk_ts, "gaps", gaps, "shrink", shrink)

if __name__ == "__main__":
    main()
