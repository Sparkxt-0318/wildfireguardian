"""Kalman filter and multi-target tracker: filter algebra, association, lifecycle, timing."""
import time

import numpy as np
import pytest

from wfglink.config import load_config
from wfglink.detect.candidates import Detections
from wfglink.track import kalman as kf
from wfglink.track.tracker import (CONFIRMED, FINISHED, RECORD_FIELDS, Track, Tracker,
                                   TrackSnapshot, tracks_to_frame)

FPS = 30.0
DT = 1.0 / FPS


def make_det(xy, length=None, theta=None, flags=None):
    xy = np.asarray(xy, dtype=np.float64).reshape(-1, 2)
    m = xy.shape[0]
    z = np.zeros(m)
    return Detections(x=xy[:, 0].copy(), y=xy[:, 1].copy(), area=z + 3, peak=z + 50, flux=z + 100,
                      lam1=z, lam2=z, theta=z.copy() if theta is None else np.asarray(theta, float),
                      length=z.copy() if length is None else np.asarray(length, float),
                      width=z + 2, sat_frac=z, color=z + 20,
                      flags=np.zeros(m, np.uint8) if flags is None else np.asarray(flags, np.uint8))


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# Kalman filter ---------------------------------------------------------------------------
def test_predict_matches_generic_formula_and_composes():
    rng = np.random.default_rng(0)
    n = 6
    x = rng.normal(0, 50, (n, 4))
    a = rng.normal(0, 1, (n, 4, 4))
    p = a @ np.swapaxes(a, 1, 2) + np.eye(4)
    q = kf.process_psd(3.0, DT)
    xp, pp = kf.predict(x, p, DT, q)
    f = kf.transition(DT)
    assert np.allclose(xp, x @ f.T)
    assert np.allclose(pp, f @ p @ f.T + kf.process_noise(DT, q))
    # Continuous white-noise acceleration composes: two half steps equal one full step.
    x2, p2 = kf.predict(*kf.predict(x, p, 0.4 * DT, q), 0.6 * DT, q)
    assert np.allclose(x2, xp) and np.allclose(p2, pp)
    # Per-track time steps.
    dts = rng.uniform(0.01, 0.1, n)
    xv, pv = kf.predict(x, p, dts, q)
    for i in range(n):
        xi, pi = kf.predict(x[i:i + 1], p[i:i + 1], dts[i], q)
        assert np.allclose(xv[i], xi[0]) and np.allclose(pv[i], pi[0])


def test_process_psd_matches_per_frame_acceleration():
    a_px = 3.0
    q = kf.process_psd(a_px, DT)
    qn = kf.process_noise(DT, q)
    # Velocity variance per nominal frame equals (a_px / dt)^2, the discrete model's value.
    assert qn[2, 2] == pytest.approx((a_px / DT) ** 2)
    model = kf.ConstantVelocityModel({"track": {"accel_sigma_px": a_px}}, DT)
    assert model.accel_sigma_px_s2 == pytest.approx(a_px * FPS ** 2)


def test_update_matches_textbook_and_shrinks_covariance():
    rng = np.random.default_rng(1)
    n = 5
    x = rng.normal(0, 10, (n, 4))
    a = rng.normal(0, 1, (n, 4, 4))
    p = a @ np.swapaxes(a, 1, 2) + 2 * np.eye(4)
    z = x[:, :2] + rng.normal(0, 2, (n, 2))
    r = kf.measurement_cov(rng.uniform(0, 20, n), rng.uniform(0, np.pi, n), 1.0, 0.1)
    xu, pu = kf.update(x, p, z, r)
    h = np.hstack((np.eye(2), np.zeros((2, 2))))
    for i in range(n):
        s = h @ p[i] @ h.T + r[i]
        k = p[i] @ h.T @ np.linalg.inv(s)
        assert np.allclose(xu[i], x[i] + k @ (z[i] - h @ x[i]))
        assert np.allclose(pu[i], (np.eye(4) - k @ h) @ p[i])
        assert np.trace(pu[i]) < np.trace(p[i])
        assert np.all(np.linalg.eigvalsh(pu[i]) > 0)


def test_measurement_cov_is_elongated_along_streak():
    r = kf.measurement_cov(np.array([0.0, 20.0]), np.array([0.3, np.pi / 2]), 1.0, 0.1)
    assert np.allclose(r[0], np.eye(2))
    assert r[1, 1, 1] == pytest.approx(1.0 + 4.0)      # vertical streak, 0.1 * 20 = 2 px
    assert r[1, 0, 0] == pytest.approx(1.0)


