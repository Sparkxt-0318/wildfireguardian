"""Tests for crossing.terrain and crossing.geometry on SYNTHETIC scenes (no camera, no DEM tile of a real place).

The flame is a vertical sheet across the road at along-course distance D, height H above the ground there, lateral
half-width W. The forward renderer below is written independently of crossing.geometry (Rodrigues rotations about
physical axes, dense ground march) so a sign error in the module would not cancel out.
"""
import math

import numpy as np
import pytest

from crossing.geometry import (Attitude, CameraPose, base_cut_off, flame_height, flame_top_cut_off,
                               intersect_profile, near_edge, pixel_ray)
from crossing.terrain import Dem, Profile, grid_bearing_deg, imu_plane_profile, road_profile
from crossing.thermal import CameraModel

CAM = CameraModel()


def rod(axis, deg):
    """Rotation matrix, right-hand rule about `axis` by `deg` (Rodrigues)."""
    k = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    t = math.radians(deg)
    return np.eye(3) + math.sin(t) * K + (1 - math.cos(t)) * K @ K


def true_rays(cam_pitch_total_deg, roll_deg, mount_roll=0.0):
    """Level-frame rays for every pixel centre. Nose-up = rotation about the RIGHT axis (0,-1,0); right side down =
    rotation about the FORWARD axis (1,0,0). Body then mount pitch (mount_yaw = 0)."""
    rows, cols = np.mgrid[0:CAM.h, 0:CAM.w].astype(float)
    v = np.stack([np.ones_like(rows), -(cols - CAM.ppx) / CAM.fx, -(rows - CAM.ppy) / CAM.fy], axis=-1)
    return v, rows, cols


def render(ground, D, H, W, h_cam, body_pitch=0.0, body_roll=0.0, mount_pitch=0.0, x_max=None):
    """Bool flame mask [h, w]. ground: callable x -> dz (vectorised). A pixel is flame if its centre ray reaches the
    sheet x = D without meeting the ground first, between ground(D) and ground(D) + H, with |y| <= W."""
    R = rod([0, -1, 0], body_pitch) @ rod([1, 0, 0], body_roll) @ rod([0, -1, 0], mount_pitch)
    v, _, _ = true_rays(0, 0)
    r = v.reshape(-1, 3) @ R.T
    r /= np.linalg.norm(r, axis=1, keepdims=True)
    mask = np.zeros(r.shape[0], bool)
    fwd = r[:, 0] > 1e-6
    k = np.where(fwd, r[:, 2] / np.where(fwd, r[:, 0], 1), 0)
    zD = h_cam + k * D
    yD = D * r[:, 1] / np.where(fwd, r[:, 0], 1)
    gD = ground(np.array([D]))[0]
    cand = fwd & (zD >= gD) & (zD <= gD + H) & (np.abs(yD) <= W)
    xs = np.arange(0.005, D, 0.01)
    gx = ground(xs)
    for i in np.flatnonzero(cand):
        if np.any(h_cam + k[i] * xs - gx < 0):             # ground hit before the sheet: occluded
            continue
        mask[i] = True
    return mask.reshape(CAM.h, CAM.w)


# --- pixel rays ---------------------------------------------------------------------------------------------------
def test_pixel_ray_conventions():
    pose = CameraPose(height_m=2.0)
    r = pixel_ray(CAM, pose, Attitude(), CAM.ppy, CAM.ppx)
    assert np.allclose(r, [1, 0, 0])
    assert pixel_ray(CAM, pose, Attitude(), CAM.ppy, 250)[1] < 0           # right of centre -> y negative
    assert pixel_ray(CAM, pose, Attitude(), 180, CAM.ppx)[2] < 0           # below centre -> down
    up = pixel_ray(CAM, pose, Attitude(pitch_deg=5.0), CAM.ppy, CAM.ppx)
    assert math.degrees(math.asin(up[2])) == pytest.approx(5.0)
    # roll right side down: a pixel right of centre on the centre row now points below the horizon
    rr = pixel_ray(CAM, pose, Attitude(roll_deg=5.0), CAM.ppy, 250)
    assert rr[2] < 0
    # mount pitch and IMU pitch add on the centre column
    m = pixel_ray(CAM, CameraPose(mount_pitch_deg=-8.0), Attitude(pitch_deg=3.0), CAM.ppy, CAM.ppx)
    assert math.degrees(math.asin(m[2])) == pytest.approx(-5.0)
    # independent check against Rodrigues for a combined tilt
    v = np.array([1.0, -(40 - CAM.ppx) / CAM.fx, -(150 - CAM.ppy) / CAM.fy])
    R = rod([0, -1, 0], 4.0) @ rod([1, 0, 0], -3.0) @ rod([0, -1, 0], -6.0)
    want = R @ v; want /= np.linalg.norm(want)
    got = pixel_ray(CAM, CameraPose(mount_pitch_deg=-6.0), Attitude(roll_deg=-3.0, pitch_deg=4.0), 150, 40)
    assert np.allclose(got, want, atol=1e-12)


