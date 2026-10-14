"""Matching and validation metrics on small hand-built truth tables (shared schema)."""
import json

import numpy as np
import pandas as pd
import pytest

from wfglink.config import load_config
from wfglink.validate.match import match_points, match_radius
from wfglink.validate.metrics import (DetectionAccumulator, bridged_crossings, clopper_pearson,
                                      count_metrics, coverage, detectable_mask,
                                      detection_metrics, dont_care_mask, gate_metrics, load_truth,
                                      tracking_metrics, true_gate_counts, velocity_metrics)

DT = 1.0 / 30.0


def truth_row(frame, pid, x, y, kind="ember", u=0.0, v=0.0, visible=True, large=False, L=0.0):
    return {"frame": frame, "t_mid": frame * DT, "particle_id": pid, "kind": kind,
            "x_mid": x, "y_mid": y, "x_start": x - u * DT / 4, "y_start": y - v * DT / 4,
            "x_end": x + u * DT / 4, "y_end": y + v * DT / 4, "u": u, "v": v, "ua": u, "va": v,
            "flux": 500.0, "sigma_px": 1.0, "visible": visible, "in_large_region": large,
            "streak_length_px": L}


def truth_df(rows):
    df = pd.DataFrame(rows)
    return df.astype({"frame": "int64", "particle_id": "int64", "visible": bool,
                      "in_large_region": bool})


@pytest.fixture(scope="module")
def cfg():
    return load_config()


# Matching --------------------------------------------------------------------------------
def test_match_radius():
    r = match_radius(np.array([0.0, 4.0, 20.0, np.nan]))
    assert np.allclose(r, [3.0, 3.0, 10.0, 3.0])
    assert np.allclose(match_radius(np.array([10.0]), base_px=2.0, streak_frac=0.1), [2.0])
    c = {"validate": {"match_radius_px": 4.0, "streak_radius_frac": 1.0}}
    assert np.allclose(match_radius(np.array([0.0, 6.0]), c), [4.0, 6.0])


def test_match_points_hungarian_beats_greedy_and_gates():
    gt = np.array([[0.0, 0.0], [2.5, 0.0]])
    det = np.array([[1.5, 0.0], [4.5, 0.0]])
    gi, di, d = match_points(gt, det, 3.0)
    # Greedy nearest would take (gt1, det0) at 1.0 and leave gt0 unmatched.
    assert list(zip(gi, di)) == [(0, 0), (1, 1)] and np.allclose(d, [1.5, 2.0])
    # Per-truth radius: a long streak accepts a centroid 8 px away, a point does not.
    gi, di, d = match_points(np.array([[0.0, 0.0], [50.0, 0.0]]),
                             np.array([[8.0, 0.0], [58.0, 0.0]]), np.array([10.0, 3.0]))
    assert list(gi) == [0] and list(di) == [0]
    for a, b in ((np.zeros((0, 2)), det), (gt, np.zeros((0, 2)))):
        gi, di, d = match_points(a, b, 3.0)
        assert gi.size == di.size == d.size == 0
    gi, _, _ = match_points(gt, det + 100, 3.0)
    assert gi.size == 0


def test_match_points_large_random_is_one_to_one():
    rng = np.random.default_rng(0)
    gt = rng.uniform(0, 100, (200, 2))
    det = gt[rng.permutation(200)[:150]] + rng.normal(0, 0.8, (150, 2))
    gi, di, d = match_points(gt, det, 3.0)
    assert len(set(gi)) == gi.size and len(set(di)) == di.size
    assert np.all(d <= 3.0) and gi.size >= 140


# Detection -------------------------------------------------------------------------------
def build_detection_case():
    rows = [
        truth_row(0, 1, 10.0, 10.0), truth_row(0, 2, 50.0, 50.0, L=20.0),
        truth_row(0, 3, 90.0, 90.0, kind="spark"),
        truth_row(0, 4, 130.0, 10.0, visible=False),          # too faint: don't care
        truth_row(1, 1, 12.0, 10.0), truth_row(1, 5, 70.0, 70.0, large=True),  # in a flame
        truth_row(2, 1, 14.0, 10.0),
    ]
    truth = truth_df(rows)
    det = pd.DataFrame({
        "frame": [0, 0, 0, 0, 0, 1, 1, 2],
        "x": [11.0, 58.0, 90.5, 130.2, 300.0, 70.0, 12.0, 30.0],
        "y": [10.0, 50.0, 90.0, 10.0, 300.0, 70.5, 11.0, 10.0]})
    return truth, det


