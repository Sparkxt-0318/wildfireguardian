"""DEM lookup and the road profile ahead of the vehicle (DESIGN.md section 6.4, step 4). No flat-ground assumption.

DEM file (`.npz`): `z` float32 [h, w] elevation in m, row 0 = north; `x0` west edge of column 0 and `y_top` north
edge of row 0 in the DEM CRS (m); `res` cell size (m); `crs` = "EPSG:5179" (Korea 2000 / Unified CS; needs pyproj)
or any other projected EPSG code pyproj knows, or "local-enu" with `lat0`, `lon0` (degrees). Elevations are cell
CENTRE values; lookup is bilinear between centres, NaN outside the centre grid or next to NaN cells.

Road profile assumptions (stated):
- The road ahead follows the GNSS true course (straight line). A bend within s_max puts the profile off the road.
  GNSS course is meaningless when stopped: the caller must pass the last course from when the vehicle was moving.
- Meridian convergence: in a transverse-Mercator grid (EPSG:5179) grid north differs from true north by the
  convergence gamma (PROJ `get_factors().meridian_convergence`, + east of the central meridian 127.5 E in the
  northern hemisphere). Grid bearing = true course - gamma. The grid scale factor k is applied to distances.
  Verified against a pyproj projection in tests/test_terrain_geometry.py.
- "local-enu" uses an equirectangular tangent plane at (lat0, lon0), R = 6371008.8 m; grid north = true north.
  Good to ~1e-4 relative within a few km of the origin.
- The profile is the DEM surface, not the road surface: cuttings, embankments and bridges are not in a 5-30 m DEM.
- Without a DEM the fallback is a plane through the vehicle's ground point with grade tan(pitch) from the IMU,
  corrected by the IMU mounting pitch. That assumes the vehicle body is parallel to the road under it (suspension
  and tyre deflection ignored) and that the road ahead keeps that grade; `source = "imu"` says so to the UI.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

EARTH_R = 6371008.8


@dataclass
class Profile:
    """Ground height along the course. s: horizontal distance ahead (m, starts at 0); dz: height (m) relative to the
    vehicle's ground point (dz[0] = 0); source: "dem" | "imu" (or a test label)."""
    s: np.ndarray
    dz: np.ndarray
    source: str
    valid: bool = True
    reason: str = ""

    @classmethod
    def plane(cls, grade: float, s_max_m: float = 80.0, ds: float = 2.0, source: str = "imu") -> "Profile":
        """Plane with constant grade (rise/run, + uphill ahead)."""
        if not math.isfinite(grade):
            return cls(np.array([0.0]), np.array([0.0]), source, False, "grade not finite")
        s = np.arange(0.0, s_max_m + 1e-9, ds)
        return cls(s, grade * s, source)

    @property
    def s_max(self) -> float:
        return float(self.s[-1]) if self.s.size else 0.0

    def dz_at(self, s):
        """Linear interpolation; NaN outside [0, s_max] or on an invalid profile."""
        if not self.valid or self.s.size < 2:
            return np.full(np.shape(s), np.nan) if np.ndim(s) else float("nan")
        out = np.interp(s, self.s, self.dz, left=np.nan, right=np.nan)
        return out if np.ndim(s) else float(out)

    def visible(self, cam_height_m: float) -> np.ndarray:
        """Per sample: is the ground point visible from a camera cam_height_m above s = 0 (line of sight not cut by
        nearer terrain along the profile)? Elevation angle to each point must be >= every nearer one."""
        ang = np.full(self.s.size, -np.inf)
        pos = self.s > 0
        ang[pos] = np.arctan2(self.dz[pos] - cam_height_m, self.s[pos])
        prev_max = np.maximum.accumulate(np.concatenate([[-np.inf], ang[:-1]]))
        return ang >= prev_max - 1e-12