def test_intersect_profile_plane_analytic():
    prof = Profile.plane(0.1, s_max_m=80, ds=2.0, source="dem")
    ray = np.array([math.cos(math.radians(-10)), 0, math.sin(math.radians(-10))])
    x = intersect_profile(ray, 3.0, prof)
    assert x == pytest.approx(3.0 / (math.tan(math.radians(10)) + 0.1), abs=2e-3)
    assert intersect_profile(np.array([1.0, 0, 0.2]), 3.0, prof) is None          # never meets the ground
    assert intersect_profile(np.array([-1.0, 0, -0.2]), 3.0, prof) is None         # backwards


# --- (a) grades: no flat-ground assumption -----------------------------------------------------------------------
@pytest.mark.parametrize("grade", [0.10, -0.10])
def test_near_edge_on_grade_matches_analytic_and_flat_is_wrong(grade):
    D, H, W, h = 10.0, 3.0, 3.0, 3.0
    pose = CameraPose(height_m=h, mount_pitch_deg=-8.0)
    mask = render(lambda x: grade * x, D, H, W, h, mount_pitch=-8.0)
    assert mask.any()
    prof = Profile.plane(grade, source="dem")
    ne = near_edge(mask, CAM, pose, Attitude(), prof)
    err = abs(ne.d_m - D) / D
    flat = near_edge(mask, CAM, pose, Attitude(), Profile.plane(0.0, source="flat"))
    flat_err = math.inf if flat is None else abs(flat.d_m - D) / D
    print(f"\ngrade {grade:+.0%}: near edge {ne.d_m:.3f} m (truth {D}) err {err:.2%}, interval "
          f"[{ne.d_lo_m:.2f}, {ne.d_hi_m:.2f}]; flat-ground {None if flat is None else round(flat.d_m, 2)} m "
          f"err {flat_err:.1%}")
    assert err < 0.02
    assert ne.d_lo_m <= D <= ne.d_hi_m
    assert flat_err > 0.02 and flat_err > 5 * err
    assert ne.slope_source == "dem"
    fh = flame_height(mask, ne, CAM, pose, Attitude(), prof)
    assert fh is not None
    assert abs(fh[0] - H) / H < 0.10 and fh[1] <= H <= fh[2]


# --- D5: flame base cut off by the image ---------------------------------------------------------------------------
def test_base_cut_off_by_bottom_row_level_camera_and_seen_with_downward_pitch():
    """A level camera at 2.6 m sees no ground nearer than 2.6 / tan(21 deg) = 6.8 m. A flame 5 m ahead fills the
    bottom row: the base is NOT observed (base_cut_off, d_lo = 0). Pitched 18 deg down (the unit's default) the
    nearest visible ground is 3.2 m and the same base is measured."""
    D, H, W, h = 5.0, 3.0, 3.0, 2.6
    flat = Profile.plane(0.0, source="dem")
    mask = render(lambda x: 0.0 * x, D, H, W, h)
    assert mask[-1].any()
    ne = near_edge(mask, CAM, CameraPose(height_m=h), Attitude(), flat, bearing_deg=0.0, tol_deg=6.0)
    assert ne is not None and ne.base_cut_off and "bottom" in ne.cut_off_reason
    assert ne.d_lo_m == 0.0 and ne.d_m > D                     # the reported distance is only a far bound
    assert base_cut_off(mask, CAM, 0.0, 6.0)[0]
    pose = CameraPose(height_m=h, mount_pitch_deg=-18.0)
    mask2 = render(lambda x: 0.0 * x, D, H, W, h, mount_pitch=-18.0)
    ne2 = near_edge(mask2, CAM, pose, Attitude(), flat, bearing_deg=0.0, tol_deg=6.0)
    assert ne2 is not None and not ne2.base_cut_off and ne2.cut_off_reason == ""
    assert abs(ne2.d_m - D) < 0.1 and ne2.d_lo_m <= D <= ne2.d_hi_m


