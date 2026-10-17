"""Offline verifier tools: audit (reproduces label-score), sheets, blind windows, truth merge, run identity, CLI."""
import json

import av
import cv2
import numpy as np
import pandas as pd
import pytest
import yaml
from dots_clip import dots_clip

from wfglink.config import load_config
from wfglink.detect.candidates import Detections
from wfglink.track.tracker import Tracker, tracks_to_frame
from wfglink.validate import labels as L
from wfglink.verify import audit as A
from wfglink.verify import identity as I
from wfglink.verify import sheets as S
from wfglink.verify import truth as T
from wfglink.verify import windows as W
from wfglink.verify.cli_tools import main as verify_main

VIDEO_SHA = "ab" * 32
ROI_WH = (200, 150)
FPS = 30.0


# A synthetic tile set and run (tables only) --------------------------------------------------

def _synthetic_label_set(root, seed: int = 0, frac: float = 0.5):
    """Tiles, labels and a run folder written as label-tiles and process write them, with
    engineered cases in tile A of every frame (x0 10, y0 10, 32 px): a static light at (20, 20)
    (track 1, flagged static at frame 35), a labelled ember (track 2, coasting in frame 10), a
    detection matching an unsure label, a detection just outside the tile matching a label
    inside it, an unlabelled detection and a missed label; tile B is random."""
    rng = np.random.default_rng(seed)
    tiles, run = root / "tiles", root / "run"
    tiles.mkdir()
    run.mkdir()
    n_frames = 40
    frames = pd.DataFrame({"frame": np.arange(n_frames), "t": np.arange(n_frames) / FPS,
                           "duplicate": np.isin(np.arange(n_frames), [12]), "ready": np.arange(n_frames) >= 5,
                           "ms": rng.uniform(1, 9, n_frames)})
    frames.to_parquet(run / "frames.parquet", index=False)
    drawn = [20, 12, 3, 36, 7, 25, 33, 15, 30, 22]          # 12 repeated, 3 not ready, 30 and 22 not needed
    det_rows, lab_rows, man_rows = [], [], []
    for f in range(n_frames):
        if not frames.loc[f, "ready"] or frames.loc[f, "duplicate"]:
            continue
        fixed = [(20.0, 20.0), (30.0 + 0.1 * f, 25.0), (15.5, 35.0), (42.0, 12.0), (25.0, 38.0)]
        rand = np.column_stack([rng.uniform(0, ROI_WH[0] - 1, 60), rng.uniform(0, ROI_WH[1] - 1, 60)])
        rand = rand[(rand[:, 0] > 55) | (rand[:, 1] > 55)][:25]         # none near the engineered cases
        for k, (x, y) in enumerate(fixed + [tuple(p) for p in rand]):
            det_rows.append({"frame": f, "t": f / FPS, "x": x, "y": y, "area": 4.0, "peak": 30.0, "flux": 100.0,
                             "length": 0.0 if k < 5 else float(rng.uniform(0, 12)), "width": 2.0, "theta": 0.0,
                             "sat_frac": 0.0, "color": 1.0, "flags": np.uint8(0), "scale": 1.0})
    dets = pd.DataFrame(det_rows)
    dets.to_parquet(run / "detections.parquet", index=False)
    by_f = {f: g for f, g in dets.groupby("frame")}
    n_tile = 0
    for rank, f in enumerate(drawn):
        bx, by = int(rng.integers(0, ROI_WH[0] - 32)), int(rng.integers(0, ROI_WH[1] - 32))
        for (x0, y0) in ((10, 10), (bx, by)):
            tid = f"t{n_tile:03d}"
            n_tile += 1
            man_rows.append({"tile_id": tid, "clip_id": "synthetic", "segment": 0, "run_start_s": 0.0, "frame": f,
                             "t": f / FPS, "pts_s": f / FPS, "draw": rank, "reserve": rank >= 6, "check": rank < 2,
                             "x0": x0, "y0": y0, "w": 32, "h": 32, "roi_x0": 0, "roi_y0": 0, "scale": 4,
                             "png": f"{tid}.png", "raw_png": f"raw/{tid}.png", "context_frames": "",
                             "context_png": "", "raw_sha256": ""})
            if (x0, y0) == (10, 10):
                for x, y, c in ((30.5 + 0.1 * f, 25.5, 1.0), (15.0, 35.0, 0.5), (40.6, 12.0, 1.0), (12.0, 30.0, 1.0)):
                    lab_rows.append({"tile_id": tid, "x": x - x0, "y": y - y0, "confidence": c, "note": ""})
                if f == 7:
                    lab_rows.append({"tile_id": tid, "x": 40.0, "y": 5.0, "confidence": 1.0, "note": "outside"})
                continue
            if f == 25:
                continue                                          # this tile is not labelled
            g = by_f.get(f)
            n_lab = 0
            if g is not None:
                p = g[["x", "y"]].to_numpy()
                inside = L._in_tile(p, x0, y0, 32, 32)
                for x, y in p[inside]:
                    if rng.random() < 0.7:
                        lab_rows.append({"tile_id": tid, "x": x - x0 + rng.normal(0, 2.0), "y": y - y0 + rng.normal(0, 2.0),
                                         "confidence": float(rng.choice([1.0, 1.0, 0.5])), "note": ""})
                        n_lab += 1
            for _ in range(int(rng.integers(0, 2))):
                lab_rows.append({"tile_id": tid, "x": float(rng.uniform(0, 31)), "y": float(rng.uniform(0, 31)),
                                 "confidence": 1.0, "note": ""})
                n_lab += 1
            if not n_lab:
                lab_rows.append({"tile_id": tid, "x": np.nan, "y": np.nan, "confidence": np.nan, "note": "none"})
    pd.DataFrame(man_rows).to_csv(tiles / L.MANIFEST, index=False)
    (tiles / L.TILES_JSON).write_text(json.dumps({"tile_set_id": "synthetic", "video_sha256": VIDEO_SHA,
                                                  "roi_px": [0, 0, *ROI_WH], "frames_requested": 6}))
    labels = root / "labels.csv"
    pd.DataFrame(lab_rows, columns=L.LABEL_COLUMNS).to_csv(labels, index=False)
    # Tracks: 1 is the static light, 2 the labelled ember (coasting in frame 10).
    pts = []
    for f in range(5, n_frames):
        if f == 12:
            continue
        pts.append({"track_id": 1, "frame": f, "t": f / FPS, "x_meas": 20.0, "y_meas": 20.0, "coasted": False,
                    "det_index": 0, "status": "finished", "static": True})
        co = f == 10
        pts.append({"track_id": 2, "frame": f, "t": f / FPS, "x_meas": np.nan if co else 30.0 + 0.1 * f,
                    "y_meas": np.nan if co else 25.0, "coasted": co, "det_index": -1 if co else 1,
                    "status": "finished", "static": False})
    tp_ = pd.DataFrame(pts)
    tp_["x"], tp_["y"], tp_["length"] = tp_["x_meas"].fillna(31.0), tp_["y_meas"].fillna(25.0), 0.0
    tp_.to_parquet(run / "track_points.parquet", index=False)
    pd.DataFrame({"track_id": [1, 2], "static": [True, False], "crossings_pos": [0, 1], "crossings_neg": [0, 0]}
                 ).to_parquet(run / "tracks.parquet", index=False)
    summary = {"input": {"sha256": VIDEO_SHA, "roi_px": [0, 0, *ROI_WH], "width": ROI_WH[0], "height": ROI_WH[1],
                         "segment_s": [0.0, None], "fps": FPS},
               "outputs": {"detections": "detections.parquet", "frames": "frames.parquet",
                           "track_points": "track_points.parquet", "tracks": "tracks.parquet"},
               "config_sha256": "synthetic", "git_commit": "synthetic", "created": "x", "seconds": 1.0}
    (run / "summary.json").write_text(json.dumps(summary))
    cfg_path = root / "labels_cfg.yaml"
    cfg_path.write_text(yaml.safe_dump({"labels": {"streak_radius_frac": frac}}))
    return {"tiles": tiles, "run": run, "labels": labels, "cfg_path": cfg_path,
            "cfg": load_config(cfg_path)}


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_audit_reproduces_score_labels_and_label_score(tmp_path, seed):
    s = _synthetic_label_set(tmp_path, seed)
    res = A.audit_labels(s["tiles"], s["labels"], s["run"], s["cfg"])
    ref = L.score_labels(s["tiles"], s["labels"], s["run"], s["cfg"])
    out = tmp_path / "score.json"
    from wfglink.cli import main

    assert main(["label-score", str(s["tiles"]), "--labels", str(s["labels"]), "--run", str(s["run"]),
                 "--out", str(out), "--config", str(s["cfg_path"])]) == 0
    cli = json.loads(out.read_text())
    tab = res["table"]
    for key, status in (("tp", "tp"), ("fp", "fp"), ("fn", "fn"), ("dont_care_detections", "dont_care"),
                        ("labels_outside_tile", "label_outside")):
        assert res["totals"][key] == ref[key] == cli[key] == int((tab["status"] == status).sum())
    assert res["reproduces_score_labels"] and ref["tp"] > 5 and ref["fp"] > 5 and ref["fn"] > 0
    assert res["totals"]["frames"] == 6 and sorted(tab["frame"].unique()) == [7, 15, 20, 25, 33, 36]
    # Per-tile counts as score_labels gives them.
    det = tab[tab["kind"] == "detection"]
    for pt in ref["per_tile"]:
        d = det[det["tile_id"] == pt["tile_id"]]
        assert (d["status"] == "tp").sum() == pt["tp"] and (d["status"] == "fp").sum() == pt["fp"]
        assert d["inside_tile"].sum() == pt["detections"]


