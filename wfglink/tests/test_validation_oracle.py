"""Oracle checks of the validation machinery: ground truth fed in as perfect estimates.

A small synthetic clip (320x180, 1.5 s, with repeated frames, a flame over the vertical
gate and two static lights) is generated once. Its truth is turned into the tables the
pipeline would write (detections, track points, a gate counter, the exposure), and every
metric must then report a perfect score, or exactly the documented limit of the method
(a hysteresis gate cannot count a track that never leaves the band on one side). The
same tables also go through `validate.suite.score_clip`, the scoring half of
`evaluate_clip`, to check its frame windows, clocks and record keys.
"""
from __future__ import annotations

import importlib.util
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from wfglink import PROJECT_ROOT
from wfglink.config import load_config
from wfglink.measure.field import estimate_field, field_errors
from wfglink.measure.gate import Gate, GateCounter
from wfglink.synth.generate import generate_clip, load_synth_config
from wfglink.validate import suite
from wfglink.validate.metrics import (bridged_crossings, detectable_mask, detection_metrics, dont_care_mask,
                                      gate_metrics, load_truth, tracking_metrics, truth_field,
                                      velocity_metrics)

WARMUP = 3          # frames before the oracle's "detector" is ready

CLIP_CFG = {
    "frame_size": [320, 180], "duration_s": 1.5, "field_grid": [4, 3],
    "embers": {"density": {"on_screen": 40, "pilot_particles": 300}, "snr": {"median": 15.0}},
    "scene": {"lights": {"count": 2},
              "flame": {"enabled": True, "center_frac": [0.5, 0.3], "size_frac": [0.08, 0.12]}},
    "timing": {"duplicate_prob": 0.1},
    "compression": {"preset": "ultrafast"},
}


@pytest.fixture(scope="module")
def cfg():
    return load_config(overrides={"field": {"grid": [4, 3]}})


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    out = tmp_path_factory.mktemp("oracle") / "clip"
    generate_clip(load_synth_config([], CLIP_CFG), out, seed=3)
    return out


@pytest.fixture(scope="module")
def truth(clip):
    t = load_truth(clip)
    p, fr = t["particles"], t["frames"]
    # The fixture must exercise what it is meant to: repeats, flame rows, distractors.
    assert fr["duplicate"].sum() >= 1 and p["in_large_region"].any() and (p["kind"] == "light").any()
    assert len(t["gate"]) > 10
    return t


# Oracle tables ----------------------------------------------------------------------------
def real_frames(truth) -> pd.DataFrame:
    """Frames the pipeline analyses: the repeats are recognised and skipped."""
    fr = truth["frames"]
    return fr[~fr["duplicate"].to_numpy()]


def detectable_rows(truth, frames=None) -> pd.DataFrame:
    p = truth["particles"]
    rows = p[detectable_mask(p)]
    if frames is not None:
        rows = rows[rows["frame"].isin(set(frames))]
    return rows.sort_values(["particle_id", "frame"], kind="stable")


def oracle_detections(rows) -> pd.DataFrame:
    return pd.DataFrame({"frame": rows["frame"].to_numpy(), "x": rows["x_mid"].to_numpy(),
                         "y": rows["y_mid"].to_numpy()})


def segment_ids(rows, max_gap: int | None) -> np.ndarray:
    """One id per particle, or per run of a particle's rows without a gap longer than
    max_gap frames (what a tracker coasting over max_gap missed frames can link)."""
    pid = rows["particle_id"].to_numpy()
    f = rows["frame"].to_numpy()
    new = np.r_[True, pid[1:] != pid[:-1]]
    if max_gap is not None:
        new[1:] |= np.diff(f) - 1 > max_gap
    return np.cumsum(new)