def test_base_cut_off_by_image_side_inside_the_path_window():
    """A wide line fire reaches both image sides. With the path window inside the image it is not cut off; when the
    path window (camera yawed so the path is near the image edge) contains the side columns, it is."""
    D, H, W, h = 12.0, 2.0, 60.0, 3.0
    pose = CameraPose(height_m=h, mount_pitch_deg=-8.0)
    flat = Profile.plane(0.0, source="dem")
    mask = render(lambda x: 0.0 * x, D, H, W, h, mount_pitch=-8.0)
    assert mask[:, 0].any() and mask[:, -1].any()
    ok = near_edge(mask, CAM, pose, Attitude(), flat, bearing_deg=0.0, tol_deg=6.0)
    assert ok is not None and not ok.base_cut_off and abs(ok.d_m - D) < 0.2
    cut = near_edge(mask, CAM, pose, Attitude(), flat, bearing_deg=25.0, tol_deg=6.0)
    assert cut is not None and cut.base_cut_off and "right" in cut.cut_off_reason
    assert base_cut_off(mask, CAM, -25.0, 6.0) == (True, "flame at the image left edge inside the path window")
    assert base_cut_off(np.zeros((CAM.h, CAM.w), bool), CAM, 0.0, 6.0) == (False, "")


def test_flame_top_cut_off_gives_no_height():
    """A flame taller than the (downward-pitched) view reaches the top row: its height is only a lower bound, so
    flame_height returns None (fail closed) unless allow_top_cut."""
    D, H, W, h = 10.0, 8.0, 3.0, 2.6
    pose = CameraPose(height_m=h, mount_pitch_deg=-18.0)
    flat = Profile.plane(0.0, source="dem")
    mask = render(lambda x: 0.0 * x, D, H, W, h, mount_pitch=-18.0)
    assert mask[0].any()
    ne = near_edge(mask, CAM, pose, Attitude(), flat, bearing_deg=0.0, tol_deg=6.0)
    assert ne is not None and not ne.base_cut_off and flame_top_cut_off(mask, ne)
    assert flame_height(mask, ne, CAM, pose, Attitude(), flat) is None
    lb = flame_height(mask, ne, CAM, pose, Attitude(), flat, allow_top_cut=True)
    assert lb is not None and lb[0] < H


# --- (b) camera tilt compensated by the IMU -----------------------------------------------------------------------
@pytest.mark.parametrize("pitch,roll", [(5.0, 0.0), (-5.0, 0.0), (0.0, 5.0), (0.0, -5.0)])
def test_imu_tilt_compensation(pitch, roll):
    D, H, W, h = 12.0, 3.0, 4.0, 3.0
    pose = CameraPose(height_m=h, mount_pitch_deg=-8.0)
    prof = Profile.plane(0.0, source="dem")
    mask = render(lambda x: 0.0 * x, D, H, W, h, body_pitch=pitch, body_roll=roll, mount_pitch=-8.0)
    ne = near_edge(mask, CAM, pose, Attitude(roll_deg=roll, pitch_deg=pitch), prof)
    raw = near_edge(mask, CAM, pose, Attitude(), prof)                     # tilt ignored
    err = abs(ne.d_m - D) / D
    raw_err = math.inf if raw is None else abs(raw.d_m - D) / D
    print(f"\npitch {pitch:+} roll {roll:+}: compensated {ne.d_m:.3f} m err {err:.2%}; uncompensated "
          f"{None if raw is None else round(raw.d_m, 2)} m err {raw_err:.1%}")
    assert err < 0.02
    assert ne.d_lo_m <= D <= ne.d_hi_m
    assert raw_err > 0.02


def test_imu_plane_fallback_on_uniform_grade():
    # vehicle on a uniform 10 % up-grade, no DEM: body pitch = atan(0.1); fallback plane from the IMU
    D, H, W, h = 10.0, 3.0, 3.0, 3.0
    pitch = math.degrees(math.atan(0.1))
    pose = CameraPose(height_m=h, mount_pitch_deg=-8.0)
    mask = render(lambda x: 0.1 * x, D, H, W, h, body_pitch=pitch, mount_pitch=-8.0)
    prof = imu_plane_profile(pitch)
    assert prof.source == "imu"
    ne = near_edge(mask, CAM, pose, Attitude(pitch_deg=pitch), prof)
    assert ne.slope_source == "imu"
    assert abs(ne.d_m - D) / D < 0.02
    flat = near_edge(mask, CAM, pose, Attitude(pitch_deg=pitch), Profile.plane(0.0))
    assert flat is None or abs(flat.d_m - D) / D > 0.02
    assert not imu_plane_profile(float("nan")).valid