def test_audit_rows_engineered_cases(tmp_path):
    s = _synthetic_label_set(tmp_path, 0)
    tab = A.audit_labels(s["tiles"], s["labels"], s["run"], s["cfg"])["table"]
    man = pd.read_csv(s["tiles"] / L.MANIFEST)
    tile_a = set(man.loc[(man["x0"] == 10) & (man["y0"] == 10), "tile_id"])
    det = tab[(tab["kind"] == "detection") & tab["tile_id"].isin(tile_a)].set_index(["frame", "det_index"]).sort_index()
    assert det.index.is_unique
    labs = pd.read_csv(s["labels"])
    for f in (7, 20, 36):
        assert det.loc[(f, 1), "status"] == "tp" and det.loc[(f, 2), "status"] == "dont_care"
        row = det.loc[(f, 3)]
        assert row["status"] == "tp" and not row["inside_tile"]     # outside the tile, matched to a label inside
        assert labs.loc[int(row["matched_label"]), "x"] == pytest.approx(30.6)
        assert det.loc[(f, 4), "status"] == "fp" and pd.isna(det.loc[(f, 4), "track_id"])
        assert det.loc[(f, 0), "status"] == "fp" and det.loc[(f, 0), "track_id"] == 1
        assert det.loc[(f, 1), "track_id"] == 2 and bool(det.loc[(f, 1), "track_has_crossing"])
    # Track 2 is confirmed after its third hit (frame 7); the static light is flagged at frame 35.
    assert det.loc[(7, 1), "hits_so_far"] == 3 and det.loc[(7, 1), "confirmed_at_frame"]
    assert det.loc[(20, 0), "booth_drawn"] and not det.loc[(20, 0), "static_at_frame"]
    assert det.loc[(36, 0), "static_at_frame"] and not det.loc[(36, 0), "booth_drawn"]
    fn = tab[(tab["status"] == "fn") & (tab["frame"] == 20)]
    assert len(fn) >= 1
    miss = fn[np.isclose(fn["x"], 12.0) & np.isclose(fn["y"], 30.0)].iloc[0]
    assert miss["nearest_det_px"] == pytest.approx(np.hypot(12 - 15.5, 30 - 35.0))
    assert abs(int(miss["nearest_det_window_offset"])) <= 2
    assert (tab["status"] == "label_outside").sum() == 1 and (tab["status"] == "unsure").sum() >= 6
    # The CLI writes the same table and totals.
    out = tmp_path / "audit.parquet"
    assert verify_main(["verify", "audit", str(s["tiles"]), "--labels", str(s["labels"]), "--run", str(s["run"]),
                        "--out", str(out), "--config", str(s["cfg_path"])]) == 0
    back = pd.read_parquet(out)
    assert len(back) == len(tab) and json.loads(out.with_suffix(".json").read_text())["reproduces_score_labels"]


