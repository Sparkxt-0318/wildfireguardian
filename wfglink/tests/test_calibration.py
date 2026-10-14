"""Calibration: ember scale interval, and camera height and pitch from road points."""
import math

import cv2
import numpy as np

from wfglink.measure.calibration import EmberScale, focal_from_hfov, ground_pose_interval, solve_ground_pose


def test_focal_from_hfov_and_scale_interval():
    f = focal_from_hfov(1920, 90.0)
    assert math.isclose(f, 960.0)
    s = EmberScale(f, 10.0, 20.0)
    lo, hi = s.speed_interval(96.0)
    assert math.isclose(lo, 1.0) and math.isclose(hi, 2.0)


def _project(height, pitch_deg, f, size, ground):
    """Camera at (0, 0, height) looking along +Y, tilted down by pitch."""
    w, h = size
    K = np.array([[f, 0, (w - 1) / 2], [0, f, (h - 1) / 2], [0, 0, 1]])
    p = math.radians(pitch_deg)
    # Camera axes in ground coordinates: x right (+X), y down, z forward.
    zc = np.array([0, math.cos(p), -math.sin(p)])
    xc = np.array([1.0, 0, 0])
    yc = np.cross(zc, xc)
    R = np.vstack([xc, yc, zc])               # ground -> camera rotation
    t = -R @ np.array([0, 0, height])
    obj = np.column_stack([ground, np.zeros(len(ground))])
    img, _ = cv2.projectPoints(obj, cv2.Rodrigues(R)[0], t, K, None)
    return img.reshape(-1, 2)


def test_ground_pose_recovers_height_and_pitch():
    size = (1920, 1080)
    f = focal_from_hfov(1920, 100.0)
    # Two lane lines 3.5 m apart, dash ends every 5 m from 6 to 21 m ahead.
    ground = np.array([[x, y] for y in (6.0, 11.0, 16.0, 21.0) for x in (-1.75, 1.75)])
    img = _project(1.3, 8.0, f, size, ground)
    pose = solve_ground_pose(img, ground, f, size)
    assert abs(pose.height_m - 1.3) < 0.01
    assert abs(pose.pitch_deg - 8.0) < 0.1
    assert pose.reproj_rms_px < 0.01
    mc = ground_pose_interval(img, ground, f, size, n=200)
    assert mc.height_ci[0] < 1.3 < mc.height_ci[1]
    assert mc.pitch_ci[0] < 8.0 < mc.pitch_ci[1]


def test_unknown_road_scale_widens_height_but_not_pitch():
    size = (1920, 1080)
    f = focal_from_hfov(1920, 100.0)
    ground = np.array([[x, y] for y in (6.0, 11.0, 16.0, 21.0) for x in (-1.75, 1.75)])
    img = _project(1.3, 8.0, f, size, ground)
    a = ground_pose_interval(img, ground, f, size, n=200)
    b = ground_pose_interval(img, ground, f, size, n=200, ground_scale_range=(0.8, 1.2))
    assert (b.height_ci[1] - b.height_ci[0]) > 3 * (a.height_ci[1] - a.height_ci[0])
    assert abs((b.pitch_ci[1] - b.pitch_ci[0]) - (a.pitch_ci[1] - a.pitch_ci[0])) < 0.5
