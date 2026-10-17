"""Calibration (plan section 3): pixels by default, meters only at a stated distance range.

Ember scale. One camera cannot see depth, so an ember's meters per pixel follow from an
assumed distance Z and the focal length f in pixels: m/px = Z / f (pinhole, near the image
centre). Each clip states a distance interval [Z_min, Z_max]; speeds are reported as the
interval [v_px Z_min / f, v_px Z_max / f]. That interval is a statement about the
assumption, kept separate from the statistical interval for f.

Ground geometry. Points on the road with known ground coordinates (lane dash ends, for
example) give the camera's height and pitch by a pose fit (cv2.solvePnP on the ground
plane Z = 0). This describes the road surface only and is never used to scale airborne
embers: an ember 1 m above the road would be placed several times too far away. A Monte
Carlo over click noise and the focal-length uncertainty gives intervals for height and
pitch.

Focal length. From the horizontal field of view of the video frame,
f = (W / 2) / tan(HFOV / 2), or given directly. Wide dashcam lenses distort strongly
away from the centre; the pinhole scale holds near the centre only.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np


def focal_from_hfov(width_px: int, hfov_deg: float) -> float:
    return (width_px / 2.0) / math.tan(math.radians(hfov_deg) / 2.0)


@dataclass(frozen=True)
class EmberScale:
    focal_px: float
    z_min_m: float
    z_max_m: float

    @property
    def m_per_px(self) -> tuple[float, float]:
        return self.z_min_m / self.focal_px, self.z_max_m / self.focal_px

    def speed_interval(self, v_px_s: float) -> tuple[float, float]:
        lo, hi = self.m_per_px
        return v_px_s * lo, v_px_s * hi

    def label(self) -> str:
        return f"at Z = {self.z_min_m:g} to {self.z_max_m:g} m"


@dataclass
class GroundPose:
    height_m: float
    pitch_deg: float            # downward tilt of the optical axis below the horizon
    roll_deg: float
    reproj_rms_px: float
    height_ci: tuple[float, float] | None = None
    pitch_ci: tuple[float, float] | None = None


def _camera_matrix(f: float, size: tuple[int, int], center: tuple[float, float] | None = None) -> np.ndarray:
    w, h = size
    cx, cy = center if center is not None else ((w - 1) / 2.0, (h - 1) / 2.0)
    return np.array([[f, 0, cx], [0, f, cy], [0, 0, 1]], np.float64)


def solve_ground_pose(image_pts: np.ndarray, ground_pts: np.ndarray, focal_px: float,
                      size: tuple[int, int]) -> GroundPose:
    """Camera height and pitch from at least 4 ground points (X, Y in m on the road plane)."""
    img = np.asarray(image_pts, np.float64).reshape(-1, 2)
    gnd = np.asarray(ground_pts, np.float64).reshape(-1, 2)
    if len(img) < 4 or len(img) != len(gnd):
        raise ValueError("need at least 4 matching image and ground points")
    obj = np.column_stack([gnd, np.zeros(len(gnd))])
    K = _camera_matrix(focal_px, size)
    flag = cv2.SOLVEPNP_IPPE if len(img) >= 4 else cv2.SOLVEPNP_ITERATIVE
    ok, rvec, tvec = cv2.solvePnP(obj, img, K, None, flags=flag)
    if not ok:
        raise ValueError("pose fit failed")
    ok, rvec, tvec = cv2.solvePnP(obj, img, K, None, rvec, tvec, useExtrinsicGuess=True,
                                  flags=cv2.SOLVEPNP_ITERATIVE)
    R, _ = cv2.Rodrigues(rvec)
    cam = (-R.T @ tvec).ravel()                 # camera centre in ground coordinates
    height = abs(float(cam[2]))
    axis = R.T @ np.array([0.0, 0.0, 1.0])       # optical axis in ground coordinates
    pitch = math.degrees(math.asin(np.clip(-axis[2] * np.sign(cam[2] or 1.0), -1, 1)))
    xr = R.T @ np.array([1.0, 0.0, 0.0])         # image x axis in ground coordinates
    roll = math.degrees(math.asin(np.clip(xr[2], -1, 1)))
    proj, _ = cv2.projectPoints(obj, rvec, tvec, K, None)
    rms = float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - img) ** 2, axis=1))))
    return GroundPose(height, pitch, roll, rms)


def ground_pose_interval(image_pts, ground_pts, focal_px: float, size: tuple[int, int],
                         click_sigma_px: float = 1.5, focal_rel_sd: float = 0.05, n: int = 400,
                         seed: int = 0, ci: float = 0.95,
                         ground_scale_range: tuple[float, float] = (1.0, 1.0)) -> GroundPose:
    """Pose plus Monte Carlo intervals over click noise, focal length and ground scale.

    ground_scale_range: the ground coordinates are multiplied by a factor drawn uniformly
    from this range in each draw, for a road length that is only known as a range (Korean
    dashed lane lines are 3 to 10 m by the KNPA manual; see data/SOURCES.md). Height scales
    with it; pitch does not.
    """
    base = solve_ground_pose(image_pts, ground_pts, focal_px, size)
    rng = np.random.default_rng(seed)
    img = np.asarray(image_pts, np.float64).reshape(-1, 2)
    hs, ps = [], []
    for _ in range(n):
        f = focal_px * (1 + rng.normal(0, focal_rel_sd))
        g = np.asarray(ground_pts, np.float64) * rng.uniform(*ground_scale_range)
        try:
            p = solve_ground_pose(img + rng.normal(0, click_sigma_px, img.shape), g, f, size)
        except (ValueError, cv2.error):
            continue
        hs.append(p.height_m)
        ps.append(p.pitch_deg)
    a = (1 - ci) / 2
    if hs:
        base.height_ci = (float(np.quantile(hs, a)), float(np.quantile(hs, 1 - a)))
        base.pitch_ci = (float(np.quantile(ps, a)), float(np.quantile(ps, 1 - a)))
    return base


def ground_point_at_pixel(u: float, v: float, pose_rvec, pose_tvec, K: np.ndarray) -> np.ndarray | None:
    """Where the ray through a pixel meets the road (for overlay geometry only)."""
    R, _ = cv2.Rodrigues(pose_rvec)
    ray = R.T @ np.linalg.inv(K) @ np.array([u, v, 1.0])
    c = (-R.T @ np.asarray(pose_tvec).reshape(3)).ravel()
    if abs(ray[2]) < 1e-12:
        return None
    s = -c[2] / ray[2]
    return None if s <= 0 else c + s * ray
