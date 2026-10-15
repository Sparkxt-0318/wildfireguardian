"""Blind label tiles and scores (plan 4.5): frame naming, coordinates, protocol, bootstrap, inter-labeler F1."""
import json
import shutil

import av
import cv2
import numpy as np
import pandas as pd
import pytest
from dots_clip import dots_clip, write_clip_settings

from wfglink.cli import main
from wfglink.config import load_config
from wfglink.validate import labels as L

ROI = [40, 20, 300, 230]
START, END = 0.5, 2.5


@pytest.fixture(scope="module")
def dots(tmp_path_factory):
    """A dots clip that opens on repeated frames, processed by the `process` command with a ROI and a
    segment that starts after a seek, plus label tiles of it (8 frames to score, 2 in reserve)."""
    d = tmp_path_factory.mktemp("labels")
    clip = d / "dots.mp4"
    grid = [(20 + 50 * i, 15 + 45 * j, 4, 3) for i in range(6) for j in range(5)]
    truth = dots_clip(clip, repeat=set(range(16, 26)), dots=grid)
    cs = write_clip_settings(d / "dots.yaml", clip, roi=ROI, segments_s=[[START, END]])
    assert main(["process", str(cs), "--out", str(d / "run"), "--no-overlay"]) == 0
    L.make_tiles(cs, d / "tiles", frames=8, reserve=2, tiles_per_frame=2, tile_px=64, seed=3)
    return {"dir": d, "clip": clip, "settings": cs, "truth": truth, "run": d / "run", "tiles": d / "tiles"}


def _manifest(tiles):
    return pd.read_csv(tiles / "manifest.csv", dtype={"tile_id": str})


def _truth_labels(man: pd.DataFrame, truth, shift: int = 0, dx: float = 0.0, confidence: float = 1.0
                  ) -> pd.DataFrame:
    """Labels at the true dot centres of each tile's frame (shift: of another file frame; dx: moved
    right by this many pixels)."""
    rows = []
    for _, t in man.iterrows():
        k = int(round(t["pts_s"] * 30)) + shift
        p = truth[k] - [ROI[0] + t["x0"], ROI[1] + t["y0"]]
        p = p[(p[:, 0] >= -0.5) & (p[:, 0] < t["w"] - 0.5) & (p[:, 1] >= -0.5) & (p[:, 1] < t["h"] - 0.5)]
        rows += [{"tile_id": t["tile_id"], "x": x + dx, "y": y, "confidence": confidence, "note": ""} for x, y in p]
        if not len(p):
            rows.append({"tile_id": t["tile_id"], "x": np.nan, "y": np.nan, "confidence": np.nan, "note": "none"})
    return pd.DataFrame(rows)


def _copy_run(dots, tmp_path):
    run = tmp_path / "run"
    shutil.copytree(dots["run"], run)
    return run, json.loads((run / "summary.json").read_text())


def test_tile_frames_are_the_runs_frames(dots):
    """The frame named in the manifest is the tile's picture: decoded here linearly without a seek
    (frames named from the first one at or after the segment start), independently of FileSource.
    The run gives that frame the same index and time."""
    man = _manifest(dots["tiles"])
    frames = pd.read_parquet(dots["run"] / "frames.parquet").set_index("frame")
    assert len(man) >= 10 and (man["run_start_s"] == START).all() and man["reserve"].sum() > 0
    decoded = {}
    with av.open(str(dots["clip"])) as c:
        k = 0
        for vf in c.decode(video=0):
            if vf.time < START - 1e-6:
                continue
            if vf.time - START > END - START:
                break
            decoded[k] = (vf.time - START, vf.to_ndarray(format="bgr24")[ROI[1]:ROI[3], ROI[0]:ROI[2]])
            k += 1
    for _, t in man.iterrows():
        ft, img = decoded[int(t["frame"])]
        assert ft == pytest.approx(t["t"], abs=1e-9)
        assert frames.loc[int(t["frame"]), "t"] == pytest.approx(t["t"], abs=1e-9)
        assert not frames.loc[int(t["frame"]), "duplicate"] and frames.loc[int(t["frame"]), "ready"]
        x0, y0, w, h = (int(t[k]) for k in ("x0", "y0", "w", "h"))
        raw = cv2.imread(str(dots["tiles"] / t["raw_png"]), cv2.IMREAD_COLOR)
        assert np.array_equal(raw, img[y0:y0 + h, x0:x0 + w])
        # The enlarged PNG shows the same pixels (block corners are never on a grid line).
        png = cv2.imread(str(dots["tiles"] / t["png"]), cv2.IMREAD_COLOR)
        top, left, s = 46, 44, int(t["scale"])
        assert np.array_equal(png[top:top + h * s:s, left:left + w * s:s], raw)


