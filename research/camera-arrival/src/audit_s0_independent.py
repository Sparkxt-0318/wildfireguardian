"""Independent audit of the Step 0 feasibility gate (does NOT import s0_feasibility.py / viewshed.py).

Credits: camera sites and view directions from HPWREN (hpwren.ucsd.edu), UC San Diego (sites.js, cached
in cache/hpwren/). Perimeters: GOFER v0.2 Combined (Liu et al., doi:10.5281/zenodo.14642378), read directly
from the original shapefile. DEM: AWS Terrain Tiles 'skadi' 1-arcsec, read with an own .hgt reader.

Method (deliberately different from src/viewshed.py):
  * targets = N random points drawn uniformly (by area, EPSG:3310) inside the final GOFER-Combined perimeter,
    not raster cells;
  * line of sight = straight profile camera->target, sampled every 15 m, bilinear DEM, earth curvature with
    refraction k=0.13 (drop = d^2 (1-k) / 2R); visible if target elevation angle >= max angle of all profile
    samples between 0 and d-30 m (also reported with a 0 m exclusion zone);
  * FOV = geodesic azimuth camera->target within camera azimuth +- HFOV/2 (horizontal only);
  * distances are geodesic (WGS84) from the camera to the densified perimeter boundary.
Writes outputs/audit_s0_independent.json and prints a summary.
"""
import gzip, json, math, pathlib, re
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely.prepared import prep
from pyproj import Geod, Transformer

ROOT = pathlib.Path(__file__).resolve().parent.parent
GEOD = Geod(ellps="WGS84")
R, K = 6371000.0, 0.13
N_SAMPLES = 2500
SEED = 20261111

# ---------- (a) cameras straight from HPWREN sites.js ----------
def parse_sites(path):
    txt = path.read_text(errors="ignore")
    out = {}
    for site in ["wilson", "chino", "ihvy"]:
        i = txt.index(f'"{site}": {{')
        blk = txt[i:i + 6000]
        lat = float(re.search(r'"lat":\s*([-\d.]+)', blk).group(1))
        lon = float(re.search(r'"long":\s*([-\d.]+)', blk).group(1))
        elev = float(re.search(r'"elev":\s*([-\d.]+)', blk).group(1))
        cams = {}
        for m in re.finditer(r'"([a-z0-9]+-[nesw]-mobo-c)":\s*\{(.*?)\}', blk, re.S):
            b = m.group(2)
            cams[m.group(1)] = dict(
                az=float(re.search(r'"azimuth":\s*([-\d.]+)', b).group(1)),
                hfov=float(re.search(r'"horizontalView":\s*([-\d.]+)', b).group(1)),
                agl=float(re.search(r'"agl":\s*([-\d.]+)', b).group(1)))
        out[site] = dict(lat=lat, lon=lon, elev=elev, cams=cams)
    return out

# ---------- DEM ----------
class DEM:
    def __init__(self):
        self.tiles = {}
    def _tile(self, la, lo):
        key = (la, lo)
        if key not in self.tiles:
            name = f"N{la:02d}W{-lo:03d}.hgt.gz"
            p = ROOT / "cache" / "dem" / name
            a = np.frombuffer(gzip.open(p).read(), ">i2").reshape(3601, 3601).astype(np.float32)
            a[a < -1000] = np.nan
            self.tiles[key] = a
        return self.tiles[key]
    def __call__(self, lat, lon):
        lat = np.asarray(lat, float); lon = np.asarray(lon, float)
        out = np.full(lat.shape, np.nan, np.float32)
        la0 = np.floor(lat).astype(int); lo0 = np.floor(lon).astype(int)
        for (la, lo) in set(zip(la0.ravel().tolist(), lo0.ravel().tolist())):
            m = (la0 == la) & (lo0 == lo)
            a = self._tile(la, lo)
            r = (la + 1 - lat[m]) * 3600.0
            c = (lon[m] - lo) * 3600.0
            r0 = np.clip(np.floor(r).astype(int), 0, 3599); c0 = np.clip(np.floor(c).astype(int), 0, 3599)
            fr = r - r0; fc = c - c0
            out[m] = (a[r0, c0] * (1 - fr) * (1 - fc) + a[r0, c0 + 1] * (1 - fr) * fc
                      + a[r0 + 1, c0] * fr * (1 - fc) + a[r0 + 1, c0 + 1] * fr * fc)
        return out

