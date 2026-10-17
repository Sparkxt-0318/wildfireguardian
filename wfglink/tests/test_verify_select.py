"""Selection under protocol amendment 2: reviewed precision, proposal retention, every branch."""
import importlib.util
import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wfglink.provenance import sha256_file
from wfglink.verify.calibrate import (ACCEPTED_COLUMNS, REVIEWED_RULE, accepted_rows_of, cluster_bootstrap_precision,
                                      review_counts, reviewed_metrics, select_reviewed)

ROOT = Path(__file__).resolve().parents[1]


def _pt(name, family, recall=None, delay=0.1):
    return {"name": name, "family": family, "recall": recall, "median_confirmation_delay_s": delay,
            "available": True, "seed": 0, "q": 0.01 if family == "rules" else None,
            "threshold": None if family == "rules" else 0.9}


def _rev(t, f, a=0, u=0, accepted=None, minutes=10.0):
    shown = t + f + a + u
    return reviewed_metrics({"true": t, "false": f, "ambiguous": a, "unresolved": u},
                            accepted if accepted is not None else shown, minutes)


def test_review_counts_maps_categories_and_unresolved():
    c = review_counts(["ember", "reflection", "codec_artifact", "faint_possible_ember", "unclear", None, "ember"])
    assert c == {"true": 2, "false": 2, "ambiguous": 2, "unresolved": 1}
    assert review_counts(["true_ember", "", "  ", None]) == {"true": 1, "false": 0, "ambiguous": 0, "unresolved": 3}
    for bad in ("smoke", "Ember", "false"):
        with pytest.raises(ValueError, match="not one of the protocol's categories"):
            review_counts(["ember", bad])


def test_reviewed_metrics_primary_excludes_ambiguous_and_unresolved():
    m = _rev(18, 2, a=3, u=1, accepted=48, minutes=4.0)
    assert m["precision"] == pytest.approx(0.9)
    assert m["precision_optimistic"] == pytest.approx(21 / 23)
    assert m["precision_pessimistic"] == pytest.approx(18 / 24)      # unresolved and ambiguous count against
    assert m["inclusion_probability"] == pytest.approx(24 / 48)
    assert m["false_per_supported_min"] == pytest.approx((2 / 0.5) / 4.0)
    assert m["precision_lower95"] < 0.9 and m["precision_defined"]
    assert m["true_yield_per_supported_min"] == pytest.approx(0.9 * 48 / 4.0)


def test_lower_bound_of_all_true():
    m = _rev(20, 0)
    assert m["precision"] == 1.0 and m["precision_lower95"] == pytest.approx(0.05 ** (1 / 20))
    assert not _rev(5, 0)["precision_defined"]        # fewer than 10 true + false: undefined


def test_selects_highest_retention_among_precise_points_with_family_ties():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal"),
           _pt("patch_a", "patch"), _pt("rules_loose", "rules")]
    rev = {"accept_all": _rev(10, 90, accepted=1000), "rules_a": _rev(20, 0, accepted=100),
           "temporal_a": _rev(20, 0, accepted=100), "patch_a": _rev(20, 0, accepted=100),
           "rules_loose": _rev(18, 2, accepted=400)}
    s = select_reviewed(pts, rev, observable=3)
    assert s["status"] == "SELECTED" and s["point"]["name"] == "rules_a"      # tie on retention: rules first
    assert "proposal retention" in s["recall_basis"] and "not ember recall" in s["recall_basis"]
    assert s["branch"] == "reviewed precision >= 0.99: highest proposal retention" and "recall" not in s["branch"]
    assert s["point"]["proposal_retention"] == pytest.approx((1.0 * 100 / 10) / (0.1 * 1000 / 10))
    assert s["proposal_retention_measurable"] and not s["target_missed"] and "best_available" not in s


def test_window_recall_ranks_when_enough_observable_truth():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules", recall=0.2), _pt("patch_a", "patch", recall=0.6)]
    rev = {"accept_all": _rev(10, 90), "rules_a": _rev(20, 0, accepted=500), "patch_a": _rev(20, 0, accepted=50)}
    s = select_reviewed(pts, rev, observable=25)
    assert s["recall_basis"].startswith("window recall") and s["point"]["name"] == "patch_a"
    assert s["branch"] == "reviewed precision >= 0.99: highest window recall" and s["ranking_basis"] == "window recall"
    assert "proposal retention" not in s["branch"]