def test_tile_coordinates_match_detections(dots):
    """Labels at the true dot centres match the run's detections within 0.75 px, and the same labels
    moved by 1 px, or taken from the previous frame, do not: tile coordinates and frame naming are
    those of detections.parquet to well under a pixel."""
    man = _manifest(dots["tiles"])
    res = L.score_labels(dots["tiles"], _truth_labels(man, dots["truth"]), dots["run"], match_px=0.75)
    assert res["tag"] == "agent-labeled" and res["frames"] == 8 and res["frames_target"] == 8
    assert res["tiles_scored"] == int((~man["reserve"]).sum()) and not res["warnings"]
    assert {s["reason"] for s in res["tiles_skipped"]} == {"reserve not needed (enough frames scored)"}
    assert res["tp"] > 10 and res["fp"] == 0 and res["fn"] == 0
    assert res["precision"]["value"] == 1.0 and res["recall"]["value"] == 1.0 and res["f1"]["ci"] == [1.0, 1.0]
    moved = L.score_labels(dots["tiles"], _truth_labels(man, dots["truth"], dx=1.0), dots["run"], match_px=0.75)
    assert moved["tp"] == 0
    off = L.score_labels(dots["tiles"], _truth_labels(man, dots["truth"], shift=-1), dots["run"])
    assert off["recall"]["value"] < 0.5


def test_warmup_matches_the_detector(dots):
    """make_tiles finds the first ready frame of the run without running the detector."""
    rows = L._scan(dots["clip"], START, END, tuple(ROI), load_config())
    frames = pd.read_parquet(dots["run"] / "frames.parquet")
    first_ready = float(frames.loc[frames["ready"], "t"].iloc[0])
    assert L.detector_ready_time(rows, load_config()) == pytest.approx(first_ready, abs=1e-9)
    assert [r["repeat"] for r in rows] == frames["duplicate"].tolist()   # exact repeats: the same flags
    man = _manifest(dots["tiles"])
    assert man["t"].min() >= first_ready + load_config()["labels"]["settle_s"] - 1e-9


def test_draw_order_reserve_and_check_frames(dots):
    """Tile IDs follow the random draw; the first labels.check_frames frames are marked for the second
    labeler and the frames after labels.frames are the reserve."""
    man = _manifest(dots["tiles"])
    assert man["draw"].is_monotonic_increasing and man["draw"].nunique() == 10
    assert (man["reserve"] == (man["draw"] >= 8)).all() and (man["check"] == (man["draw"] < 5)).all()
    assert not man.sort_values("draw")["frame"].drop_duplicates().is_monotonic_increasing   # random, not sorted
    rec = json.loads((dots["tiles"] / "tiles.json").read_text())
    assert rec["frames_requested"] == 8 and rec["reserve_frames"] == 2 and rec["frames_drawn"] == 10
    assert len(rec["tile_set_id"]) == 16 and rec["tile_set_id"] in (dots["tiles"] / "README.txt").read_text()