def line_of_sight(profile: Profile, cam_height_m: float, s_target_m: float) -> "tuple[bool, str, float]":
    """(visible, reason, dz at the target) for the ground point at ``s_target_m`` along ``profile`` seen from a
    camera ``cam_height_m`` above s = 0 (FS-8). Visible only when no profile sample strictly between the camera and
    the target rises above the straight sight line. Fail closed: an invalid profile, a target outside it or a
    non-finite height gives False. Terrain only: a bare-earth DEM has no buildings, walls, vegetation or vehicles,
    and a plane profile (no DEM) is visible everywhere, so it proves nothing (the pipeline needs a DEM)."""
    if not profile.valid or profile.s.size < 2:
        return False, "no valid profile (%s)" % (profile.reason or "invalid"), float("nan")
    if not (math.isfinite(s_target_m) and math.isfinite(cam_height_m) and s_target_m > 0 and cam_height_m > 0):
        return False, "bad target distance or camera height", float("nan")
    if s_target_m > profile.s_max + 1e-9:
        return False, "target %.0f m beyond the profile (%.0f m)" % (s_target_m, profile.s_max), float("nan")
    zt = float(profile.dz_at(s_target_m))
    if not math.isfinite(zt):
        return False, "no ground height at the target", float("nan")
    m = (profile.s > 1e-9) & (profile.s < s_target_m - 1e-6)
    if np.any(~np.isfinite(profile.dz[m])):
        return False, "profile has gaps", zt
    sight = cam_height_m + (zt - cam_height_m) * profile.s[m] / s_target_m
    over = profile.dz[m] - sight
    if over.size and float(np.max(over)) > 1e-6:
        k = int(np.argmax(over))
        return False, "terrain at %.0f m rises %.1f m above the sight line" % (float(profile.s[m][k]),
                                                                             float(over[k])), zt
    return True, "", zt


def imu_plane_profile(imu_pitch_deg: float, mount_pitch_deg: float = 0.0, s_max_m: float = 80.0,
                      ds: float = 2.0) -> Profile:
    """Fallback without a DEM: grade = tan(imu_pitch - imu_mount_pitch) (pitch + nose up). source = "imu"."""
    if imu_pitch_deg is None or not math.isfinite(imu_pitch_deg):
        return Profile(np.array([0.0]), np.array([0.0]), "imu", False, "IMU pitch missing")
    return Profile.plane(math.tan(math.radians(imu_pitch_deg - mount_pitch_deg)), s_max_m, ds, "imu")