def oracle_tracks(rows, truth, ids=None) -> pd.DataFrame:
    """Track points as `tracks_to_frame` writes them, at the true midpoints (PTS times)."""
    pts = truth["frames"].set_index("frame")["t_start"]
    n = len(rows)
    return pd.DataFrame({
        "track_id": rows["particle_id"].to_numpy() if ids is None else ids,
        "frame": rows["frame"].to_numpy(), "t": pts.loc[rows["frame"]].to_numpy(),
        "x_meas": rows["x_mid"].to_numpy(), "y_meas": rows["y_mid"].to_numpy(),
        "x": rows["x_mid"].to_numpy(), "y": rows["y_mid"].to_numpy(),
        "vx_poly": rows["u"].to_numpy(), "vy_poly": rows["v"].to_numpy(),
        "length": rows["streak_length_px"].to_numpy(),
        "theta": np.mod(np.arctan2(rows["v"], rows["u"]).to_numpy(), np.pi),
        "flags": np.zeros(n, np.uint8), "coasted": np.zeros(n, bool), "static": np.zeros(n, bool)})


def driven_counter(truth, cfg, tracks, frames) -> GateCounter:
    """The pipeline's gate counter fed with oracle track points on the PTS clock."""
    counter = GateCounter(Gate.from_spec(truth["meta"]["gates"][0], cfg), cfg)
    for t in truth["frames"].set_index("frame").loc[list(frames), "t_start"]:
        counter.observe(float(t))
    for tid, g in tracks.sort_values(["track_id", "frame"]).groupby("track_id"):
        for t, x, y in zip(g["t"], g["x"], g["y"]):
            counter.update_point(int(tid), float(t), float(x), float(y))
    return counter


# (a) Detection ----------------------------------------------------------------------------
def test_detection_oracle_is_perfect(truth, cfg):
    p = truth["particles"]
    rows = detectable_rows(truth)
    m = detection_metrics(p, oracle_detections(rows), cfg)
    assert (m["tp"], m["fp"], m["fn"], m["ignored"]) == (len(rows), 0, 0, 0)
    assert m["precision"] == m["recall"] == m["f1"] == 1.0 and m["loc_rmse_px"] == 0.0
    # Estimates on every ember, detectable or not: the others are don't care.
    embers = p[p["kind"] == "ember"]
    m2 = detection_metrics(p, oracle_detections(embers), cfg)
    assert m2["f1"] == 1.0 and m2["ignored"] == int(dont_care_mask(p).sum())
    # Estimates on the static lights are false positives.
    lights = p[p["kind"] == "light"]
    m3 = detection_metrics(p, oracle_detections(pd.concat([rows, lights])), cfg)
    assert m3["fp"] == len(lights) and m3["recall"] == 1.0


# (e) Completeness ----------------------------------------------------------------------------
def test_completeness_oracle_is_one_in_every_bin(truth, cfg):
    p = truth["particles"]
    frames = sorted(p["frame"].unique().tolist())
    comp = suite.completeness_by_snr(p, oracle_detections(detectable_rows(truth)), truth["meta"], frames, cfg)
    populated = {k: v for k, v in comp.items() if v[1] > 0}
    assert len(populated) >= 2 and all(h == n for h, n in populated.values())
    assert sum(n for _, n in comp.values()) == int(detectable_mask(p).sum())
    # Perfect completeness puts the 50% point below the lowest bin: an upper bound only.
    if any(n >= suite.SNR50_MIN_N for _, n in comp.values()):
        assert suite.snr50_is_upper_bound(comp) is True


# (b) Tracking and velocity -----------------------------------------------------------------
def test_tracking_and_velocity_oracle_is_perfect(truth, cfg):
    p = truth["particles"]
    rows = detectable_rows(truth)
    tp = oracle_tracks(rows, truth)
    m = tracking_metrics(p, tp, cfg)
    n_obj = rows["particle_id"].nunique()
    assert (m["mota"], m["id_switches"], m["fp"], m["fn"]) == (1.0, 0, 0, 0)
    assert m["motp_px"] == 0.0 and m["mostly_tracked"] == m["n_truth_objects"] == n_obj
    v = velocity_metrics(p, tp, cfg, x_col="x_meas", y_col="y_meas")
    assert v["n"] == len(rows)
    for k in ("median_rel_speed_err", "p90_rel_speed_err", "median_signed_rel_speed_err",
              "median_angle_err_deg", "rmse_u", "rmse_v"):
        assert v[k] == pytest.approx(0.0, abs=1e-9), k