def test_tile_folder_holds_nothing_from_detections(dots, tmp_path, monkeypatch):
    """Tiles are made without a detector and without a run; the folder holds only the protocol files."""
    from wfglink.detect.candidates import Detector
    from wfglink.pipeline import Pipeline

    def boom(*a, **k):
        raise AssertionError("make_tiles must not detect")

    monkeypatch.setattr(Detector, "detect", boom)
    monkeypatch.setattr(Pipeline, "process", boom)
    out = tmp_path / "tiles"
    rec = L.make_tiles(dots["settings"], out, frames=3, reserve=0, tiles_per_frame=1, tile_px=48, seed=1)
    assert rec["tiles"] == 3
    names = {p.name for p in out.iterdir()}
    assert {"manifest.csv", "labels_template.csv", "README.txt", "tiles.json", "raw"} <= names
    for n in names - {"manifest.csv", "labels_template.csv", "README.txt", "tiles.json", "raw"}:
        assert n.startswith("t") and n.endswith(".png"), n
    assert all(p.suffix == ".png" for p in (out / "raw").iterdir())
    man = pd.read_csv(out / "manifest.csv")
    assert not {"x", "y", "area", "peak", "flux", "detections", "track_id"} & set(man.columns)
    assert list(pd.read_csv(out / "labels_template.csv").columns) == L.LABEL_COLUMNS
    assert len(pd.read_csv(out / "labels_template.csv")) == 0
    rec_keys = set(json.loads((out / "tiles.json").read_text()))
    assert not {k for k in rec_keys if "detection" in k or "track" in k}
    # A folder holding run outputs is refused, and scoring writes nothing into the tile folder.
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "detections.parquet").write_bytes(b"")
    with pytest.raises(ValueError):
        L.make_tiles(dots["settings"], tmp_path / "other", frames=1)
    before = sorted(p.name for p in dots["tiles"].rglob("*"))
    labels = dots["dir"] / "labels.csv"
    _truth_labels(_manifest(dots["tiles"]), dots["truth"]).to_csv(labels, index=False)
    assert main(["label-score", str(dots["tiles"]), "--labels", str(labels), "--run", str(dots["run"]),
                 "--out", str(dots["dir"] / "scores.json")]) == 0
    scores = json.loads((dots["dir"] / "scores.json").read_text())
    assert scores["tag"] == "agent-labeled" and len(scores["labels_sha256"]) == 64
    assert scores["tile_set_id"] == json.loads((dots["tiles"] / "tiles.json").read_text())["tile_set_id"]
    assert sorted(p.name for p in dots["tiles"].rglob("*")) == before
    with pytest.raises(SystemExit):
        main(["label-score", str(dots["tiles"]), "--labels", str(labels), "--run", str(dots["run"]),
              "--out", str(dots["tiles"] / "scores.json")])


def test_make_tiles_is_reproducible_and_keeps_an_earlier_set(dots, tmp_path):
    """The same seed gives the same tiles; an earlier tile set is replaced only with force (labels made
    on it would otherwise be scored against new tiles under the same IDs)."""
    kw = dict(frames=3, reserve=1, tiles_per_frame=1, tile_px=48)
    a = L.make_tiles(dots["settings"], tmp_path / "a", seed=5, **kw)
    b = L.make_tiles(dots["settings"], tmp_path / "b", seed=5, **kw)
    assert _manifest(tmp_path / "a").equals(_manifest(tmp_path / "b")) and a["tile_set_id"] == b["tile_set_id"]
    before = {p.name: p.read_bytes() for p in (tmp_path / "a").glob("*.*")}
    with pytest.raises(ValueError, match="already holds a tile set"):
        L.make_tiles(dots["settings"], tmp_path / "a", seed=6, **kw)
    with pytest.raises(SystemExit, match="label-tiles: .*already holds a tile set"):
        main(["label-tiles", str(dots["settings"]), "--out", str(tmp_path / "a"), "--seed", "6"])
    assert {p.name: p.read_bytes() for p in (tmp_path / "a").glob("*.*")} == before
    c = L.make_tiles(dots["settings"], tmp_path / "a", seed=6, force=True, **kw)
    assert c["tile_set_id"] != a["tile_set_id"]
    man = _manifest(tmp_path / "a")
    want = set(man["png"]) | {n for v in man["context_png"].dropna() for n in v.split(";")}
    assert {p.name for p in (tmp_path / "a").glob("t*.png")} == want         # nothing left of the old set
    assert {f"raw/{p.name}" for p in (tmp_path / "a" / "raw").iterdir()} == set(man["raw_png"])


def test_label_tiles_command_and_failures(dots, tmp_path, capsys):
    out = tmp_path / "cli"
    assert main(["label-tiles", str(dots["settings"]), "--out", str(out), "--frames", "2", "--reserve", "0",
                 "--tile-px", "48", "--tiles-per-frame", "1", "--seed", "2"]) == 0
    assert "2 tiles from 2 frames" in capsys.readouterr().out and len(_manifest(out)) == 2
    # A segment shorter than the warm-up: a one-line error, and the folder is never touched.
    short = write_clip_settings(tmp_path / "short.yaml", dots["clip"], roi=ROI, segments_s=[[1.0, 1.1]])
    with pytest.raises(SystemExit, match="label-tiles: .*warm-up"):
        main(["label-tiles", str(short), "--out", str(tmp_path / "short_tiles")])
    assert not (tmp_path / "short_tiles").exists()
    before = {p.name: p.read_bytes() for p in out.glob("*.*")}
    with pytest.raises(SystemExit):
        main(["label-tiles", str(short), "--out", str(out), "--force"])
    assert {p.name: p.read_bytes() for p in out.glob("*.*")} == before


