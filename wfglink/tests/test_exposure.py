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


def biased_points(t_exp, seed, measured, n_tracks=60, n_pts=12, v_range=(150.0, 1500.0),
                  sigma_l=0.8):
    """Like synth_points, but the measured length is a function of the true streak length
    T |v| that is not proportional to it (a length floor, lost faint ends, ...)."""
    rng = np.random.default_rng(seed)
    tid = np.repeat(np.arange(n_tracks), n_pts)
    true_v = np.repeat(rng.uniform(*v_range, n_tracks), n_pts) * rng.uniform(0.95, 1.05, tid.size)
    t = np.tile(np.arange(n_pts) / FPS, n_tracks) + np.repeat(rng.uniform(0, 8, n_tracks), n_pts)
    speed = true_v + rng.normal(0, speed_noise_sd(1.0, FPS, 5, 2), true_v.size)
    length = measured(t_exp * true_v) + rng.normal(0, sigma_l, true_v.size)
    return tid, t, speed, length, np.zeros(length.size, np.int64)


# Measured length against true length: a floor (round spots look elongated), lost ends of
# long faint streaks, and both together (the shape seen on the synthetic core suite).
LENGTH_MODELS = {
    "floor": lambda ell: np.sqrt(ell ** 2 + 3.0 ** 2),
    "lost_ends": lambda ell: ell * (1.0 - 0.025 * ell),
    "compressed": lambda ell: 2.0 + 0.45 * ell,
}


@pytest.mark.parametrize("model", sorted(LENGTH_MODELS))
@pytest.mark.parametrize("ratio", [0.25, 0.5, 1.0])
@pytest.mark.parametrize("seed", [0, 1])
def test_biased_lengths_are_declined_or_within_ten_percent(cfg, model, ratio, seed):
    """The contract: when L is not proportional to |v|, decline or stay within 10 percent."""
    t_exp = ratio / FPS
    pts = biased_points(t_exp, seed, LENGTH_MODELS[model])
    est = estimate_exposure(*pts, fps=FPS, cfg=cfg, seed=seed)
    assert (not est.ok) or abs(est.t_exp / t_exp - 1) <= 0.10, (est.t_exp * FPS, est.details)
    if not est.ok:
        assert est.reason and np.isnan(est.t_exp)


def test_compressed_lengths_are_declined_with_the_reason(cfg):
    # Lengths that grow much more slowly than speed, as measured on the core suite: a fit
    # through the origin answers whatever the speeds in the clip make it answer.
    t_exp = 0.5 / FPS
    pts = biased_points(t_exp, 3, LENGTH_MODELS["compressed"], v_range=(150.0, 700.0))
    est = estimate_exposure(*pts, fps=FPS, cfg=cfg)
    assert not est.ok and "proportional" in est.reason
    d = est.details
    # The diagnostics of the failed check are kept for the log.
    assert d["t_exp_unchecked"] > 0 and "speed_cut_px_s" in d
    assert d["t_exp_free_intercept"] == pytest.approx(0.45 * t_exp, rel=0.1)   # the slope of 2 + 0.45 T |v|


def test_short_streak_reason_says_why_the_cut_scan_stopped(cfg):
    """Streaks too short at every cut: the reason says whether the cuts ran out of tracks
    or the list of cuts ran out (then higher cuts would still have tracks)."""
    t_exp = 0.25 / FPS
    many = estimate_exposure(*biased_points(t_exp, 2, lambda ell: ell, n_tracks=300, v_range=(150.0, 400.0)),
                             fps=FPS, cfg=cfg)
    assert not many.ok and "under 4 px at every speed cut (speed quantiles up to 0.8)" in many.reason
    assert len(many.details["cut_scan"]) == len(cfg["velocity"]["exposure"]["cut_quantiles"])
    few = estimate_exposure(*biased_points(t_exp, 2, lambda ell: ell, n_tracks=40, v_range=(150.0, 400.0)),
                            fps=FPS, cfg=cfg)
    assert not few.ok and "under 4 px at every speed cut with enough tracks" in few.reason


def test_a_constant_fraction_length_bias_is_not_detectable(cfg):
    """The limit of the checks: lengths that are all short by the same fraction still
    scale with speed, so nothing in L and |v| reveals the bias (documented in METHODS)."""
    t_exp = 0.5 / FPS
    est = estimate_exposure(*biased_points(t_exp, 5, lambda ell: 0.85 * ell), fps=FPS, cfg=cfg)
    assert est.ok and est.t_exp == pytest.approx(0.85 * t_exp, rel=0.02)