def test_tracks_split_at_long_gaps_count_one_switch_per_split(truth, cfg):
    """A particle whose visibility gap is longer than track.max_coast cannot be linked by
    the tracker; its next segment is a new hypothesis, and CLEAR MOT counts one switch."""
    rows = detectable_rows(truth)
    ids = segment_ids(rows, int(cfg["track"]["max_coast"]))
    splits = len(np.unique(ids)) - rows["particle_id"].nunique()
    assert splits >= 1
    m = tracking_metrics(truth["particles"], oracle_tracks(rows, truth, ids), cfg)
    assert m["id_switches"] == splits and (m["fp"], m["fn"]) == (0, 0)


# (c) Gate ----------------------------------------------------------------------------------
def _gate_truth(truth, cfg):
    tg = truth["gate"]
    tg = tg[tg["gate"] == truth["meta"]["gates"][0]["name"]]
    return tg[bridged_crossings(tg, truth["particles"], int(cfg["track"]["max_coast"]), truth["frames"])]


def test_gate_oracle_without_hysteresis_reproduces_the_truth(truth, cfg):
    """Counter on the PTS clock, truth on exposure midpoints selected by frames: equal."""
    c0 = load_config(overrides={"gate": {"hysteresis_px": 0.0}, "field": {"grid": [4, 3]}})
    frames = real_frames(truth)["frame"].tolist()
    rows = detectable_rows(truth, frames)
    tracks = oracle_tracks(rows, truth, segment_ids(rows, int(c0["track"]["max_coast"])))
    counter = driven_counter(truth, c0, tracks, frames)
    m = gate_metrics(counter, truth["gate"], truth["particles"], cfg=c0, frame_range=(frames[0], frames[-1]),
                     truth_frames=truth["frames"])
    assert m["truth"]["gross"] > 5 and m["truth_rule"].startswith("bridged")
    assert m["estimate"] == m["truth"]
    assert m["cpc_gross"]["rel_err"] == 0.0 and m["pnf"]["rel_err"] == 0.0 and m["cpc_gross"]["in_ci"]
    # The crossings it counts are exactly the true ones, particle by particle.
    seg_pid = dict(zip(tracks["track_id"], rows["particle_id"]))
    got = sorted((seg_pid[e.track_id], e.direction) for e in counter.events)
    tg = _gate_truth(truth, c0)
    assert got == sorted(zip(tg["particle_id"].tolist(), tg["direction"].astype(int).tolist()))


def test_gate_oracle_misses_only_tracks_inside_the_hysteresis_band(truth, cfg):
    """With hysteresis h, the counter arms a direction once a track is beyond 2h on the
    side it comes from and counts the crossing once the same track is beyond h on the
    other side; every true crossing it misses is one where its track never was."""
    frames = real_frames(truth)["frame"].tolist()
    rows = detectable_rows(truth, frames)
    ids = segment_ids(rows, int(cfg["track"]["max_coast"]))
    tracks = oracle_tracks(rows, truth, ids)
    counter = driven_counter(truth, cfg, tracks, frames)
    gate = counter.gate
    seg_pid = dict(zip(ids, rows["particle_id"]))
    got = {(seg_pid[e.track_id], e.direction) for e in counter.events}
    tg = _gate_truth(truth, cfg)
    want = set(zip(tg["particle_id"].tolist(), tg["direction"].astype(int).tolist()))
    assert got <= want
    tracks["d"] = gate.signed_distance(tracks["x"], tracks["y"])
    for pid, direction in want - got:
        r = tg[(tg["particle_id"] == pid) & (tg["direction"] == direction)].iloc[0]
        own = tracks[tracks["track_id"].map(seg_pid) == pid]
        # The counter keeps its state per track: only the segment that holds the crossing.
        pre = own[own["frame"] <= r["frame_before"]]
        seg = own[own["track_id"] == pre["track_id"].iloc[-1]] if len(pre) else pre
        before = seg.loc[seg["frame"] <= r["frame_before"], "d"].to_numpy() * direction
        after = seg.loc[seg["frame"] >= r["frame_after"], "d"].to_numpy() * direction
        assert not (np.any(before < -2 * gate.h) and np.any(after > gate.h)), (pid, direction)