def test_tiles_come_from_the_segment_process_analyses(dots, tmp_path):
    """`process` analyses the first segment only, so the tiles come from it."""
    cs = write_clip_settings(tmp_path / "two.yaml", dots["clip"], roi=ROI, segments_s=[[0.5, 1.5], [1.5, 2.5]])
    rec = L.make_tiles(cs, tmp_path / "t", frames=4, reserve=0, tiles_per_frame=1, tile_px=48, seed=0)
    man = _manifest(tmp_path / "t")
    assert (man["run_start_s"] == 0.5).all() and (man["t"] <= 1.0).all() and (man["segment"] == 0).all()
    assert rec["segments_in_clip"] == 2 and rec["segment_s"] == [0.5, 1.5]


def test_score_refuses_another_video_roi_or_frame_naming(dots, tmp_path):
    labels = _truth_labels(_manifest(dots["tiles"]), dots["truth"])
    run, summ = _copy_run(dots, tmp_path)
    (run / "summary.json").write_text(json.dumps({**summ, "input": {**summ["input"], "sha256": "0" * 64}}))
    with pytest.raises(ValueError, match="another video"):
        L.score_labels(dots["tiles"], labels, run)
    (run / "summary.json").write_text(json.dumps({**summ, "input": {**summ["input"], "roi_px": [41, 20, 300, 230]}}))
    with pytest.raises(ValueError, match="ROI"):
        L.score_labels(dots["tiles"], labels, run)
    # Same origin, smaller ROI: tiles could reach where the run has no detections.
    tiles_roi = json.loads((dots["tiles"] / "tiles.json").read_text())["roi_px"]
    smaller = [tiles_roi[0], tiles_roi[1], tiles_roi[2] - 10, tiles_roi[3]]
    (run / "summary.json").write_text(json.dumps({**summ, "input": {**summ["input"], "roi_px": smaller}}))
    with pytest.raises(ValueError, match="differs from the tiles' ROI"):
        L.score_labels(dots["tiles"], labels, run)
    (run / "summary.json").write_text(json.dumps(summ))
    fr = pd.read_parquet(run / "frames.parquet")
    fr["t"] += 0.001
    fr.to_parquet(run / "frames.parquet", index=False)
    with pytest.raises(ValueError, match="name frames differently"):
        L.score_labels(dots["tiles"], labels, run)


def test_score_skips_frames_and_uses_the_reserve(dots, tmp_path):
    """Tiles on frames the run skipped are listed, not scored, and the next frames of the draw (the
    reserve) take their place; a run of another segment scores nothing."""
    man = _manifest(dots["tiles"])
    labels = _truth_labels(man, dots["truth"])
    run, summ = _copy_run(dots, tmp_path)
    fr = pd.read_parquet(run / "frames.parquet")
    first, second = man.loc[man["draw"] == 0, "frame"].iloc[0], man.loc[man["draw"] == 1, "frame"].iloc[0]
    fr.loc[fr["frame"] == first, "duplicate"] = True                       # as a content repeat
    fr[fr["frame"] != second].to_parquet(run / "frames.parquet", index=False)
    res = L.score_labels(dots["tiles"], labels, run, match_px=0.75)
    why = {s["tile_id"]: s["reason"] for s in res["tiles_skipped"]}
    assert {why[t] for t in man.loc[man["draw"] == 0, "tile_id"]} == {"repeated frame"}
    assert {why[t] for t in man.loc[man["draw"] == 1, "tile_id"]} == {"frame not in the run"}
    assert res["frames"] == 8 and res["fn"] == 0 and res["fp"] == 0
    assert set(man.loc[man["draw"] == 9, "tile_id"]) <= {r["tile_id"] for r in res["per_tile"]}
    (run / "summary.json").write_text(json.dumps({**summ, "input": {**summ["input"], "segment_s": [0.7, END]}}))
    res = L.score_labels(dots["tiles"], labels, run)
    assert res["frames"] == 0 and {s["reason"] for s in res["tiles_skipped"]} == {"segment not in this run"}
    assert res["warnings"] and res["f1"]["value"] is None