def test_narrow_speed_range_is_declined(cfg):
    """Floor and lost ends cannot be told from T_exp when every ember moves alike."""
    t_exp = 0.5 / FPS
    pts = biased_points(t_exp, 4, lambda ell: ell, v_range=(500.0, 560.0))
    est = estimate_exposure(*pts, fps=FPS, cfg=cfg)
    assert not est.ok and "too narrow" in est.reason
    # A wide range with the same (proportional) lengths is estimated.
    pts = biased_points(t_exp, 4, lambda ell: ell)
    est = estimate_exposure(*pts, fps=FPS, cfg=cfg)
    assert est.ok and est.t_exp == pytest.approx(t_exp, rel=0.02)


def test_proportionality_must_be_confirmed_not_just_unrefuted(cfg):
    """Proportional but noisy lengths over a narrow speed range: the free-intercept slope
    agrees with T, but its interval is too wide to rule out a 10 percent bias."""
    t_exp = 1.0 / FPS
    pts = biased_points(t_exp, 0, lambda ell: ell, v_range=(300.0, 480.0), sigma_l=3.0, n_tracks=40)
    est = estimate_exposure(*pts, fps=FPS, cfg=cfg)
    d = est.details
    assert abs(d["offset_effect"]) <= cfg["velocity"]["exposure"]["prop_tol"]
    assert not est.ok and "confirm" in est.reason
    lo, hi = d["offset_effect_ci"]
    assert lo < -0.1 or hi > 0.1


def test_three_led_tracks_use_the_point_check_only(cfg):
    """An LED turntable gives three long tracks at three speeds: a bootstrap over three
    tracks cannot confirm anything, so only the point value of the check applies."""
    rng = np.random.default_rng(0)
    t_exp = 0.5 / FPS
    tid, t, speed, length = [], [], [], []
    for k, v in enumerate((190.0, 420.0, 700.0)):
        tid.append(np.full(140, k))
        t.append(np.arange(140) / FPS)
        speed.append(v + rng.normal(0, 9.5, 140))
        length.append(t_exp * v + rng.normal(0, 0.5, 140))
    pts = [np.concatenate(a) for a in (tid, t, speed, length)] + [np.zeros(420, np.int64)]
    led = deep_merge(cfg, {"velocity": {"exposure": {"min_tracks": 2, "window_s": 1e9}}})
    est = estimate_exposure(*pts, fps=FPS, cfg=led)
    assert est.ok and est.t_exp == pytest.approx(t_exp, rel=0.02)
    strict = deep_merge(led, {"velocity": {"exposure": {"min_tracks_interval": 2}}})
    assert not estimate_exposure(*pts, fps=FPS, cfg=strict).ok


def test_unique_answer_under_perturbed_cut_start_and_order(cfg):
    """One answer: no dependence on the order of the points, small changes of the
    minimum length or the starting value move a good estimate by far less than its
    tolerance, and a bad data set is declined every time (no flipping between answers)."""
    t_exp = 0.5 / FPS
    good = synth_points(t_exp, 31)
    bad = biased_points(t_exp, 31, LENGTH_MODELS["compressed"], v_range=(150.0, 700.0))
    perm = np.random.default_rng(0).permutation(good[0].size)
    ref = estimate_exposure(*good, fps=FPS, cfg=cfg)
    assert ref.ok
    shuffled = estimate_exposure(*(a[perm] for a in good), fps=FPS, cfg=cfg)
    assert shuffled.t_exp == pytest.approx(ref.t_exp, rel=1e-9)
    assert all(abs(s / ref.t_exp - 1) <= 0.01 for s in ref.details["t_exp_other_starts"])
    for min_len in (3.0, 3.5, 4.5, 5.0):
        c2 = deep_merge(cfg, {"velocity": {"exposure": {"min_length_px": min_len}}})
        est = estimate_exposure(*good, fps=FPS, cfg=c2)
        assert est.ok and est.t_exp == pytest.approx(ref.t_exp, rel=0.02)
        assert not estimate_exposure(*bad, fps=FPS, cfg=c2).ok


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