def test_detectable_and_dont_care_masks():
    truth, _ = build_detection_case()
    assert list(truth.loc[detectable_mask(truth), "particle_id"]) == [1, 2, 1, 1]
    assert list(truth.loc[dont_care_mask(truth), "particle_id"]) == [4, 5]


def test_detection_metrics(cfg):
    truth, det = build_detection_case()
    m = detection_metrics(truth, det, cfg)
    # Frame 0: TP pid 1 (1 px) and pid 2 (8 px, streak radius 10); spark and the far one
    # are FP; the faint ember is ignored. Frame 1: TP pid 1 (1 px), flame ember ignored.
    # Frame 2: pid 1 missed (16 px away) and that detection is FP.
    assert (m["tp"], m["fp"], m["fn"], m["ignored"]) == (3, 3, 1, 2)
    assert m["precision"] == pytest.approx(0.5) and m["recall"] == pytest.approx(0.75)
    assert m["f1"] == pytest.approx(2 * 0.5 * 0.75 / 1.25)
    assert m["loc_rmse_px"] == pytest.approx(np.sqrt((1 + 64 + 1) / 3))
    assert m["n_frames"] == 3
    strict = detection_metrics(truth, det, cfg, ignore_dont_care=False)
    assert strict["fp"] == 5 and strict["ignored"] == 0
    # Frames with truth but no detections count their misses.
    none = detection_metrics(truth, det.iloc[:0], cfg)
    assert (none["tp"], none["fn"], none["fp"]) == (0, 4, 0) and np.isnan(none["precision"])


def test_detection_accumulator_direct():
    acc = DetectionAccumulator()
    acc.add(np.array([[0.0, 0.0]]), np.array([3.0]), np.array([[0.0, 1.0], [9.0, 9.0]]))
    acc.add(np.zeros((0, 2)), np.zeros(0), np.zeros((0, 2)))
    s = acc.summary()
    assert (s["tp"], s["fp"], s["fn"], s["n_frames"]) == (1, 1, 0, 2)
    assert s["loc_rmse_px"] == pytest.approx(1.0)


# Tracking --------------------------------------------------------------------------------
def test_clear_mot_id_switch_fp_and_mota(cfg):
    rows, hyp = [], []
    for f in range(6):
        rows.append(truth_row(f, 1, 10.0 + 2 * f, 20.0))
        rows.append(truth_row(f, 2, 100.0 + 2 * f, 80.0))
        hyp.append((f, 11, 10.0 + 2 * f + 0.5, 20.0))           # follows object 1 throughout
        hyp.append((f, 12 if f < 3 else 13, 100.0 + 2 * f, 80.5))  # object 2: id changes once
    hyp.append((4, 99, 400.0, 400.0))                             # a false track point
    truth = truth_df(rows)
    tp = pd.DataFrame(hyp, columns=["frame", "track_id", "x", "y"])
    m = tracking_metrics(truth, tp, cfg)
    assert (m["gt"], m["matches"], m["fp"], m["fn"], m["id_switches"]) == (12, 12, 1, 0, 1)
    assert m["mota"] == pytest.approx(1 - 2 / 12)
    assert m["motp_px"] == pytest.approx(0.5)
    assert m["mostly_tracked"] == 2 and m["mostly_lost"] == 0
    assert m["n_hypotheses"] == 4 and m["n_truth_objects"] == 2


def test_clear_mot_correspondence_persistence(cfg):
    rows, hyp = [], []
    for f in range(4):
        rows.append(truth_row(f, 1, 50.0, 50.0))
        hyp.append((f, 1, 52.0, 50.0))                 # 2 px away, within the 3 px radius
    hyp.append((2, 2, 50.1, 50.0))                     # a closer newcomer in frame 2
    truth = truth_df(rows)
    m = tracking_metrics(truth, pd.DataFrame(hyp, columns=["frame", "track_id", "x", "y"]), cfg)
    # The existing correspondence persists: no ID switch, the newcomer is a false positive.
    assert m["id_switches"] == 0 and m["fp"] == 1 and m["matches"] == 4
    # Losing the object for a frame and then reacquiring it with another id is a switch.
    hyp2 = [(0, 1, 50.0, 50.0), (1, 1, 50.0, 50.0), (3, 2, 50.0, 50.0)]
    m2 = tracking_metrics(truth, pd.DataFrame(hyp2, columns=["frame", "track_id", "x", "y"]), cfg)
    assert m2["id_switches"] == 1 and m2["fn"] == 1