def test_label_files_are_checked(dots, tmp_path):
    tiles, run = dots["tiles"], dots["run"]
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(ValueError, match="empty; a labels file starts with the header tile_id,x,y"):
        L.score_labels(tiles, empty, run)
    with pytest.raises(SystemExit, match="label-score: "):
        main(["label-score", str(tiles), "--labels", str(empty), "--run", str(run)])
    header = tmp_path / "header.csv"
    header.write_text("tile_id,x,y,confidence,note\n")
    res = L.score_labels(tiles, header, run)
    assert res["tiles_labelled"] == 0 and res["frames"] == 0 and res["warnings"]
    bad = tmp_path / "bad.csv"
    bad.write_text("tile_id,x,y,confidence,note\nt000,12,5,1,\nt000,12px,5,1,\nt001,4,,1,\nt002,,,,none\n")
    with pytest.raises(ValueError, match=r"line 3: x '12px' is not a number.*line 4: only one of x and y"):
        L.read_labels(bad)
    with pytest.raises(ValueError, match="not in the manifest"):
        L.score_labels(tiles, pd.DataFrame({"tile_id": ["t999"], "x": [1.0], "y": [1.0]}), run)
    ok = L.read_labels(tmp_path / "header.csv")
    assert list(ok.columns) == L.LABEL_COLUMNS and len(ok) == 0


def test_unsure_labels_are_dont_care(dots):
    """A label below labels.min_confidence counts neither as hit nor as miss, and the detection it
    matches is not a false one."""
    man = _manifest(dots["tiles"])
    unsure = _truth_labels(man, dots["truth"], confidence=0.5)
    res = L.score_labels(dots["tiles"], unsure, dots["run"], match_px=0.75)
    assert res["tp"] == 0 and res["fp"] == 0 and res["fn"] == 0 and res["precision"]["value"] is None
    assert res["dont_care_detections"] == res["unsure_labels"] > 10
    mixed = _truth_labels(man, dots["truth"])
    mixed.loc[mixed.index[::2], "confidence"] = 0.5
    res = L.score_labels(dots["tiles"], mixed, dots["run"], match_px=0.75)
    assert res["precision"]["value"] == 1.0 and res["recall"]["value"] == 1.0 and res["dont_care_detections"] > 0


def test_render_tile_grid_convention():
    """A grid line or tick marked k passes through the centre of tile pixel k; the line is light on dark
    pixels and dark on bright ones."""
    crop = np.zeros((40, 40, 3), np.uint8)
    crop[16, 32] = 255                                   # tile pixel x = 32, y = 16
    img = L.render_tile(crop, 4, 16, 4, 32)
    top, left = 46, 44
    block = img[top + 16 * 4:top + 17 * 4, left + 32 * 4:left + 33 * 4]
    assert (block > 100).all()                           # the pixel is a 4 x 4 block
    col = left + 32 * 4 + 2                              # the vertical line marked 32
    assert left + 32 * 4 <= col < left + 33 * 4
    assert img[top + 4, col, 0] > 30 and img[top + 4, col - 2, 0] == 0   # a light line on the dark tile, not beside it
    assert (img[top - 9:top, col] < 100).all()           # the labelled tick above it
    bright = L.render_tile(np.full((40, 40, 3), 250, np.uint8), 4, 16, 4, 32)
    assert bright[top + 4, col].mean() < 200 and bright[top + 4, col - 2].mean() == 250


def test_bootstrap_over_frames():
    tp, fp, fn = [5] * 6, [1] * 6, [0] * 6
    r = L.bootstrap_prf(tp, fp, fn, n_boot=500, seed=0)
    assert r["precision"]["value"] == pytest.approx(30 / 36) and r["recall"]["value"] == 1.0
    assert r["precision"]["ci"] == pytest.approx([30 / 36, 30 / 36])     # identical frames: no spread
    r = L.bootstrap_prf([9, 1, 5, 5, 2, 7], [1, 9, 2, 0, 1, 1], [0, 3, 1, 1, 2, 0], n_boot=2000, seed=0)
    lo, hi = r["f1"]["ci"]
    assert lo < r["f1"]["value"] < hi and r["frames"] == 6
    assert L.bootstrap_prf([9, 1, 5, 5, 2, 7], [1, 9, 2, 0, 1, 1], [0, 3, 1, 1, 2, 0], n_boot=2000, seed=0) == r
    assert r["f1"]["value"] == pytest.approx(2 * 29 / (2 * 29 + 14 + 7))
    # Too few frames: no interval, rather than one that looks certain.
    few = L.bootstrap_prf([3], [1], [0], n_boot=500, seed=0)
    assert few["f1"]["value"] == pytest.approx(6 / 7) and few["f1"]["ci"] == [None, None] and "ci_note" in few
    # Replicates with a zero denominator are left out and counted.
    r = L.bootstrap_prf([0, 0, 0, 0, 0, 5], [0, 0, 0, 0, 0, 1], [1, 1, 1, 1, 1, 0], n_boot=1000, seed=0)
    assert r["replicates_undefined"]["precision"] > 0 and r["replicates_undefined"]["recall"] == 0


