"""DEM access (AWS 'skadi' 1-arcsec SRTM-derived tiles) and a polar line-of-sight
viewshed with earth curvature + standard refraction.

Data credits: DEM = Mapzen/AWS Terrain Tiles 'skadi' (SRTM / USGS NED derived, 1 arc-second),
https://s3.amazonaws.com/elevation-tiles-prod/skadi/ . Camera positions from HPWREN
(hpwren.ucsd.edu), UC San Diego.

Viewshed method (polar sweep, camera-centred):
  * Local azimuthal-equidistant (AEQD) projection centred on the camera.
  * Rays are cast at azimuth step daz (arc spacing <= `arc_m` at the maximum range)
    and sampled every `dr` metres; DEM is bilinearly interpolated at every sample.
  * Apparent elevation angle of a sample at range d with terrain height z:
        tan(a) = (z - drop(d) - z_cam) / d,   drop(d) = d^2 (1 - k) / (2 R)
    with R = 6 371 000 m and refraction coefficient k = 0.13.
  * A target at range d (height z_t + h_target) is visible iff its tan(a) is >= the
    running maximum of tan(a) of every ray sample with range <= d - dr
    (the sample right next to the target is excluded to avoid self-blocking).
  * Target cells look up the nearest ray (azimuth) and use their OWN DEM height.
"""
import gzip, os, pathlib, urllib.request
import numpy as np
from scipy.ndimage import map_coordinates
from pyproj import CRS, Transformer

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMDIR = ROOT / "cache" / "dem"
SKADI = "https://s3.amazonaws.com/elevation-tiles-prod/skadi/{ns}/{name}.hgt.gz"
R_EARTH = 6371000.0
K_REFR = 0.13
UA = "research-poc-camera-arrival/0.1"


def tile_name(lat_floor, lon_floor):
    ns = ("N" if lat_floor >= 0 else "S") + "%02d" % abs(lat_floor)
    ew = ("E" if lon_floor >= 0 else "W") + "%03d" % abs(lon_floor)
    return ns, ns + ew