def test_audit_records_whether_the_config_is_the_runs(tmp_path):
    from wfglink.outputs.process import _legacy_cfg
    from wfglink.provenance import sha256_json

    s = _synthetic_label_set(tmp_path, 0)
    res = A.audit_labels(s["tiles"], s["labels"], s["run"], s["cfg"])
    assert res["totals"]["config_matches_run"] is False and "not the run's" in res["warnings"][0]
    with pytest.raises(ValueError, match="not the run's"):
        A.audit_labels(s["tiles"], s["labels"], s["run"], s["cfg"], strict_config=True)
    summ = json.loads((s["run"] / "summary.json").read_text())
    summ["config_sha256"] = sha256_json(_legacy_cfg(s["cfg"]))
    (s["run"] / "summary.json").write_text(json.dumps(summ))
    res = A.audit_labels(s["tiles"], s["labels"], s["run"], s["cfg"], strict_config=True)
    assert res["totals"]["config_matches_run"] is True and not res["warnings"]


def _det(xy):
    xy = np.asarray(xy, float).reshape(-1, 2)
    z = np.zeros(len(xy))
    return Detections(x=xy[:, 0].copy(), y=xy[:, 1].copy(), area=z + 3, peak=z + 50, flux=z + 100, lam1=z, lam2=z,
                      theta=z.copy(), length=z.copy(), width=z + 2, sat_frac=z, color=z + 20,
                      flags=np.zeros(len(xy), np.uint8))