def test_mahalanobis_dense_pairs_and_gate_agree():
    rng = np.random.default_rng(2)
    n, m = 30, 40
    x = np.zeros((n, 4))
    x[:, :2] = rng.uniform(0, 100, (n, 2))
    a = rng.normal(0, 1, (n, 4, 4))
    p = a @ np.swapaxes(a, 1, 2) + np.eye(4)
    z = rng.uniform(0, 100, (m, 2))
    r = kf.measurement_cov(rng.uniform(0, 10, m), rng.uniform(0, np.pi, m), 1.0, 0.1)
    d2 = kf.mahalanobis_sq(x, p, z, r)
    i, j = 3, 7
    s = p[i, :2, :2] + r[j]
    dz = z[j] - x[i, :2]
    assert d2[i, j] == pytest.approx(dz @ np.linalg.inv(s) @ dz)
    gate = 9.21
    rows, cols, dd = kf.gated_pairs(x, p, z, r, gate)
    want = set(zip(*np.nonzero(d2 <= gate)))
    assert set(zip(rows.tolist(), cols.tolist())) == want
    assert np.allclose(dd, d2[rows, cols])


def test_two_point_init_and_filter_convergence():
    q = kf.process_psd(0.5, DT)
    r1 = kf.measurement_cov(np.zeros(1), np.zeros(1), 1.0, 0.0)
    x0, p0 = kf.init_from_two(np.array([[0.0, 0.0]]), np.array([0.0]), r1,
                              np.array([[6.0, -3.0]]), np.array([DT]), r1, q)
    assert np.allclose(x0[0], [6.0, -3.0, 180.0, -90.0])
    assert np.all(np.linalg.eigvalsh(p0[0]) > 0)
    # Track a noisy constant-velocity target with variable time steps.
    rng = np.random.default_rng(3)
    v_true = np.array([180.0, -90.0])
    x, p, t = x0, p0, DT
    for _ in range(60):
        dt = DT * rng.uniform(0.6, 1.6)
        t += dt
        x, p = kf.predict(x, p, dt, q)
        z = (v_true * t)[None, :] + rng.normal(0, 1.0, (1, 2))
        x, p = kf.update(x, p, z, r1)
    assert np.allclose(x[0, 2:], v_true, atol=15.0)
    assert np.allclose(x[0, :2], v_true * t, atol=2.0)


# Tracker ---------------------------------------------------------------------------------
def run_scene(cfg, positions, times=None, frames=None, lengths=None, thetas=None, fps=FPS,
              tracker=None):
    """positions: list over frames of (k, 2) arrays (may be empty)."""
    tr = tracker or Tracker(cfg, fps=fps)
    snaps = []
    for i, xy in enumerate(positions):
        t = times[i] if times is not None else i / fps
        f = frames[i] if frames is not None else i
        L = lengths[i] if lengths is not None else None
        th = thetas[i] if thetas is not None else None
        snaps.append(tr.update(make_det(xy, L, th), t, f))
    return tr, snaps


def straight(x0, y0, vx, vy, n, fps=FPS, t0=0.0):
    t = t0 + np.arange(n) / fps
    return np.column_stack((x0 + vx * t, y0 + vy * t))


def test_single_track_confirms_records_and_finishes(cfg):
    path = straight(100, 100, 120, -60, 20)
    pos = [path[i:i + 1] for i in range(20)] + [np.zeros((0, 2))] * 6
    tr, snaps = run_scene(cfg, pos)
    # confirm_hits = 3: confirmed snapshots appear from the third frame on.
    assert snaps[0] == [] and snaps[1] == []
    assert len(snaps[2]) == 1 and isinstance(snaps[2][0], TrackSnapshot)
    # Coasting: still reported for max_coast frames without detections, flagged coasted.
    assert snaps[20][0].coasted and len(snaps[20 + cfg["track"]["max_coast"] - 1]) == 1
    assert snaps[20 + cfg["track"]["max_coast"]] == []
    fin = tr.pop_finished()
    assert len(fin) == 1 and tr.pop_finished() == []
    t = fin[0]
    assert t.status == FINISHED and not t.static
    a = t.arrays()
    assert set(a) == set(RECORD_FIELDS)
    assert len(t) == 20 and not a["coasted"].any()          # trailing coasted points trimmed
    assert np.allclose(a["x_meas"], path[:, 0]) and np.array_equal(a["frame"], np.arange(20))
    assert np.allclose(a["vx"][5:], 120.0, atol=1e-6) and np.allclose(a["vy"][5:], -60.0, atol=1e-6)
    assert np.all(a["det_index"] == 0) and np.all(a["color"] == 20)
    df = tracks_to_frame(fin)
    assert len(df) == 20 and set(df["track_id"]) == {t.track_id}