def test_gate_truth_leaves_out_crossings_inside_large_regions(truth):
    """Embers inside a flame are don't care for detection, so for the gate truth too."""
    tg, p = truth["gate"], truth["particles"]
    large = set(zip(p.loc[p["in_large_region"], "particle_id"], p.loc[p["in_large_region"], "frame"]))
    inside = np.array([(a, b) in large or (a, c) in large
                       for a, b, c in zip(tg["particle_id"], tg["frame_before"], tg["frame_after"])])
    assert np.any(tg["visible_both"].to_numpy() & inside)        # the old rule counted these
    rule = bridged_crossings(tg, p, 0)
    assert not np.any(rule & inside)
    assert np.array_equal(rule, tg["visible_both"].to_numpy() & ~inside)


# (d) Field -----------------------------------------------------------------------------------
def _field_points(rows):
    return pd.DataFrame({"track_id": rows["particle_id"].to_numpy(), "t": rows["t_mid"].to_numpy(),
                         "x_meas": rows["x_mid"].to_numpy(), "y_meas": rows["y_mid"].to_numpy(),
                         "vx_poly": rows["u"].to_numpy(), "vy_poly": rows["v"].to_numpy()})


def test_truth_field_helper_reproduces_the_generator_table(clip, truth):
    meta = truth["meta"]
    tf = pd.read_parquet(clip / "truth_field.parquet")
    mine = truth_field(truth["particles"], truth["frames"], tuple(meta["frame_size"]), tuple(meta["field_grid"]),
                       eulerian=tf, exclude_large=False)
    for c in tf.columns:
        assert np.allclose(mine[c].to_numpy(float), tf[c].to_numpy(float), equal_nan=True), c


def test_field_oracle_on_the_scored_frames_is_exact(clip, truth, cfg):
    """True per-point velocities in, the per-cell medians of the truth out, as long as the
    truth covers the same frames (the estimator's outlier rejection switched off: it is
    meant to drop wrong tracks, and also drops real embers of a settling-speed mixture)."""
    no_reject = load_config(overrides={"field": {"grid": [4, 3], "mad_k": 1e9, "mad_floor_px_s": 1e9,
                                                 "min_tracks_show": 3}})
    meta = truth["meta"]
    fs, grid = tuple(meta["frame_size"]), tuple(meta["field_grid"])
    scored = [f for f in real_frames(truth)["frame"].tolist() if f >= WARMUP]
    rows = detectable_rows(truth, scored)
    est = estimate_field(_field_points(rows), fs, no_reject)
    e = field_errors(est, truth_field(truth["particles"], truth["frames"], fs, grid, frames=scored))
    assert e["cells"] >= 3
    assert e["rmse_ember_u"] == pytest.approx(0.0, abs=1e-9)
    assert e["rmse_ember_v"] == pytest.approx(0.0, abs=1e-9)
    # The air field of the same embers is the lag, not an error of the estimate.
    assert np.isfinite(e["rmse_air_v"])
    # The whole-clip truth_field.parquet also holds the warm-up frames and the embers
    # inside the flame: against it the same perfect estimate shows an error (which is why
    # score_clip recomputes the truth).
    whole = field_errors(est, pd.read_parquet(clip / "truth_field.parquet"))
    assert whole["rmse_ember_v"] > 0.1


