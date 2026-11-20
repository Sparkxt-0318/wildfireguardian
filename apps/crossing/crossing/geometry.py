"""Step 4: near-edge distance and flame height from the thermal mask, the IMU and the road profile (DESIGN 6.4).

Frames and conventions:
- Vehicle-level frame: x forward along the course (horizontal), y left, z up (right-handed). Bearings are + right.
- IMU attitude (protocol `imu`): pitch + nose up, roll + right side down, applied as intrinsic yaw-pitch-roll with
  yaw = 0 (x is the course). It is the attitude of the body the camera is mounted on (the roof head; the BNO055 is
  in the same housing). Heading is not used: the course comes from GNSS.
- CameraPose mount angles are the camera's boresight relative to that body (calibration): pitch + up,
  roll + right side down, yaw + right. height_m is the camera's vertical height above the ground point at s = 0.
- Camera: `thermal.CameraModel` pinhole; pixel (row i, col j) has its centre at continuous coordinates (i, j);
  rows grow downward. Lens distortion is not corrected.

Assumptions (stated; geometry verified only against synthetic scenes in tests/test_terrain_geometry.py):
- No flat-ground assumption: rays are intersected with the road `Profile` (DEM along the course, or the IMU-grade
  plane fallback). Cross slope is ignored: a ray off the course axis meets the profile height at the same
  along-course distance. Distances reported are ALONG THE COURSE (x), the quantity a crossing needs.
- The camera sits at s = 0 (GNSS antenna / camera longitudinal offset ignored, < 2 m on a roof).
- The near edge is the flame BASE. The lowest flame pixel's bottom edge (row + 0.5) is taken as the base, +-0.5 px
  for the pixel boundary, and +-pitch_sigma_deg (default 0.5 deg) IMU pitch uncertainty, as the interval.
- If the base is hidden behind a crest (ground between the camera and the flame is out of sight), the result is
  flagged `occluded`, d_m = d_lo_m = the last visible ground point before the hidden stretch (nearest possible
  base) and d_hi_m = inf. The hidden stretch is searched over the whole ground footprint of the lowest flame pixel
  (from the ray below it to the farthest landing of the ray through its TOP edge, +-pitch_sigma; PHYS-3), so a crest
  that cuts the flame inside that pixel is caught too. An occluded base is NOT an observed base: d_m is only a
  near bound, ``flame_height`` gets h_hi = inf from d_hi_m = inf, ``depth.intensity`` is then invalid and the
  pipeline gives NEAR_EDGE_NOT_OBSERVED. If the flame base is hidden by vegetation or the base of the flame reads below the flame
  threshold, the lowest flame pixel is above the true base and the distance is OVERESTIMATED; nothing here can see
  that.
- A flame base CUT OFF by the image is flagged ``base_cut_off`` (D5, 2026-11-17): a flame column within the bearing
  window whose lowest flame pixel is on the bottom image row (the base is below the image: nearer than any ground
  the camera sees; a level camera at 2.6 m sees no ground nearer than about 6.8 m), or flame in the outermost
  ``edge_cols`` image columns inside the bearing window (the base may continue outside the image). d_m is then
  only a far bound; the pipeline gives CLOSED with NEAR_EDGE_NOT_OBSERVED. A downward camera pitch (unit config)
  brings the near ground into view.
- Flame height is the top flame pixel (top edge) at the near-edge distance minus the ground there. A flame leaning
  towards the camera reads taller, one leaning away shorter; the interval covers pixel, distance and pitch only.
  A flame whose top reaches the TOP image row (a downward-pitched camera sees only about 3 m above the road at
  10 m) has an unknown height: ``flame_height`` returns None then (fail closed: no Byram intensity from a lower
  bound), unless ``allow_top_cut=True``. ``flame_top_cut_off`` reports it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np

from .terrain import Profile
from .thermal import DEFAULT_CAMERA, CameraModel, lowest_flame_row, top_flame_row


@dataclass(frozen=True)
class CameraPose:
    height_m: float = 2.5
    mount_pitch_deg: float = 0.0
    mount_roll_deg: float = 0.0
    mount_yaw_deg: float = 0.0


@dataclass(frozen=True)
class Attitude:
    """IMU roll/pitch in degrees (pitch + nose up, roll + right side down)."""
    roll_deg: float = 0.0
    pitch_deg: float = 0.0


def _att(imu) -> Attitude:
    if imu is None:
        return Attitude()
    if isinstance(imu, Attitude):
        return imu
    if isinstance(imu, dict):
        return Attitude(float(imu.get("roll_deg", 0.0)), float(imu.get("pitch_deg", 0.0)))
    return Attitude(float(imu.roll_deg), float(imu.pitch_deg))


def _pitch_up(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, 0.0, -s], [0.0, 1.0, 0.0], [s, 0.0, c]])       # x -> (c, 0, s)


def _roll_right_down(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]])       # y (left) -> (0, c, s): right side goes down


def _yaw_right(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]])       # x -> (c, -s, 0): toward the right


def level_from_camera(pose: CameraPose, imu) -> np.ndarray:
    """3x3 rotation taking camera-frame vectors (forward, left, up) to the vehicle-level frame."""
    a = _att(imu)
    body = _pitch_up(a.pitch_deg) @ _roll_right_down(a.roll_deg)
    mount = _yaw_right(pose.mount_yaw_deg) @ _pitch_up(pose.mount_pitch_deg) @ _roll_right_down(pose.mount_roll_deg)
    return body @ mount


def pixel_ray(model: CameraModel, pose: CameraPose, imu, row: float, col: float) -> np.ndarray:
    """Unit ray of image point (row, col) in the vehicle-level frame (x fwd along course, y left, z up)."""
    v = np.array([1.0, -(float(col) - model.ppx) / model.fx, -(float(row) - model.ppy) / model.fy])
    r = level_from_camera(pose, imu) @ v
    return r / np.linalg.norm(r)


def intersect_profile(ray, cam_height: float, profile: Profile, step_m: Optional[float] = None) -> Optional[float]:
    """Along-course distance x (m) where the ray first meets the ground, or None (ray level/upward never meeting
    it within the profile, backwards ray, invalid profile). The camera is at (0, 0, cam_height) above dz(0) = 0.

    Numeric march along x in steps of step_m (default a quarter of the profile spacing, <= 0.5 m), then bisection
    to 0.1 mm. A grazing ray that touches a crest between two march points can be missed (a step of 0.5 m on a
    rounded crest is a few mm of height)."""
    ray = np.asarray(ray, dtype=float)
    if not profile.valid or profile.s.size < 2 or not np.all(np.isfinite(ray)) or ray[0] <= 1e-9:
        return None
    if not (cam_height > 0 and math.isfinite(cam_height)):
        return None
    k = ray[2] / ray[0]
    ds = float(np.min(np.diff(profile.s)))
    step = step_m if step_m is not None else min(0.5, ds / 4.0)
    xs = np.arange(0.0, profile.s_max + 1e-9, step)
    f = cam_height + k * xs - profile.dz_at(xs)
    below = np.flatnonzero(f <= 0)
    if below.size == 0:
        return None
    i = int(below[0])
    if i == 0:
        return 0.0
    a, b = xs[i - 1], xs[i]
    for _ in range(60):
        m = 0.5 * (a + b)
        fm = cam_height + k * m - profile.dz_at(m)
        if fm > 0:
            a = m
        else:
            b = m
        if b - a < 1e-4:
            break
    return float(0.5 * (a + b))


@dataclass
class NearEdge:
    """d_m: along-course distance to the flame base (m); [d_lo_m, d_hi_m] interval (d_hi may be inf);
    bearing_deg: camera-frame bearing of the column used (+ right); row/col of the lowest flame pixel;
    slope_source from the profile; occluded: base hidden behind terrain; ground_dz_m: ground height at d_m."""
    d_m: float
    bearing_deg: float
    row: int
    col: int
    d_lo_m: float
    d_hi_m: float
    slope_source: str
    occluded: bool = False
    ground_dz_m: float = float("nan")
    columns: list = field(default_factory=list)
    base_cut_off: bool = False
    cut_off_reason: str = ""


def _column_near(model, pose, imu, profile, row_low, col, pitch_sigma_deg):
    """Per-column near-edge (d, lo, hi, occluded) or None."""
    a = _att(imu)
    h = pose.height_m

    def x_for(row, dp=0.0):
        att = Attitude(a.roll_deg, a.pitch_deg + dp)
        return intersect_profile(pixel_ray(model, pose, att, row, col), h, profile)

    x_n = x_for(row_low + 0.5)
    x_below = x_for(row_low + 1.0) if row_low + 1 < model.h else None
    if x_below is not None:
        vis = profile.visible(h)
        # PHYS-3: the base may lie anywhere in the ground footprint of the lowest flame pixel, up to where the ray
        # through its TOP edge (row - 0.5) lands, farthest over the +-pitch_sigma rays (s_max + 1 when one never
        # meets the ground). Hidden ground anywhere in (x_below, x_top) means the base may be hidden behind a crest
        # that the pixel's lower half rests on: occluded (fails closed; a flame on a slope in front of a hidden
        # hollow is also flagged, accepted).
        tops = [x_for(row_low - 0.5, dp) for dp in (-pitch_sigma_deg, 0.0, pitch_sigma_deg)]
        x_top = profile.s_max + 1.0 if any(v is None for v in tops) else max(tops)
        if x_n is not None:
            x_top = max(x_top, x_n)
        hidden = (~vis) & (profile.s > x_below) & (profile.s < x_top)
        if hidden.any():
            return x_below, x_below, math.inf, True
    if x_n is None:
        return None
    vals = []
    for row in (row_low + 0.0, row_low + 1.0):
        for dp in (-pitch_sigma_deg, 0.0, pitch_sigma_deg):
            vals.append(x_for(row, dp))
    fin = [v for v in vals if v is not None]
    lo = min(fin + [x_n])
    hi = math.inf if any(v is None for v in vals) else max(fin + [x_n])
    return x_n, lo, hi, False


def base_cut_off(mask, model: CameraModel = DEFAULT_CAMERA, bearing_deg: Optional[float] = None,
                 tol_deg: float = 5.0, edge_cols: int = 2) -> Tuple[bool, str]:
    """(cut_off, reason): is the flame base inside the bearing window cut off by the image (bottom row, or the
    outermost ``edge_cols`` columns at either side)? See the module docstring (D5)."""
    m = np.asarray(mask, dtype=bool)
    if m.shape != (model.h, model.w):
        return True, "mask shape %s != %s" % (m.shape, (model.h, model.w))
    low = lowest_flame_row(m)
    allc = np.arange(model.w)
    inwin = np.ones(model.w, dtype=bool) if bearing_deg is None else \
        np.abs(model.col_bearing_deg(allc) - bearing_deg) <= tol_deg
    bottom = np.flatnonzero(inwin & (low == model.h - 1))
    if bottom.size:
        return True, "flame base below the image (bottom row, %d columns in the path window)" % bottom.size
    k = max(1, int(edge_cols))
    side = np.zeros(model.w, dtype=bool)
    side[:k] = True
    side[-k:] = True
    hit = np.flatnonzero(inwin & side & (low >= 0))
    if hit.size:
        return True, "flame at the image %s edge inside the path window" % ("left" if hit[0] < k else "right")
    return False, ""


def near_edge(mask, model: CameraModel = DEFAULT_CAMERA, pose: CameraPose = CameraPose(), imu=None,
              profile: Optional[Profile] = None, bearing_deg: Optional[float] = None, tol_deg: float = 5.0,
              pitch_sigma_deg: float = 0.5, edge_cols: int = 2) -> Optional[NearEdge]:
    """Nearest flame base over the flame columns within tol_deg of bearing_deg (all flame columns if None).

    For each column: lowest flame pixel, its bottom-edge ray intersected with the profile; the nearest column wins,
    and the interval is the per-column interval of that minimum (lo = min of lo, hi = min of hi). None when there is
    no flame column, no valid profile, or no ray meets the ground. ``base_cut_off`` is set when the base in the
    window is cut off by the image (``base_cut_off()``); then d_lo_m = 0 (the base may be anywhere nearer)."""
    m = np.asarray(mask, dtype=bool)
    if profile is None or not profile.valid or m.shape != (model.h, model.w):
        return None
    cut, cut_why = base_cut_off(m, model, bearing_deg, tol_deg, edge_cols)
    low = lowest_flame_row(m)
    cols = np.flatnonzero(low >= 0)
    if bearing_deg is not None:
        b = model.col_bearing_deg(cols)
        cols = cols[np.abs(b - bearing_deg) <= tol_deg]
    if cols.size == 0:
        return None
    best = None
    lo_all = math.inf
    hi_all = math.inf
    used = []
    for c in cols:
        r = _column_near(model, pose, imu, profile, int(low[c]), int(c), pitch_sigma_deg)
        if r is None:
            continue
        d, lo, hi, occ = r
        used.append(int(c))
        lo_all = min(lo_all, lo)
        hi_all = min(hi_all, hi)
        if best is None or d < best[0]:
            best = (d, int(c), occ)
    if best is None:
        if not cut:
            return None
        # the only flame base in the window is below the image: report it as not observed (nothing measurable)
        c = int(cols[np.argmax(low[cols])])
        return NearEdge(d_m=math.nan, bearing_deg=float(model.col_bearing_deg(c)), row=int(low[c]), col=c,
                        d_lo_m=0.0, d_hi_m=math.inf, slope_source=profile.source, columns=[],
                        base_cut_off=True, cut_off_reason=cut_why)
    d, c, occ = best
    return NearEdge(d_m=d, bearing_deg=float(model.col_bearing_deg(c)), row=int(low[c]), col=c,
                    d_lo_m=0.0 if cut else lo_all, d_hi_m=hi_all, slope_source=profile.source, occluded=occ,
                    ground_dz_m=float(profile.dz_at(min(d, profile.s_max))), columns=used,
                    base_cut_off=cut, cut_off_reason=cut_why)


def flame_top_cut_off(mask, ne: Optional[NearEdge]) -> bool:
    """True when a flame column of the near edge reaches the top image row (its height is only a lower bound)."""
    if ne is None:
        return False
    top = top_flame_row(np.asarray(mask, dtype=bool))
    return any(top[c] == 0 for c in (ne.columns or [ne.col]))


def flame_height(mask, ne: NearEdge, model: CameraModel = DEFAULT_CAMERA, pose: CameraPose = CameraPose(),
                 imu=None, profile: Optional[Profile] = None,
                 pitch_sigma_deg: float = 0.5, allow_top_cut: bool = False) -> Optional[Tuple[float, float, float]]:
    """(h_m, h_lo, h_hi): top flame pixel (top edge, +-0.5 px) over the near edge's columns, ray height at the
    near-edge distance (and its interval), minus the ground height there. None when not computable, and (unless
    ``allow_top_cut``) when the flame reaches the top image row (height unknown, see ``flame_top_cut_off``)."""
    if ne is None or profile is None or not profile.valid:
        return None
    m = np.asarray(mask, dtype=bool)
    top = top_flame_row(m)
    cols = [c for c in (ne.columns or [ne.col]) if top[c] >= 0]
    if not cols:
        return None
    if not allow_top_cut and any(top[c] == 0 for c in cols):
        return None
    a = _att(imu)
    h = pose.height_m

    def height(row, col, d, dp=0.0):
        if d is None or not math.isfinite(d):
            return None
        g = profile.dz_at(d)
        if not math.isfinite(g):
            return None
        r = pixel_ray(model, pose, Attitude(a.roll_deg, a.pitch_deg + dp), row, col)
        if r[0] <= 1e-9:
            return None
        return h + d * r[2] / r[0] - g

    c_top = min(cols, key=lambda c: top[c])
    r_top = int(top[c_top])
    nominal = height(r_top - 0.5, c_top, ne.d_m)
    if nominal is None:
        return None
    vals = []
    for row in (r_top - 1.0, r_top + 0.0):
        for d in (ne.d_lo_m, ne.d_m, ne.d_hi_m):
            for dp in (-pitch_sigma_deg, pitch_sigma_deg):
                vals.append(height(row, c_top, d, dp))
    fin = [v for v in vals if v is not None]
    lo = max(0.0, min(fin + [nominal]))
    hi = math.inf if any(v is None for v in vals) else max(fin + [nominal])
    return float(nominal), float(lo), float(hi)
