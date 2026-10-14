"""Exposure time from streak length versus track speed (Deming regression through the origin)."""
import numpy as np
import pytest

from wfglink.config import deep_merge, load_config
from wfglink.detect.candidates import FLAG_SATURATED
from wfglink.measure.exposure import (RollingExposure, deming_origin, estimate_exposure,
                                      speed_noise_sd)

FPS = 30.0


@pytest.fixture(scope="module")
def cfg():
    return load_config()


def synth_points(t_exp, seed, n_tracks=40, n_pts=12, sigma_l=1.0, outlier_frac=0.0,
                 t_offset=0.0, span_s=8.0):
    """Tracks with roughly constant speed; noisy L = T |v| and noisy measured speed."""
    rng = np.random.default_rng(seed)
    tid = np.repeat(np.arange(n_tracks), n_pts)
    base = np.repeat(rng.uniform(150, 1500, n_tracks), n_pts)
    true_v = base * rng.uniform(0.9, 1.1, base.size)
    t = (np.tile(np.arange(n_pts) / FPS, n_tracks)
         + np.repeat(rng.uniform(0, span_s, n_tracks), n_pts) + t_offset)
    sig_v = speed_noise_sd(1.0, FPS, 5, 2)
    speed = true_v + rng.normal(0, sig_v, true_v.size)
    length = t_exp * true_v + rng.normal(0, sigma_l, true_v.size)
    if outlier_frac:
        bad = rng.random(length.size) < outlier_frac
        # Wrong associations and merged blobs: lengths unrelated to the speed.
        length[bad] = rng.uniform(3, 60, bad.sum())
    return tid, t, speed, length, np.zeros(length.size, np.int64)


def test_deming_origin_limits_and_exact():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    assert deming_origin(x, 0.5 * x, 1.0) == pytest.approx(0.5)
    rng = np.random.default_rng(0)
    xn = x + rng.normal(0, 0.1, 4)
    yn = 0.5 * x + rng.normal(0, 0.1, 4)
    assert deming_origin(xn, yn, np.inf) == pytest.approx(np.dot(xn, yn) / np.dot(xn, xn))
    assert deming_origin(xn, yn, 0.0) == pytest.approx(np.dot(yn, yn) / np.dot(xn, yn))
    big = deming_origin(xn, yn, 1e12)
    assert big == pytest.approx(np.dot(xn, yn) / np.dot(xn, xn), rel=1e-6)
    assert np.isnan(deming_origin(x, -x, 1.0))


@pytest.mark.parametrize("ratio", [0.25, 0.5, 1.0])
@pytest.mark.parametrize("outliers", [0.0, 0.1])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_recovers_exposure_within_two_percent(cfg, ratio, outliers, seed):
    t_exp = ratio / FPS
    pts = synth_points(t_exp, seed, outlier_frac=outliers)
    est = estimate_exposure(*pts, fps=FPS, cfg=cfg, seed=seed)
    assert est.ok
    assert est.t_exp == pytest.approx(t_exp, rel=0.02)
    assert est.duty == pytest.approx(ratio, rel=0.02)
    assert est.ci_low < est.t_exp < est.ci_high
    assert est.n_tracks >= cfg["velocity"]["exposure"]["min_tracks"]
    if outliers:
        assert est.n_outliers >= 0.05 * est.n_points


def test_interval_covers_truth_and_is_track_level(cfg):
    t_exp = 0.5 / FPS
    hits = 0
    for seed in range(20):
        est = estimate_exposure(*synth_points(t_exp, 100 + seed), fps=FPS, cfg=cfg, seed=seed)
        hits += est.ci_low <= t_exp <= est.ci_high
    assert hits >= 16
    # Same points, but every point given its own track id: the bootstrap is then over
    # points and the interval narrows, which is the correlation the track bootstrap keeps.
    tid, t, s, length, fl = synth_points(t_exp, 5)
    a = estimate_exposure(tid, t, s, length, fl, fps=FPS, cfg=cfg)
    b = estimate_exposure(np.arange(tid.size), t, s, length, fl, fps=FPS, cfg=cfg)
    assert (b.ci_high - b.ci_low) < (a.ci_high - a.ci_low)


def test_needs_enough_tracks_and_filters_points(cfg):
    t_exp = 0.5 / FPS
    tid, t, s, length, fl = synth_points(t_exp, 3, n_tracks=10)
    est = estimate_exposure(tid, t, s, length, fl, fps=FPS, cfg=cfg)
    assert not est.ok and np.isnan(est.t_exp) and est.reason == "too few tracks"
    empty = estimate_exposure(np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0),
                              fps=FPS, cfg=cfg)
    assert not empty.ok
    # Saturated points are skipped even when their lengths are wrong.
    tid, t, s, length, fl = synth_points(t_exp, 4)
    sat = np.random.default_rng(4).random(length.size) < 0.3
    length[sat] *= 0.5                            # clipped streaks look shorter
    fl[sat] = FLAG_SATURATED
    est = estimate_exposure(tid, t, s, length, fl, fps=FPS, cfg=cfg)
    assert est.t_exp == pytest.approx(t_exp, rel=0.02)
    # Slow points (displacement under min_disp_px per frame) are skipped.
    slow = estimate_exposure(tid, t, s * 0 + 60.0, length, fl, fps=FPS, cfg=cfg)
    assert not slow.ok
    # The track count threshold comes from the config.
    c2 = deep_merge(cfg, {"velocity": {"exposure": {"min_tracks": 5}}})
    tid, t, s, length, fl = synth_points(t_exp, 3, n_tracks=10)
    assert estimate_exposure(tid, t, s, length, fl, fps=FPS, cfg=c2).ok


