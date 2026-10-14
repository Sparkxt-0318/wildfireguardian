"""Per-point and per-track velocity, streak speed, fusion and the circular-motion gain."""
import numpy as np
import pandas as pd
import pytest
from scipy.signal import savgol_coeffs, savgol_filter

from wfglink.config import load_config
from wfglink.detect.candidates import FLAG_SATURATED
from wfglink.measure.velocity import (add_point_velocities, correct_circular_speed,
                                      derivative_gain, derivative_noise_gain,
                                      derivative_weights, estimate_angular_rate,
                                      local_poly_velocity, mean_velocity, streak_velocity,
                                      summarize_track_speed, track_point_velocities)

DT = 1.0 / 30.0


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.mark.parametrize("window,order", [(5, 2), (5, 1), (7, 3), (9, 2)])
def test_weights_equal_savgol(window, order):
    assert np.allclose(derivative_weights(window, order, DT),
                       savgol_coeffs(window, order, deriv=1, delta=DT, use="dot"))
    assert derivative_noise_gain(window, order, DT) == pytest.approx(
        np.sqrt(np.sum(savgol_coeffs(window, order, deriv=1, delta=DT) ** 2)))


def test_uniform_spacing_equals_savgol_filter():
    rng = np.random.default_rng(0)
    t = 3.0 + np.arange(50) * DT
    x = rng.normal(0, 1, 50).cumsum()
    y = rng.normal(0, 1, 50).cumsum()
    vx, vy, interior = local_poly_velocity(t, x, y, 5, 2)
    assert np.allclose(vx, savgol_filter(x, 5, 2, deriv=1, delta=DT, mode="interp"), atol=1e-8)
    assert np.allclose(vy, savgol_filter(y, 5, 2, deriv=1, delta=DT, mode="interp"), atol=1e-8)
    assert interior.sum() == 46 and not interior[:2].any() and not interior[-2:].any()


def test_exact_for_quadratic_motion_with_variable_timestamps():
    rng = np.random.default_rng(1)
    t = np.cumsum(DT * rng.uniform(0.5, 2.0, 30))
    x = 5 + 120 * t - 40 * t ** 2
    y = -3 - 60 * t + 9.81 * t ** 2
    vx, vy, _ = local_poly_velocity(t, x, y, 5, 2)
    assert np.allclose(vx, 120 - 80 * t, atol=1e-6)
    assert np.allclose(vy, -60 + 2 * 9.81 * t, atol=1e-6)


def test_coasted_points_and_short_tracks():
    t = np.arange(8) * DT
    x = 100 + 90 * t
    y = 50 - 30 * t
    x[3] = y[3] = np.nan                        # a coasted point
    vx, vy, _ = local_poly_velocity(t, x, y, 5, 2)
    assert np.isnan(vx[3]) and np.allclose(vx[np.arange(8) != 3], 90)
    for n in (2, 3, 4):
        vx, vy, interior = local_poly_velocity(t[:n], x[:n] if n < 4 else 100 + 90 * t[:n],
                                               y[:n] if n < 4 else 50 - 30 * t[:n], 5, 2)
        assert np.allclose(vx, 90) and np.allclose(vy, -30)
    vx, _, _ = local_poly_velocity(t[:1], x[:1], y[:1], 5, 2)
    assert np.isnan(vx).all()


def test_circular_gain_and_correction():
    # Closed form for the 5-point filter: G = (sin a + 2 sin 2a) / (5 a), a = omega dt.
    omega = 2 * np.pi * 45 / 60                 # 45 rpm
    a = omega * DT
    g = derivative_gain(omega, DT, 5, 2)
    assert g == pytest.approx((np.sin(a) + 2 * np.sin(2 * a)) / (5 * a), rel=1e-12)
    assert g == pytest.approx(1 - 17 * a * a / 30, abs=1e-4)
    assert derivative_gain(0.0, DT, 5, 2) == 1.0
    # Simulated LED on a turntable: the raw speed is low by G, the correction removes it.
    r = 120.0
    t = np.arange(90) * DT
    x = 400 + r * np.cos(omega * t + 0.3)
    y = 300 + r * np.sin(omega * t + 0.3)
    vx, vy, interior = local_poly_velocity(t, x, y, 5, 2)
    sp = np.hypot(vx, vy)[interior]
    assert np.allclose(sp, g * r * omega, rtol=1e-9)
    assert np.allclose(correct_circular_speed(sp, omega, DT, 5, 2), r * omega, rtol=1e-9)
    assert estimate_angular_rate(t, vx, vy) == pytest.approx(omega, rel=1e-3)
    assert estimate_angular_rate(t, vx, -vy) == pytest.approx(-omega, rel=1e-3)