def test_no_precise_point_takes_highest_precision_with_retention_half():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal")]
    rev = {"accept_all": _rev(10, 10, accepted=100), "rules_a": _rev(17, 3, accepted=60),
           "temporal_a": _rev(19, 1, accepted=5)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"]["name"] == "rules_a" and "proposal retention >= 0.5" in s["branch"] and s["target_missed"]
    assert "recall" not in s["branch"]


def test_no_precise_point_takes_highest_precision_with_window_recall_half():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules", recall=0.4),
           _pt("temporal_a", "temporal", recall=0.7), _pt("patch_a", "patch", recall=0.9)]
    rev = {"accept_all": _rev(10, 10), "rules_a": _rev(19, 1), "temporal_a": _rev(17, 3), "patch_a": _rev(15, 5)}
    s = select_reviewed(pts, rev, observable=30)
    assert s["point"]["name"] == "temporal_a" and "window recall >= 0.5" in s["branch"] and s["target_missed"]
    assert "proposal retention" not in s["branch"]


def test_no_point_with_retention_half_takes_highest_defined_precision():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal")]
    rev = {"accept_all": _rev(10, 10, accepted=1000), "rules_a": _rev(15, 5, accepted=20),
           "temporal_a": _rev(18, 2, accepted=20)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"]["name"] == "temporal_a" and s["status"] == "SELECTED" and s["target_missed"]
    assert "nor proposal retention >= 0.5" in s["branch"] and "recall" not in s["branch"]


def test_retention_is_not_measurable_without_defined_accept_all_precision():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("temporal_a", "temporal")]
    rev = {"accept_all": _rev(6, 2, accepted=500), "rules_a": _rev(17, 3, accepted=200),
           "temporal_a": _rev(18, 2, accepted=20)}
    s = select_reviewed(pts, rev, observable=0)
    assert not s["proposal_retention_measurable"] and "not measurable" in s["recall_basis"]
    assert all(x["proposal_retention"] is None for x in s["rows"])
    assert s["point"]["name"] == "temporal_a" and s["status"] == "SELECTED" and s["target_missed"]
    assert "proposal retention is not measurable" in s["branch"] and "recall" not in s["branch"]
    # At reviewed precision >= 0.99 the tie order decides; window recall does not need accept_all.
    rev.update(rules_a=_rev(20, 0, accepted=5), temporal_a=_rev(30, 0, accepted=500))
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"]["name"] == "rules_a" and "tie order decides" in s["branch"] and not s["target_missed"]
    pts[2]["recall"] = 0.8
    s = select_reviewed(pts, rev, observable=20)
    assert s["point"]["name"] == "temporal_a" and s["branch"].endswith("highest window recall")