def test_clear_mot_persistence_survives_a_dropout(cfg):
    """py-motmetrics rule: an object keeps the hypothesis it was last matched to, also
    after frames where it was not detectable (flicker), as long as that hypothesis is
    within its radius and was not matched to another object meanwhile."""
    rows, hyp = [], []
    for f in range(5):
        rows.append(truth_row(f, 1, 50.0 + 3 * f, 50.0, visible=f != 2))   # dropout in frame 2
        hyp.append((f, 1, 52.0 + 3 * f, 50.0))         # the track coasts through, 2 px off
    hyp.append((3, 2, 59.1, 50.0))                     # a newcomer 0.1 px from the object
    hyp.append((4, 2, 62.1, 50.0))
    m = tracking_metrics(truth_df(rows), pd.DataFrame(hyp, columns=["frame", "track_id", "x", "y"]), cfg)
    # Previous-frame persistence alone would hand the object to the closer newcomer in
    # frame 3 and count a switch.
    assert m["id_switches"] == 0 and m["matches"] == 4 and m["fp"] == 2 and m["ignored"] == 1
    # A hypothesis that moved on to another object (7: object 1, then object 2) is not
    # reclaimed by object 1's older correspondence: object 2 keeps it (0.1 px) and
    # object 1 takes 8, one switch. Reclaiming it would pair 1-7 (0.9 px) and 2-8 (1 px).
    rows2 = [truth_row(0, 1, 10.0, 10.0), truth_row(1, 2, 10.0, 10.0), truth_row(2, 1, 10.0, 10.0),
             truth_row(2, 2, 11.0, 10.0)]
    hyp2 = [(0, 7, 10.0, 10.0), (1, 7, 10.0, 10.0), (2, 7, 10.9, 10.0), (2, 8, 10.0, 10.0)]
    m2 = tracking_metrics(truth_df(rows2), pd.DataFrame(hyp2, columns=["frame", "track_id", "x", "y"]), cfg)
    assert m2["id_switches"] == 1 and m2["fn"] == 0 and m2["fp"] == 0
    assert m2["motp_px"] == pytest.approx(0.1 / 4)


def test_clear_mot_dont_care_and_coasted_nan(cfg):
    rows = [truth_row(0, 1, 10.0, 10.0), truth_row(0, 2, 60.0, 60.0, visible=False)]
    hyp = pd.DataFrame([(0, 1, 10.0, 10.0), (0, 2, 60.5, 60.0), (0, 3, np.nan, np.nan)],
                       columns=["frame", "track_id", "x", "y"])
    m = tracking_metrics(truth_df(rows), hyp, cfg)
    assert m["fp"] == 0 and m["ignored"] == 1 and m["mota"] == pytest.approx(1.0)