@dataclass
class Dem:
    z: np.ndarray
    x0: float
    y_top: float
    res: float
    crs: str
    lat0: Optional[float] = None
    lon0: Optional[float] = None

    @classmethod
    def load(cls, path) -> "Dem":
        with np.load(Path(path), allow_pickle=False) as d:
            crs = str(d["crs"])
            dem = cls(z=np.asarray(d["z"], dtype=np.float32), x0=float(d["x0"]), y_top=float(d["y_top"]),
                      res=float(d["res"]), crs=crs,
                      lat0=float(d["lat0"]) if "lat0" in d.files else None,
                      lon0=float(d["lon0"]) if "lon0" in d.files else None)
        if dem.z.ndim != 2 or dem.res <= 0:
            raise ValueError("DEM z must be 2-D and res > 0")
        if dem.crs == "local-enu" and (dem.lat0 is None or dem.lon0 is None):
            raise ValueError("local-enu DEM needs lat0 and lon0")
        return dem

    def save(self, path) -> None:
        kw = dict(z=self.z.astype(np.float32), x0=self.x0, y_top=self.y_top, res=self.res, crs=np.array(self.crs))
        if self.lat0 is not None:
            kw.update(lat0=self.lat0, lon0=self.lon0)
        np.savez_compressed(Path(path), **kw)

    # --- projection ---
    def _pyproj(self):
        try:
            import pyproj
        except ImportError as e:            # pragma: no cover - pyproj is in the dev venv
            raise ImportError(f"DEM CRS {self.crs} needs pyproj") from e
        cache = getattr(self, "_pp", None)
        if cache is None:
            cache = (pyproj.Transformer.from_crs("EPSG:4326", self.crs, always_xy=True), pyproj.Proj(self.crs))
            object.__setattr__(self, "_pp", cache)
        return cache

    def to_xy(self, lat, lon):
        """(lat, lon) degrees WGS84 -> DEM grid (x east, y north) in m."""
        if self.crs == "local-enu":
            lat = np.asarray(lat, dtype=float); lon = np.asarray(lon, dtype=float)
            x = EARTH_R * np.radians(lon - self.lon0) * math.cos(math.radians(self.lat0))
            y = EARTH_R * np.radians(lat - self.lat0)
            return x, y
        tr, _ = self._pyproj()
        return tr.transform(lon, lat)

    def convergence_deg(self, lat: float, lon: float) -> float:
        """Meridian convergence gamma (deg): grid bearing = true bearing - gamma. 0 for local-enu."""
        if self.crs == "local-enu":
            return 0.0
        _, proj = self._pyproj()
        return float(proj.get_factors(lon, lat).meridian_convergence)

    def scale_factor(self, lat: float, lon: float) -> float:
        """Grid distance / ground distance at the point (conformal projection). 1 for local-enu."""
        if self.crs == "local-enu":
            return 1.0
        _, proj = self._pyproj()
        return float(proj.get_factors(lon, lat).meridional_scale)

    # --- lookup ---
    def elevation_xy(self, x, y):
        """Bilinear elevation at grid coordinates; NaN outside the cell-centre grid or next to NaN cells."""
        x = np.asarray(x, dtype=float); y = np.asarray(y, dtype=float)
        h, w = self.z.shape
        u = (x - self.x0) / self.res - 0.5          # fractional column (cell centres at integers)
        v = (self.y_top - y) / self.res - 0.5       # fractional row
        inside = (u >= 0) & (u <= w - 1) & (v >= 0) & (v <= h - 1) & np.isfinite(u) & np.isfinite(v)
        uc = np.clip(u, 0, w - 1); vc = np.clip(v, 0, h - 1)
        j0 = np.minimum(np.floor(uc).astype(int), max(w - 2, 0)); i0 = np.minimum(np.floor(vc).astype(int), max(h - 2, 0))
        j1 = np.minimum(j0 + 1, w - 1); i1 = np.minimum(i0 + 1, h - 1)
        fu = uc - j0; fv = vc - i0
        z = self.z.astype(float)
        out = ((1 - fu) * (1 - fv) * z[i0, j0] + fu * (1 - fv) * z[i0, j1] + (1 - fu) * fv * z[i1, j0]
               + fu * fv * z[i1, j1])
        out = np.where(inside, out, np.nan)
        return out if out.ndim else float(out)

    def elevation(self, lat, lon):
        x, y = self.to_xy(lat, lon)
        return self.elevation_xy(x, y)


def grid_bearing_deg(dem: Dem, lat: float, lon: float, course_deg: float) -> float:
    """True course (deg clockwise from true north) -> bearing in the DEM grid: course - convergence."""
    return (course_deg - dem.convergence_deg(lat, lon)) % 360.0


def road_profile(dem: Optional[Dem], lat: float, lon: float, course_deg: float, s_max_m: float = 80.0,
                 ds: float = 2.0) -> Profile:
    """Ground profile from the DEM along the true course, dz relative to the vehicle's ground point.

    s is ground distance; the grid step is s * k (scale factor). The profile is cut at the first NaN (DEM edge or
    void). Invalid (valid=False) when there is no DEM, any input is non-finite, or the vehicle point has no
    elevation."""
    if dem is None:
        return Profile(np.array([0.0]), np.array([0.0]), "dem", False, "no DEM")
    if not all(v is not None and math.isfinite(v) for v in (lat, lon, course_deg)):
        return Profile(np.array([0.0]), np.array([0.0]), "dem", False, "position or course missing")
    x0, y0 = dem.to_xy(lat, lon)
    beta = math.radians(grid_bearing_deg(dem, lat, lon, course_deg))
    k = dem.scale_factor(lat, lon)
    s = np.arange(0.0, s_max_m + 1e-9, ds)
    z = np.asarray(dem.elevation_xy(x0 + k * s * math.sin(beta), y0 + k * s * math.cos(beta)), dtype=float)
    if not math.isfinite(z[0]):
        return Profile(np.array([0.0]), np.array([0.0]), "dem", False, "no DEM elevation at the vehicle")
    bad = np.flatnonzero(~np.isfinite(z))
    n = bad[0] if bad.size else z.size
    if n < 2:
        return Profile(s[:1], np.zeros(1), "dem", False, "DEM ends at the vehicle")
    reason = "" if n == z.size else f"DEM ends at s = {s[n - 1]:.0f} m"
    return Profile(s[:n], z[:n] - z[0], "dem", True, reason)
