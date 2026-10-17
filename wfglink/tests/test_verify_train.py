"""Training rows, training, rules thresholds and the selection rule of the verifier (verify dataset,
train, calibrate)."""
import copy
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from dots_clip import dots_clip

from wfglink.provenance import sha256_file
from wfglink.verify.config import OVERLAY, VerifyConfig, hp_config
from wfglink.verify.features import FEATURE_NAMES, WINDOW_NAMES

T_EXP = 0.012
W, H = 320, 240


def _dump_cfg():
    return hp_config("accept_all", overrides={"verify": {"dump": True}})


@pytest.fixture(scope="module")
def dots(tmp_path_factory):
    """A dots clip (with a slow pair of dots) processed with accept_all and a dump."""
    from wfglink.outputs.process import process_clip

    d = tmp_path_factory.mktemp("train")
    clip = d / "dots.mp4"
    grid = [(20 + 60 * i, 20 + 50 * j, 4, 3) for i in range(5) for j in range(4)]
    truth = dots_clip(clip, dots=grid, frames=90)
    process_clip(clip, d / "dump", _dump_cfg(), t_exp=T_EXP, overlay=False)
    dec = pd.read_parquet(d / "dump" / "high_precision" / "hp_decisions.parquet")
    return {"root": d, "clip": clip, "dump": d / "dump", "truth": truth, "keys": sorted(dec["key"].astype(int))}


# Dataset ------------------------------------------------------------------------------------------

CYCLE = ["ember", "fixture_light", "ember", "reflection", "unclear", "ember", "duplicate_fragment", "moving_non_ember",
         "faint_possible_ember", "codec_artifact"]


def _labels(dots, path):
    keys = dots["keys"]
    rows = [{"track_key": k, "category": CYCLE[i % len(CYCLE)], "reviewer": "agent_a", "adjudicated": False}
            for i, k in enumerate(keys)]
    rows.append({"track_key": 999999, "category": "ember", "reviewer": "agent_a", "adjudicated": False})
    pd.DataFrame(rows).to_csv(path, index=False)
    return rows


def test_dataset_maps_categories_groups_cells_and_reports_exclusions(dots, tmp_path):
    from wfglink.verify.dataset import CATEGORIES, build_dataset, load_dataset

    review = tmp_path / "review.csv"
    rows = _labels(dots, review)
    keys = dots["keys"]
    # An audit table: det rows of the first track with an adjudicated category overriding the review
    # (fixture_light to ember), and two rows of the second track that disagree (a conflict).
    audit = pd.DataFrame({"det_row": [1, 2, 3, 4], "track_id": [keys[1], keys[1], keys[3], keys[3]],
                          "status": ["fp", "fp", "tp", "tp"],
                          "adjudicated_category": ["ember", "ember", "ember", "reflection"]})
    audit.to_csv(tmp_path / "audit.csv", index=False)
    rec = build_dataset(dots["dump"], [review, tmp_path / "audit.csv"], tmp_path / "ds", _dump_cfg(), block_s=1.0,
                        cell_px=16)
    ds = load_dataset(tmp_path / "ds")
    tr, hits, patches = ds["tracks"], ds["hits"], ds["patches"]
    want = {k: CYCLE[i % len(CYCLE)] for i, k in enumerate(keys)}
    want[keys[1]] = "ember"
    assert set(tr["category"]) <= {c for c, v in CATEGORIES.items() if v is not None}
    for k, c, y in zip(tr["key"], tr["category"], tr["label"]):
        assert c == want[int(k)] and y == (1 if c == "ember" else 0)
    ex = rec["exclusions"]
    assert ex.get("ambiguous:unclear", 0) >= 1 and ex.get("ambiguous:duplicate_fragment", 0) >= 1
    assert ex["conflicting_labels"] == 1 and ex["not_confirmed"] == 1
    assert keys[3] not in set(tr["key"]) and not (tr["category"] == "unclear").any()
    # Groups and cells.
    assert (tr["group"] == (tr["t_first"] // 1.0).astype(int)).all()
    assert (tr["cell_x"] == (tr["x0"] // 16).astype(int)).all() and (tr["cell_y"] == (tr["y0"] // 16).astype(int)).all()
    # Window hits: contiguous rows of the same track, with patches; hit samples carry the track's label and group.
    for r in tr.itertuples(index=False):
        w = hits.iloc[r.win_hit_start:r.win_hit_start + r.win_hit_count]
        assert (w["key"] == r.key).all() and w["window"].all() and r.win_hit_count == r.n_feature_hits
        assert (w["label"] == r.label).all() and (w["group"] == r.group).all()
    assert hits["sample"].sum() <= 8 * len(tr) and patches.shape == (len(hits), 2, 17, 17)
    assert patches.dtype == np.float16 and (hits["patch_row"] == np.arange(len(hits))).all()
    assert rec["floor"]["adequate"] is False and "positive" in rec["floor"]["reason"]
    assert rec["missing_patches"]["buffer_hits_without_dumped_patch"] == 0 and len(rec["feature_settings_sha256"]) == 64
    assert rec["sources"]["labels"][0]["sha256"] == sha256_file(review)
    assert rec["counts"]["labels_by_category"]["ember"] >= 1 and len(rows) == len(keys) + 1
    # The window of a track sample is the one the online rules would score first: at least min_hits hits.
    assert (tr["n_hits"] >= 4).all()
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"track_id": [keys[0]], "category": ["sparkle"]}).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="unknown category"):
        build_dataset(dots["dump"], [bad], tmp_path / "ds2", _dump_cfg())


def test_negatives_are_capped_per_cell_with_a_seeded_subset():
    from wfglink.verify.dataset import cap_negatives

    tr = pd.DataFrame({"key": np.arange(45), "label": [1] * 10 + [0] * 35, "cell": ["a"] * 40 + ["b"] * 5})
    k0, k0b, k1 = cap_negatives(tr, 20, 0), cap_negatives(tr, 20, 0), cap_negatives(tr, 20, 1)
    assert k0[:10].all() and k0.sum() == 10 + 20 + 5 and k1.sum() == k0.sum()
    assert (k0 == k0b).all() and not (k0 == k1).all()
    assert k0[40:].all()                                                # a small cell keeps everything


def test_hit_samples_drop_near_duplicates_and_are_evenly_spaced():
    from wfglink.verify.dataset import sample_hits

    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, (2, 17, 17))
    same = np.stack([base + 1e-4 * rng.normal(0, 1, base.shape) for _ in range(5)])
    other = rng.normal(0, 1, (20, 2, 17, 17))
    p = np.concatenate([same, other]).astype(np.float16)
    keep = sample_hits(p, 8)
    assert keep[0] == 0 and not set(keep.tolist()) & {1, 2, 3, 4} and len(keep) == 8
    assert np.all(np.diff(keep) > 0)
    assert list(sample_hits(other.astype(np.float16), 30)) == list(range(20))