# Velocity --------------------------------------------------------------------------------
def test_velocity_metrics(cfg):
    rows = [truth_row(0, 1, 10.0, 10.0, u=100.0, v=0.0),
            truth_row(0, 2, 50.0, 50.0, u=0.0, v=-200.0),
            truth_row(1, 1, 13.0, 10.0, u=100.0, v=0.0),
            truth_row(1, 3, 90.0, 90.0, u=0.5, v=0.0),           # too slow for relative errors
            truth_row(1, 4, 150.0, 150.0, u=300.0, v=0.0, kind="spark")]
    truth = truth_df(rows)
    ang = np.radians(10.0)
    est = pd.DataFrame({
        "frame": [0, 0, 1, 1, 1, 1],
        "x": [10.2, 50.0, 13.0, 90.0, 150.0, 500.0],
        "y": [10.0, 50.3, 10.0, 90.0, 150.0, 500.0],
        "vx_poly": [110.0, 0.0, 100 * np.cos(ang), 0.5, 300.0, 1.0],
        "vy_poly": [0.0, -190.0, 100 * np.sin(ang), 0.0, 0.0, 1.0],
    })
    m = velocity_metrics(truth, est, cfg)
    # Matched to embers: (10%), (-5%), (0%, 10 degrees), the slow one only in RMSE.
    assert m["n"] == 4 and m["n_rel"] == 3
    assert m["median_rel_speed_err"] == pytest.approx(0.05, abs=1e-9)
    assert m["p90_rel_speed_err"] == pytest.approx(np.percentile([0.1, 0.05, 0.0], 90))
    assert m["median_signed_rel_speed_err"] == pytest.approx(0.0, abs=1e-9)
    assert m["median_angle_err_deg"] == pytest.approx(0.0, abs=1e-9)
    du = np.array([10.0, 0.0, 100 * np.cos(ang) - 100, 0.0])
    dv = np.array([0.0, 10.0, 100 * np.sin(ang), 0.0])
    assert m["rmse_u"] == pytest.approx(np.sqrt(np.mean(du ** 2)))
    assert m["rmse_v"] == pytest.approx(np.sqrt(np.mean(dv ** 2)))
    # Speed-only estimates (streak speed): direction errors are not available.
    est2 = est.assign(speed_streak=[95.0, 200.0, 100.0, np.nan, 1.0, 1.0])
    m2 = velocity_metrics(truth, est2, cfg, vx_col=None, vy_col=None, speed_col="speed_streak")
    assert m2["n"] == 3 and m2["median_rel_speed_err"] == pytest.approx(0.0)
    assert np.isnan(m2["median_angle_err_deg"]) and np.isnan(m2["rmse_u"])
    empty = velocity_metrics(truth, est.iloc[:0], cfg)
    assert empty["n"] == 0 and np.isnan(empty["median_rel_speed_err"])


# Counts ----------------------------------------------------------------------------------
def test_true_gate_counts_and_count_metrics():
    gate = pd.DataFrame({
        "gate": ["g1", "g1", "g1", "g1", "g2", "g1"],
        "particle_id": np.array([1, 2, 3, 4, 1, 5], np.int64),
        "t": [0.5, 1.0, 1.5, 2.0, 0.7, 3.0],
        "frame_before": np.array([14, 29, 44, 59, 20, 89], np.int64),
        "frame_after": np.array([15, 30, 45, 60, 21, 90], np.int64),
        "direction": np.array([1, 1, -1, 1, 1, 1], np.int8),
        "visible_both": [True, True, True, False, True, True]})
    particles = truth_df([truth_row(0, p, 0.0, 0.0, kind="spark" if p == 5 else "ember")
                          for p in (1, 2, 3, 4, 5)])
    c = true_gate_counts(gate, particles, gate="g1")
    assert c == {"gross": 3, "net": 1, "positive": 2, "negative": 1}
    assert true_gate_counts(gate, gate="g1")["gross"] == 4             # spark counted
    assert true_gate_counts(gate, particles, "g1", require_visible_both=False)["gross"] == 4
    assert true_gate_counts(gate, particles, "g1", t0=0.9, t1=1.6)["gross"] == 2
    m = count_metrics(27, 30, 25, 33)
    assert m["rel_err"] == pytest.approx(-0.1) and m["in_ci"] and m["abs_err"] == -3
    assert not count_metrics(10, 30, 5, 20)["in_ci"]
    assert count_metrics(0, 0)["rel_err"] == 0.0 and np.isnan(count_metrics(2, 0)["rel_err"])


def test_clopper_pearson_and_coverage():
    assert clopper_pearson(9, 10) == pytest.approx((0.55498, 0.99747), abs=1e-5)
    assert clopper_pearson(0, 10) == pytest.approx((0.0, 0.30850), abs=1e-5)
    assert clopper_pearson(10, 10) == pytest.approx((0.69150, 1.0), abs=1e-5)
    assert all(np.isnan(clopper_pearson(0, 0)))
    cv = coverage([True] * 180 + [False] * 20)
    assert cv["fraction"] == pytest.approx(0.9) and cv["n"] == 200
    assert cv["lo"] == pytest.approx(0.84979, abs=1e-4)
    assert cv["hi"] == pytest.approx(0.93784, abs=1e-4)