# --- (c) DEM with a crest ----------------------------------------------------------------------------------------
LAT0, LON0 = 37.5, 128.0
COURSE = 30.0
CREST = 25.0


def crest_f(a):
    a = np.asarray(a, float)
    return np.where(a < CREST, 0.08 * a, 0.08 * CREST - 0.08 * (a - CREST))


@pytest.fixture(scope="module")
def crest_dem(tmp_path_factory):
    res = 1.0
    xs = -150 + (np.arange(300) + 0.5) * res
    ys = 150 - (np.arange(300) + 0.5) * res
    X, Y = np.meshgrid(xs, ys)
    along = X * math.sin(math.radians(COURSE)) + Y * math.cos(math.radians(COURSE))
    z = (100.0 + crest_f(along)).astype(np.float32)
    p = tmp_path_factory.mktemp("dem") / "crest.npz"
    Dem(z=z, x0=-150.0, y_top=150.0, res=res, crs="local-enu", lat0=LAT0, lon0=LON0).save(p)
    return Dem.load(p)


def test_dem_profile_with_crest(crest_dem):
    assert crest_dem.elevation(LAT0, LON0) == pytest.approx(100.0, abs=0.05)
    prof = road_profile(crest_dem, LAT0, LON0, COURSE, s_max_m=80, ds=1.0)
    assert prof.valid and prof.source == "dem"
    # the crest's kink is smoothed by bilinear interpolation over one cell
    assert np.max(np.abs(prof.dz - crest_f(prof.s))) < 0.06
    assert prof.s[np.argmax(prof.dz)] == pytest.approx(CREST, abs=1.0)
    off = road_profile(crest_dem, LAT0, LON0, COURSE + 90.0, s_max_m=80, ds=1.0)
    assert np.max(np.abs(off.dz)) < 0.05                     # across the slope it is level
    assert not road_profile(crest_dem, LAT0 + 1.0, LON0, COURSE).valid    # off the DEM
    assert not road_profile(None, LAT0, LON0, COURSE).valid


def test_near_edge_before_and_behind_crest(crest_dem):
    h = 3.0
    pose = CameraPose(height_m=h, mount_pitch_deg=-5.0)
    prof = road_profile(crest_dem, LAT0, LON0, COURSE, s_max_m=80, ds=1.0)
    # flame before the crest, on the 8 % up-slope
    D = 18.0
    mask = render(lambda x: crest_f(x), D, 3.0, 3.0, h, mount_pitch=-5.0)
    ne = near_edge(mask, CAM, pose, Attitude(), prof)
    flat = near_edge(mask, CAM, pose, Attitude(), Profile.plane(0.0, source="flat"))
    print(f"\ncrest DEM, flame at {D} m: {ne.d_m:.3f} m err {abs(ne.d_m - D) / D:.2%}; flat-ground "
          f"{None if flat is None else round(flat.d_m, 2)} m")
    assert abs(ne.d_m - D) / D < 0.02 and not ne.occluded
    assert flat is None or abs(flat.d_m - D) / D > 0.02
    # flame behind the crest: base hidden; result must say so and not claim a far base
    D2 = 40.0
    mask2 = render(lambda x: crest_f(x), D2, 4.0, 3.0, h, mount_pitch=-5.0)
    assert mask2.any()
    ne2 = near_edge(mask2, CAM, pose, Attitude(), prof)
    print(f"crest DEM, flame at {D2} m behind the crest: occluded={ne2.occluded}, d={ne2.d_m:.2f}, "
          f"interval [{ne2.d_lo_m:.2f}, {ne2.d_hi_m}]")
    assert ne2.occluded
    assert ne2.d_lo_m <= D2 <= ne2.d_hi_m
    assert ne2.d_m <= CREST + 1.0                             # nearest possible base: the crest