def test_data_floor_verdict():
    from wfglink.verify.dataset import floor_verdict

    assert floor_verdict(100, 200, 30)["adequate"]
    v = floor_verdict(99, 250, 29)
    assert not v["adequate"] and "99 positive" in v["reason"] and "29 distinct negative cells" in v["reason"]
    assert "negative tracks" in floor_verdict(150, 199, 40)["reason"]


# Training -----------------------------------------------------------------------------------------

def _synthetic_dataset(d: Path, n_pos=60, n_neg=100, adequate=True, seed=0, groups=2):
    """A dataset folder in the format verify dataset writes: positives are bright compact blobs that
    move fast, negatives dim flat ones that barely move. Few block groups keep the cross-validation
    short (folds without test groups are not fitted)."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[-8:9, -8:9]
    blob = np.exp(-(xx ** 2 + yy ** 2) / 3.0)
    tracks, hits, patches = [], [], []
    for i in range(n_pos + n_neg):
        y = int(i < n_pos)
        key = 1000 + i
        group = i % groups
        cell = (i % 45, (i * 7) % 11)
        vec = {n: float(rng.normal(0, 1)) for n in WINDOW_NAMES}
        vec.update(n_hits=6.0, snr_med=float(rng.normal(12 if y else 6, 2)), speed_med=float(rng.normal(150 if y else 40,
                                                                                                         30)))
        start = len(hits)
        for j in range(3):
            amp = rng.normal(3.0 if y else 1.0, 0.4)
            p = np.stack([amp * blob + rng.normal(0, 0.3, blob.shape), 0.3 * amp * blob + rng.normal(0, 0.2, blob.shape)])
            vals = {n: float(rng.normal(0, 1)) for n in FEATURE_NAMES}
            vals["snr"] = float(rng.normal(12 if y else 6, 2))
            hits.append({"key": key, "track_id": key, "frame": 10 + j, "det_index": 0, "t": 0.3 + j / 30, "label": y,
                         "group": group, "sample": True, "window": True, "patch_row": len(hits), **vals})
            patches.append(p)
        tracks.append({"key": key, "track_id": key, "category": "ember" if y else "fixture_light", "label": y,
                       "group": group, "cell_x": cell[0], "cell_y": cell[1], "cell": f"{cell[0]}_{cell[1]}",
                       "x0": 16.0 * cell[0], "y0": 16.0 * cell[1], "t_first": 4.0 * group, "t_confirm": 4.0 * group,
                       "t_window": 4.0 * group, "frame_window": 12, "n_feature_hits": 3, "win_hit_start": start,
                       "win_hit_count": 3, **vec})
    d.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(tracks).to_parquet(d / "tracks.parquet", index=False)
    pd.DataFrame(hits).to_parquet(d / "hits.parquet", index=False)
    np.save(d / "patches.npy", np.stack(patches).astype(np.float16))
    floor = {"adequate": adequate, "reason": "" if adequate else "10 positive tracks (at least 100 needed)"}
    rec = {"profile": "file_native", "settings": {"max_neg_per_cell": 20}, "floor": floor,
           "files_sha256": {n: sha256_file(d / n) for n in ("tracks.parquet", "hits.parquet", "patches.npy")}}
    (d / "dataset.json").write_text(json.dumps(rec), encoding="utf-8")
    return d


def test_training_is_seed_deterministic_and_saves_pinned_models(tmp_path):
    from wfglink.verify.ledger import Window
    from wfglink.verify.scorers import PatchScorer, TemporalScorer, build_scorer
    from wfglink.verify.train import train_all

    ds = _synthetic_dataset(tmp_path / "ds")
    rep = train_all(ds, tmp_path / "m1", tmp_path / "r1.json", max_seconds=120, command_line="test train")
    rep2 = train_all(ds, tmp_path / "m2", tmp_path / "r2.json", max_seconds=120, cv=False)
    assert rep["status"] == "OK" and "PROVISIONAL" in rep["label"]
    for name, m in rep["models"].items():
        assert m["final"]["sha256"] == rep2["models"][name]["final"]["sha256"], name      # same seed, same bytes
        assert m["cv"]["auc"] > 0.9 and len(m["cv"]["by_threshold"]) == 8
        assert m["cv"]["scored"] == m["tracks"]
    assert rep["models"]["patch_seed0"]["final"]["sha256"] != rep["models"]["patch_seed1"]["final"]["sha256"]
    # No cell holds more negatives than the cap: both seeds draw the same tracks, so the temporal seeds are one model.
    assert rep["sampling"]["cap_binding"] is False and rep["sampling"]["identical_training_sets"] is True
    assert rep["models"]["temporal_seed1"]["same_as"] == "temporal_seed0" and "same_as" not in rep["models"]["patch_seed1"]
    assert rep["distinct_models"]["temporal"] == [["temporal_seed0", "temporal_seed1"]]
    assert rep["deterministic"] is True and "warnings" not in rep and len(rep["caveats"]) >= 2
    cv = rep["models"]["patch_seed0"]["cv"]
    assert {"auc_runtime", "ood_tracks", "test_negatives_sharing_a_training_cell", "by_threshold_without_ood"} <= set(cv)
    assert rep["settings"]["ood"]["z_max"] == 6.0
    side = json.loads(Path(rep["models"]["patch_seed0"]["final"]["path"]).with_suffix(".json").read_text())
    assert side["command_line"] == "test train" and side["profile"] == "file_native" and side["seed"] == 0
    assert side["epochs"] == side["fit"]["epochs_run"] <= 80 and side["training_data_sha256"]["tracks.parquet"]
    assert side["wall_s"] >= 0 and side["feature_names"][-14:] == ["snr", "log_flux", "area", "width", "length",
                                                                   "sat_frac", "color", "color_nan", "scale",
                                                                   "bg_luma", "bg_grad", "large_near", "codec",
                                                                   "density"]
    # The saved models run in the scorers when pinned by their SHA-256.
    tr = pd.read_parquet(ds / "tracks.parquet")
    hits = pd.read_parquet(ds / "hits.parquet")
    pt = np.load(ds / "patches.npy")
    i = int(np.flatnonzero(tr["label"] == 1)[0])
    rows = np.arange(tr["win_hit_start"][i], tr["win_hit_start"][i] + 3)
    win = Window(tr.loc[i, list(WINDOW_NAMES)].to_numpy(float), pt[rows], 3,
                 hit_values=hits.loc[rows, list(FEATURE_NAMES)].to_numpy(float))
    for fam, cls in (("patch", PatchScorer), ("temporal", TemporalScorer)):
        f = rep["models"][f"{fam}_seed0"]["final"]
        v = VerifyConfig.from_cfg(hp_config(fam, overrides={"verify": {"models": {fam: {"file_native": {
            "path": f["path"], "sha256": f["sha256"], "threshold": 0.5}}}}}))
        sc = build_scorer(v, "file_native")
        assert isinstance(sc, cls), getattr(sc, "reason", "")
        s, ok, why = sc.score_window(win) if fam == "patch" else sc.score(win.vec, win.patches)
        assert ok and s > 0.5, why
    f = rep["models"]["patch_seed0"]["final"]
    v = VerifyConfig.from_cfg(hp_config("patch", overrides={"verify": {"models": {"patch": {"file_native": {
        "path": f["path"], "sha256": f["sha256"], "threshold": 0.5}}}}}))
    s, ok, why = build_scorer(v, "file_native").score(win.vec, win.patches)       # its hit scalars are needed
    assert not ok and why == "missing_feature:hit_values"


def test_training_is_not_run_below_the_data_floor(tmp_path):
    from wfglink.verify.train import train_all

    ds = _synthetic_dataset(tmp_path / "ds", n_pos=10, n_neg=30, adequate=False)
    rep = train_all(ds, tmp_path / "models", tmp_path / "report.json")
    assert rep["status"] == "NOT_RUN" and "data floor" in rep["reason"]
    assert json.loads((tmp_path / "report.json").read_text())["status"] == "NOT_RUN"
    assert not (tmp_path / "models").exists() or not list((tmp_path / "models").rglob("*.npz"))


# Calibration and selection ----------------------------------------------------------------------------

def test_rules_thresholds_come_from_the_development_positives():
    from wfglink.verify.calibrate import IQR_EPS, rule_candidates, rule_thresholds
    from wfglink.verify.scorers import RULE_LOWER, RULE_UPPER, RuleScorer

    rng = np.random.default_rng(0)
    pos = pd.DataFrame({n: rng.normal(10, 3, 50) for n in WINDOW_NAMES})
    pos["codec_med"] = 0.0
    pos["ctx_change_med"] = np.nan
    th0, sk0 = rule_thresholds(pos, 0.0)
    assert th0["lower"]["snr_med"] == pos["snr_med"].min() and th0["upper"]["hotspot_max"] == pos["hotspot_max"].max()
    th, sk = rule_thresholds(pos, 0.1)
    assert th["lower"]["speed_med"] == pytest.approx(np.quantile(pos["speed_med"], 0.1))
    assert th["upper"]["bg_grad_med"] == pytest.approx(np.quantile(pos["bg_grad_med"], 0.9))
    q1, q3 = np.quantile(pos["net_disp"], [0.25, 0.75])
    assert th["iqr"]["net_disp"] == pytest.approx(q3 - q1) and th["iqr"]["codec_med"] == IQR_EPS
    assert sk == ["ctx_change_med"] and set(th["lower"]) == set(RULE_LOWER)
    assert set(th["upper"]) == set(RULE_UPPER) - {"ctx_change_med"}
    RuleScorer(th, 4)                                                      # the overlay format the scorer reads
    c = rule_candidates(pos, (0.0, 0.025, 0.3))
    assert list(c) == ["0", "0.025", "0.3"] and c["0.3"]["thresholds"]["lower"]["snr_med"] > th0["lower"]["snr_med"]


def _pt(family, precision, recall, accepted=10, delay=0.2, seed=None, **kw):
    p = {"family": family, "precision": precision, "recall": recall, "accepted_tracks": accepted,
         "median_confirmation_delay_s": delay, "seed": seed, "name": kw.pop("name", f"{family}_{precision}_{recall}")}
    p["q" if family == "rules" else "threshold"] = kw.pop("param", 0.5)
    return {**p, **kw}


def test_selection_rule_branches_and_ties():
    from wfglink.verify.calibrate import INSUFFICIENT, SELECTED, family_bests, select

    # Precision target met: the highest recall wins; ties go to rules, then temporal, then patch, then delay.
    pts = [_pt("accept_all", 1.0, 1.0, name="control"), _pt("patch", 0.995, 0.8, seed=0), _pt("temporal", 1.0, 0.8, seed=1),
           _pt("rules", 0.99, 0.6), _pt("patch", 0.98, 0.95, seed=0)]
    s = select(pts)
    assert s["status"] == SELECTED and s["branch"] == "precision_target_met" and not s["target_missed"]
    assert s["point"]["family"] == "temporal"
    pts.append(_pt("rules", 0.99, 0.8, delay=0.5, name="slow_rules"))
    pts.append(_pt("rules", 1.0, 0.8, delay=0.1, name="fast_rules"))
    assert select(pts)["point"]["name"] == "fast_rules"
    # None reaches 0.99: the highest precision with recall >= 0.5.
    pts = [_pt("rules", 0.98, 0.4), _pt("temporal", 0.95, 0.6, seed=0), _pt("patch", 0.97, 0.55, seed=0),
           _pt("accept_all", 0.985, 1.0)]
    s = select(pts)
    assert s["branch"] == "recall_floor" and s["target_missed"] and s["point"]["family"] == "patch"
    # Nor recall 0.5: the highest precision with at least 5 accepted tracks; the target is missed.
    pts = [_pt("rules", 0.98, 0.4, accepted=4), _pt("temporal", 0.9, 0.3, accepted=5, seed=0),
           _pt("patch", 0.8, 0.2, accepted=50, seed=1)]
    s = select(pts)
    assert s["branch"] == "min_accepted" and s["target_missed"] and s["point"]["family"] == "temporal"
    # Nothing with 5 accepted tracks: INSUFFICIENT_EVIDENCE with the best available point.
    pts = [_pt("rules", 0.95, 0.1, accepted=2), _pt("patch", 0.5, 0.1, accepted=4, seed=0),
           _pt("temporal", None, None, accepted=0, seed=0)]
    s = select(pts)
    assert s["status"] == INSUFFICIENT and s["point"] is None and s["best_available"]["family"] == "rules"
    assert select([])["status"] == INSUFFICIENT and select([])["best_available"] is None
    fb = family_bests(pts)
    assert fb["rules"]["precision"] == 0.95 and fb["patch"]["precision"] == 0.5 and fb["temporal"] is None
    # The rule as written: a point at precision >= 0.99 is chosen however few tracks it accepted.
    assert select([_pt("rules", 1.0, 0.1, accepted=2), _pt("patch", 0.9, 0.9, seed=0)])["point"]["family"] == "rules"


def test_write_config_pins_settings_and_keeps_comments(tmp_path):
    from wfglink.config import load_config
    from wfglink.verify.calibrate import write_config
    from wfglink.verify.scorers import RuleScorer, Unavailable, build_scorer

    ov = tmp_path / "high_precision.yaml"
    shutil.copy(OVERLAY, ov)
    before = ov.read_text()
    cands = {"0.025": {"q": 0.025, "thresholds": {"lower": {"snr_med": 4.5, "net_disp": 1e-06},
                                                  "upper": {"hotspot_max": 30.0},
                                                  "iqr": {"snr_med": 2.0, "net_disp": 1e-06, "hotspot_max": 5.0}}}}
    pins = {"rules": {"q": 0.025},
            "patch": {"model_path": str(tmp_path / "patch_seed1.npz"), "model_sha256": "1e5" + "0" * 61,
                      "threshold": 0.9}}
    written = write_config(ov, "file_native", pins, cands)
    text = ov.read_text()
    comments = [ln.split("#", 1)[1] for ln in before.splitlines() if "#" in ln]
    assert all(c in text for c in comments)                          # every comment kept
    assert chr(0x2014) not in text and chr(0x2013) not in text
    cfg = load_config(ov)
    v = VerifyConfig.from_cfg(cfg)
    assert v.rules_thresholds["file_native"] == cands["0.025"]["thresholds"] and v.rules_q == 0.025
    spec = v.models["patch"]["file_native"]
    assert spec.sha256 == "1e5" + "0" * 61 and spec.threshold == 0.9 and spec.path.endswith("patch_seed1.npz")
    assert v.models["temporal"]["file_native"].sha256 is None          # not pinned: unchanged
    assert written["patch"]["threshold"] == 0.9
    rules_cfg = copy.deepcopy(cfg)
    rules_cfg["verify"]["method"] = "rules"
    assert isinstance(build_scorer(VerifyConfig.from_cfg(rules_cfg), "file_native"), RuleScorer)
    assert isinstance(build_scorer(VerifyConfig.from_cfg(rules_cfg), "live_downscaled"), Unavailable)


def _truth_for_dots(dots, frames_list):
    """Window truth of the dots clip: full-frame windows whose observable tracks are the dots."""
    fr = pd.read_parquet(dots["dump"] / "frames.parquet")
    ft = dict(zip(fr["frame"].astype(int), fr["t"].astype(float)))
    summ = json.loads((dots["dump"] / "summary.json").read_text())
    wins = []
    for n, frames in enumerate(frames_list):
        tracks = []
        for e in range(len(dots["truth"][0])):
            pts = []
            for k, f in enumerate(frames):
                x, y = (float(v) for v in dots["truth"][f][e])
                inside = min(x, y, W - 1 - x, H - 1 - y) >= 4
                pts.append({"k": k, "frame": f, "t": ft[f], "x": x, "y": y, "sure": True, "dont_care": not inside})
            tracks.append({"truth_id": f"w{n}_{e}", "observable": any(not p["dont_care"] for p in pts),
                           "ambiguous": False, "points": pts})
        wins.append({"window_id": f"w{n:03d}", "status": "ok", "frames": list(frames), "t": [ft[f] for f in frames],
                     "x0": 0, "y0": 0, "w": W, "h": H, "tracks": tracks, "dont_care": []})
    return {"video_sha256": summ["input"]["sha256"], "segment_s": [0.0, None], "roi_px": [0, 0, W, H],
            "windows": wins}


def _cal_protocol(d: Path, entries, sealed=True):
    """A frozen protocol (JSON) whose truth entries are (population, sealed, truth path); git_clean is
    patched by the tests that load it."""
    truth = []
    for pop, sealed_entry, tp in entries:
        tj = json.loads(Path(tp).read_text())
        truth.append({"population": pop, "recording": Path(tp).stem, "sealed": sealed_entry, "path": str(tp),
                      "sha256": sha256_file(tp), "video_sha256": tj.get("video_sha256"),
                      "segment_s": tj.get("segment_s")})
    d.mkdir(parents=True, exist_ok=True)
    p = d / "protocol.json"
    p.write_text(json.dumps({"schema_version": 1, "name": "cal_test", "sealed": sealed, "truth": truth,
                             "targets": {"precision": 0.99}}), encoding="utf-8")
    return p, sha256_file(p)


@pytest.fixture()
def cal_inputs(dots, tmp_path, monkeypatch):
    from wfglink.verify import evaluate as E
    from wfglink.verify.dataset import build_dataset

    monkeypatch.setattr(E, "git_clean", lambda p: True)
    labels = tmp_path / "labels.csv"
    pd.DataFrame({"track_key": dots["keys"], "category": "ember"}).to_csv(labels, index=False)
    build_dataset(dots["dump"], [labels], tmp_path / "ds", _dump_cfg())
    truth = tmp_path / "truth.json"
    truth.write_text(json.dumps(_truth_for_dots(dots, [range(30, 38), range(55, 63)])), encoding="utf-8")
    ov = tmp_path / "overlay.yaml"
    shutil.copy(OVERLAY, ov)
    return {"ds": tmp_path / "ds", "truth": truth, "overlay": ov, "labels": labels}


def test_calibrate_replays_candidates_scores_them_and_writes_the_selection(dots, cal_inputs, tmp_path):
    from wfglink.verify.calibrate import calibrate

    truth, ov = cal_inputs["truth"], cal_inputs["overlay"]
    proto, sha = _cal_protocol(tmp_path / "proto", [("calibration_selection", False, truth)])
    rec = calibrate(cal_inputs["ds"], tmp_path / "no_models", [(str(dots["dump"]), str(truth))], tmp_path / "cal",
                    _dump_cfg(), protocol=proto, protocol_sha256=sha, families=("accept_all", "rules"),
                    write_overlay=True, overlay=ov)
    cp = json.loads((tmp_path / "cal" / "calibration_points.json").read_text())
    names = [p["name"] for p in cp["points"]]
    assert names[0] == "accept_all" and len([n for n in names if n.startswith("rules_q")]) == 8
    ctrl = cp["points"][0]
    assert ctrl["accepted_tracks"] == len(dots["keys"]) and ctrl["tp"] > 0 and ctrl["recall"] is not None
    for p in cp["points"]:
        assert {"tp", "fp", "fn", "judged", "precision", "recall", "accepted_tracks", "false_tracks_per_min",
                "median_confirmation_delay_s"} <= set(p)
        assert all(r["missing_patches"] == 0 for r in p["per_recording"])
    assert cp["protocol"]["sha256"] == sha and cp["development"] is False
    assert cp["truth_entries"][0]["entry"]["population"] == "calibration_selection"
    assert cp["dataset"]["dataset_json_sha256"] == sha256_file(cal_inputs["ds"] / "dataset.json")
    sel = json.loads((tmp_path / "cal" / "selection.json").read_text())
    assert sel["calibration_points_sha256"] == sha256_file(tmp_path / "cal" / "calibration_points.json")
    assert sel["overlay_sha256"] == sha256_file(ov) and sel.get("family") in (None, "rules")
    assert sel["protocol"]["sha256"] == sha and sel["truth_entries"] == cp["truth_entries"]
    if sel["status"] == "SELECTED":
        v = VerifyConfig.from_cfg(hp_config("rules", (ov,)))
        assert "file_native" in v.rules_thresholds and sel["q"] == v.rules_q
        from wfglink.verify.scorers import RuleScorer

        want = RuleScorer(v.rules_thresholds["file_native"], v.min_hits).identity()["thresholds_sha256"]
        assert sel["pinned_identity"]["rules"]["thresholds_sha256"] == want
    assert rec["family_bests"]["patch"] is None
    rc = json.loads((tmp_path / "cal" / "rules_candidates.json").read_text())
    assert rc["positives"] > 0 and set(rc["candidates"]) == {"0", "0.005", "0.01", "0.025", "0.05", "0.1", "0.2",
                                                             "0.3"}


def test_calibrate_refuses_sealed_foreign_and_unfrozen_truth(dots, cal_inputs, tmp_path):
    """Sealed-test truth never reaches calibration, a truth the protocol does not list only in
    development, and a development calibration never pins the overlay."""
    from wfglink.verify.calibrate import calibrate
    from wfglink.verify.evaluate import ProtocolError

    truth, ov, ds = cal_inputs["truth"], cal_inputs["overlay"], cal_inputs["ds"]
    before = ov.read_text()
    rec = [(str(dots["dump"]), str(truth))]

    def run(proto=None, sha=None, **kw):
        return calibrate(ds, tmp_path / "no_models", rec, tmp_path / "cal", _dump_cfg(), protocol=proto,
                         protocol_sha256=sha, families=("accept_all",), overlay=ov, **kw)

    p, sha = _cal_protocol(tmp_path / "sealed", [("sealed_test", True, truth)])
    for kw in ({}, {"allow_unfrozen_truth": True}):
        with pytest.raises(ProtocolError, match="calibration uses calibration_selection truth only"):
            run(p, sha, **kw)
    p, sha = _cal_protocol(tmp_path / "other_pop", [("development", False, truth)])
    with pytest.raises(ProtocolError, match="calibration uses calibration_selection truth only"):
        run(p, sha)
    # Another truth of a sealed recording's video (re-derived windows) is refused too.
    t2 = tmp_path / "truth_sealed_copy.json"
    t2.write_text(json.dumps({**json.loads(truth.read_text()), "windows": []}), encoding="utf-8")
    p, sha = _cal_protocol(tmp_path / "same_video", [("sealed_test", True, t2)])
    with pytest.raises(ProtocolError, match="its video is the protocol's recording"):
        run(p, sha, allow_unfrozen_truth=True)
    # Not frozen: refused, or development only (no overlay).
    p, sha = _cal_protocol(tmp_path / "empty", [])
    with pytest.raises(ProtocolError, match="not a calibration_selection truth entry"):
        run(p, sha)
    with pytest.raises(ProtocolError, match="pinned only"):
        run(p, sha, allow_unfrozen_truth=True, write_overlay=True)
    for kw in ({}, {"allow_unfrozen_truth": True}):
        with pytest.raises(ProtocolError, match="frozen protocol"):
            run(**kw)
    # The frozen truth of a calibration recording is the only one used for it.
    p2, sha2 = _cal_protocol(tmp_path / "frozen_other", [("calibration_selection", False, t2)])
    with pytest.raises(ProtocolError, match="whose frozen truth is another file"):
        run(p2, sha2, allow_unfrozen_truth=True)
    with pytest.raises(ProtocolError, match="not the pinned"):
        run(p, "0" * 64)
    dev = run(p, sha, allow_unfrozen_truth=True)
    assert dev["development"] and dev["truth_entries"][0]["frozen"] is False and "overlay_sha256" not in dev
    assert (tmp_path / "cal" / "selection_preview.json").exists() and not (tmp_path / "cal" / "selection.json").exists()
    assert ov.read_text() == before


def test_calibration_models_must_come_from_the_dataset_and_identical_seeds_count_once(tmp_path):
    from wfglink.verify.calibrate import build_candidates
    from wfglink.verify.scorers import TemporalScorer, Unavailable
    from wfglink.verify.train import train_all

    ds = _synthetic_dataset(tmp_path / "ds")
    rep = train_all(ds, tmp_path / "m", tmp_path / "r.json", families=("temporal",), cv=False)
    cfg = hp_config("temporal")
    ds_sha = sha256_file(ds / "dataset.json")
    kw = {"thresholds": (0.5, 0.9), "seeds": {"patch": (), "temporal": (0, 1)}, "families": ("temporal",)}
    dups = []
    c = build_candidates({}, tmp_path / "m", cfg, "file_native", dataset_sha256=ds_sha, train_report=rep,
                         duplicates=dups, **kw)
    assert sorted(c) == ["temporal_seed0_t0.5", "temporal_seed0_t0.9"]
    assert isinstance(c["temporal_seed0_t0.5"]["scorer"], TemporalScorer)
    assert c["temporal_seed0_t0.5"]["sidecar_sha256"] == sha256_file(tmp_path / "m" / "file_native" /
                                                                     "temporal_seed0.json")
    assert dups == [{"family": "temporal", "seed": 1, "same_as_seed": 0, "sha256": rep["models"]["temporal_seed0"]
                     ["final"]["sha256"], "note": dups[0]["note"]}]
    other = _synthetic_dataset(tmp_path / "ds2", seed=1)
    for args, why in (({"dataset_sha256": sha256_file(other / "dataset.json")}, "model_not_from_dataset"),
                      ({"dataset_sha256": ds_sha, "train_report": {**rep, "status": "NOT_RUN"}}, "train_report_not_ok"),
                      ({"dataset_sha256": ds_sha, "train_report": {**rep, "models": {}}}, "model_not_in_train_report")):
        c = build_candidates({}, tmp_path / "m", cfg, "file_native", **args, **kw)
        assert len(c) == 4 and all(isinstance(v["scorer"], Unavailable) for v in c.values())
        assert {v["scorer"].reason for v in c.values()} == {f"method_unavailable:{why}"}


def test_dataset_train_and_calibrate_command_lines(dots, tmp_path, monkeypatch):
    from wfglink.verify import evaluate as E
    from wfglink.verify.cli_tools import main

    monkeypatch.setattr(E, "git_clean", lambda p: True)
    labels = tmp_path / "labels.csv"
    pd.DataFrame({"track_key": dots["keys"], "category": "ember"}).to_csv(labels, index=False)
    assert main(["verify", "dataset", str(dots["dump"]), "--labels", str(labels), "--out", str(tmp_path / "ds")]) == 0
    rec = json.loads((tmp_path / "ds" / "dataset.json").read_text())
    assert rec["command_line"].startswith("python -m wfglink") and not rec["floor"]["adequate"]
    assert main(["verify", "train", str(tmp_path / "ds"), "--models", str(tmp_path / "m"), "--report",
                 str(tmp_path / "train_report.json")]) == 1                                    # below the data floor
    assert json.loads((tmp_path / "train_report.json").read_text())["status"] == "NOT_RUN"
    truth = tmp_path / "truth.json"
    truth.write_text(json.dumps(_truth_for_dots(dots, [range(30, 38)])), encoding="utf-8")
    ov = tmp_path / "overlay.yaml"
    shutil.copy(OVERLAY, ov)
    proto, sha = _cal_protocol(tmp_path / "proto", [("calibration_selection", False, truth)])
    (tmp_path / "proto" / "protocol.sha256").write_text(f"{sha}  protocol.json\n", encoding="utf-8")
    base = ["verify", "calibrate", "--dataset", str(tmp_path / "ds"), "--models", str(tmp_path / "m"),
            "--recording", str(dots["dump"]), str(truth), "--out", str(tmp_path / "cal"), "--families",
            "accept_all", "rules", "--overlay", str(ov)]
    with pytest.raises(SystemExit, match="frozen protocol"):
        main([*base, "--write-config"])
    assert main([*base, "--write-config", "--protocol", str(proto), "--sha256",
                 str(tmp_path / "proto" / "protocol.sha256")]) == 0
    sel = json.loads((tmp_path / "cal" / "selection.json").read_text())
    assert sel["overlay_sha256"] == sha256_file(ov) and sel["protocol"]["sha256"] == sha


def test_dataset_ties_labels_to_the_run_and_carries_confidence(dots, tmp_path):
    """A label row with a frame and position must sit on a measured point of its track; the
    review confidence reaches tracks.parquet and the counts."""
    from wfglink.verify.dataset import build_dataset, load_dataset

    pts = pd.read_parquet(dots["dump"] / "track_points.parquet")
    pts = pts[~pts["coasted"].astype(bool)]
    rows = []
    for i, k in enumerate(dots["keys"]):
        p = pts[pts["track_id"] == k].iloc[[0, -1]]
        for r in p.itertuples(index=False):
            rows.append({"track_id": k, "frame": int(r.frame), "x": float(r.x_meas) + 0.5, "y": float(r.y_meas),
                         "category": "ember" if i % 2 else "reflection", "confidence": "unsure" if i % 3 else "sure",
                         "adjudicated": False})
    bad_key = dots["keys"][1]
    q = pts[pts["track_id"] == bad_key].iloc[0]
    rows.append({"track_id": bad_key, "frame": int(q.frame), "x": float(q.x_meas) + 10.0, "y": float(q.y_meas),
                 "category": "ember", "confidence": "sure", "adjudicated": False})
    pd.DataFrame(rows).to_csv(tmp_path / "audit.csv", index=False)
    rec = build_dataset(dots["dump"], [tmp_path / "audit.csv"], tmp_path / "ds", _dump_cfg())
    tr = load_dataset(tmp_path / "ds")["tracks"]
    assert rec["label_positions"] == {"rows_checked": len(rows), "rows_mismatched": 1, "tracks_left_out": 1}
    assert rec["exclusions"]["label_position_mismatch"] == 1 and bad_key not in set(tr["key"])
    want = {k: ("unsure" if i % 3 else "sure") for i, k in enumerate(dots["keys"])}
    assert all(c == want[int(k)] for k, c in zip(tr["key"], tr["confidence"]))
    by = rec["counts"]["track_samples_by_class_and_confidence"]
    assert sum(sum(v.values()) for v in by.values()) == len(tr) and set(by) == {"0", "1"}
    # Labels of another run: most positions miss, so the build is refused.
    far = pd.DataFrame(rows).assign(x=lambda d: d["x"] + 25.0)
    far.to_csv(tmp_path / "far.csv", index=False)
    with pytest.raises(ValueError, match="not of this run"):
        build_dataset(dots["dump"], [tmp_path / "far.csv"], tmp_path / "ds_far", _dump_cfg())


def test_label_files_review_rounds_and_audit_categories(tmp_path):
    """Two reviewers and an adjudicator: the adjudicated row decides; reviewers who agree decide;
    reviewers who disagree without an adjudicator make a conflict; the error audit's own names
    are read (true_ember is ember; position errors are left out, never background)."""
    from wfglink.verify.dataset import read_labels

    review = pd.DataFrame({"item_id": ["r0", "r0", "r0", "r1", "r1", "r2", "r2"],
                           "track_key": [5, 5, 5, 6, 6, 7, 7], "track_id": [5, 5, 5, 6, 6, 7, 7],
                           "category": ["ember", "reflection", "reflection", "fixture_light", "fixture_light",
                                        "ember", "codec_artifact"],
                           "reviewer": ["A", "B", "adjudicator", "A", "B", "A", "B"],
                           "adjudicated": [False, False, True, False, False, False, False]})
    review.to_csv(tmp_path / "review.csv", index=False)
    audit = pd.DataFrame({"item_id": ["a0", "a1", "a2", "a3"], "kind": ["detection"] * 3 + ["label"],
                          "track_id": [8.0, 9.0, 9.0, np.nan], "status": ["tp", "fp", "fp", "fn"],
                          "category": ["true_ember", "detected_but_displaced", "detected_but_displaced",
                                       "missed_merged_or_crowded"], "adjudicated": [False, True, True, False]})
    audit.to_csv(tmp_path / "audit.csv", index=False)
    lab, conflicts = read_labels([tmp_path / "review.csv", tmp_path / "audit.csv"])
    got = dict(zip(lab["key"], lab["category"]))
    assert got == {5: "reflection", 6: "fixture_light", 8: "ember", 9: "detected_but_displaced"}
    assert dict(zip(lab["key"], lab["label"]))[8] == 1 and pd.isna(dict(zip(lab["key"], lab["label"]))[9])
    assert conflicts == [{"key": 7, "categories": ["codec_artifact", "ember"]}]