def test_load_truth_roundtrip(tmp_path):
    truth, _ = build_detection_case()
    truth.to_parquet(tmp_path / "truth_particles.parquet")
    frames = pd.DataFrame({"frame": np.arange(3, dtype=np.int64), "t_start": np.arange(3) * DT,
                           "t_mid": (np.arange(3) + 0.25) * DT, "t_end": (np.arange(3) + 0.5) * DT,
                           "exposure_s": np.full(3, DT / 2), "duplicate": [False] * 3,
                           "n_visible_embers": np.array([2, 1, 1], np.int64)})
    frames.to_parquet(tmp_path / "truth_frames.parquet")
    (tmp_path / "meta.json").write_text(json.dumps({"fps": 30, "gates": []}), encoding="utf-8")
    out = load_truth(tmp_path)
    assert len(out["particles"]) == len(truth) and out["gate"] is None
    assert out["frames"]["n_visible_embers"].tolist() == [2, 1, 1] and out["meta"]["fps"] == 30
    assert detection_metrics(out["particles"], pd.DataFrame({"frame": [0], "x": [10.0],
                                                             "y": [10.0]}))["tp"] == 1


def test_mostly_lost_and_partially_tracked_boundaries(cfg):
    """MT >= 80%, ML < 20%, PT in between (py-motmetrics convention): an object tracked
    in exactly 1 of 5 frames is partially tracked, not mostly lost."""
    rows, hyp = [], []
    for f in range(5):
        rows.append(truth_row(f, 1, 10.0 + f, 10.0))
        rows.append(truth_row(f, 2, 80.0 + f, 80.0))
        rows.append(truth_row(f, 3, 150.0 + f, 150.0))
        hyp.append((f, 1, 10.0 + f, 10.0))                 # 5 of 5: mostly tracked
        if f == 0:
            hyp.append((f, 2, 80.0, 80.0))                 # 1 of 5 = 0.2: partially tracked
    m = tracking_metrics(truth_df(rows), pd.DataFrame(hyp, columns=["frame", "track_id", "x", "y"]),
                         cfg)
    assert (m["mostly_tracked"], m["partially_tracked"], m["mostly_lost"]) == (1, 1, 1)


def test_tracking_metrics_restricted_frames(cfg):
    """Frames the tracker never processed (dropped duplicates) can be left out; scored by
    default, their truth counts as misses."""
    rows, hyp = [], []
    for f in range(6):
        rows.append(truth_row(f, 1, 10.0 + 2 * f, 20.0))
        if f != 3:                                         # frame 3 was a duplicate, skipped
            hyp.append((f, 7, 10.0 + 2 * f, 20.0))
    truth = truth_df(rows)
    tp = pd.DataFrame(hyp, columns=["frame", "track_id", "x", "y"])
    m_all = tracking_metrics(truth, tp, cfg)
    assert m_all["fn"] == 1 and m_all["gt"] == 6
    m = tracking_metrics(truth, tp, cfg, frames=[0, 1, 2, 4, 5])
    assert m["fn"] == 0 and m["gt"] == 5 and m["mota"] == pytest.approx(1.0)
    assert m["id_switches"] == 0
    # Hypotheses are counted over the scored frames only.
    tp2 = pd.concat([tp, pd.DataFrame([(3, 99, 500.0, 500.0)], columns=tp.columns)])
    assert tracking_metrics(truth, tp2, cfg, frames=[0, 1, 2, 4, 5])["n_hypotheses"] == 1
    assert tracking_metrics(truth, tp2, cfg)["n_hypotheses"] == 2


def _gate_truth_rows(rows: pd.DataFrame, gate_y: float = 200.0):
    """truth_gate rows by the shared-schema rule for a horizontal gate y = gate_y spanning
    the whole width: midpoint to midpoint moves between consecutive frames."""
    out = []
    for pid, g in rows.sort_values(["particle_id", "frame"]).groupby("particle_id"):
        f, y, t, vis = (g[c].to_numpy() for c in ("frame", "y_mid", "t_mid", "visible"))
        for k in range(len(g) - 1):
            if f[k + 1] != f[k] + 1:
                continue
            s0, s1 = y[k] - gate_y, y[k + 1] - gate_y
            if (s0 > 0) != (s1 > 0):
                lam = s0 / (s0 - s1)
                out.append({"gate": "g1", "particle_id": int(pid), "t": t[k] + lam * (t[k + 1] - t[k]),
                            "frame_before": int(f[k]), "frame_after": int(f[k + 1]),
                            "direction": np.int8(1 if s1 > 0 else -1),
                            "visible_both": bool(vis[k] and vis[k + 1])})
    return pd.DataFrame(out).astype({"particle_id": "int64", "frame_before": "int64",
                                     "frame_after": "int64", "direction": "int8"})