def test_confirmation_window(cfg):
    p = np.array([[50.0, 50.0]])
    e = np.zeros((0, 2))
    # Hits at frames 0, 2, 3 (one miss) confirm within the 4-frame window.
    tr, snaps = run_scene(cfg, [p, e, p + [4, 0], p + [6, 0], p + [8, 0]])
    assert len(snaps[3]) == 1 and len(snaps[4]) == 1
    # Hits at frames 0 and 3 only: the single-hit track is dropped, nothing confirms.
    tr, snaps = run_scene(cfg, [p, e, e, p + [6, 0], e, e, e])
    assert all(s == [] for s in snaps)
    assert tr.all_tracks() == [] and tr.n_deleted_tentative >= 1
    # Two hits then misses: never confirmed, dropped.
    tr, snaps = run_scene(cfg, [p, p + [2, 0], e, e, e, e])
    assert all(s == [] for s in snaps) and tr.finish_all() == []


def test_zero_detections_and_reset(cfg):
    tr = Tracker(cfg)
    for i in range(5):
        assert tr.update(make_det(np.zeros((0, 2))), i * DT, i) == []
    assert tr.all_tracks() == [] and tr.pop_finished() == []
    run_scene(cfg, [straight(10, 10, 90, 0, 8)[i:i + 1] for i in range(8)], tracker=tr,
              times=[(5 + i) * DT for i in range(8)], frames=list(range(5, 13)))
    assert len(tr.all_tracks()) == 1
    tr.reset()
    assert tr.all_tracks() == [] and tr.active_tracks(include_tentative=True) == []
    # After a reset the time base restarts, so earlier times are fine again.
    assert tr.update(make_det([[1.0, 1.0]]), 0.0, 0) == []


def test_time_must_increase(cfg):
    tr = Tracker(cfg)
    tr.update(make_det([[1.0, 1.0]]), 1.0, 0)
    with pytest.raises(ValueError):
        tr.update(make_det([[1.0, 1.0]]), 1.0, 1)


def test_crossing_particles_keep_identity(cfg):
    n = 30
    a = straight(100, 100, 200, 100, n)
    b = straight(100, 160, 200, -100, n)        # paths cross mid-way
    pos = [np.vstack((a[i], b[i])) for i in range(n)]
    sp = np.hypot(200, 100) * DT * 0.5
    lengths = [np.array([sp, sp])] * n
    thetas = [np.array([np.arctan2(100, 200), np.arctan2(-100, 200)])] * n
    tr, _ = run_scene(cfg, pos, lengths=lengths, thetas=thetas)
    tracks = tr.finish_all()
    assert len(tracks) == 2
    for t in tracks:
        arr = t.arrays()
        assert len(t) == n
        dy = np.diff(arr["y_meas"])
        assert np.all(dy > 0) or np.all(dy < 0)   # each track stays on one particle


def test_fast_streak_birth_and_exposure_hint(cfg):
    n = 12
    v = 1200.0                                   # 40 px per frame
    path = straight(50, 300, v, 0, n)
    # Duty 0.75: L = 30 px, birth reach max(15, 1.5 L) = 45 px covers the 40 px step.
    tr, snaps = run_scene(cfg, [path[i:i + 1] for i in range(n)],
                          lengths=[np.array([30.0])] * n, thetas=[np.array([0.0])] * n)
    assert len(snaps[-1]) == 1 and snaps[-1][0].vx == pytest.approx(v, rel=1e-3)
    # Duty 0.25: L = 10 px, reach 15 px is too short without a hint ...
    tr, snaps = run_scene(cfg, [path[i:i + 1] for i in range(n)],
                          lengths=[np.array([10.0])] * n, thetas=[np.array([0.0])] * n)
    assert snaps[-1] == []
    # ... and enough with the exposure hint (reach 1.5 L dt / T_exp = 60 px).
    tr = Tracker(cfg, fps=FPS)
    tr.set_exposure_hint(0.25 * DT)
    tr, snaps = run_scene(cfg, [path[i:i + 1] for i in range(n)], tracker=tr,
                          lengths=[np.array([10.0])] * n, thetas=[np.array([0.0])] * n)
    assert len(snaps[-1]) == 1