def test_streak_radius_is_per_detection():
    """With labels.streak_radius_frac, a long streak's detection matches a label further away."""
    det, lab = np.array([[0.0, 0.0], [50.0, 0.0]]), np.array([[4.0, 0.0], [54.0, 0.0]])
    pairs, _, _ = L._match_dont_care(det, np.ones(2, bool), lab, np.ones(2, bool), np.array([5.0, 3.0]))
    assert pairs.tolist() == [[0, 0]]


def test_inter_labeler_f1(tmp_path):
    a = pd.DataFrame({"tile_id": ["t000"] * 4 + ["t001", "t002"], "x": [10, 20, 30, 40, np.nan, 5],
                      "y": [10, 20, 30, 40, np.nan, 5], "confidence": 1.0, "note": ""})
    b = pd.DataFrame({"tile_id": ["t000"] * 3 + ["t001", "t003"], "x": [11, 21.5, 60, 7, 1],
                      "y": [10, 19, 60, 7, 1], "confidence": 1.0, "note": ""})
    r = L.inter_labeler_f1(a, b, match_px=3.0)
    # Tiles both labelled: t000 (2 matches of 4 and 3 labels) and t001 (a saw none, b one).
    assert r["tiles"] == 2 and r["matches"] == 2 and r["labels_a"] == 4 and r["labels_b"] == 4
    assert r["f1"]["value"] == pytest.approx(2 * 2 / (4 + 4)) and r["tag"] == "agent-labeled vs user-labeled"
    man = tmp_path / "manifest.csv"
    pd.DataFrame({"tile_id": ["t000", "t001", "t002", "t003"], "frame": [7, 7, 9, 9], "run_start_s": 0.5,
                  "w": 64, "h": 64}).to_csv(man, index=False)
    r2 = L.inter_labeler_f1(a, b, match_px=3.0, manifest=man)
    assert r2["units"] == 1 and r2["bootstrap_over"] == "frames" and r2["f1"]["value"] == r["f1"]["value"]
    assert r2["f1"]["ci"] == [None, None]                                 # one frame: no interval
    # Units are (segment start, frame): the same frame index in another segment is another frame.
    man2 = tmp_path / "manifest2.csv"
    pd.DataFrame({"tile_id": ["t000", "t001", "t002", "t003"], "frame": [7, 7, 9, 9],
                  "run_start_s": [0.5, 1.5, 0.5, 0.5], "w": 64, "h": 64}).to_csv(man2, index=False)
    assert L.inter_labeler_f1(a, b, match_px=3.0, manifest=man2)["units"] == 2
    # Tile IDs are checked against the manifest, and labels outside their tile are left out.
    with pytest.raises(ValueError, match="not in the manifest"):
        L.inter_labeler_f1(a, pd.DataFrame({"tile_id": ["t009"], "x": [1.0], "y": [1.0]}), manifest=man)
    out = pd.concat([b, pd.DataFrame({"tile_id": ["t000"], "x": [70.0], "y": [3.0], "confidence": 1.0, "note": ""})])
    r3 = L.inter_labeler_f1(a, out, match_px=3.0, manifest=man)
    assert r3["labels_outside_tile"] == 1 and r3["labels_b"] == 4
    # An unsure label (below labels.min_confidence) is don't care, and so is the label it matches.
    b.loc[0, "confidence"] = 0.5
    r4 = L.inter_labeler_f1(a, b, match_px=3.0)
    assert r4["matches"] == 1 and r4["labels_a"] == 3 and r4["labels_b"] == 3 and r4["unsure_labels"] == 1
