"""verify evaluate: track- and frame-level scoring against window truth, deliberate failure controls,
footage rates inside the windows' boxes, statuses, complete inputs and the frozen protocol (hash pinned,
committed, sealed test scored once)."""
import json
import shutil

import numpy as np
import pandas as pd
import pytest

from wfglink.provenance import sha256_file
from wfglink.verify import evaluate as E

FPS = 30.0
VIDEO_SHA = "cd" * 32


@pytest.fixture(autouse=True)
def _project_lock_dir(tmp_path, monkeypatch):
    """Sealed-test locks of the tests go to a temporary folder, never to the project's results/."""
    monkeypatch.setattr(E, "SEALED_DIR", tmp_path / "project_locks")


def _truth(n=4, k=6, roi=(0, 0, 640, 480)):
    wins = []
    for j in range(n):
        frames = [20 * j + i for i in range(k)]
        wins.append({"window_id": f"w{j:03d}", "status": "ok", "frames": frames, "t": [f / FPS for f in frames],
                     "x0": 50 + 100 * (j % 5), "y0": 50 + 100 * (j // 5), "w": 64, "h": 64, "tracks": [],
                     "dont_care": [], "rejected": []})
    return {"windows": wins, "roi_px": list(roi), "video_sha256": VIDEO_SHA, "segment_s": [0.0, None]}


def _track(w, start, vel=(2.0, 1.0), ks=None, sure=True, observable=True, ambiguous=False):
    ks = range(len(w["frames"])) if ks is None else ks
    pts = []
    for k in ks:
        tx, ty = start[0] + vel[0] * k, start[1] + vel[1] * k
        pts.append({"k": k, "frame": w["frames"][k], "t": w["t"][k], "tx": tx, "ty": ty, "x": w["x0"] + tx,
                    "y": w["y0"] + ty, "sure": sure, "edge": False, "dont_care": not (observable and sure),
                    "source": "both"})
    tr = {"truth_id": f"{w['window_id']}_{len(w['tracks']):02d}", "observable": observable, "ambiguous": ambiguous,
          "n_points": len(pts), "n_sure": len(pts) if sure else 0, "points": pts}
    w["tracks"].append(tr)
    return tr


def _with_embers(n=4):
    t = _truth(n)
    for w in t["windows"]:
        _track(w, (10.0, 12.0))
    return t


def _preds(truth, offset=(0.0, 0.0), id0=1, keep=None):
    """One predicted track per observable truth track, following it (offset in px)."""
    rows, tid = [], id0
    for w in truth["windows"]:
        for tr in w["tracks"]:
            if not tr["observable"]:
                continue
            for p in tr["points"]:
                if keep is None or p["k"] in keep:
                    rows.append({"track_id": tid, "frame": p["frame"], "t": p["t"], "x": p["x"] + offset[0],
                                 "y": p["y"] + offset[1], "length": 0.0})
            tid += 1
    return pd.DataFrame(rows, columns=["track_id", "frame", "t", "x", "y", "length"])


def _light(frames, xy=(100.0, 100.0), tid=900):
    return pd.DataFrame({"track_id": tid, "frame": frames, "t": [f / FPS for f in frames], "x": xy[0], "y": xy[1],
                         "length": 0.0})


def _events(rows):
    return pd.DataFrame(rows, columns=["track_id", "t", "x", "y"])


MINUTES4 = 4 * (6 / FPS) * (64 * 64 / (640 * 480)) / 60       # four windows of six frames, 64 px tiles


def test_perfect_predictions_and_evidence():
    t = _with_embers(30)
    r = E.track_level(t, _preds(t), targets={"precision": 0.5, "recall_min": 0.5})
    assert r["precision"]["value"] == 1.0 and r["recall"]["value"] == 1.0 and r["counts"]["tp"] == 30
    assert r["precision"]["lower"] == pytest.approx(0.05 ** (1 / 30))       # exact one-sided bound for 30 of 30
    assert r["status"] == {"precision": "PASSED", "recall": "PASSED"} and r["capability_passed"]
    small = _with_embers(3)
    r = E.track_level(small, _preds(small), targets={"precision": 0.9})
    assert r["precision"]["value"] == 1.0 and r["status"]["precision"] == "INSUFFICIENT_EVIDENCE"
    assert not r["capability_passed"]
    r = E.track_level(t, _preds(t))
    assert not r["capability_passed"] and r["capability_note"] == "no precision target"


def test_control_empty_detector_is_undefined_and_not_passed():
    t = _with_embers(10)
    empty = _preds(t).iloc[:0]
    r = E.track_level(t, empty, targets={"precision": 0.9})
    assert r["precision"]["value"] is None and r["status"]["precision"] == "FAILED" and not r["capability_passed"]
    assert r["recall"]["value"] == 0.0 and r["counts"]["truth_observable"] == 10
    full = E.evaluate(t, {"points": empty, "detections": pd.DataFrame(columns=["frame", "x", "y"])},
                      {"targets": {"precision": 0.9}})
    assert not full["capability_passed"] and full["frame_level"]["r3px"]["precision"]["value"] is None
    assert full["frame_level"]["r3px"]["fn"] == 60


def test_control_persistent_false_light_gives_false_tracks_and_fails():
    t = _with_embers(4)
    light = _light(list(range(0, 80)))               # a still light inside window w000's tile, all clip long
    pts = pd.concat([_preds(t), light], ignore_index=True)
    cr = _events([(900, 2 / FPS, 100.0, 100.0),      # inside w000's box: counted
                  (900, 50 / FPS, 100.0, 100.0),     # in no window's time
                  (900, 3 / FPS, 10.0, 10.0),        # in w000's time, outside its tile
                  (1, 2 / FPS, 62.0, 64.0)])         # an ember's crossing: not false
    r = E.track_level(t, pts, cr, targets={"precision": 0.95, "false_tracks_per_min_max": 0.5})
    c = r["counts"]
    assert c["tp"] == 4 and c["false"] == 1 and c["unique_false_tracks"] == 1
    rt = r["rates"]
    assert rt["supported_minutes"] == pytest.approx(MINUTES4)
    d, life = 6 / FPS, 79 / FPS
    assert rt["false_tracks_per_min"]["value"] == pytest.approx(d / (d + life) / MINUTES4)
    assert rt["false_tracks_per_min"]["count"] == 1
    assert rt["false_crossings_per_min"]["value"] == pytest.approx(1 / MINUTES4)
    # Occupancy: the six frames the light is seen inside the box, not its whole life.
    assert rt["false_occupancy_s_per_min"]["value"] == pytest.approx(0.2 / MINUTES4)
    assert rt["false_occupancy_s_per_min"]["value"] == pytest.approx(1125.0)
    assert r["status"]["false_tracks_per_min"] == "FAILED" and r["status"]["precision"] != "PASSED"
    assert "cannot PASS" in r["status_notes"]["false_tracks_per_min"]
    assert not r["capability_passed"] and r["precision"]["value"] == pytest.approx(0.8)
    # Camera-motion time in that window leaves it out of the rates (not out of precision).
    r = E.track_level(t, pts, cr, unsupported_frames=[2])
    assert r["counts"]["unique_false_tracks"] == 0 and r["counts"]["false"] == 1
    assert r["rates"]["supported_minutes"] == pytest.approx(MINUTES4 * 3 / 4)
    assert r["rates"]["false_crossings_per_min"]["value"] == 0.0 and r["counts"]["windows_supported"] == 3


def test_rates_count_only_what_is_inside_the_boxes():
    """A short and a long still light at the same place give the same occupancy per in-window
    second; the long one weighs less as a track (it is more likely to meet a window)."""
    t = _with_embers(4)
    short, long_ = (E.track_level(t, pd.concat([_preds(t), _light(fr)], ignore_index=True), _events([]))
                    for fr in (list(range(0, 6)), list(range(0, 200))))
    for key in ("false_occupancy_s_per_min",):
        assert short["rates"][key]["value"] == pytest.approx(long_["rates"][key]["value"])
        assert short["rates"][key]["seconds"] == pytest.approx(0.2)
    d = 6 / FPS
    assert short["rates"]["false_tracks_per_min"]["weighted_count"] == pytest.approx(d / (d + 5 / FPS))
    assert long_["rates"]["false_tracks_per_min"]["weighted_count"] == pytest.approx(d / (d + 199 / FPS))
    # A light present in two windows' boxes is judged in both, each judgment weighted.
    t2 = _truth(2)
    t2["windows"][1].update(x0=50, y0=50)
    two = E.track_level(t2, _light(list(range(0, 40))), _events([]))
    assert two["counts"]["false"] == 2 and two["counts"]["unique_false_tracks"] == 1
    assert two["rates"]["false_tracks_per_min"]["count"] == 2
    assert two["rates"]["false_tracks_per_min"]["weighted_count"] == pytest.approx(2 * d / (d + 39 / FPS))
    assert two["rates"]["false_occupancy_s_per_min"]["seconds"] == pytest.approx(0.4)


def test_zero_events_bound_says_which_rate_targets_can_pass():
    t = _with_embers(4)
    r = E.track_level(t, _preds(t), _events([]), targets={"precision": 0.5, "false_tracks_per_min_max": 1.0,
                                                          "false_crossings_per_min_max": 1e6})
    z = 2.9957 / MINUTES4
    for key in ("false_tracks_per_min", "false_crossings_per_min"):
        assert r["rates"][key]["value"] == 0.0 and r["rates"][key]["zero_event_upper"] == pytest.approx(z, rel=1e-4)
    assert r["status"]["false_tracks_per_min"] == "INSUFFICIENT_EVIDENCE"
    assert "cannot PASS" in r["status_notes"]["false_tracks_per_min"]
    assert r["status"]["false_crossings_per_min"] == "PASSED" and "false_crossings_per_min" not in r["status_notes"]
    # No crossing events at all (a legacy run): the rate is unavailable and its target fails.
    r = E.track_level(t, _preds(t), None, targets={"false_crossings_per_min_max": 1e6}, crossings_reason="legacy")
    assert r["rates"]["false_crossings_per_min"]["value"] is None
    assert r["status"]["false_crossings_per_min"] == "FAILED" and "unavailable" in r["status_notes"]["false_crossings_per_min"]
    with pytest.raises(ValueError, match="events"):
        E.track_level(t, _preds(t), pd.DataFrame({"track_id": [1], "crossings": [2]}))


def test_control_duplicates_and_fragments():
    t = _with_embers(1)
    two = pd.concat([_preds(t), _preds(t, offset=(1.0, 0.0), id0=2)], ignore_index=True)
    r = E.track_level(t, two)
    c = r["counts"]
    assert c["tp"] == 1 and c["duplicate"] == 1 and c["false"] == 0 and c["fragmented_truth"] == 1
    assert r["precision"]["value"] == 0.5 and r["precision_fragment_tolerant"]["value"] == 1.0
    assert c["id_switches"] == 0
    # A track broken in two: one match, one duplicate, one ID switch.
    split = pd.concat([_preds(t, keep={0, 1, 2}), _preds(t, keep={3, 4, 5}, id0=2)], ignore_index=True)
    c = E.track_level(t, split)["counts"]
    assert c["tp"] == 1 and c["duplicate"] == 1 and c["id_switches"] == 1 and c["truth_matched"] == 1


def test_judging_rules():
    t = _truth(1)
    w = t["windows"][0]
    _track(w, (10.0, 12.0))                                             # observable
    _track(w, (40.0, 40.0), ks=[0, 1], observable=False)                # two points: not observable
    _track(w, (20.0, 50.0), vel=(0.0, 0.0), sure=False, observable=False)   # unsure
    rows = []
    for k, f in enumerate(w["frames"]):
        tt = f / FPS
        rows += [{"track_id": 1, "frame": f, "t": tt, "x": w["x0"] + 10 + 2 * k + 0.5, "y": w["y0"] + 12 + k},
                 {"track_id": 2, "frame": f, "t": tt, "x": w["x0"] + 40 + 2 * k, "y": w["y0"] + 40 + k},
                 {"track_id": 3, "frame": f, "t": tt, "x": w["x0"] + 20.5, "y": w["y0"] + 50},
                 {"track_id": 4, "frame": f, "t": tt, "x": w["x0"] + 5.0, "y": w["y0"] + 5.0}]
    rows += [{"track_id": 5, "frame": w["frames"][0], "t": 0.0, "x": w["x0"] + 30.0, "y": w["y0"] + 30.0},
             {"track_id": 6, "frame": w["frames"][0], "t": 0.0, "x": w["x0"] - 9.0, "y": w["y0"] + 30.0},
             {"track_id": 6, "frame": w["frames"][1], "t": 0.0, "x": w["x0"] - 8.0, "y": w["y0"] + 30.0}]
    pts = pd.DataFrame(rows).assign(length=0.0)
    j = E.judge_window(w, pts, E.settings()["track"])
    assert j["classes"] == {"1": "tp", "2": "dont_care", "3": "dont_care", "4": "false"}   # 5, 6: not judged
    assert j["judged"] == 4 and j["truth_observable"] == 1 and j["truth_matched"] == 1
    assert j["in_box_frames"] == {"1": 6, "2": 6, "3": 6, "4": 6}
    # A long streak widens the point radius: 0.5 L.
    far = pts[pts["track_id"] == 1].assign(x=lambda d: d["x"] + 6.0)
    assert E.judge_window(w, far, E.settings()["track"])["classes"] == {"1": "false"}
    assert E.judge_window(w, far.assign(length=14.0), E.settings()["track"])["classes"] == {"1": "tp"}


def test_frame_level_matches_points_with_dont_care():
    t = _truth(1)
    w = t["windows"][0]
    _track(w, (10.0, 12.0))
    _track(w, (40.0, 40.0), vel=(0.0, 0.0), sure=False, observable=False)
    f0 = w["frames"][0]
    det = pd.DataFrame({"frame": [f0, f0, f0, f0], "x": [w["x0"] + 10.5, w["x0"] + 40.0, w["x0"] + 30.0, w["x0"] + 66.0],
                        "y": [w["y0"] + 12.0, w["y0"] + 40.5, w["y0"] + 5.0, w["y0"] + 5.0]})
    r = E.frame_level(t, det, 3.0)
    assert (r["tp"], r["fp"], r["fn"], r["dont_care"]) == (1, 1, 5, 1)      # the point outside the tile is not counted
    shifted = det.assign(x=det["x"] + 4.0).iloc[:1]
    assert E.frame_level(t, shifted, 3.0)["tp"] == 0 and E.frame_level(t, shifted, 5.0)["tp"] == 1
    assert E.frame_level(t, det, 3.0, skip_frames=[f0])["fn"] == 5                # a frame the run skipped


def test_status_rules():
    assert E.status(0.97, 0.95, 0.99, 0.95) == "PASSED"
    assert E.status(0.97, 0.90, 0.99, 0.95) == "INSUFFICIENT_EVIDENCE"
    assert E.status(0.90, 0.80, 0.94, 0.95) == "FAILED"
    assert E.status(0.93, 0.85, 0.97, 0.95) == "INSUFFICIENT_EVIDENCE"
    assert E.status(None, None, None, 0.95) == "FAILED" and E.status(float("nan"), 0, 1, 0.5) == "FAILED"
    assert E.status(0.2, 0.1, 0.4, 0.5, higher_is_better=False) == "PASSED"
    assert E.status(0.2, 0.1, 0.9, 0.5, higher_is_better=False) == "INSUFFICIENT_EVIDENCE"
    assert E.status(2.0, 0.6, 3.0, 0.5, higher_is_better=False) == "FAILED"
    lo, hi = E.poisson_bounds(0)
    assert lo == 0.0 and hi == pytest.approx(2.9957, abs=1e-3)


def test_pr_curve_from_replays():
    t = _with_embers(6)
    pts = pd.concat([_preds(t), _light(list(range(0, 120)), tid=900),
                     _light(list(range(0, 120)), xy=(160.0, 70.0), tid=901)], ignore_index=True)
    replays = [(0.9, [1, 2]), (0.1, [1, 2, 3, 4, 5, 6, 900, 901]), (0.5, [1, 2, 3, 4, 5, 6, 900])]
    pr = E.pr_curve(t, pts, replays, _events([(900, 1 / FPS, 100.0, 100.0)]))
    assert [p["threshold"] for p in pr] == [0.1, 0.5, 0.9]
    assert [p["precision"] for p in pr] == pytest.approx([6 / 8, 6 / 7, 1.0])
    assert [p["recall"] for p in pr] == pytest.approx([1.0, 1.0, 2 / 6])


# Runs and protocols ----------------------------------------------------------------------------

def _hp_run(root, points, video_sha=VIDEO_SHA, rejected_ids=(), revoked_ids=(), unsupported=(), events=None,
            hp_status="ok", method="accept_all", profile="file_native", n_frames=200, revoked_at=None):
    """A high-precision run folder as process writes it (tables only): decisions, events, frames,
    hp_summary.json and the frame-level pseudo-run. revoked_at: {track_id: time of its revocation}."""
    run = root / "run"
    hp = run / "high_precision"
    (hp / "frame_level").mkdir(parents=True)
    (run / "summary.json").write_text(json.dumps({"input": {"sha256": video_sha}}))
    fr = pd.DataFrame({"frame": np.arange(n_frames), "t": np.arange(n_frames) / FPS, "duplicate": False})
    fr.to_parquet(run / "frames.parquet", index=False)
    tp = points.rename(columns={"x": "x_meas", "y": "y_meas"}).assign(coasted=False, static=False,
                                                                       x=points["x"], y=points["y"])
    tp.to_parquet(run / "track_points.parquet", index=False)
    ids = sorted(points["track_id"].unique())
    state = ["rejected" if (i in rejected_ids or i in revoked_ids) else "method_accepted" for i in ids]
    pd.DataFrame({"key": ids, "epoch": 0, "track_id": ids, "state": state,
                  "reason": ["static" if i in revoked_ids else "" for i in ids],
                  "revoked": [i in revoked_ids for i in ids],
                  "t_decision": [float((revoked_at or {}).get(i, np.nan)) for i in ids]}).to_parquet(
        hp / "hp_decisions.parquet", index=False)
    acc = points[~points["track_id"].isin(rejected_ids)]
    acc[["frame", "t", "x", "y"]].to_parquet(hp / "frame_level" / "detections.parquet", index=False)
    ev = events if events is not None else _events([(ids[0], 0.1, 0.0, 0.0)])
    pd.DataFrame({"key": ev["track_id"], "epoch": 0, "track_id": ev["track_id"], "t": ev["t"], "direction": 1,
                  "x": ev["x"], "y": ev["y"]}).to_parquet(hp / "hp_events.parquet", index=False)
    fr.assign(motion_unsupported=fr["frame"].isin(list(unsupported))).drop(columns="duplicate").to_parquet(
        hp / "hp_frames.parquet", index=False)
    (hp / "hp_summary.json").write_text(json.dumps({"mode": "high_precision", "method": method, "profile": profile,
                                                    "status": hp_status, "status_reason": "",
                                                    "scorer": {"method": method, "overlay_sha256": "ef" * 32}}))
    return run


def _protocol(root, truth, sealed=True, targets=None, **extra):
    tp = root / "truth.json"
    tp.write_text(json.dumps(truth))
    p = root / "protocol.json"
    p.write_text(json.dumps({"schema_version": 1, "name": "test", "sealed": sealed,
                             "truth": {"path": "truth.json", "sha256": sha256_file(tp)},
                             "targets": targets or {"precision": 0.5}, **extra}))
    return p, sha256_file(p)


def test_evaluate_run_and_the_sealed_test_is_scored_once(tmp_path, monkeypatch):
    t = _with_embers(8)
    pts = pd.concat([_preds(t), _light(list(range(0, 160)))], ignore_index=True)
    run = _hp_run(tmp_path, pts, rejected_ids=(900,))
    proto, sha = _protocol(tmp_path, t)
    with pytest.raises(E.ProtocolError, match="allow-dirty"):
        E.evaluate_run(proto, sha, run, require_clean=False)             # a sealed protocol has no override
    monkeypatch.setattr(E, "git_clean", lambda p: True)
    res = E.evaluate_run(proto, sha, run, tmp_path / "out" / "eval.json")
    tl = res["track_level"]
    assert res["source"] == "high_precision" and tl["counts"]["tp"] == 8 and tl["counts"]["false"] == 0
    assert tl["precision"]["value"] == 1.0 and res["frame_level"]["r3px"]["tp"] == 48
    assert res["run"]["method"] == "accept_all" and res["run"]["profile"] == "file_native"
    assert res["run"]["status"] == "ok" and len(res["run"]["hp_summary_sha256"]) == 64
    assert res["run"]["scorer"]["overlay_sha256"] == "ef" * 32
    assert json.loads((tmp_path / "out" / "eval.json").read_text())["protocol"]["sha256"] == sha
    local, central = E.lock_paths(E.load_protocol(proto, sha))
    assert central == tmp_path / "project_locks" / f"{sha}.json"
    for lock in (local, central):
        rec = json.loads(lock.read_text())
        assert rec["status"] == "scored" and rec["protocol_sha256"] == sha and rec["result_sha256"]
    with pytest.raises(E.ProtocolError, match="scored already"):
        E.evaluate_run(proto, sha, run)
    # A copy of the same sealed protocol in another folder is refused too.
    other = tmp_path / "copy"
    other.mkdir()
    shutil.copy(proto, other / "protocol.json")
    shutil.copy(tmp_path / "truth.json", other / "truth.json")
    assert sha256_file(other / "protocol.json") == sha
    with pytest.raises(E.ProtocolError, match="scored already"):
        E.evaluate_run(other / "protocol.json", sha, run)
    assert not (other / E.LOCK_NAME).exists()


def test_protocol_refusals(tmp_path, monkeypatch):
    t = _with_embers(2)
    run = _hp_run(tmp_path, _preds(t))
    proto, sha = _protocol(tmp_path, t, sealed=False)
    with pytest.raises(E.ProtocolError, match="not the pinned"):
        E.load_protocol(proto, "0" * 64, require_clean=False)
    with pytest.raises(E.ProtocolError, match="must be given"):
        E.load_protocol(proto, None, require_clean=False)
    with pytest.raises(E.ProtocolError, match="not in a git working tree"):
        E.load_protocol(proto, sha)                        # the test folder is not a git checkout
    monkeypatch.setattr(E, "git_clean", lambda p: False)
    with pytest.raises(E.ProtocolError, match="not committed or changed"):
        E.evaluate_run(proto, sha, run)
    monkeypatch.setattr(E, "git_clean", lambda p: True)
    assert E.evaluate_run(proto, sha, run)["track_level"]["counts"]["tp"] == 2
    assert not (tmp_path / E.LOCK_NAME).exists()          # not sealed: no lock
    # A changed truth file, a run of another video and an edited protocol are refused.
    (tmp_path / "truth.json").write_text(json.dumps({**t, "windows": t["windows"][:1]}))
    with pytest.raises(E.ProtocolError, match="truth's SHA-256"):
        E.evaluate_run(proto, sha, run)
    (tmp_path / "x").mkdir()
    proto2, sha2 = _protocol(tmp_path / "x", t, sealed=True)
    run2 = _hp_run(tmp_path / "x", _preds(t), video_sha="ef" * 32)
    with pytest.raises(E.ProtocolError, match="another video"):
        E.evaluate_run(proto2, sha2, run2)
    late = tmp_path / "x" / "late"
    run3 = _hp_run(late, _preds(t))
    (run3 / "summary.json").write_text(json.dumps({"input": {"sha256": VIDEO_SHA, "segment_s": [2.0, None]}}))
    with pytest.raises(E.ProtocolError, match="frame indices differ"):
        E.evaluate_run(proto2, sha2, run3)
    (run3 / "summary.json").write_text(json.dumps({"input": {"sha256": VIDEO_SHA, "roi_px": [0, 0, 320, 240]}}))
    with pytest.raises(E.ProtocolError, match="ROI"):
        E.evaluate_run(proto2, sha2, run3)
    # Frames the run names otherwise, or does not have, are refused before the sealed test is used.
    (run3 / "summary.json").write_text(json.dumps({"input": {"sha256": VIDEO_SHA}}))
    fr = pd.read_parquet(run3 / "frames.parquet")
    fr.assign(t=fr["t"] + 1.0 / 60).to_parquet(run3 / "frames.parquet", index=False)
    with pytest.raises(E.ProtocolError, match="name frames differently"):
        E.evaluate_run(proto2, sha2, run3)
    fr[fr["frame"] != 21].to_parquet(run3 / "frames.parquet", index=False)
    with pytest.raises(E.ProtocolError, match="frame 21 is not in the run"):
        E.evaluate_run(proto2, sha2, run3)
    fr.to_parquet(run3 / "frames.parquet", index=False)
    # A run of another method, profile, or one whose verifier was unavailable.
    (tmp_path / "y").mkdir()
    proto4, sha4 = _protocol(tmp_path / "y", t, sealed=True, method="rules", profile="file_native")
    with pytest.raises(E.ProtocolError, match="method 'rules'"):
        E.evaluate_run(proto4, sha4, run3)
    run5 = _hp_run(tmp_path / "y", _preds(t), method="rules", profile="live_downscaled")
    with pytest.raises(E.ProtocolError, match="profile 'file_native'"):
        E.evaluate_run(proto4, sha4, run5)
    run6 = _hp_run(tmp_path / "y" / "u", _preds(t), method="rules", hp_status="unavailable")
    with pytest.raises(E.ProtocolError, match="not spent"):
        E.evaluate_run(proto4, sha4, run6)
    for d in (tmp_path / "x", tmp_path / "y"):
        assert not (d / E.LOCK_NAME).exists()              # refused before the sealed test was used
    assert not (tmp_path / "project_locks").exists()
    proto2.write_text(proto2.read_text().replace('"test"', '"edited"'))
    with pytest.raises(E.ProtocolError, match="not the pinned"):
        E.evaluate_run(proto2, sha2, run2)


def test_unsealed_unavailable_run_is_scored_with_a_note(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "git_clean", lambda p: True)
    t = _with_embers(2)
    run = _hp_run(tmp_path, _preds(t).iloc[:0], hp_status="unavailable", events=_events([]))
    proto, sha = _protocol(tmp_path, t, sealed=False)
    res = E.evaluate_run(proto, sha, run)
    assert res["track_level"]["precision"]["value"] is None and not res["capability_passed"]
    assert any("unavailable" in n for n in res["notes"])


def test_control_accepted_then_revoked_light_is_a_false_accepted_track(tmp_path):
    """A still light accepted and later flagged static (revoked) was drawn while accepted: it is
    a false accepted track, and the variant without revoked tracks is reported next to it."""
    t = _with_embers(4)
    pts = pd.concat([_preds(t), _light(list(range(0, 80)))], ignore_index=True)
    preds = E.load_predictions(_hp_run(tmp_path, pts, revoked_ids=(900,), revoked_at={900: 40 / FPS}))
    assert preds["revoked_ids"] == {900}
    # Drawn until its revocation, as a legacy static track until its flag frame.
    assert sorted(preds["points"].loc[preds["points"]["track_id"] == 900, "frame"]) == list(range(40))
    res = E.evaluate(t, preds, {"targets": {"precision": 0.95}})
    tl = res["track_level"]
    assert tl["counts"]["false"] == 1 and tl["counts"]["revoked_judged"] == 1 and tl["counts"]["revoked_false"] == 1
    assert tl["precision"]["value"] == pytest.approx(0.8) and not res["capability_passed"]
    assert tl["without_revoked"]["precision"]["value"] == 1.0 and tl["without_revoked"]["counts"]["false"] == 0
    # Revoked before it had two points in the window's box: never judged there.
    (tmp_path / "early").mkdir()
    early = E.load_predictions(_hp_run(tmp_path / "early", pts, revoked_ids=(900,), revoked_at={900: 1 / FPS}))
    assert sorted(early["points"].loc[early["points"]["track_id"] == 900, "frame"]) == [0]
    tl = E.evaluate(t, early, {"targets": {"precision": 0.95}})["track_level"]
    assert tl["counts"]["false"] == 0 and tl["counts"]["revoked_judged"] == 0
    # A revoked track needs its revocation time.
    (tmp_path / "nt").mkdir()
    nt = _hp_run(tmp_path / "nt", pts, revoked_ids=(900,), revoked_at={900: 1 / FPS})
    dec = pd.read_parquet(nt / "high_precision" / "hp_decisions.parquet")
    dec.drop(columns="t_decision").to_parquet(nt / "high_precision" / "hp_decisions.parquet", index=False)
    with pytest.raises(E.ProtocolError, match="t_decision"):
        E.load_predictions(nt)
    # A track rejected without ever being accepted is no prediction.
    (tmp_path / "r").mkdir()
    preds = E.load_predictions(_hp_run(tmp_path / "r", pts, rejected_ids=(900,)))
    assert 900 not in set(preds["points"]["track_id"]) and not preds["revoked_ids"]


@pytest.mark.parametrize("piece", ["hp_summary.json", "hp_events.parquet", "hp_frames.parquet",
                                   "frame_level/detections.parquet", "events_shape", "frames_shape", "decisions_shape"])
def test_an_incomplete_high_precision_run_is_refused(tmp_path, piece):
    t = _with_embers(2)
    run = _hp_run(tmp_path, _preds(t))
    hp = run / "high_precision"
    if piece == "events_shape":
        pd.read_parquet(hp / "hp_events.parquet").drop(columns=["x", "y"]).to_parquet(hp / "hp_events.parquet")
        what = "hp_events.parquet with track_id"
    elif piece == "frames_shape":
        f = pd.read_parquet(hp / "hp_frames.parquet")
        f.assign(motion_unsupported=f["motion_unsupported"].astype(int)).to_parquet(hp / "hp_frames.parquet")
        what = "boolean motion_unsupported"
    elif piece == "decisions_shape":
        pd.read_parquet(hp / "hp_decisions.parquet").drop(columns="revoked").to_parquet(hp / "hp_decisions.parquet")
        what = "revoked"
    else:
        (hp / piece).unlink()
        what = piece
    with pytest.raises(E.ProtocolError, match=what):
        E.load_predictions(run)


def test_camera_motion_frames_leave_their_windows_out_of_the_rates(tmp_path):
    t = _with_embers(4)
    pts = pd.concat([_preds(t), _light(list(range(0, 80)), xy=(260.0, 70.0))], ignore_index=True)   # in w002
    w2 = t["windows"][2]["frames"]
    preds = E.load_predictions(_hp_run(tmp_path, pts, unsupported=w2[2:4]))
    assert preds["unsupported_frames"] == set(w2[2:4])
    tl = E.evaluate(t, preds)["track_level"]
    assert tl["counts"]["windows_supported"] == 3 and tl["rates"]["supported_minutes"] == pytest.approx(MINUTES4 * 3 / 4)
    assert tl["counts"]["false"] == 1 and tl["counts"]["unique_false_tracks"] == 0
    assert tl["rates"]["false_tracks_per_min"]["value"] == 0.0


def test_legacy_predictions_keep_static_tracks_until_their_flag(tmp_path):
    from wfglink.config import load_config
    from wfglink.outputs.process import _legacy_cfg
    from wfglink.provenance import sha256_json
    from wfglink.verify.audit import static_flag_frames

    run = tmp_path / "legacy"
    run.mkdir()
    cfg = load_config()
    n = 60
    rng = np.random.default_rng(0)
    rows = []
    for f in range(n):
        rows.append({"track_id": 1, "frame": f, "x_meas": 10.0 + 4 * f, "y_meas": 20.0, "static": False,
                     "coasted": f == 7})
        rows.append({"track_id": 2, "frame": f, "x_meas": 50 + rng.normal(0, 0.2), "y_meas": 60 + rng.normal(0, 0.2),
                     "static": True, "coasted": False})
    rows += [{"track_id": 3, "frame": f, "x_meas": 90.0, "y_meas": 90.0, "static": True, "coasted": False}
             for f in (5, 6)]                                # static, but too short for the replay to place
    tp = pd.DataFrame(rows).assign(t=lambda d: d["frame"] / FPS, length=0.0)
    tp["x"], tp["y"] = tp["x_meas"], tp["y_meas"]
    tp.to_parquet(run / "track_points.parquet", index=False)
    pd.DataFrame({"frame": np.arange(n), "t": np.arange(n) / FPS, "duplicate": False}).to_parquet(
        run / "frames.parquet", index=False)
    pd.DataFrame({"track_id": [1, 2, 3], "crossings_pos": [1, 0, 0], "crossings_neg": [1, 0, 0]}).to_parquet(
        run / "tracks.parquet", index=False)
    pd.DataFrame({"frame": [0, 1], "x": [1.0, 2.0], "y": [1.0, 1.0]}).to_parquet(run / "detections.parquet", index=False)
    summary = {"input": {"sha256": VIDEO_SHA, "fps": FPS}, "config_sha256": sha256_json(_legacy_cfg(cfg))}
    (run / "summary.json").write_text(json.dumps(summary))
    p = E.load_predictions(run, cfg)
    flag = static_flag_frames(tp, cfg, FPS, 0.0, (np.arange(n), np.arange(n) / FPS))
    assert 2 in flag and 0 < flag[2] < n and 3 not in flag
    got = p["points"]
    assert p["source"] == "legacy" and set(got["track_id"]) == {1, 2}
    assert len(got[got["track_id"] == 1]) == n - 1                                  # its coasted frame left out
    assert sorted(got.loc[got["track_id"] == 2, "frame"]) == list(range(flag[2]))   # drawn until its flag
    info = p["run_info"]
    assert info["config_matches_run"] is True and info["method"] == "legacy" and info["profile"] is None
    assert (info["static_tracks"], info["static_kept_until_flag"], info["static_left_out"]) == (2, 1, 1)
    assert p["crossings"] is None and len(p["detections"]) == 2
    summary["config_sha256"] = "other"
    (run / "summary.json").write_text(json.dumps(summary))
    p = E.load_predictions(run, cfg)
    assert p["run_info"]["config_matches_run"] is False and any("not the run's" in x for x in p["notes"])


def test_git_clean_on_the_repository():
    from wfglink import PROJECT_ROOT

    committed = PROJECT_ROOT / "configs" / "default.yaml"
    state = E.git_clean(committed)
    if state is None:
        pytest.skip("the project is not a git checkout")
    assert state is True                                     # default.yaml is committed and never edited here
    runs = PROJECT_ROOT / "results" / "runs"
    if not runs.is_dir():
        pytest.skip("no results/runs folder")
    import tempfile

    with tempfile.NamedTemporaryFile(dir=runs, suffix=".json") as f:
        assert E.git_clean(f.name) is False                  # an ignored, untracked path


# End to end on a processed clip ------------------------------------------------------------------

@pytest.fixture(scope="module")
def processed(tmp_path_factory):
    """A dots clip processed with --high-precision accept_all, blind windows of it, and labels
    written from the clip's known dot positions."""
    from dots_clip import dots_clip

    from wfglink.cli import main
    from wfglink.verify import truth as T
    from wfglink.verify import windows as W

    d = tmp_path_factory.mktemp("verify_e2e")
    clip = d / "dots.mp4"
    grid = [(20 + 60 * i, 20 + 50 * j, 3, 2) for i in range(5) for j in range(4)]
    dots = dots_clip(clip, dots=grid)
    assert main(["process", str(clip), "--out", str(d / "run"), "--no-overlay", "--high-precision", "accept_all"]) == 0
    W.make_windows(clip, d / "windows", n=6, k=6, seed=2, tile_px=64)
    man = W.read_manifest(d / "windows")
    rows = []
    for _, w in man.iterrows():
        n = 0
        for k, f in enumerate(w["frames"]):
            p = dots[f] - [w["x0"], w["y0"]]
            for e, (x, y) in enumerate(p):
                if -0.5 <= x < w["w"] - 0.5 and -0.5 <= y < w["h"] - 0.5:
                    rows.append((w["window_id"], k, x, y, 1.0, str(e), "s", ""))
                    n += 1
        if not n:
            rows.append((w["window_id"], np.nan, np.nan, np.nan, np.nan, None, "", "none"))
    labels = pd.DataFrame(rows, columns=W.LABEL_COLUMNS)
    rec = T.merge_truth(d / "windows", labels, labels)
    (d / "proto").mkdir()
    T.write_truth(rec, d / "proto" / "truth.json")
    return {"dir": d, "run": d / "run", "truth": rec}


def test_end_to_end_on_a_processed_clip(processed):
    d = processed["dir"]
    truth = processed["truth"]
    assert truth["totals"]["observable_tracks"] >= 3 and not truth["warnings"]
    p = d / "proto" / "protocol.json"
    p.write_text(json.dumps({"schema_version": 1, "name": "e2e", "sealed": False, "method": "accept_all",
                             "profile": "file_native",
                             "truth": {"path": "truth.json", "sha256": sha256_file(d / "proto" / "truth.json")},
                             "targets": {"precision": 0.5}}))
    res = E.evaluate_run(p, sha256_file(p), processed["run"], d / "eval.json", require_clean=False)
    tl, fl = res["track_level"], res["frame_level"]["r3px"]
    assert res["source"] == "high_precision" and res["run"]["method"] == "accept_all" and res["run"]["status"] == "ok"
    assert tl["counts"]["truth_observable"] == truth["totals"]["observable_tracks"]
    assert tl["precision"]["value"] == 1.0 and tl["recall"]["value"] == 1.0 and tl["counts"]["false"] == 0
    assert fl["tp"] > 0 and fl["fp"] == 0
    assert tl["rates"]["supported_minutes"] > 0 and tl["rates"]["false_crossings_per_min"]["value"] == 0.0
    # accept_all predicts the legacy tracks point for point (the same run's legacy tables, read alone).
    legacy = d / "legacy_only"
    shutil.copytree(processed["run"], legacy, ignore=shutil.ignore_patterns("high_precision"))
    key = ["track_id", "frame"]
    a, b = E.load_predictions(processed["run"])["points"], E.load_predictions(legacy)["points"]
    assert E.load_predictions(legacy)["source"] == "legacy" and len(a) > 0
    assert a[key].sort_values(key).reset_index(drop=True).equals(b[key].sort_values(key).reset_index(drop=True))