# Scoring path of evaluate_clip ---------------------------------------------------------------
def oracle_run(truth, cfg, hysteresis: float = 0.0):
    """The tables, counter and exposure a perfect pipeline would hand to score_clip."""
    fr = real_frames(truth)
    frames = pd.DataFrame({"frame": fr["frame"].to_numpy(), "t": fr["t_start"].to_numpy(),
                           "ready": fr["frame"].to_numpy() >= WARMUP})
    scored = frames.loc[frames["ready"], "frame"].tolist()
    rows = detectable_rows(truth, scored)
    det = oracle_detections(rows)
    frames["has_detections"] = frames["frame"].isin(set(det["frame"]))
    tracks = oracle_tracks(rows, truth).drop(columns=["vx_poly", "vy_poly"])
    c = load_config(overrides={"gate": {"hysteresis_px": hysteresis}})
    seg = oracle_tracks(rows, truth, segment_ids(rows, int(c["track"]["max_coast"])))
    counter = driven_counter(truth, c, seg, frames["frame"].tolist())
    t_exp = float(truth["meta"]["exposure_s"])
    exposure = SimpleNamespace(t_exp=t_exp, ok=True, ci_low=0.99 * t_exp, ci_high=1.01 * t_exp, reason="")
    return {"detections": det, "frames": frames, "tracks": tracks}, counter, exposure


def test_score_clip_on_oracle_tables_is_perfect(clip, truth, cfg):
    tabs, counter, exposure = oracle_run(truth, cfg)
    out = suite.score_clip(clip, tabs, counter, exposure, cfg, truth=truth)
    n_scored = int(tabs["frames"]["ready"].sum())
    assert out["frames_scored"] == n_scored
    assert out["frames_real_dropped"] == 0 and out["frames_repeat_analysed"] == 0
    assert out["detection"]["f1"] == 1.0 and out["fp_per_mpx_frame"] == 0.0
    assert out["detection"]["n_frames"] == n_scored
    assert all(h == n for h, n in out["completeness"].values())
    t = out["tracking"]
    assert (t["mota"], t["id_switches"], t["fp"], t["fn"]) == (1.0, 0, 0, 0)
    # Track velocities are fitted to the true midpoints (local polynomial): nearly exact.
    assert out["velocity_track"]["median_rel_speed_err"] < 1e-3
    assert out["velocity_track"]["median_angle_err_deg"] < 0.1
    if out.get("velocity_streak", {}).get("n"):
        assert out["velocity_streak"]["median_rel_speed_err"] < 1e-6
    assert out["exposure"]["ok"] and out["exposure"]["rel_error"] == 0.0
    g = out["gate"]
    assert g["estimate"] == g["truth"] and g["truth"]["gross"] > 5 and g["cpc_gross"]["in_ci"]
    t_ready = tabs["frames"].loc[tabs["frames"]["ready"], "t"]
    assert g["duration_s"] == pytest.approx(t_ready.max() - t_ready.min())
    assert out["field"]["cells"] >= 1
    # Bright view: perfect too wherever the clip has bright embers (NaN without any).
    for v in (out["detection_bright"]["recall"], out["detection_bright"]["precision"],
              out["tracking_bright"]["mota"]):
        assert v == 1.0 or np.isnan(v)
    assert out["gate_between_bounds"] is True


def test_score_clip_field_truth_covers_only_the_scored_frames(clip, truth, cfg, monkeypatch):
    """The field is compared with the truth of the frames the method saw, not with
    truth_field.parquet, which includes the warm-up frames before the detector is ready."""
    tabs, counter, exposure = oracle_run(truth, cfg)
    seen = {}
    real = suite.truth_field

    def spy(*args, **kw):
        seen["frames"] = sorted(kw["frames"])
        return real(*args, **kw)

    monkeypatch.setattr(suite, "truth_field", spy)
    suite.score_clip(clip, tabs, counter, exposure, cfg, truth=truth)
    assert seen["frames"] == tabs["frames"].loc[tabs["frames"]["ready"], "frame"].tolist()