def get_tile(lat_floor, lon_floor):
    """Return (array float32 3601x3601, url). Row 0 = north edge (lat_floor+1)."""
    ns, name = tile_name(lat_floor, lon_floor)
    DEMDIR.mkdir(parents=True, exist_ok=True)
    p = DEMDIR / (name + ".hgt.gz")
    url = SKADI.format(ns=ns, name=name)
    if not p.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        tmp = p.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.rename(p)
    raw = gzip.decompress(p.read_bytes())
    n = int(round(np.sqrt(len(raw) // 2)))
    a = np.frombuffer(raw, ">i2").reshape(n, n).astype(np.float32)
    a[a == -32768] = np.nan
    return a, url


class DEM:
    """Mosaic of skadi tiles covering [lon0, lon1] x [lat0, lat1] (degrees)."""

    def __init__(self, lon0, lat0, lon1, lat1):
        la0, la1 = int(np.floor(lat0)), int(np.floor(lat1))
        lo0, lo1 = int(np.floor(lon0)), int(np.floor(lon1))
        self.urls = []
        rows = []
        for la in range(la1, la0 - 1, -1):  # north to south
            row = []
            for lo in range(lo0, lo1 + 1):
                a, u = get_tile(la, lo)
                self.urls.append(u)
                row.append(a[:-1, :-1])  # drop duplicated edge row/col
            rows.append(np.hstack(row))
        self.n = 3600
        self.lat_top = la1 + 1.0
        self.lon_left = float(lo0)
        full = np.vstack(rows)
        # crop to requested box + margin to save memory
        m = 0.02
        r0 = max(int((self.lat_top - (lat1 + m)) * self.n), 0)
        r1 = min(int((self.lat_top - (lat0 - m)) * self.n) + 2, full.shape[0])
        c0 = max(int((lon0 - m - self.lon_left) * self.n), 0)
        c1 = min(int((lon1 + m - self.lon_left) * self.n) + 2, full.shape[1])
        self.z = np.ascontiguousarray(full[r0:r1, c0:c1])
        self.lat_top -= r0 / self.n
        self.lon_left += c0 / self.n
        nanfrac = np.isnan(self.z).mean()
        if nanfrac > 0:
            self.z = np.where(np.isnan(self.z), np.nanmin(self.z), self.z)
        self.void_fraction = float(nanfrac)

    def sample(self, lon, lat):
        """Bilinear elevation at lon/lat arrays (pixel-centre convention of .hgt)."""
        r = (self.lat_top - np.asarray(lat)) * self.n
        c = (np.asarray(lon) - self.lon_left) * self.n
        return map_coordinates(self.z, [r.ravel(), c.ravel()], order=1, mode="nearest").reshape(np.shape(lat))


def aeqd(lon, lat):
    crs = CRS.from_proj4(f"+proj=aeqd +lat_0={lat} +lon_0={lon} +datum=WGS84 +units=m +no_defs")
    return crs, Transformer.from_crs(crs, "EPSG:4326", always_xy=True), Transformer.from_crs("EPSG:4326", crs, always_xy=True)


def drop(d, k=K_REFR):
    return d * d * (1.0 - k) / (2.0 * R_EARTH)


def ray_profiles(height_fn, az, rmax, dr):
    """height_fn(x, y) -> z for arrays in camera-centred metres. Returns ranges (nr,),
    terrain tan-angles prefix max P (naz, nr) WITHOUT camera height applied: returns raw z."""
    rr = np.arange(1, int(np.ceil(rmax / dr)) + 2) * dr
    X = np.sin(az)[:, None] * rr[None, :]
    Y = np.cos(az)[:, None] * rr[None, :]
    return rr, height_fn(X, Y)


def polar_visibility(height_fn, z_cam, tx, ty, tz, dr=30.0, arc_m=20.0, h_targets=(0.0,), k=K_REFR,
                     chunk=2000):
    """Visibility of targets (tx, ty in camera-centred metres, tz terrain height) for each
    extra target height in h_targets. Returns dict h -> bool array, plus target ranges."""
    tx, ty, tz = map(np.asarray, (tx, ty, tz))
    d = np.hypot(tx, ty)
    taz = np.mod(np.arctan2(tx, ty), 2 * np.pi)
    rmax = float(d.max()) + dr
    daz = arc_m / rmax
    # only the azimuth sector actually occupied by targets (handle wrap-around)
    order = np.sort(taz)
    gaps = np.diff(np.concatenate([order, [order[0] + 2 * np.pi]]))
    gi = int(np.argmax(gaps))
    a0 = order[(gi + 1) % len(order)]
    span = (2 * np.pi - gaps[gi]) if len(order) > 1 else 0.0
    naz = int(np.ceil(span / daz)) + 2
    az = a0 - daz / 2 + np.arange(naz) * daz
    # target -> ray index
    rel = np.mod(taz - (a0 - daz / 2), 2 * np.pi)
    ia = np.clip(np.round(rel / daz).astype(int), 0, naz - 1)
    # blocking samples: ranges <= d - dr  -> index floor(d/dr) - 2 in rr (rr[j] = (j+1)*dr)
    jr = np.floor(d / dr).astype(int) - 2
    out = {h: np.ones(d.shape, bool) for h in h_targets}
    tan_t = {h: (tz + h - drop(d, k) - z_cam) / np.maximum(d, 1e-6) for h in h_targets}
    for s in range(0, naz, chunk):
        e = min(s + chunk, naz)
        rr, z = ray_profiles(height_fn, az[s:e], rmax, dr)
        tan_r = (z - drop(rr, k)[None, :] - z_cam) / rr[None, :]
        P = np.maximum.accumulate(tan_r, axis=1)
        sel = (ia >= s) & (ia < e)
        if not sel.any():
            continue
        jj = jr[sel]
        ok = jj >= 0
        pm = np.full(jj.shape, -np.inf)
        pm[ok] = P[ia[sel][ok] - s, jj[ok]]
        for h in h_targets:
            out[h][sel] = tan_t[h][sel] >= pm
    return out, d


def brute_los(height_fn, z_cam, x, y, z_t, h=0.0, step=10.0, k=K_REFR):
    """Reference: dense straight-line check for single targets (slow, for tests)."""
    d = np.hypot(x, y)
    n = max(int(d / step), 2)
    f = np.arange(1, n) / n
    f = f[f * d <= d - 30.0]
    if len(f) == 0:
        return True
    xs, ys = x * f, y * f
    zs = height_fn(xs, ys)
    ds = f * d
    tan_s = (zs - drop(ds, k) - z_cam) / ds
    tan_t = (z_t + h - drop(d, k) - z_cam) / d
    return bool(tan_t >= tan_s.max())