def test_static_replay_matches_the_tracker():
    """The audit's replay of the static test gives the frame at which the real tracker flags a
    still light, including a flag set while the track coasts after its last hit."""
    cfg = load_config()
    rng = np.random.default_rng(3)
    tr = Tracker(cfg, fps=FPS, keep_history=True)
    seen: dict[int, int] = {}
    times = []
    for f in range(80):
        t = f / FPS
        pts = [(50 + rng.normal(0, 0.3), 60 + rng.normal(0, 0.3)), (10 + 6.0 * f, 100.0)]
        if 40 <= f < 75:
            pts.append((150 + rng.normal(0, 0.3), 30 + rng.normal(0, 0.3)))    # a second light, ends at 74
        tr.update(_det(pts), t, f)
        times.append((f, t))
        for k in tr.active_tracks():
            if k.static and k.track_id not in seen:
                seen[k.track_id] = f
        for k in tr._finished_queue:
            if k.static and k.track_id not in seen:
                seen[k.track_id] = f
    tab = tracks_to_frame(tr.all_tracks(include_active=True))
    fa = np.array([f for f, _ in times])
    ta = np.array([t for _, t in times])
    got = A.static_flag_frames(tab, cfg, FPS, 0.0, (fa, ta))
    assert seen and got == seen


# Video fixtures -------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dots(tmp_path_factory):
    """A dots clip with repeated frames and its file-mode run."""
    from wfglink.cli import main

    d = tmp_path_factory.mktemp("verify_dots")
    clip = d / "dots.mp4"
    grid = [(20 + 60 * i, 20 + 50 * j, 3, 2) for i in range(5) for j in range(4)]
    truth = dots_clip(clip, repeat={40, 41}, dots=grid)
    assert main(["process", str(clip), "--out", str(d / "run"), "--no-overlay"]) == 0
    return {"dir": d, "clip": clip, "run": d / "run", "truth": truth}