def sample_in_poly(geom_ll, n, rng):
    to3310 = Transformer.from_crs(4326, 3310, always_xy=True)
    to4326 = Transformer.from_crs(3310, 4326, always_xy=True)
    g = gpd.GeoSeries([geom_ll], crs=4326).to_crs(3310).iloc[0]
    pg = prep(g)
    x0, y0, x1, y1 = g.bounds
    pts = []
    while len(pts) < n:
        xs = rng.uniform(x0, x1, 4 * n); ys = rng.uniform(y0, y1, 4 * n)
        for x, y in zip(xs, ys):
            if pg.contains(Point(x, y)):
                pts.append((x, y))
                if len(pts) == n:
                    break
    pts = np.array(pts)
    lon, lat = to4326.transform(pts[:, 0], pts[:, 1])
    return np.asarray(lat), np.asarray(lon)

def los(dem, clat, clon, zcam, tlat, tlon, step=15.0, excl=30.0, tgt_dz=0.0):
    az, _, dist = GEOD.inv(np.full(tlat.shape, clon), np.full(tlat.shape, clat), tlon, tlat)
    vis = np.zeros(tlat.shape, bool); vis0 = np.zeros(tlat.shape, bool)
    for i in range(len(tlat)):
        d = dist[i]
        n = max(int(d / step), 2)
        f = np.linspace(0, 1, n + 1)[1:]
        # straight-line in lon/lat is adequate at <70 km (sub-pixel deviation from geodesic)
        plat = clat + f * (tlat[i] - clat); plon = clon + f * (tlon[i] - clon)
        z = dem(plat, plon); dd = f * d
        ang = (z - dd ** 2 * (1 - K) / (2 * R) - zcam) / dd
        zt = z[-1] + tgt_dz
        at = (zt - d ** 2 * (1 - K) / (2 * R) - zcam) / d
        inner = ang[:-1]
        m30 = dd[:-1] <= d - excl
        vis[i] = (not m30.any()) or at >= np.nanmax(inner[m30])
        vis0[i] = (inner.size == 0) or at >= np.nanmax(inner)
    return vis, vis0, az % 360, dist

def ci95(k, n):
    p = k / n; h = 1.96 * math.sqrt(p * (1 - p) / n)
    return [round(100 * max(p - h, 0), 2), round(100 * (p + h), 2)]