def test_no_defined_precision_is_insufficient_evidence():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules"), _pt("patch_a", "patch")]
    rev = {"accept_all": _rev(10, 10), "rules_a": _rev(3, 0), "patch_a": _rev(1, 1)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["status"] == "INSUFFICIENT_EVIDENCE" and s["point"] is None and s["target_missed"]
    assert s["best_available"]["name"] == "rules_a" and "most reviewed true tracks" in s["branch"]
    assert "recall" not in s["branch"]
    rev["patch_a"] = _rev(3, 2)                        # equal true tracks: the family order breaks the tie
    assert select_reviewed(pts, rev, observable=0)["best_available"]["name"] == "rules_a"
    s = select_reviewed([_pt("accept_all", "accept_all")], {"accept_all": _rev(20, 0)}, observable=0)
    assert s["point"] is None and s["best_available"] is None and s["status"] == "INSUFFICIENT_EVIDENCE"


def test_accept_all_is_never_selected():
    pts = [_pt("accept_all", "accept_all"), _pt("rules_a", "rules")]
    rev = {"accept_all": _rev(20, 0, accepted=100), "rules_a": _rev(2, 0)}
    s = select_reviewed(pts, rev, observable=0)
    assert s["point"] is None and s["best_available"]["name"] == "rules_a" and s["status"] == "INSUFFICIENT_EVIDENCE"
    assert all(not math.isnan(x["reviewed"]["accepted_tracks"]) for x in s["rows"])


def test_recording_cluster_bootstrap_of_reviewed_precision():
    counts = [(5, 0), (0, 0), (3, 1)]
    b = cluster_bootstrap_precision(counts)
    assert b["replicates"] == 2000 and b["seed"] == 0 and b["recordings"] == 3 and b["cluster"] == "recording"
    c = np.array(counts)
    idx = np.random.default_rng(0).integers(0, 3, size=(2000, 3))
    t, f = c[idx, 0].sum(1), c[idx, 1].sum(1)
    ok = t + f > 0
    assert b["undefined"] == int((~ok).sum()) > 0 and b["defined"] + b["undefined"] == 2000
    p = t[ok] / (t[ok] + f[ok])
    assert b["interval95"] == pytest.approx([np.percentile(p, 2.5), np.percentile(p, 97.5)])
    assert b["lower05"] == pytest.approx(np.percentile(p, 5)) and b["interval95"][0] <= b["lower05"] <= 1.0
    assert cluster_bootstrap_precision(counts) == b                       # seeded: reproducible
    none = cluster_bootstrap_precision([])
    assert none["undefined"] == 2000 and none["interval95"] is None and none["lower05"] is None
    assert cluster_bootstrap_precision([(0, 0)])["defined"] == 0


def test_accepted_rows_carry_supported():
    d = pd.DataFrame({"track_id": [1, 2, 3], "state": ["method_accepted", "rejected", "rejected"],
                      "revoked": [False, True, False], "frame_accept": [5, 12, 20], "t_accept": [0.2, 0.5, 0.8],
                      "t_confirm": [0.2, 0.4, 0.8]})
    base = {"point_id": "rules_q0.01", "family": "rules", "seed": None, "param": 0.01, "recording": "recA",
            "run_dir": "runs/recA_dump"}
    rows = accepted_rows_of(d, {12, 13}, base)
    assert [(r["track_id"], r["supported"]) for r in rows] == [(1, True), (2, False)]
    assert set(rows[0]) == set(ACCEPTED_COLUMNS) and rows[1]["revoked"]
    assert accepted_rows_of(d.iloc[0:0], set(), base) == []


# Selection.json: the rule, the refusal in calibrate, provenance ---------------------------------

def test_check_selection_requires_the_reviewed_rule_under_precision_review(tmp_path):
    from wfglink.verify.evaluate import ProtocolError, check_selection

    sel = {"status": "SELECTED", "family": "rules", "profile": "file_native"}
    p = tmp_path / "selection.json"
    p.write_text(json.dumps(sel), encoding="utf-8")
    info = {"method": "rules", "profile": "file_native", "scorer": {}}
    amended = {"precision_review": {"why": "amendment 2"}}
    assert check_selection(p, info, require_clean=False)["family"] == "rules"       # no precision_review: as before
    assert check_selection(p, info, False, {"targets": {}})["family"] == "rules"
    with pytest.raises(ProtocolError, match="amendment_2_reviewed_precision"):
        check_selection(p, info, False, amended)
    p.write_text(json.dumps({**sel, "rule": "precision >= 0.99: highest recall"}), encoding="utf-8")
    with pytest.raises(ProtocolError, match="only a selection.json of verify select"):
        check_selection(p, info, False, amended)
    p.write_text(json.dumps({**sel, "rule": REVIEWED_RULE}), encoding="utf-8")
    assert check_selection(p, info, False, amended)["family"] == "rules"


def _protocol(d: Path, amended=True):
    d.mkdir(parents=True, exist_ok=True)
    p = d / "protocol.json"
    body = {"schema_version": 1, "name": "select_test", "sealed": False, "truth": [], "targets": {"precision": 0.99}}
    if amended:
        body["precision_review"] = {"why": "amendment 2"}
    p.write_text(json.dumps(body), encoding="utf-8")
    return p, sha256_file(p)


def test_calibrate_refuses_write_config_under_precision_review(tmp_path, monkeypatch):
    from wfglink.verify import evaluate as E
    from wfglink.verify.calibrate import calibrate
    from wfglink.verify.cli_tools import main

    monkeypatch.setattr(E, "git_clean", lambda p: True)
    proto, sha = _protocol(tmp_path / "proto")
    with pytest.raises(E.ProtocolError, match="precision_review.*verify select.*selection_preview.json only"):
        calibrate(tmp_path / "no_dataset", tmp_path / "no_models", [], tmp_path / "cal", {}, protocol=proto,
                  protocol_sha256=sha, write_overlay=True)
    assert not (tmp_path / "cal").exists()                    # refused before anything is computed or written
    with pytest.raises(SystemExit, match="verify calibrate: .*verify select"):
        main(["verify", "calibrate", "--dataset", str(tmp_path / "no_dataset"), "--recording", "run", "truth.json",
              "--out", str(tmp_path / "cal"), "--protocol", str(proto), "--sha256", sha, "--write-config"])
    # Without precision_review the refusal does not apply (the run then fails on the missing dataset).
    proto2, sha2 = _protocol(tmp_path / "proto2", amended=False)
    with pytest.raises(FileNotFoundError):
        calibrate(tmp_path / "no_dataset", tmp_path / "no_models", [], tmp_path / "cal2", {}, protocol=proto2,
                  protocol_sha256=sha2, write_overlay=True)


def _calibration(tmp_path: Path, proto_sha: str) -> Path:
    cal = tmp_path / "cal"
    cal.mkdir()
    table = cal / "calibration_accepted.parquet"
    pd.DataFrame({"point_id": ["accept_all", "rules_q0.01"], "recording": ["recA", "recA"], "track_id": [1, 1],
                  "supported": [True, True]}).to_parquet(table, index=False)
    pts = [{**_pt("accept_all", "accept_all"), "truth_observable": 3, "precision": None, "accepted_tracks": 40},
           {**_pt("rules_q0.01", "rules"), "seed": None, "truth_observable": 3, "precision": None,
            "accepted_tracks": 20}]
    cp = {"schema_version": 1, "profile": "file_native", "protocol": {"sha256": proto_sha}, "development": False,
          "points": pts, "accepted_tracks_table": {"path": str(table), "sha256": sha256_file(table)}}
    (cal / "calibration_points.json").write_text(json.dumps(cp), encoding="utf-8")
    (cal / "rules_candidates.json").write_text(json.dumps({"candidates": {}}), encoding="utf-8")
    return cal


def test_reviewed_selection_checks_the_review_provenance_and_records_the_rule(tmp_path):
    from wfglink.verify.calibrate import write_reviewed_selection
    from wfglink.verify.config import OVERLAY
    from wfglink.verify.evaluate import ProtocolError

    proto, sha = _protocol(tmp_path / "proto")
    cal = _calibration(tmp_path, sha)
    acc_sha = sha256_file(cal / "calibration_accepted.parquet")
    rp = tmp_path / "review_points.json"

    def review(points, **kw):
        rp.write_text(json.dumps({"population": "calibration", "accepted_sha256": acc_sha, "points": points, **kw}),
                      encoding="utf-8")
        return rp

    def run(**kw):
        return write_reviewed_selection(cal, rp, {}, proto, sha, require_clean=False, **kw)

    good = {"accept_all": _rev(10, 10, accepted=40), "rules_q0.01": _rev(20, 0, accepted=20)}
    for kw, why in (({"population": "test"}, "calibration review only"),
                    ({"population": None}, "calibration review only"),
                    ({"accepted_sha256": "0" * 64}, "accepted_tracks_table.sha256"),
                    ({"accepted_sha256": None}, "accepted_tracks_table.sha256")):
        review(good, **kw)
        with pytest.raises(ProtocolError, match=why):
            run()
    review(good)
    rec = run()
    assert rec["status"] == "SELECTED" and rec["family"] == "rules" and rec["rule"] == REVIEWED_RULE
    assert rec["review_points_sha256"] == sha256_file(rp) and rec["accepted_sha256"] == acc_sha
    assert rec["review_population"] == "calibration" and "best_available" not in rec
    on_disk = json.loads((cal / "selection_reviewed_preview.json").read_text())
    assert on_disk["rule"] == REVIEWED_RULE and not (cal / "selection.json").exists()
    # No defined precision: best_available is written, and nothing is pinned for it.
    review({"accept_all": _rev(10, 10, accepted=40), "rules_q0.01": _rev(4, 0, accepted=20)})
    ov = tmp_path / "overlay.yaml"
    shutil.copy(OVERLAY, ov)
    before = ov.read_text()
    rec = run(write_overlay=True, overlay=ov)
    assert rec["status"] == "INSUFFICIENT_EVIDENCE" and rec["selected"] is None and "family" not in rec
    assert rec["best_available"]["name"] == "rules_q0.01" and rec["best_available"]["reviewed"]["true"] == 4
    assert rec["pinned"] == {} and rec["family_bests"]["rules"] is None and ov.read_text() == before
    assert json.loads((cal / "selection.json").read_text())["best_available"]["name"] == "rules_q0.01"


# scripts/precision_review.py on small synthetic runs ----------------------------------------

def _review_module(runs: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("precision_review_under_test", ROOT / "scripts" / "precision_review.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "RUNS", runs)
    return m


def _synthetic_run(runs: Path, rec: str, t, unsupported, checkpoint, no_checkpoint=(), tracking_only=False):
    """A dump run folder with what the review reads: summaries, hp_frames (times and camera-motion
    flags), hp_windows (tracks in checkpoint at their frame, others below min_hits) and track points."""
    d = runs / f"{rec}_dump"
    (d / "high_precision").mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps({"metrics_scope": "tracking_only" if tracking_only else "all"}))
    (d / "high_precision" / "hp_summary.json").write_text(json.dumps(
        {"status": "not_real_time" if tracking_only else "ok"}))
    frames = np.arange(len(t))
    pd.DataFrame({"frame": frames, "t": np.asarray(t, float), "motion_unsupported": np.isin(frames, list(unsupported))}
                 ).to_parquet(d / "high_precision" / "hp_frames.parquet", index=False)
    win = [(k, f, 4) for k, f in checkpoint.items()] + [(k, f, 2) for k, f in dict(no_checkpoint).items()]
    pd.DataFrame({"key": [k for k, _, _ in win], "t": [float(t[f]) for _, f, _ in win], "frame": [f for _, f, _ in win],
                  "n_hits": [n for _, _, n in win]}).to_parquet(d / "high_precision" / "hp_windows.parquet", index=False)
    pts = [{"track_id": k, "frame": f, "t": float(t[f]), "x": 10.0 + k, "y": 20.0, "x_meas": 10.0 + k, "y_meas": 20.0}
           for k, f in {**checkpoint, **dict(no_checkpoint)}.items()]
    pd.DataFrame(pts or None, columns=["track_id", "frame", "t", "x", "y", "x_meas", "y_meas"]).to_parquet(
        d / "track_points.parquet", index=False)


def _acc_rows(point, family, rec, tracks):
    return [{"point_id": point, "family": family, "recording": rec, "track_id": k, "frame_accept": f}
            for k, f in tracks.items()]


def _write_review(out: Path, path: Path):
    key = json.loads((out / "key.json").read_text())
    cats = {0: "true_ember", 1: "reflection"}                       # true_ember is read as ember
    final = [{"item_id": i, "final": {"category": "ember" if v["role"] == "decoy" else cats[v["track_id"] % 2]}}
             for i, v in key.items()]
    path.write_text(json.dumps({"final": final}))
    return key


@pytest.fixture()
def review_runs(tmp_path):
    runs = tmp_path / "runs"
    # recA: 100 frames at 25 fps, camera motion at frames 50..59; recB: uneven frame times, motion at frame 2.
    a_tracks = {k: 5 * k for k in range(1, 13)}                     # frames 5..60: 10 and 11 in motion time
    _synthetic_run(runs, "recA", [0.04 * f for f in range(100)], range(50, 60),
                   {**a_tracks, **{k: 70 + k for k in range(20, 26)}}, no_checkpoint={30: 80, 31: 81})
    _synthetic_run(runs, "recB", [0.0, 0.1, 0.3, 0.6, 1.0], [2], {101: 0, 102: 2, 103: 3})
    _synthetic_run(runs, "recT", [0.0, 0.1, 0.2], [], {}, tracking_only=True)
    return runs, a_tracks


def test_precision_review_sample_and_score_on_synthetic_runs(review_runs, tmp_path, monkeypatch):
    runs, a_tracks = review_runs
    m = _review_module(runs, monkeypatch)
    rows = (_acc_rows("accept_all", "accept_all", "recA", a_tracks) +
            _acc_rows("accept_all", "accept_all", "recB", {101: 0, 102: 2, 103: 3}) +
            _acc_rows("rules_q0.01", "rules", "recA", {k: a_tracks[k] for k in (1, 2, 3, 4, 5, 6, 10)}) +
            _acc_rows("rules_q0.01", "rules", "recB", {101: 0}))
    acc = pd.DataFrame(rows)
    acc["supported"] = [not ((r == "recA" and 50 <= f < 60) or (r == "recB" and f == 2))
                        for r, f in zip(acc["recording"], acc["frame_accept"])]
    table = tmp_path / "calibration_accepted.parquet"
    acc.to_parquet(table, index=False)
    out = tmp_path / "review"
    base = ["sample", "--population", "calibration", "--accepted", str(table), "--out", str(out), "--per-point", "3",
            "--recordings", "recA", "recB", "recT"]
    assert m.main(base) == 0
    meta = json.loads((out / "sample.json").read_text())
    assert meta["accepted_sha256"] == sha256_file(table) and meta["key_sha256"] == sha256_file(out / "key.json")
    assert meta["recordings"] == ["recA", "recB", "recT"] and meta["tracking_only"] == ["recT"]
    inc = meta["inclusion"]
    assert inc["rules_q0.01"]["accepted"] == 7 and inc["rules_q0.01"]["excluded_rows"]["unsupported"] == 1
    assert inc["accept_all"]["accepted"] == 12 and inc["accept_all"]["excluded_rows"]["unsupported"] == 3
    assert inc["rules_q0.01"]["sampled"] == 3 and inc["rules_q0.01"]["probability"] == pytest.approx(3 / 7)
    key = _write_review(out, tmp_path / "review.json")
    sampled = {(v["recording"], v["track_id"]) for v in key.values() if v["role"] == "accepted"}
    assert not sampled & {("recA", 10), ("recA", 11), ("recB", 102)}           # unsupported rows are never shown
    sc = ["score", "--out", str(out), "--review", str(tmp_path / "review.json"), "--accepted", str(table)]
    assert m.main(sc) == 0
    rp = json.loads((out / "review_points.json").read_text())
    assert rp["population"] == "calibration" and rp["accepted_sha256"] == meta["accepted_sha256"]
    assert rp["key_sha256"] == meta["key_sha256"] and rp["tracking_only_recordings"] == ["recT"]
    # Interval to the next frame (the median interval for the last), motion frames left out.
    assert rp["supported_minutes"] == pytest.approx({"recA": 90 * 0.04 / 60, "recB": (0.1 + 0.2 + 0.4 + 0.25) / 60})
    assert "hp_frames.parquet" in rp["supported_minutes_source"]
    r = rp["points"]["rules_q0.01"]
    assert r["accepted_tracks"] == 7 and r["reviewed"] == 3 and r["excluded_rows"]["unsupported"] == 1
    assert r["accepted_per_supported_min"] == pytest.approx(7 / sum(rp["supported_minutes"].values()))
    assert set(r["per_recording"]) == {"recA", "recB"}
    b = r["precision_bootstrap"]
    assert b["replicates"] == 2000 and b["recordings"] == 2 and b["defined"] + b["undefined"] == 2000
    # Provenance: a changed key or accepted table is refused.
    kp = out / "key.json"
    kp.write_text(kp.read_text() + " ")
    with pytest.raises(SystemExit, match="key SHA-256"):
        m.main(sc)
    kp.write_text(kp.read_text()[:-1])
    pd.concat([acc, acc.iloc[:1]]).to_parquet(table, index=False)
    with pytest.raises(SystemExit, match="accepted table SHA-256"):
        m.main(sc)


def test_precision_review_sealed_control_counts_checkpoint_tracks_only(review_runs, tmp_path, monkeypatch):
    runs, a_tracks = review_runs
    m = _review_module(runs, monkeypatch)
    rows = (_acc_rows("accept_all", "accept_all", "recA", {**a_tracks, 30: 80, 31: 81}) +
            _acc_rows("accept_all", "accept_all", "recB", {101: 0, 102: 2, 103: 3}) +
            _acc_rows("temporal_seed0_t0.9", "temporal", "recA", {k: a_tracks[k] for k in (1, 2, 11)}))
    table = tmp_path / "test_accepted.parquet"
    pd.DataFrame(rows).to_parquet(table, index=False)                  # no supported column: read from hp_frames
    out = tmp_path / "sealed"
    assert m.main(["sample", "--population", "test", "--accepted", str(table), "--out", str(out),
                   "--recordings", "recA", "recB"]) == 0
    meta = json.loads((out / "sample.json").read_text())
    assert "hp_frames" in meta["supported_rows"]
    ctl = meta["inclusion"]["accept_all"]
    assert ctl["accepted"] == 12 and ctl["excluded_rows"] == {"not_scored_recording": 0, "unsupported": 3,
                                                              "no_checkpoint": 2}
    assert meta["inclusion"]["temporal_seed0_t0.9"]["accepted"] == 2
    _write_review(out, tmp_path / "review.json")
    assert m.main(["score", "--out", str(out), "--review", str(tmp_path / "review.json"), "--accepted",
                   str(table)]) == 0
    rp = json.loads((out / "review_points.json").read_text())
    assert rp["population"] == "test" and rp["points"]["accept_all"]["accepted_tracks"] == 12
    assert rp["points"]["accept_all"]["inclusion_probability"] == pytest.approx(1.0)
    assert rp["points"]["temporal_seed0_t0.9"]["accepted_tracks"] == 2