def test_windows_are_seeded_blind_and_follow_the_rules(dots, tmp_path):
    a = W.make_windows(dots["clip"], tmp_path / "a", n=5, k=4, seed=7, tile_px=64)
    b = W.make_windows(dots["clip"], tmp_path / "b", n=5, k=4, seed=7, tile_px=64)
    c = W.make_windows(dots["clip"], tmp_path / "c", n=5, k=4, seed=8, tile_px=64)
    ma, mb = (tmp_path / "a" / W.MANIFEST).read_bytes(), (tmp_path / "b" / W.MANIFEST).read_bytes()
    assert ma == mb and a["window_set_id"] == b["window_set_id"] != c["window_set_id"]
    for name in ("w000_k0.png", "w003_k2.png", "w001_context.png", "raw/w004_k3.png"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    man = W.read_manifest(tmp_path / "a")
    assert len(man) == 5 and (man["k"] == 4).all()
    rows = L._scan(dots["clip"], 0.0, None, (0, 0, 320, 240), load_config())
    changed = [r["frame"] for r in rows if not r["repeat"]]
    assert {40, 41} & set(r["frame"] for r in rows if r["repeat"])        # the clip's repeats are found
    t_ready = L.detector_ready_time(rows, load_config())
    used = [f for fs in man["frames"] for f in fs]
    assert len(used) == len(set(used))                                    # no frame in two windows
    t_of = {r["frame"]: r["t"] for r in rows}
    for fs, ts in zip(man["frames"], man["t"]):
        i = changed.index(fs[0])
        assert fs == changed[i:i + 4]                                     # consecutive changed frames
        assert min(ts) >= t_ready + 0.5 and ts == [t_of[f] for f in fs]
    assert ((man["x0"] >= 0) & (man["y0"] >= 0) & (man["x0"] + man["w"] <= 320) & (man["y0"] + man["h"] <= 240)).all()
    # Raw tiles are the decoded frames' crops, their SHA-256 in the manifest.
    import hashlib

    want = {f: (wid, k) for wid, fs in zip(man["window_id"], man["frames"]) for k, f in enumerate(fs)}
    with av.open(str(dots["clip"])) as cont:
        for i, vf in enumerate(cont.decode(video=0)):
            if i not in want:
                continue
            wid, k = want[i]
            r = man.set_index("window_id").loc[wid]
            crop = vf.to_ndarray(format="bgr24")[r["y0"]:r["y0"] + r["h"], r["x0"]:r["x0"] + r["w"]]
            raw = cv2.imread(str(tmp_path / "a" / "raw" / f"{wid}_k{k}.png"))
            assert np.array_equal(raw, crop)
            assert hashlib.sha256(raw.tobytes()).hexdigest() == r["raw_sha256"].split(";")[k]
    assert list(pd.read_csv(tmp_path / "a" / W.TEMPLATE).columns) == W.LABEL_COLUMNS
    js = json.loads((tmp_path / "a" / W.WINDOWS_JSON).read_text())
    assert js["seed"] == 7 and js["rule"] and len(js["video_sha256"]) == 64 and js["n_windows"] == 5
    big = cv2.imread(str(tmp_path / "a" / "w000_k0.png"))
    assert big.shape[0] > 4 * 64 and big.shape[1] > 4 * 64
    with pytest.raises(ValueError, match="already holds"):
        W.make_windows(dots["clip"], tmp_path / "a", n=5, k=4, seed=7, tile_px=64)
    (tmp_path / "a" / "stray.txt").write_text("x")
    with pytest.raises(ValueError, match="holds stray.txt"):
        W.make_windows(dots["clip"], tmp_path / "a", n=5, k=4, seed=7, tile_px=64, force=True)
    assert W.tile_size_for(640, 480) == 192 and W.tile_size_for(1920, 1080) == 192 and W.tile_size_for(3840, 2160) == 256


def test_a_partial_segment_keeps_the_clip_settings_other_end(dots, tmp_path):
    from dots_clip import write_clip_settings

    cs = write_clip_settings(tmp_path / "c.yaml", dots["clip"], segments_s=[[0.5, 2.0]])
    assert W._source(cs)[4] == (0.5, 2.0)
    assert W._source(cs, segment=(None, 1.5))[4] == (0.5, 1.5)
    assert W._source(cs, segment=(1.0, None))[4] == (1.0, 2.0)
    assert W._source(dots["clip"])[4] == (0.0, None) and W._source(dots["clip"], segment=(None, 1.0))[4] == (0.0, 1.0)
    rec = W.make_windows(cs, tmp_path / "w", n=2, k=4, seed=0, tile_px=64, segment=(None, 1.8))
    assert rec["segment_s"] == [0.5, 1.8]
    assert verify_main(["verify", "windows", str(cs), "--out", str(tmp_path / "w2"), "--n", "2", "--k", "4",
                        "--tile-px", "64", "--end-seconds", "1.8"]) == 0
    assert json.loads((tmp_path / "w2" / W.WINDOWS_JSON).read_text())["segment_s"] == [0.5, 1.8]


def test_sheets_render_items_from_the_run(dots, tmp_path):
    run = dots["run"]
    det = pd.read_parquet(run / "detections.parquet")
    pts = pd.read_parquet(run / "track_points.parquet")
    meas = pts[~pts["coasted"]]
    p = meas.iloc[len(meas) // 2]
    items = [S.SheetItem(int(p["frame"]), float(p["x_meas"]), float(p["y_meas"]), int(p["track_id"]), "a", "tp"),
             S.SheetItem(int(det["frame"].iloc[5]), float(det["x"].iloc[5]), float(det["y"].iloc[5]), None, "b", "fp"),
             S.SheetItem(int(det["frame"].min()), 2.0, 3.0, None, "c", "fp", "near the corner")]
    rec = S.render_sheets(run, items, tmp_path / "sheets", credit="Credit: test")
    out = tmp_path / "sheets"
    assert len(rec["sheets"]) == 3 and rec["credit_line"] == "Credit: test" and len(rec["contact_sheets"]) == 2
    for name in rec["sheets"] + rec["contact_sheets"]:
        f = out / name
        assert f.exists() and (f.stat().st_size <= 300 * 1024 or f.suffix == ".jpg")
        assert cv2.imread(str(f)) is not None
    man = pd.read_csv(out / "sheets.csv")
    frames = pd.read_parquet(run / "frames.parquet").set_index("frame")
    for _, r in man.iterrows():
        assert r["t"] == pytest.approx(frames.loc[int(r["frame"]), "t"], abs=1e-9)
    # A clip moved elsewhere is refused unless it is the same video.
    other = tmp_path / "other.mp4"
    dots_clip(other, frames=20, seed=5)
    with pytest.raises(ValueError, match="not the video the run analysed"):
        S.render_sheets(run, items[:1], tmp_path / "s2", clip=other)


def test_sheet_helpers(tmp_path):
    img = np.arange(100 * 120 * 3, dtype=np.uint32).reshape(100, 120, 3).astype(np.uint8)
    c = S.crop_at(img, 5, 7, 16)
    assert np.array_equal(c[8, 8], img[7, 5]) and (c[0, 0] == 60).all()      # padding outside the image
    noise = np.random.default_rng(0).integers(0, 255, (600, 800, 3), dtype=np.uint8)
    assert S.write_image(noise, tmp_path / "n.png").suffix == ".jpg"
    assert S.write_image(np.zeros((50, 50, 3), np.uint8), tmp_path / "z.png").suffix == ".png"
    credit, cid = S.credit_line("4aa46db5950172d6ea3d78cb4694cff0a334c45dbe2b1991ad1d381d7d798d10")
    assert cid == "C5_nist_emberometer" and credit == "Credit: NIST"
    assert S.credit_line("0" * 64, None) == ("", None)
    items = S.items_from_table(pd.DataFrame({"frame": [1, 2, 3], "x": [1.0, 2, 3], "y": [1.0, 2, 3],
                                             "status": ["fp", "fp", "tp"], "track_id": [pd.NA, 4, 5]}), limit=1)
    assert [(i.category, i.track_id) for i in items] == [("fp", None), ("tp", 5)]


# Truth merge ----------------------------------------------------------------------------------

def _windows_dir(root, n=2, k=6, w=64, h=64):
    d = root / "windows"
    d.mkdir()
    rows = []
    for j in range(n):
        fr = [100 * (j + 1) + i for i in range(k)]
        rows.append({"window_id": f"w{j:03d}", "clip_id": "x", "segment": 0, "run_start_s": 0.0, "k": k,
                     "frames": ";".join(map(str, fr)), "t": ";".join(repr(f / 30) for f in fr),
                     "x0": 10 + 100 * j, "y0": 20, "w": w, "h": h, "roi_x0": 0, "roi_y0": 0, "scale": 4})
    pd.DataFrame(rows).to_csv(d / W.MANIFEST, index=False)
    (d / W.WINDOWS_JSON).write_text(json.dumps({"window_set_id": "test", "video_sha256": "cd" * 32,
                                                "roi_px": [0, 0, 400, 200], "clip_id": "x"}))
    return d


def _lab(rows):
    return pd.DataFrame(rows, columns=["window_id", "k", "x", "y", "confidence", "ember_id", "size_class", "note"])


def _ember(wid, eid, ks, x0, y0, dx=2.0, dy=1.0, conf=1.0, jitter=0.0):
    return [(wid, k, x0 + dx * k + jitter, y0 + dy * k, conf, eid, "s", "") for k in ks]


def test_truth_merge_rules(tmp_path):
    d = _windows_dir(tmp_path)
    a = _lab(_ember("w000", "1", range(6), 20, 20)                      # agreed by both: observable
             + _ember("w000", "2", range(2), 40, 40)                     # only two points: not observable
             + _ember("w000", "3", range(4), 1, 30, dx=0.0)              # along the left edge: not observable
             + [("w000", 2, 50.0, 10.0, 1.0, "4", "s", "")]              # only a: goes to the adjudicator
             + [("w000", 3, 50.0, 50.0, 0.5, "5", "s", "")]              # unsure, only a: don't care
             + [("w000", 4, 10.0, 55.0, 1.0, "6", "s", "")]              # only a, the adjudicator rejects it
             + [("w001", np.nan, np.nan, np.nan, np.nan, None, "", "none")])
    b = _lab(_ember("w000", "9", range(6), 20, 20, jitter=0.8)
             + _ember("w000", "8", range(2), 40, 40)
             + _ember("w000", "7", range(4), 1, 30, dx=0.0)
             + [("w001", np.nan, np.nan, np.nan, np.nan, None, "", "none")])
    c = _lab([("w000", 2, 50.5, 10.0, 1.0, "x", "s", "")])
    rec = T.merge_truth(d, a, b, c)
    w0 = rec["windows"][0]
    assert w0["status"] == "ok" and w0["adjudicated"] and rec["windows"][1]["status"] == "ok"
    obs = [tr for tr in w0["tracks"] if tr["observable"]]
    assert len(obs) == 1 and obs[0]["n_sure"] == 6
    p0 = obs[0]["points"][0]
    assert p0["x"] == pytest.approx(10 + 20.4) and p0["frame"] == 100 and not p0["dont_care"]
    adj = [tr for tr in w0["tracks"] if any(p["source"] == "adjudicated" for p in tr["points"])]
    assert len(adj) == 1 and adj[0]["points"][0]["sure"] and adj[0]["points"][0]["x"] == pytest.approx(60.5)
    assert not adj[0]["observable"]                                       # one sure point only
    assert len(w0["rejected"]) == 1 and w0["rejected"][0]["x"] == pytest.approx(20.0)
    edge = [tr for tr in w0["tracks"] if tr["points"][0]["tx"] == pytest.approx(1.0)]
    assert len(edge) == 1 and not edge[0]["observable"] and "inside" in edge[0]["reason"]
    reasons = {p["reason"] for p in w0["dont_care"]}
    assert any("fewer than 3" in r for r in reasons)
    assert rec["totals"]["observable_tracks"] == 1 and rec["windows"][1]["tracks"] == []
    ag = rec["agreement"]
    assert ag["point_f1"]["value"] == pytest.approx(2 * 12 / (14 + 12)) and ag["tracks_a"] == 2 == ag["tracks_b"]
    assert ag["track_f1"] == pytest.approx(1.0)
    # Without the adjudicator the disagreement stays unresolved: don't care, nothing rejected.
    rec2 = T.merge_truth(d, a, b)
    w0 = rec2["windows"][0]
    assert not w0["rejected"] and any(p["source"] == "unadjudicated" for tr in w0["tracks"] for p in tr["points"])
    # A window only one labeller labelled gets no truth.
    rec3 = T.merge_truth(d, a, b[b["window_id"] != "w001"])
    assert rec3["windows"][1]["status"] == "not_labelled" and rec3["windows"][1]["labelled_by"] == ["a"]


def test_truth_identity_and_ambiguity(tmp_path):
    d = _windows_dir(tmp_path, n=1)
    a = _lab(_ember("w000", "1", range(6), 20, 20) + _ember("w000", "1", range(3), 40, 40))   # two embers, one id
    b = _lab(_ember("w000", "5", range(6), 20, 20) + _ember("w000", "6", range(3), 40, 40))
    rec = T.merge_truth(d, a, b)
    tracks = rec["windows"][0]["tracks"]
    assert len(tracks) == 1 and tracks[0]["ambiguous"] and not tracks[0]["observable"]
    # A point without ember_id is linked through the other labeller's identity of the same point.
    a2 = _lab(_ember("w000", "1", range(5), 20, 20) + [("w000", 5, 30.0, 25.0, 1.0, None, "s", "")])
    b2 = _lab(_ember("w000", "5", range(6), 20, 20) + _ember("w000", "6", range(3, 6), 40, 40, conf=0.5))
    rec = T.merge_truth(d, a2, b2)
    tr = [t for t in rec["windows"][0]["tracks"] if t["observable"]]
    assert len(tr) == 1 and tr[0]["n_sure"] == 6 and len(rec["windows"][0]["tracks"]) == 2
    assert rec["totals"]["sure_without_ember_id"] == {"a": 1, "b": 0, "adjudicator": 0}
    assert len(rec["warnings"]) == 1 and "w000" in rec["warnings"][0]
    # Both labellers without ember_id: every point is a track of its own, nothing observable, a warning.
    strip = _lab(_ember("w000", None, range(6), 20, 20))
    rec = T.merge_truth(d, strip, strip)
    assert rec["totals"]["observable_tracks"] == 0 and rec["totals"]["sure_without_ember_id"]["a"] == 6
    assert rec["windows"][0]["sure_without_ember_id"] == {"a": 6, "b": 6, "adjudicator": 0} and rec["warnings"]
    with pytest.raises(ValueError, match="not in the manifest"):
        T.merge_truth(d, _lab([("w009", 0, 1.0, 1.0, 1.0, "1", "s", "")]), b)
    with pytest.raises(ValueError, match="k outside"):
        T.merge_truth(d, _lab([("w000", 6, 1.0, 1.0, 1.0, "1", "s", "")]), b)
    bad = tmp_path / "bad.csv"
    bad.write_text("window_id,k,x,y,confidence,ember_id,size_class,note\nw000,,3,4,1,1,s,\nw000,1,x,4,1,1,s,\n")
    with pytest.raises(ValueError, match="line 2: a point needs an integer k"):
        T.read_window_labels(bad)


# Identity -------------------------------------------------------------------------------------

def _run_folder(root, name, ms_seed=0, compression="snappy"):
    d = root / name
    (d / "high_precision").mkdir(parents=True)
    rng = np.random.default_rng(ms_seed)
    pd.DataFrame({"frame": np.arange(5), "t": np.arange(5) / 30, "duplicate": [False] * 5,
                  "ms": rng.uniform(0, 9, 5)}).to_parquet(d / "frames.parquet", compression=compression, index=False)
    pd.DataFrame({"frame": [1, 1, 2], "x": [1.5, 2.5, 3.5], "y": [4.0, 5.0, 6.0], "status": pd.array(["a", "b", None])}
                 ).to_parquet(d / "detections.parquet", compression=compression, index=False)
    pd.DataFrame({"key": [1, 2], "state": ["method_accepted", "rejected"]}).to_parquet(
        d / "high_precision" / "hp_decisions.parquet", index=False)
    s = {"input": {"sha256": "x"}, "totals": {"cpc_gross": 3}, "created": f"c{ms_seed}", "seconds": ms_seed,
         "git_commit": f"g{ms_seed}", "git_dirty": bool(ms_seed), "high_precision": {"method": "rules", "n": ms_seed}}
    (d / "summary.json").write_text(json.dumps(s))
    return d


def test_identity_is_stable_and_sensitive(tmp_path):
    a = _run_folder(tmp_path, "a", 0, "snappy")
    b = _run_folder(tmp_path, "b", 1, "gzip")          # other timings, compression, created, git, HP block
    ia = I.run_identity(a)
    assert ia == I.run_identity(a) and I.compare(a, b)["identical"]
    assert set(ia["tables"]) == {"frames.parquet", "detections.parquet", "high_precision/hp_decisions.parquet"}
    assert set(I.run_identity(a, recursive=False)["tables"]) == {"frames.parquet", "detections.parquet"}
    det = pd.read_parquet(b / "detections.parquet")
    changed = det.copy()
    changed.loc[2, "x"] = 3.5000001
    changed.to_parquet(b / "detections.parquet", index=False)
    res = I.compare(a, b)
    assert not res["identical"] and res["different"] == ["detections.parquet"] and res["summary_equal"]
    det.assign(frame=det["frame"].astype("int32")).to_parquet(b / "detections.parquet", index=False)
    assert I.compare(a, b)["different"] == ["detections.parquet"]                  # a dtype counts
    det[["x", "frame", "y", "status"]].to_parquet(b / "detections.parquet", index=False)
    assert I.compare(a, b)["different"] == ["detections.parquet"]                  # so does column order
    det.to_parquet(b / "detections.parquet", index=False)
    assert I.compare(a, b)["identical"]
    s = json.loads((b / "summary.json").read_text())
    s["totals"]["cpc_gross"] = 4
    (b / "summary.json").write_text(json.dumps(s))
    res = I.compare(a, b)
    assert not res["identical"] and not res["summary_equal"] and not res["different"]
    (b / "frames.parquet").unlink()
    assert I.compare(a, b)["only_a"] == ["frames.parquet"]
    assert I.table_hash(pd.DataFrame({"a": []})) != I.table_hash(pd.DataFrame({"b": []}))
    assert verify_main(["verify", "identity", str(a), str(a)]) == 0
    assert verify_main(["verify", "identity", str(a), str(b)]) == 1


# CLI ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [["dataset", "run", "--labels", "l.csv", "--out", "o"],
                                 ["train", "ds", "--report", "r.json"],
                                 ["calibrate", "--dataset", "ds", "--recording", "run", "truth.json", "--out", "o"],
                                 ["replay", "run", "--method", "rules", "--out", "o"],
                                 ["freeze", "draft.yaml", "--out", "o", "--windows", "sealed_test", "w"],
                                 ["bench", "--synthetic", "--seconds", "1", "--out", "b.json"]])