def test_score_clip_reports_dropped_and_repeated_frames(clip, truth, cfg):
    tabs, counter, exposure = oracle_run(truth, cfg)
    fr = truth["frames"]
    dup = int(fr.loc[fr["duplicate"] & (fr["frame"] > WARMUP), "frame"].iloc[0])
    drop = int(tabs["frames"].loc[tabs["frames"]["ready"], "frame"].iloc[2])
    frames = tabs["frames"][tabs["frames"]["frame"] != drop]
    extra = pd.DataFrame({"frame": [dup], "t": [float(fr.loc[fr["frame"] == dup, "t_start"].iloc[0])],
                          "ready": [True], "has_detections": [False]})
    tabs = dict(tabs, frames=pd.concat([frames, extra]).sort_values("frame", ignore_index=True))
    out = suite.score_clip(clip, tabs, counter, exposure, cfg, truth=truth)
    assert out["frames_real_dropped"] == 1 and out["frames_repeat_analysed"] == 1


def test_score_clip_without_tracks_scores_mota_zero(clip, truth, cfg):
    """A clip whose tracker found nothing has MOTA 0; it must not drop out of the medians."""
    tabs, counter, exposure = oracle_run(truth, cfg)
    tabs = dict(tabs, tracks=tabs["tracks"].iloc[:0])
    out = suite.score_clip(clip, tabs, counter, None, cfg, truth=truth)
    assert out["tracking"]["mota"] == 0.0 and out["tracking"]["fn"] == out["tracking"]["gt"] > 0
    assert "velocity_track" not in out and out["exposure"]["ok"] is False


# Summary and record keys ----------------------------------------------------------------------
def test_summarize_uses_absolute_errors_and_clip_fractions():
    def clip(seed, cpc, exp, ok=True):
        return {"case": "c", "seed": seed, "gate": {"cpc_gross": {"rel_err": cpc, "in_ci": seed != 2},
                                                    "pnf": {"rel_err": cpc}},
                "exposure": {"ok": ok, "rel_error": exp if ok else None}, "completeness": {"0-5": [30, 30]}}

    row = suite.summarize([clip(0, 0.2, 0.25), clip(1, -0.2, -0.2), clip(2, 0.01, None, ok=False)])["c"]
    # Signed medians would report 0.01 and 0.025 here: both seeds with an estimate miss by 20%.
    assert row["cpc_gross_rel_err"] == pytest.approx(0.2) and row["pnf_rel_err"] == pytest.approx(0.2)
    assert row["cpc_gross_bias"] == pytest.approx(0.01)
    assert row["exposure_rel_err"] == pytest.approx(0.225) and row["exposure_bias"] == pytest.approx(0.025)
    assert row["exposure_ok"] == pytest.approx(2 / 3) and row["cpc_gross_in_ci"] == pytest.approx(2 / 3)
    assert row["snr50"] == 2.5 and row["snr50_upper_bound"] is True


def test_run_suite_has_a_unit_and_description_for_every_recorded_key():
    spec = importlib.util.spec_from_file_location("run_suite", PROJECT_ROOT / "scripts" / "run_suite.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    recorded = set(suite.SUMMARY_KEYS) | {"snr50"}
    assert recorded <= set(mod.UNITS) and recorded <= set(mod.DESCRIPTIONS)
    assert "snr50_upper_bound" in mod.DESCRIPTIONS
    assert suite.SUMMARY_ABS <= set(suite.SUMMARY_KEYS) and suite.SUMMARY_MEAN <= set(suite.SUMMARY_KEYS)