def test_bridged_truth_rule_for_flicker_dropouts():
    # Particle 1 crosses between frames 4 and 5 and is invisible in frame 5 (dropout).
    # Particle 2 crosses between 4 and 5 and is invisible in 3, 4, 5, 6: a gap of 4.
    # Particle 3 crosses visibly. Particle 4 is never visible (too faint).
    rows = []
    for f in range(10):
        y = 165.0 + 7.0 * f
        rows.append(truth_row(f, 1, 50.0, y, visible=f != 5))
        rows.append(truth_row(f, 2, 90.0, y, visible=f not in (3, 4, 5, 6)))
        rows.append(truth_row(f, 3, 130.0, y))
        rows.append(truth_row(f, 4, 170.0, y, visible=False))
    truth = truth_df(rows)
    tg = _gate_truth_rows(truth)
    assert sorted(tg["particle_id"]) == [1, 2, 3, 4] and tg["visible_both"].sum() == 1
    assert bridged_crossings(tg, truth, 0).tolist() == tg["visible_both"].tolist()
    by_pid = dict(zip(tg["particle_id"], bridged_crossings(tg, truth, 3)))
    assert by_pid == {1: True, 2: False, 3: True, 4: False}
    assert dict(zip(tg["particle_id"], bridged_crossings(tg, truth, 4)))[2]
    assert true_gate_counts(tg, truth, "g1")["gross"] == 1
    assert true_gate_counts(tg, truth, "g1", max_gap_frames=3)["gross"] == 2
    assert true_gate_counts(tg, truth, "g1", require_visible_both=False)["gross"] == 4
    # A particle inside a flame region is not detectable there, so it bridges nothing.
    flame = truth.copy()
    flame.loc[(flame.particle_id == 1) & (flame.frame == 4), "in_large_region"] = True
    flame.loc[(flame.particle_id == 1) & (flame.frame == 3), "in_large_region"] = True
    assert dict(zip(tg["particle_id"], bridged_crossings(tg, flame, 1)))[1] is np.False_
    # Visible in both bracketing frames (5 and 6) but inside a flame in frame 5: don't care,
    # not a true crossing (the detector masks the flame), unless a tracker coasting over
    # the masked frame bridges it (detectable in 4 and 6: a gap of one frame).
    flame3 = truth.copy()
    flame3.loc[(flame3.particle_id == 3) & (flame3.frame == 5), "in_large_region"] = True
    assert not dict(zip(tg["particle_id"], bridged_crossings(tg, flame3, 0)))[3]
    assert dict(zip(tg["particle_id"], bridged_crossings(tg, flame3, 1)))[3]
    assert true_gate_counts(tg, flame3, "g1")["gross"] == 0
    assert true_gate_counts(tg, None, "g1")["gross"] == 1          # no particle table: visible_both


def test_bridged_truth_rule_skips_repeated_frames():
    """A repeated frame is never analysed and the tracker counts it as a missed frame (its
    frame index still advances), so its copy of the previous frame must not shorten a gap."""
    rows = [truth_row(f, 1, 50.0, 165.0 + 7.0 * (1 if f == 2 else f), visible=f not in (3, 4, 5))
            for f in range(10)]                                    # frame 2 repeats frame 1
    truth = truth_df(rows)
    tg = _gate_truth_rows(truth)                                   # crosses between frames 5 and 6
    frames = pd.DataFrame({"frame": np.arange(10), "duplicate": np.arange(10) == 2})
    assert tg[["frame_before", "frame_after"]].values.tolist() == [[5, 6]]
    assert bridged_crossings(tg, truth, 3).tolist() == [True]          # gap counted from the repeat
    assert bridged_crossings(tg, truth, 3, frames).tolist() == [False]  # last real detection: frame 1
    assert bridged_crossings(tg, truth, 4, frames).tolist() == [True]
    assert true_gate_counts(tg, truth, "g1", max_gap_frames=3, truth_frames=frames)["gross"] == 0