def test_streak_orientation_hint_picks_aligned_candidate(cfg):
    # A horizontal streak, then two candidates 12 px away: one along the axis, one across.
    first = make_det([[100.0, 100.0]], [8.0], [0.0])
    tr = Tracker(cfg, fps=FPS)
    tr.update(first, 0.0, 0)
    second = make_det([[100.0, 112.0], [112.0, 100.0]], [8.0, 8.0], [0.0, 0.0])
    tr.update(second, DT, 1)
    kin = tr.active_tracks(include_tentative=True)
    two = [t for t in kin if t.hits == 2]
    assert len(two) == 1
    a = two[0].arrays()
    assert a["x_meas"][1] == pytest.approx(112.0) and a["y_meas"][1] == pytest.approx(100.0)


def test_angle_penalty_breaks_ties_for_kinematic_tracks(cfg):
    # A track moving right at 300 px/s; next frame two detections at the same Mahalanobis
    # distance, one streak along the motion and one across it.
    c = dict(cfg)
    tr = Tracker(c, fps=FPS)
    path = straight(100, 100, 300, 0, 6)
    for i in range(5):
        tr.update(make_det(path[i:i + 1], [5.0 + 1], [0.0]), i * DT, i)
    pred = path[5]
    dets = make_det([pred + [0, 2.0], pred + [0, -2.0]], [8.0, 8.0], [np.pi / 2, 0.0])
    tr.update(dets, 5 * DT, 5)
    t = tr.active_tracks()[0]
    assert t.records[-1][15] == 1                  # the aligned streak was chosen


def test_variable_frame_rate_and_gaps(cfg):
    rng = np.random.default_rng(5)
    n = 40
    dts = DT * rng.uniform(0.7, 1.5, n)
    times = np.cumsum(dts)
    v = np.array([150.0, 80.0])
    pos = [(np.array([200.0, 200.0]) + v * t + rng.normal(0, 0.3, 2))[None, :] for t in times]
    tr, snaps = run_scene(cfg, pos, times=list(times), fps=None)
    assert tr.nominal_dt == pytest.approx(np.median(dts[1:16]), rel=1e-9)
    assert len(snaps[-1]) == 1 and len(tr.all_tracks()) == 1
    assert np.allclose([snaps[-1][0].vx, snaps[-1][0].vy], v, atol=15.0)
    # A frame-index gap longer than max_coast finishes the track; a new one starts after.
    t0 = times[-1]
    later = [(np.array([200.0, 200.0]) + v * (t0 + k * DT))[None, :] for k in range(20, 26)]
    frames = list(range(n)) + list(range(n + 19, n + 25))
    tr2 = Tracker(cfg, fps=FPS)
    run_scene(cfg, pos + later, times=list(times) + [t0 + k * DT for k in range(20, 26)],
              frames=frames, tracker=tr2)
    ids = [t.track_id for t in tr2.all_tracks()]
    assert len(ids) == 2
    first = [t for t in tr2.all_tracks() if t.status == FINISHED]
    assert len(first) == 1 and first[0].arrays()["frame"].max() == n - 1
    # A pure time gap (consecutive indices) is treated the same way.
    tr3 = Tracker(cfg, fps=FPS)
    run_scene(cfg, pos + later, times=list(times) + [t0 + k * DT for k in range(20, 26)],
              tracker=tr3)
    assert len(tr3.all_tracks()) == 2


def test_static_light_is_flagged(cfg):
    rng = np.random.default_rng(6)
    n = int(1.6 * FPS)
    still = np.array([300.0, 200.0])
    mover = straight(50, 50, 60, 0, n)
    pos = [np.vstack((still + rng.normal(0, 1.0, 2), mover[i] + rng.normal(0, 0.3, 2)))
           for i in range(n)]
    tr, snaps = run_scene(cfg, pos)
    by_static = {s.static: s for s in snaps[-1]}
    assert set(by_static) == {True, False}
    assert abs(by_static[True].x - 300) < 3
    # Not flagged before it has existed for static_seconds.
    early = snaps[int(0.8 * FPS)]
    assert len(early) == 2 and not any(s.static for s in early)


def test_hundreds_of_detections_per_frame(cfg):
    rng = np.random.default_rng(7)
    tr = Tracker(cfg, fps=FPS)
    true = straight(20, 20, 100, 50, 15)
    for i in range(15):
        noise = rng.uniform(0, [1280, 720], (400, 2))
        tr.update(make_det(np.vstack((true[i], noise))), i * DT, i)
    tracks = tr.finish_all()
    real = [t for t in tracks if np.allclose(t.arrays()["x_meas"][:3], true[:3, 0], atol=1e-6)]
    assert len(real) == 1 and len(real[0]) == 15