def test_mean_velocity_fit():
    rng = np.random.default_rng(2)
    t = np.arange(20) * DT
    x = 10 + 200 * t + rng.normal(0, 0.5, 20)
    y = 30 - 200 * t + rng.normal(0, 0.5, 20)
    mv = mean_velocity(t, x, y, meas_sigma_px=0.5)
    assert mv.u == pytest.approx(200, abs=10) and mv.v == pytest.approx(-200, abs=10)
    assert mv.direction_deg == pytest.approx(-45, abs=3)
    assert mv.speed == pytest.approx(np.hypot(200, 200), rel=0.05)
    assert 0.3 < mv.sd_axis_px < 0.8 and mv.n == 20
    assert mv.duration_s == pytest.approx(19 * DT)
    two = mean_velocity(t[:2], x[:2], y[:2], meas_sigma_px=1.0)
    assert np.isnan(two.sd_axis_px)
    assert two.speed_sd == pytest.approx(1.0 / np.sqrt(np.sum((t[:2] - t[:2].mean()) ** 2)))
    assert np.isnan(mean_velocity(t[:1], x[:1], y[:1]).speed)


def test_streak_velocity_sign_follows_track():
    L = np.array([10.0, 10.0, 10.0])
    theta = np.array([0.0, np.pi / 4, 0.0])
    sx, sy, s = streak_velocity(L, theta, 0.01, np.array([-50.0, 30.0, 0.0]),
                                np.array([1.0, 30.0, 0.0]))
    assert np.allclose(s, 1000.0)
    assert sx[0] == pytest.approx(-1000.0) and sy[0] == pytest.approx(0.0, abs=1e-9)
    assert sx[1] == pytest.approx(1000 / np.sqrt(2)) and sy[1] == pytest.approx(1000 / np.sqrt(2))
    assert np.isnan(sx[2]) and np.isnan(sy[2])


def test_fusion_only_for_short_tracks(cfg):
    t_exp, t_sd = 0.01, 0.0005
    v = 800.0
    t = np.arange(4) * DT
    x = 100 + v * t
    y = np.full(4, 50.0)
    L = np.full(4, v * t_exp)
    theta = np.zeros(4)
    flags = np.zeros(4, np.uint8)
    s = summarize_track_speed(t, x, y, L, theta, flags, cfg, t_exp=t_exp, t_exp_sd=t_sd)
    assert s.best_source == "fused" and s.n_streak == 4
    assert s.streak_speed == pytest.approx(v) and s.track_speed == pytest.approx(v)
    sigma_l = cfg["velocity"]["exposure"].get("length_sigma_px", 1.0)
    assert s.streak_sd_indep == pytest.approx(sigma_l / (t_exp * 2))
    assert s.streak_sd_shared == pytest.approx(v * t_sd / t_exp)
    w_tr = 1 / s.track_speed_sd ** 2
    w_st = 1 / (s.streak_sd_indep ** 2 + s.streak_sd_shared ** 2)
    assert s.fused_sd == pytest.approx(np.sqrt(1 / (w_tr + w_st)))
    assert s.fused_shared_sd == pytest.approx(w_st / (w_tr + w_st) * s.streak_sd_shared)
    assert s.fused_speed == pytest.approx(v)
    # Inverse-variance weighting with unequal inputs.
    s2 = summarize_track_speed(t, x, y, L * 1.1, theta, flags, cfg, t_exp=t_exp, t_exp_sd=t_sd)
    w2 = 1 / (s2.streak_sd_indep ** 2 + s2.streak_sd_shared ** 2)
    want = (w_tr * v + w2 * 1.1 * v) / (w_tr + w2)
    assert s2.fused_speed == pytest.approx(want)
    # Five or more points: no fusion, the track speed is the best value.
    t5 = np.arange(6) * DT
    s3 = summarize_track_speed(t5, 100 + v * t5, np.full(6, 50.0), np.full(6, 8.0), np.zeros(6),
                               np.zeros(6, np.uint8), cfg, t_exp=t_exp, t_exp_sd=t_sd)
    assert np.isnan(s3.fused_speed) and s3.best_source == "track"
    assert s3.streak_speed == pytest.approx(800.0)
    # Saturated or short streaks do not give streak speed; no exposure, no streak speed.
    sat = summarize_track_speed(t, x, y, L, theta, np.full(4, FLAG_SATURATED, np.uint8), cfg,
                                t_exp=t_exp)
    assert sat.n_streak == 0 and sat.best_source == "track"
    none = summarize_track_speed(t, x, y, L, theta, flags, cfg)
    assert np.isnan(none.streak_speed)