def main():
    sites = parse_sites(ROOT / "cache" / "hpwren" / "sites.js")
    gof = gpd.read_file(ROOT / "cache/gofer/x/GOFER/GOFER_Combined/GOFERC_fireProg.shp")
    dem = DEM()
    rng = np.random.default_rng(SEED)
    res = {"credits": "HPWREN (hpwren.ucsd.edu), UC San Diego; GOFER v0.2 Liu et al. doi:10.5281/zenodo.14642378; AWS skadi DEM",
           "n_samples": N_SAMPLES, "seed": SEED, "k_refraction": K, "pairs": {}, "gofer_time": {}}
    pairs = [("Bobcat", "wilson", ["wilson-e-mobo-c", "wilson-n-mobo-c"]),
             ("Bobcat", "chino", ["chino-n-mobo-c"]),
             ("Kincade", "ihvy", ["ihvy-n-mobo-c"]),
             ("Glass", "ihvy", ["ihvy-e-mobo-c"])]
    for fire, site, cams in pairs:
        f = gof[gof.fname == fire].sort_values("timestep")
        last = f.iloc[-1]
        geom = last.geometry
        s = sites[site]
        zdem = float(dem(np.array([s["lat"]]), np.array([s["lon"]]))[0])
        agl = s["cams"][cams[0]]["agl"]
        zcam = zdem + agl
        # (b) distance: geodesic to densified boundary
        b = gpd.GeoSeries([geom.boundary], crs=4326).to_crs(3310).iloc[0].segmentize(30)
        bll = gpd.GeoSeries([b], crs=3310).to_crs(4326).iloc[0]
        coords = np.vstack([np.asarray(g.coords) for g in getattr(bll, "geoms", [bll])])
        _, _, dd = GEOD.inv(np.full(len(coords), s["lon"]), np.full(len(coords), s["lat"]), coords[:, 0], coords[:, 1])
        inside = geom.contains(Point(s["lon"], s["lat"]))
        tlat, tlon = sample_in_poly(geom, N_SAMPLES, rng)
        vis, vis0, az, dist = los(dem, s["lat"], s["lon"], zcam, tlat, tlon)
        vis20, _, _, _ = los(dem, s["lat"], s["lon"], zcam, tlat, tlon, tgt_dz=20.0)
        # centroid bearing
        cen = gpd.GeoSeries([geom], crs=4326).to_crs(3310).centroid.to_crs(4326).iloc[0]
        caz, _, cd = GEOD.inv(s["lon"], s["lat"], cen.x, cen.y)
        out = dict(site_lat=s["lat"], site_lon=s["lon"], site_elev_listed=s["elev"], dem_at_site_m=round(zdem, 1),
                   agl_m=agl, z_cam_m=round(zcam, 1), last_tUTC=last.tUTC, last_farea_km2=float(last.farea),
                   camera_inside_perimeter=bool(inside),
                   dist_site_to_perimeter_km=round(float(dd.min()) / 1000, 2),
                   dist_median_to_samples_km=round(float(np.median(dist)) / 1000, 2),
                   bearing_to_centroid_deg=round(caz % 360, 1), dist_to_centroid_km=round(cd / 1000, 1),
                   bearing_range_of_samples_deg=[round(float(np.percentile(az, 2)), 1), round(float(np.percentile(az, 98)), 1)],
                   visible_any_dir_pct=round(100 * vis.mean(), 2), visible_any_dir_ci95=ci95(vis.sum(), len(vis)),
                   visible_any_dir_noexcl_pct=round(100 * vis0.mean(), 2),
                   visible_any_dir_20m_pct=round(100 * vis20.mean(), 2), cams={})
        union = np.zeros(len(vis), bool)
        for c in cams:
            cc = s["cams"][c]
            dlt = (az - cc["az"] + 180) % 360 - 180
            infov = np.abs(dlt) <= cc["hfov"] / 2
            union |= infov & vis
            out["cams"][c] = dict(azimuth=cc["az"], hfov=cc["hfov"], in_fov_burn_pct=round(100 * infov.mean(), 2),
                                  in_fov_visible_ground_pct=round(100 * (infov & vis).mean(), 2),
                                  ci95=ci95((infov & vis).sum(), len(vis)),
                                  in_fov_visible_20m_pct=round(100 * (infov & vis20).mean(), 2),
                                  median_dist_visible_in_fov_km=(round(float(np.median(dist[infov & vis])) / 1000, 2)
                                                                 if (infov & vis).any() else None))
        if len(cams) > 1:
            out["union_" + "+".join(cams) + "_ground_pct"] = round(100 * union.mean(), 2)
        res["pairs"][f"{fire}__{site}"] = out
        print(fire, site, json.dumps(out, indent=1))
    # (f) GOFER time handling: tLocal - tUTC offset and Pacific-date peak growth
    for fire in ["Bobcat", "Kincade", "Glass"]:
        f = gof[gof.fname == fire].sort_values("timestep").copy()
        tu = pd.to_datetime(f.tUTC); tl = pd.to_datetime(f.tLocal)
        off = sorted(set(((tl - tu).dt.total_seconds() / 3600).round(2)))
        tp = tu.dt.tz_localize("UTC").dt.tz_convert("America/Los_Angeles")
        # hourly new area attributed to the END of the hour (end-of-hour timestamps), Pacific date
        f["new"] = f.farea.diff().fillna(f.farea.iloc[0])
        f["pdate"] = tp.dt.date.astype(str)
        g = f.groupby("pdate").new.sum()
        # interval (T-1h, T] assigned by its midpoint (the original gate's convention)
        f["pdate_mid"] = (tp - pd.Timedelta(minutes=30)).dt.date.astype(str)
        gm = f.groupby("pdate_mid").new.sum()
        res["gofer_time"][fire] = dict(first_tUTC=f.tUTC.iloc[0], last_tUTC=f.tUTC.iloc[-1],
                                       tLocal_minus_tUTC_h=off, tLocal_matches_zoneinfo=bool((tp.dt.tz_localize(None) == tl).all()),
                                       peak_pacific_date_end_of_hour=g.idxmax(), peak_km2_end_of_hour=round(float(g.max()), 1),
                                       peak_pacific_date_midpoint=gm.idxmax(), peak_km2_midpoint=round(float(gm.max()), 1))
    print(json.dumps(res["gofer_time"], indent=1))
    (ROOT / "outputs" / "audit_s0_independent.json").write_text(json.dumps(res, indent=1, default=str))

if __name__ == "__main__":
    main()