def test_all_tracks_and_history_off(cfg):
    pos = [np.vstack((straight(10, 10, 90, 0, 10)[i], straight(10, 300, 90, 0, 10)[i]))
           for i in range(10)]
    tr, _ = run_scene(cfg, pos)
    assert len(tr.all_tracks()) == 2 and len(tr.all_tracks(include_active=False)) == 0
    assert all(t.status == CONFIRMED for t in tr.active_tracks())
    tr2 = Tracker(cfg, fps=FPS, keep_history=False)
    run_scene(cfg, pos + [np.zeros((0, 2))] * 5, tracker=tr2)
    assert len(tr2.pop_finished()) == 2 and tr2.all_tracks() == []
    assert len(Track(1, 0, 0.0).arrays()["t"]) == 0


def test_performance_100_tracks_100_detections(cfg):
    rng = np.random.default_rng(8)
    n, w, h = 100, 1280, 720
    pos0 = rng.uniform([50, 50], [w - 50, h - 50], (n, 2))
    vel = rng.uniform(-150, 150, (n, 2))
    sp = np.hypot(vel[:, 0], vel[:, 1])
    th = np.arctan2(vel[:, 1], vel[:, 0])
    tr = Tracker(cfg, fps=FPS)
    times = []
    for f in range(150):
        xy = pos0 + vel * f * DT
        xy[:, 0] %= w
        xy[:, 1] %= h
        d = make_det(xy + rng.normal(0, 0.5, xy.shape), sp * DT * 0.5, th)
        t0 = time.perf_counter()
        snaps = tr.update(d, f * DT, f)
        times.append(time.perf_counter() - t0)
    ms = np.array(times[20:]) * 1e3
    assert len(snaps) >= 95
    print(f"tracker per frame: median {np.median(ms):.2f} ms, p95 {np.percentile(ms, 95):.2f} ms")
    # Target is 3 ms; the assertion leaves room for a busy shared machine.
    assert np.median(ms) < 6.0


def test_confirmed_tracks_choose_before_tentative_ones(cfg):
    tr = Tracker(cfg, fps=FPS)
    path = straight(100, 100, 300, 0, 10)            # 10 px per frame
    k = 8
    d = path[k] + [0.0, 1.5]                          # the detection at frame k, a bit off
    for i in range(k):
        xy = [path[i]]
        if i >= k - 2:
            xy.append(d)                              # a still blob exactly where d will be
        tr.update(make_det(xy), i * DT, i)
    a = [t for t in tr.active_tracks() if t.status == CONFIRMED]
    assert len(a) == 1
    tent = [t for t in tr.active_tracks(include_tentative=True) if t.hits == 2]
    assert len(tent) == 1
    tr.update(make_det([d]), k * DT, k)
    # Without the cascade the still tentative track (distance 0) would win the detection.
    assert a[0].records[-1][14] is False and a[0].records[-1][15] == 0
    assert tent[0].records[-1][14] is True


def test_static_since_marks_the_slow_window(cfg):
    n_move, n_rest = 15, int(1.5 * FPS)
    move = straight(100, 100, 150, 0, n_move)
    rest = np.repeat(move[-1:] + [5.0, 0.0], n_rest, axis=0)
    pos = [p[None, :] for p in np.vstack((move, rest))]
    tr, snaps = run_scene(cfg, pos)
    t = tr.active_tracks()[0]
    assert t.static
    # The slow window ends at the flagging time and lasts static_seconds.
    t_flag = next(s.t for s in (snap[0] for snap in snaps if snap) if s.static)
    assert t.static_since == pytest.approx(t_flag - cfg["track"]["static_seconds"])
    assert t.static_since > (n_move - 1) * DT - 0.5 * cfg["track"]["static_seconds"]


def test_track_ids_stay_unique_across_reset(cfg):
    """After a reset (booth clip loop) new tracks get new ids, so a gate counter or a
    rolling exposure estimate keyed by track id that keeps running is not corrupted.
    Reused ids made a still-running gate counter count a spurious -1 crossing."""
    from wfglink.measure.gate import Gate, GateCounter

    gate = Gate((100.0, 200.0), (300.0, 200.0), 2.0, "g")
    counter = GateCounter(gate, cfg)
    tr = Tracker(cfg, fps=FPS)
    ids = []
    for _loop in range(2):
        for f in range(20):
            tr.update(make_det([[200.0, 150.0 + 7.0 * f]]), f * DT, f)
            counter.update_tracks(tr.active_tracks())
            counter.update_tracks(tr.pop_finished())
        counter.update_tracks(tr.finish_all())
        ids.extend(t.track_id for t in tr.all_tracks())
        tr.reset()
    assert len(ids) == 2 and ids[0] != ids[1]
    assert counter.counts() == {"gross": 2, "net": 2, "positive": 2, "negative": 0}