def test_training_selection_and_runtime_subcommands_parse(cmd):
    """dataset, train, calibrate, replay, freeze and bench are real subcommands (their behaviour is
    tested in test_verify_train.py and test_verify_replay.py); a call without their required
    arguments is a usage error."""
    import argparse

    from wfglink.verify import cli_tools
    from wfglink.verify.cli_tools import add_parser

    parser = argparse.ArgumentParser(prog="wfglink")
    add_parser(parser.add_subparsers(dest="command", required=True))
    args = parser.parse_args(["verify", *cmd])
    assert args.func is getattr(cli_tools, f"cmd_{cmd[0]}")
    with pytest.raises(SystemExit) as exc:
        verify_main(["verify", cmd[0], "--anything", "x"])
    assert exc.value.code == 2


def test_verify_group_adds_to_the_wfglink_parser():
    import argparse

    from wfglink.verify.cli_tools import add_parser

    parser = argparse.ArgumentParser(prog="wfglink")
    sub = parser.add_subparsers(dest="command", required=True)
    add_parser(sub)
    for cmd in (["verify", "audit", "t", "--labels", "l", "--run", "r"], ["verify", "windows", "c", "--out", "o"],
                ["verify", "truth", "w", "--a", "a", "--b", "b", "--out", "o"],
                ["verify", "eval", "--protocol", "p", "--sha256", "s", "--run", "r"], ["verify", "identity", "r"],
                ["verify", "sheets", "--run", "r", "--items", "i", "--out", "o"]):
        assert callable(parser.parse_args(cmd).func)
    with pytest.raises(SystemExit):
        parser.parse_args(["verify"])


def test_no_dashes_in_verify_sources():
    from pathlib import Path

    import wfglink

    root = Path(wfglink.__file__).parent / "verify"
    mine = ["cli_tools.py", "audit.py", "sheets.py", "windows.py", "truth.py", "evaluate.py", "identity.py",
            "dataset.py", "train.py", "calibrate.py", "replay.py", "freeze.py", "bench.py"]
    for name in mine:
        text = (root / name).read_text(encoding="utf-8")
        assert chr(0x2014) not in text and chr(0x2013) not in text, name