# --- meridian convergence (EPSG:5179) ----------------------------------------------------------------------------
def test_meridian_convergence_sign_with_pyproj(tmp_path):
    pyproj = pytest.importorskip("pyproj")
    lat, lon = 37.5, 129.0                                    # east of the 127.5 E central meridian
    tr = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    x0, y0 = tr.transform(lon, lat)
    res = 2.0
    n = 200
    # DEM rising toward GRID east, 5 %: z = 0.05 * (x - x0)
    xs = (x0 - 200.0) + (np.arange(n) + 0.5) * res
    z = np.tile(0.05 * (xs - x0), (n, 1)).astype(np.float32)
    p = tmp_path / "k5179.npz"
    Dem(z=z, x0=x0 - 200.0, y_top=y0 + 200.0, res=res, crs="EPSG:5179").save(p)
    dem = Dem.load(p)
    gamma = dem.convergence_deg(lat, lon)
    assert gamma == pytest.approx(pyproj.Proj("EPSG:5179").get_factors(lon, lat).meridian_convergence)
    assert gamma > 0.5                                        # ~0.91 deg here
    # numerical check: walk 100 m along TRUE course 40 deg on the ellipsoid, measure the grid azimuth
    geod = pyproj.Geod(ellps="GRS80")
    lon2, lat2, _ = geod.fwd(lon, lat, 40.0, 100.0)
    x2, y2 = tr.transform(lon2, lat2)
    grid_az = math.degrees(math.atan2(x2 - x0, y2 - y0))
    assert grid_az == pytest.approx(40.0 - gamma, abs=0.01)
    assert grid_bearing_deg(dem, lat, lon, 40.0) == pytest.approx(grid_az, abs=0.01)
    # a profile due TRUE north runs slightly WEST in the grid here, so it descends on this east-rising DEM
    prof = road_profile(dem, lat, lon, 0.0, s_max_m=80, ds=2.0)
    expect = 0.05 * 80.0 * dem.scale_factor(lat, lon) * math.sin(math.radians(-gamma))
    assert prof.dz[-1] == pytest.approx(expect, abs=0.003)
    assert prof.dz[-1] < -0.05


# --- PHYS-3: a crest that cuts the flame inside the lowest flame pixel -------------------------------------------
def _crest20(x):
    """Ground (m) along the course: level to 18 m, +2 m crest at 20 m, back to level at 22 m, level beyond."""
    x = np.asarray(x, float)
    return np.interp(x, [0.0, 18.0, 20.0, 22.0, 200.0], [0.0, 0.0, 2.0, 0.0, 0.0])


@pytest.mark.parametrize("D,H", [(28.0, 4.0), (40.0, 4.0), (43.0, 4.0), (43.0, 6.0)])
def test_crest_cutting_the_lowest_flame_pixel_is_occluded_and_fails_closed(D, H):
    """PHYS-3 (probes p4/p5): camera 2.6 m, pitched 10 deg down, crest at 20 m (+2 m), flame base behind it at
    28-43 m. The rays through the lower half of the lowest flame pixel both met the crest, so the base was taken at
    the crest (d 19.76 m, not occluded) and the flame height / intensity upper end were far too low. Now the whole
    footprint of that pixel is searched: occluded, d_hi = inf, flame height upper end inf, intensity invalid."""
    from crossing import depth as dp
    from crossing.fuels import get_fuel
    h = 2.6
    pose = CameraPose(height_m=h, mount_pitch_deg=-10.0)
    s = np.arange(0.0, 80.0 + 1e-9, 0.5)
    prof = Profile(s, _crest20(s), "dem")
    mask = render(_crest20, D, H, 3.0, h, mount_pitch=-10.0)
    assert mask.any()
    ne = near_edge(mask, CAM, pose, Attitude(), prof)
    assert ne is not None and ne.occluded, (ne.d_m, ne.d_hi_m)
    assert ne.d_hi_m == math.inf and ne.d_lo_m <= D
    fh = flame_height(mask, ne, CAM, pose, Attitude(), prof)
    assert fh is None or fh[2] == math.inf
    inten = dp.intensity(fh, None, get_fuel("DEFAULT"))
    true_i = dp.byram_intensity_from_length(H)
    assert (not inten.valid) or inten.hi >= true_i


def test_flat_road_flame_is_not_flagged_occluded_by_the_wider_search():
    """The PHYS-3 search must not flag a flame on visible ground (flat road, level and pitched camera)."""
    for pitch in (0.0, -10.0):
        pose = CameraPose(height_m=2.6, mount_pitch_deg=pitch)
        mask = render(lambda x: np.zeros_like(np.asarray(x, float)), 15.0, 2.0, 3.0, 2.6, mount_pitch=pitch)
        ne = near_edge(mask, CAM, pose, Attitude(), Profile.plane(0.0))
        assert ne is not None and not ne.occluded and abs(ne.d_m - 15.0) / 15.0 < 0.03