def test_frame_range_selection_is_clock_free():
    gate = pd.DataFrame({
        "gate": ["g1"] * 4, "particle_id": np.array([1, 2, 3, 4], np.int64),
        "t": [0.02, 1.0, 4.95, 4.99],
        "frame_before": np.array([0, 29, 148, 149], np.int64),
        "frame_after": np.array([1, 30, 149, 150], np.int64),
        "direction": np.array([1, 1, -1, 1], np.int8), "visible_both": [True] * 4})
    c = true_gate_counts(gate, None, "g1", frame_range=(0, 149))
    assert c == {"gross": 3, "net": 1, "positive": 2, "negative": 1}
    assert true_gate_counts(gate, None, "g1", frame_range=(1, 149))["gross"] == 2


def test_gate_metrics_under_flicker_and_clock_offset(cfg):
    """End to end: tracker and live gate counter on embers with 15% flicker dropouts.

    Frame times are the PTS (exposure start) while truth times are exposure midpoints.
    The visible_both truth makes a working counter look about 35% high; the bridged
    rule with frame-range selection matches it within a few percent.
    """
    from wfglink.detect.candidates import Detections
    from wfglink.measure.gate import Gate, GateCounter
    from wfglink.track.tracker import Tracker

    fps, n_frames, n = 30.0, 240, 160
    t_exp = 0.5 / fps
    rng = np.random.default_rng(4)
    start = rng.integers(-20, n_frames - 30, n)
    life = rng.integers(30, 60, n)
    x0 = rng.uniform(150, 1130, n)
    y0 = 200 + rng.choice([-1, 1], n) * rng.uniform(60, 180, n)
    vy = -np.sign(y0 - 200) * rng.uniform(150, 400, n)
    vx = rng.uniform(-80, 80, n)
    rows, dets = [], []
    for f in range(n_frames):
        alive = np.flatnonzero((f >= start) & (f < start + life))
        tm = (f - start[alive]) / fps + t_exp / 2
        x, y = x0[alive] + vx[alive] * tm, y0[alive] + vy[alive] * tm
        vis = rng.random(alive.size) > 0.15
        for k, p in enumerate(alive.tolist()):
            r = truth_row(f, p, x[k], y[k], visible=bool(vis[k]))
            r["t_mid"] = f / fps + t_exp / 2
            rows.append(r)
        k = np.flatnonzero(vis)
        z = np.zeros(k.size)
        dets.append(Detections(x=x[k] + rng.normal(0, 0.3, k.size), y=y[k] + rng.normal(0, 0.3, k.size),
                               area=z + 3, peak=z + 50, flux=z + 100, lam1=z, lam2=z, theta=z,
                               length=z, width=z + 2, sat_frac=z, color=z,
                               flags=np.zeros(k.size, np.uint8)))
    truth = truth_df(rows)
    tg = _gate_truth_rows(truth)
    counter = GateCounter(Gate((0.0, 200.0), (1280.0, 200.0), 2.0, "g1"), cfg)
    tracker = Tracker(cfg, fps=fps)
    for f, d in enumerate(dets):
        tracker.update(d, f / fps, f)                     # PTS: exposure start
        counter.observe(f / fps)
        counter.update_tracks(tracker.active_tracks())
        counter.update_tracks(tracker.pop_finished())
    counter.update_tracks(tracker.finish_all())
    strict = gate_metrics(counter, tg, None, cfg=cfg)
    assert strict["truth_rule"] == "visible_both"
    assert strict["cpc_gross"]["rel_err"] > 0.2
    m = gate_metrics(counter, tg, truth, cfg=cfg, frame_range=(0, n_frames - 1))
    assert m["truth_rule"].startswith("bridged")
    assert abs(m["cpc_gross"]["rel_err"]) < 0.05 and m["cpc_gross"]["in_ci"]
    assert abs(m["cpc_net"]["abs_err"]) <= 2 and m["pnf"]["in_ci"]
    with pytest.raises(ValueError):
        gate_metrics(GateCounter(Gate((0, 0), (1, 0), 2.0, "g1"), cfg), tg)