def test_point_velocities_dataframe(cfg):
    rows = []
    for tid, (vx, vy) in enumerate([(100.0, 0.0), (0.0, -50.0)], start=1):
        for i in range(7):
            t = i * DT
            coast = tid == 2 and i == 3
            rows.append({"track_id": tid, "t": t, "frame": i,
                         "x_meas": np.nan if coast else 10 + vx * t,
                         "y_meas": np.nan if coast else 20 + vy * t,
                         "length": 6.0, "theta": np.pi / 2 if tid == 2 else 0.0})
    df = pd.DataFrame(rows).sample(frac=1.0, random_state=0)
    out = add_point_velocities(df, cfg, t_exp=0.02)
    assert out.index.equals(df.index)                      # same rows, same order
    a = out[out.track_id == 1]
    assert np.allclose(a["vx_poly"], 100) and np.allclose(a["vy_poly"], 0, atol=1e-9)
    b = out[out.track_id == 2]
    assert b["vx_poly"].isna().sum() == 1
    ok = b["vy_poly"].notna()
    assert np.allclose(b.loc[ok, "vy_poly"], -50)
    assert np.allclose(b.loc[ok, "speed_streak"], 300.0)
    assert np.allclose(b.loc[ok, "vy_streak"], -300.0)        # signed by the track direction
    arrs = {"t": np.arange(5) * DT, "x_meas": np.arange(5.0), "y_meas": np.zeros(5),
            "length": np.zeros(5), "theta": np.zeros(5)}
    res = track_point_velocities(arrs, cfg)
    assert set(res) == {"vx_poly", "vy_poly", "speed_poly", "interior"}
    assert np.allclose(res["vx_poly"], 30.0)


def test_point_streak_speed_only_for_usable_streaks(cfg):
    """Per-point streak speed follows the spec (L > 5 px, not saturated), like the summary.

    A point-like blob has L near 0, which says nothing about its speed; reporting
    L / T_exp = 0 there made per-point streak speed errors look like -100%.
    """
    min_len = cfg["velocity"].get("streak_min_length_px", 5.0)
    n = 9
    t = np.arange(n) * DT
    length = np.array([0.0, 2.0, min_len, min_len + 0.5, 8.0, 8.0, np.nan, 12.0, 12.0])
    flags = np.zeros(n, np.uint8)
    flags[5] = FLAG_SATURATED
    df = pd.DataFrame({"track_id": 1, "t": t, "frame": np.arange(n), "x_meas": 10 + 200 * t,
                       "y_meas": np.full(n, 40.0), "length": length, "theta": 0.0,
                       "flags": flags})
    out = add_point_velocities(df, cfg, t_exp=0.02)
    usable = np.array([False, False, False, True, True, False, False, True, True])
    assert np.array_equal(out["speed_streak"].notna().to_numpy(), usable)
    assert np.allclose(out["speed_streak"][usable], length[usable] / 0.02)
    assert out["vx_streak"].notna().to_numpy().tolist() == usable.tolist()
    # Without a flags column only the length rule applies.
    out2 = add_point_velocities(df.drop(columns="flags"), cfg, t_exp=0.02)
    assert out2["speed_streak"].notna().sum() == usable.sum() + 1


def test_interior_needs_the_full_window():
    """Only full-size centred windows are interior: their noise and circular gains are known.

    A 3-point track fitted over all 3 points has a derivative noise gain sqrt(1/2) / dt,
    2.2 times the 5-point filter's, so marking its middle point interior fed noisier
    speeds to the exposure fit and the wrong gain to the circular correction.
    """
    t = np.arange(9) * DT
    x = 100 + 90 * t
    y = 50 - 30 * t
    for n in (2, 3, 4):
        _, _, interior = local_poly_velocity(t[:n], x[:n], y[:n], 5, 2)
        assert not interior.any()
    _, _, interior = local_poly_velocity(t[:5], x[:5], y[:5], 5, 2)
    assert interior.tolist() == [False, False, True, False, False]
    # Coasted points do not count toward the window: 5 measured of 6 records.
    xc, yc = x[:6].copy(), y[:6].copy()
    xc[2] = yc[2] = np.nan
    _, _, interior = local_poly_velocity(t[:6], xc, yc, 5, 2)
    assert interior.tolist() == [False, False, False, True, False, False]
    # An even window is made odd (4 -> 5) and still has interior points.
    _, _, interior = local_poly_velocity(t, x, y, 4, 2)
    assert interior.sum() == 5