def test_rolling_window_follows_an_exposure_step(cfg):
    t1, t2 = 0.25 / FPS, 1.0 / FPS
    a = synth_points(t1, 6, t_offset=0.0, span_s=9.0)
    b = synth_points(t2, 7, t_offset=12.0, span_s=8.0)
    cat = [np.concatenate((u, v)) for u, v in zip(a, b)]
    cat[0] = np.concatenate((a[0], b[0] + 1000))
    early = estimate_exposure(*cat, fps=FPS, cfg=cfg, t_now=9.5)
    late = estimate_exposure(*cat, fps=FPS, cfg=cfg, t_now=20.5)
    assert early.t_exp == pytest.approx(t1, rel=0.02)
    assert late.t_exp == pytest.approx(t2, rel=0.02)
    assert late.t_start == pytest.approx(10.5)


def test_rolling_estimator_from_track_arrays(cfg):
    rng = np.random.default_rng(9)
    t_exp = 0.5 / FPS
    roll = RollingExposure(cfg, FPS)
    for k in range(30):
        n = 10
        t = 0.2 * k + np.arange(n) / FPS
        v = rng.uniform(300, 1200) * np.array([np.cos(k), np.sin(k)])
        x = 50 + v[0] * (t - t[0]) + rng.normal(0, 0.5, n)
        y = 60 + v[1] * (t - t[0]) + rng.normal(0, 0.5, n)
        arrs = {"t": t, "x_meas": x, "y_meas": y,
                "length": t_exp * np.hypot(*v) + rng.normal(0, 0.5, n),
                "flags": np.zeros(n, np.uint8)}
        if k == 0:
            arrs["x_meas"][4] = arrs["y_meas"][4] = np.nan     # a coasted point is skipped
        roll.add_track(k, arrs)
    est = roll.estimate(t_now=6.5)
    assert est.ok and est.t_exp == pytest.approx(t_exp, rel=0.03)
    # Far later, every track has left the window.
    assert not roll.estimate(t_now=100.0).ok


def test_end_to_end_from_tracker_output(cfg):
    """Streak detections -> tracker -> per-point speeds -> T_exp."""
    from wfglink.detect.candidates import Detections
    from wfglink.track.tracker import Tracker

    rng = np.random.default_rng(12)
    duty = 0.5
    t_exp = duty / FPS
    n, n_frames = 60, 240
    start = rng.integers(0, n_frames - 30, n)
    life = rng.integers(15, 30, n)
    speed = rng.uniform(200, 440, n)               # up to 14.7 px per frame
    ang = rng.uniform(0, 2 * np.pi, n)
    p0 = rng.uniform([100, 100], [1180, 620], (n, 2))
    tracker = Tracker(cfg, fps=FPS)
    roll = RollingExposure(cfg, FPS)
    for f in range(n_frames):
        alive = np.flatnonzero((f >= start) & (f < start + life))
        tt = (f - start[alive]) / FPS
        vel = speed[alive, None] * np.column_stack((np.cos(ang[alive]), np.sin(ang[alive])))
        xy = p0[alive] + vel * tt[:, None] + rng.normal(0, 0.4, (alive.size, 2))
        m = alive.size
        z = np.zeros(m)
        det = Detections(x=xy[:, 0], y=xy[:, 1], area=z + 4, peak=z + 60, flux=z + 200,
                         lam1=z, lam2=z, theta=np.mod(ang[alive], np.pi),
                         length=t_exp * speed[alive] + rng.normal(0, 0.5, m), width=z + 2,
                         sat_frac=z, color=z, flags=np.zeros(m, np.uint8))
        tracker.update(det, f / FPS, f)
        for tr in tracker.pop_finished():
            roll.add_track(tr.track_id, tr.arrays())
    for tr in tracker.finish_all():
        roll.add_track(tr.track_id, tr.arrays())
    est = roll.estimate(t_now=n_frames / FPS)
    assert est.ok and est.n_tracks >= 40
    assert est.t_exp == pytest.approx(t_exp, rel=0.03)
    assert est.ci_low < t_exp < est.ci_high
    assert est.duty == pytest.approx(duty, rel=0.03)


def test_not_fooled_by_point_like_false_tracks(cfg):
    """False tracks from clutter: fast random speeds with L near 0, as many as real tracks."""
    t_exp = 0.5 / FPS
    tid, t, s, length, fl = synth_points(t_exp, 21)
    rng = np.random.default_rng(22)
    k = tid.size
    tid = np.concatenate((tid, 1000 + rng.integers(0, 60, k)))
    t = np.concatenate((t, rng.uniform(0, 8, k)))
    s = np.concatenate((s, rng.uniform(200, 3000, k)))
    length = np.concatenate((length, np.abs(rng.normal(0, 0.8, k))))
    fl = np.concatenate((fl, np.zeros(k, np.int64)))
    est = estimate_exposure(tid, t, s, length, fl, fps=FPS, cfg=cfg)
    assert est.ok and est.t_exp == pytest.approx(t_exp, rel=0.02)
