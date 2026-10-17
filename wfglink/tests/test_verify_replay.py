"""Offline replay equals the online decisions and crossings; the frozen protocol is accepted by
evaluate; the live benchmark runs (verify replay, freeze, bench)."""
import json
import math
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest
from dots_clip import dots_clip

from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.verify.config import VerifyConfig, hp_config
from wfglink.verify.features import WINDOW_NAMES
from wfglink.verify.replay import (ReplayError, compare_decisions, compare_events, load_dump, predictions, replay,
                                   replay_many)
from wfglink.verify.scorers import AcceptAll, RuleScorer

RULES_A = {"lower": {"snr_med": 4.0, "speed_med": 40.0, "straightness": 0.6},
           "upper": {"hotspot_max": 30.0},
           "iqr": {"snr_med": 2.0, "speed_med": 20.0, "straightness": 0.1, "hotspot_max": 5.0}}
RULES_B = {"lower": {"snr_med": 2.0}, "iqr": {"snr_med": 1.0}}
T_EXP = 0.012


def _write(path, frames, fps=30):
    import av

    h, w = frames[0].shape[:2]
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=fps)
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        s.options = {"crf": "8", "preset": "veryfast"}
        for img in frames:
            for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(img), format="bgr24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    return path


def _synthetic_frames(n=120, size=(400, 224), seed=3):
    cv2.setRNGSeed(seed)
    src = SyntheticLiveSource(width=size[0], height=size[1], realtime=False, seed=seed)
    src.open()
    return [src.read().image for _ in range(n)]


def _pan_frames(n=110, pan=(45, 75), step=4):
    """Moving dots on a textured scene; the camera pans by `step` px per frame during `pan` frames."""
    rng = np.random.default_rng(2)
    big = np.clip(cv2.GaussianBlur(rng.normal(60, 25, (300, 900)).astype(np.float32), (0, 0), 3), 0, 255)
    yy, xx = np.mgrid[0:240, 0:320]
    out, x0 = [], 20
    for i in range(n):
        if pan[0] <= i < pan[1]:
            x0 += step
        img = big[30:270, x0:x0 + 320].astype(np.float64) + rng.normal(0, 1.5, (240, 320))
        for k in range(8):
            px, py = (15 + 37 * k + 5 * i) % 320, (20 + 25 * k + 1.5 * i) % 240
            img += 160 * np.exp(-((xx - px) ** 2 + (yy - py) ** 2) / 2.0)
        g = np.clip(img, 0, 255).astype(np.uint8)
        out.append(np.stack([g // 2, (g * 3) // 4, g], axis=2))
    return out


def _rules_cfg(rules, dump=False):
    return hp_config("rules", overrides={"verify": {"rules": {"thresholds": {"file_native": rules}}, "dump": dump}})


def _dump_cfg():
    return hp_config("accept_all", overrides={"verify": {"dump": True}})


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """Two clips (synthetic embers; dots with a camera pan), each processed online with a rules
    threshold set (and a dump, for its windows) and with accept_all and a dump."""
    from wfglink.outputs.process import process_clip

    d = tmp_path_factory.mktemp("replay")
    out = {}
    for name, frames, rules in (("embers", _synthetic_frames(), RULES_A), ("pan", _pan_frames(), RULES_B)):
        clip = _write(d / f"{name}.mp4", frames)
        process_clip(clip, d / f"{name}_dump", _dump_cfg(), t_exp=T_EXP, overlay=False)
        process_clip(clip, d / f"{name}_rules", _rules_cfg(rules, dump=True), t_exp=T_EXP, overlay=False)
        out[name] = {"clip": clip, "dump": d / f"{name}_dump", "rules": d / f"{name}_rules", "thresholds": rules}
    out["root"] = d
    return out


def _online(run, name):
    return pd.read_parquet(Path(run) / "high_precision" / f"{name}.parquet")


@pytest.mark.parametrize("clip", ["embers", "pan"])
def test_replaying_rules_on_an_accept_all_dump_equals_the_online_rules_run(runs, clip):
    r = runs[clip]
    cfg = _rules_cfg(r["thresholds"])
    dump = load_dump(r["dump"])
    res = replay(dump, cfg, RuleScorer(r["thresholds"], 4))
    online = _online(r["rules"], "hp_decisions")
    cmp = compare_decisions(online, res.decisions)
    assert cmp["identical"], cmp
    a = online.set_index("key").sort_index()
    b = res.decisions.set_index("key").sort_index()
    assert (a["state"] == b["state"]).all() and (a["reason"] == b["reason"]).all()
    assert np.array_equal(a["t_decision"].to_numpy(), b["t_decision"].to_numpy(), equal_nan=True)
    assert compare_events(_online(r["rules"], "hp_events"), res.events)["identical"]
    if clip == "embers":
        assert {"method_accepted", "rejected"} <= set(online["state"])            # the rules decide both ways
    else:
        assert dump.hp_frames["motion_unsupported"].any()                         # the pan was flagged
        assert (_online(r["rules"], "hp_frames")["withheld"]).any()


def test_replaying_the_control_equals_the_dump_run_itself(runs):
    dump = load_dump(runs["embers"]["dump"])
    res = replay_many(dump, {"aa": AcceptAll(), "rules": RuleScorer(RULES_A, 4)}, _dump_cfg())
    assert compare_decisions(dump.decisions, res["aa"].decisions)["identical"]
    assert compare_events(dump.events, res["aa"].events)["identical"] and len(dump.events) > 0
    assert len(res["rules"].accepted_ids()) < len(res["aa"].accepted_ids())       # one pass, two scorers


def test_replaying_a_pinned_patch_model_with_hit_scalars_equals_the_online_run(runs, tmp_path):
    """The patch family's run-time path (window patches and hit scalars) online and on replay."""
    from wfglink.outputs.process import process_clip
    from wfglink.provenance import sha256_file
    from wfglink.verify.models import LogReg, Model, save
    from wfglink.verify.scorers import PatchScorer, build_scorer
    from wfglink.verify.train import PATCH_PCA_K, fit_pca, patch_names

    rng = np.random.default_rng(0)
    P = rng.normal(0, 1, (200, 2 * 17 * 17))
    pca = fit_pca(P, PATCH_PCA_K)
    names = patch_names()
    X = np.hstack([pca.transform(P), rng.normal(0, 1, (200, len(names) - PATCH_PCA_K))])
    est = LogReg().fit(X, (X[:, 0] + X[:, -14] > 0).astype(float))
    path = tmp_path / "patch_seed0.npz"
    save(path, Model("patch", est, names, pca=pca), {"profile": "file_native"})
    spec = {"path": str(path), "sha256": sha256_file(path), "threshold": 0.5}
    cfg = hp_config("patch", overrides={"verify": {"models": {"patch": {"file_native": spec}}}})
    online = tmp_path / "patch_run"
    process_clip(runs["embers"]["clip"], online, cfg, t_exp=T_EXP, overlay=False)
    hs = json.loads((online / "high_precision" / "hp_summary.json").read_text())
    assert hs["scorer_status"] == "available" and hs["observer_error"] is None
    scorer = build_scorer(VerifyConfig.from_cfg(cfg), "file_native")
    assert isinstance(scorer, PatchScorer)
    res = replay(load_dump(runs["embers"]["dump"]), cfg, scorer)
    dec = _online(online, "hp_decisions")
    assert compare_decisions(dec, res.decisions)["identical"]
    assert compare_events(_online(online, "hp_events"), res.events)["identical"]
    assert "method_accepted" in set(dec["state"]) and dec["state"].nunique() > 1      # it does not accept all


def test_scorers_replayed_together_decide_as_each_replayed_alone(runs):
    """replay_many builds a window once per frame and shares it among its scorers: one pass with
    several scorers gives every scorer the decisions and events of its own replay."""
    for clip in ("embers", "pan"):
        r = runs[clip]
        dump = load_dump(r["dump"])
        scorers = {"aa": AcceptAll, "a": lambda: RuleScorer(RULES_A, 4), "b": lambda: RuleScorer(RULES_B, 4)}
        together = replay_many(dump, {k: f() for k, f in scorers.items()}, _dump_cfg())
        for k, f in scorers.items():
            alone = replay_many(load_dump(r["dump"]), {k: f()}, _dump_cfg())[k]
            assert compare_decisions(alone.decisions, together[k].decisions)["identical"], (clip, k)
            assert compare_events(alone.events, together[k].events)["identical"], (clip, k)


def test_a_scorer_cannot_write_into_a_shared_window(runs):
    class Writing(RuleScorer):
        def score(self, window_vec, patch_stats):
            window_vec[0] = 0.0
            return super().score(window_vec, patch_stats)

    with pytest.raises(ReplayError, match="observer failed"):
        replay_many(load_dump(runs["embers"]["dump"]), {"w": Writing(RULES_A, 4), "aa": AcceptAll()}, _dump_cfg())


def test_replayed_windows_are_the_online_windows(runs):
    """The window features rebuilt from the dumped hit features equal those the online run computed."""
    r = runs["embers"]

    class Recording(RuleScorer):
        key = None          # set by the replay's ledger before each scoring
        observer = None     # set by replay_many: its hit buffers name the window's last hit

        def score(self, window_vec, patch_stats):
            last = self.observer.last_hits[self.key][-1]
            seen.append((self.key, last.frame, np.array(window_vec)))
            return super().score(window_vec, patch_stats)

    seen = []
    replay(load_dump(r["dump"]), _rules_cfg(RULES_A), Recording(RULES_A, 4))
    win = _online(r["rules"], "hp_windows")
    by = {}
    for row in win.itertuples(index=False):
        by.setdefault((int(row.key), int(row.frame)), []).append(np.array([getattr(row, n) for n in WINDOW_NAMES]))
    assert len(seen) > 20
    for key, frame, vec in seen:
        cands = by.get((int(key), int(frame)), [])
        assert any(np.array_equal(vec, c, equal_nan=True) for c in cands), (key, frame)


def test_replayed_counting_gives_evaluate_the_online_inputs(runs):
    """Crossings of replayed methods: the observer's own counter on the re-run tracks, so the
    inputs of evaluate.track_level equal what load_predictions reads from the online run."""
    from wfglink.verify.evaluate import load_predictions

    for clip in ("embers", "pan"):
        r = runs[clip]
        dump = load_dump(r["dump"])
        res = replay(dump, _rules_cfg(r["thresholds"]), RuleScorer(r["thresholds"], 4))
        mine, theirs = predictions(dump, res), load_predictions(r["rules"])
        key = ["track_id", "frame"]
        a = mine["points"].sort_values(key).reset_index(drop=True)
        b = theirs["points"].sort_values(key).reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False)
        ca = mine["crossings"].sort_values(["track_id", "t"]).reset_index(drop=True)
        cb = theirs["crossings"].sort_values(["track_id", "t"]).reset_index(drop=True)
        pd.testing.assert_frame_equal(ca, cb, check_dtype=False)
        assert mine["unsupported_frames"] == theirs["unsupported_frames"]
        assert mine["revoked_ids"] == theirs["revoked_ids"]
    # A retro or late acceptance still counts each crossing at its own record time.
    ev = res.events
    if len(ev):
        assert (ev["t_counted"] >= ev["t"] - 1e-9).all() and (ev["delay_s"] >= -1e-9).all()


def test_replay_refuses_another_config_and_a_run_without_a_dump(runs):
    dump = load_dump(runs["embers"]["dump"])
    other = hp_config("accept_all", overrides={"track": {"confirm_hits": 4}, "verify": {"dump": True}})
    with pytest.raises(ReplayError, match="config"):
        replay(dump, other, AcceptAll())
    with pytest.raises(ReplayError, match="tracker"):
        replay(dump, other, AcceptAll(), strict_config=False)        # the tracker then makes other tracks
    for p in ("hp_hits.parquet", "hp_patches.npz"):
        assert (runs["embers"]["dump"] / "high_precision" / p).exists()
    from wfglink.outputs.process import process_clip

    legacy = runs["root"] / "legacy_hp"
    process_clip(runs["embers"]["clip"], legacy, hp_config("accept_all"), t_exp=T_EXP, overlay=False)
    with pytest.raises(ReplayError, match="not a verify dump"):
        load_dump(legacy)


def test_replay_cli_writes_the_comparison(runs, tmp_path):
    from wfglink.verify.cli_tools import main

    assert main(["verify", "replay", str(runs["embers"]["dump"]), "--method", "accept_all", "--out",
                 str(tmp_path / "r")]) == 0
    rec = json.loads((tmp_path / "r" / "replay.json").read_text())
    assert rec["online_comparison"]["decisions"]["identical"] and rec["online_comparison"]["events"]["identical"]
    assert (tmp_path / "r" / "replay_decisions.parquet").exists()


# Freeze -------------------------------------------------------------------------------------------

DRAFT = """# A protocol draft for tests.
run_id: test_freeze
created: FILLED_AT_FREEZE
source_identity:
  scoring_commit: FILLED_AT_FREEZE          # the commit that scores
  default_config_sha256: FILLED_AT_FREEZE
populations:
  calibration_selection:
    recordings: []
  sealed_test:
    recordings: FILLED_AT_FREEZE   # from the window sets
annotation:
  windows:
    seed: 20261017
    per_recording: FILLED_AT_FREEZE
    frames_per_window: 8
    tile_px: FILLED_AT_FREEZE
    enlargement: FILLED_AT_FREEZE
targets:   # fixed before results
  accepted_track_precision: 0.5
  accepted_track_recall: 0.0
"""


@pytest.fixture(scope="module")
def frozen_inputs(runs):
    """A window set of the embers clip and its truth (two labellers who saw no ember)."""
    from wfglink.verify.truth import merge_truth, write_truth
    from wfglink.verify.windows import make_windows, read_manifest

    d = runs["root"] / "freeze_inputs"
    wdir = d / "windows"
    make_windows(runs["embers"]["clip"], wdir, n=2, k=8, seed=20261017)
    man = read_manifest(wdir)
    rows = pd.DataFrame({"window_id": man["window_id"], "k": np.nan, "x": np.nan, "y": np.nan, "confidence": np.nan,
                         "ember_id": np.nan, "size_class": "", "note": "none"})
    for n in ("a", "b"):
        rows.to_csv(d / f"{n}.csv", index=False)
    tp = write_truth(merge_truth(wdir, d / "a.csv", d / "b.csv"), d / "truth.json")
    (d / "draft.yaml").write_text(DRAFT, encoding="utf-8")
    return {"windows": wdir, "truth": tp, "draft": d / "draft.yaml"}


def test_freeze_refuses_unfilled_fields(frozen_inputs, tmp_path):
    from wfglink.verify.freeze import FreezeError, freeze

    with pytest.raises(FreezeError, match="FILLED_AT_FREEZE remains"):
        freeze(frozen_inputs["draft"], tmp_path / "p", {})                     # no window sets: recordings stay open
    extra = tmp_path / "extra.yaml"
    extra.write_text(DRAFT + "contingency: FILLED_AT_FREEZE\n", encoding="utf-8")
    fill = {"windows": {"sealed_test": [frozen_inputs["windows"]]}, "truth": [frozen_inputs["truth"]]}
    with pytest.raises(FreezeError, match="contingency"):
        freeze(extra, tmp_path / "p", fill)
    with pytest.raises(FreezeError, match="no truth"):
        freeze(frozen_inputs["draft"], tmp_path / "p", {"windows": fill["windows"]})
    assert not (tmp_path / "p" / "protocol.yaml").exists()


def test_freeze_writes_a_protocol_evaluate_accepts(runs, frozen_inputs, tmp_path, monkeypatch):
    import yaml

    from wfglink.provenance import sha256_file
    from wfglink.verify import evaluate as E
    from wfglink.verify.freeze import freeze, read_sha256

    out = tmp_path / "proto"
    rec = freeze(frozen_inputs["draft"], out, {"windows": {"sealed_test": [frozen_inputs["windows"]]},
                                               "truth": [frozen_inputs["truth"]], "scoring_commit": "abc123"})
    text = (out / "protocol.yaml").read_text(encoding="utf-8")
    assert "FILLED_AT_FREEZE" not in text and "# the commit that scores" in text      # comments kept
    assert chr(0x2014) not in text and chr(0x2013) not in text
    sha = read_sha256(str(out / "protocol.sha256"))
    assert sha == rec["sha256"] == sha256_file(out / "protocol.yaml")
    data = yaml.safe_load(text)
    assert data["source_identity"]["scoring_commit"] == "abc123"
    assert data["populations"]["sealed_test"]["recordings"] == ["embers"]
    assert data["annotation"]["windows"]["per_recording"] == {"embers": 2}
    assert data["created"].endswith("+08:00")
    with pytest.raises(E.ProtocolError, match="SHA-256"):
        E.load_protocol(out / "protocol.yaml", "0" * 64, require_clean=True)
    monkeypatch.setattr(E, "git_clean", lambda p: True)
    monkeypatch.setattr(E, "SEALED_DIR", tmp_path / "sealed")
    proto = E.load_protocol(out / "protocol.yaml", sha)
    assert proto["targets"]["precision"] == 0.5 and proto["name"] == "test_freeze" and proto["sealed"]
    res = E.evaluate_run(out / "protocol.yaml", sha, runs["embers"]["rules"], tmp_path / "eval.json")
    assert res["protocol"]["sha256"] == sha and res["track_level"]["counts"]["windows"] == 2
    assert (out / "sealed_test_scored_embers.json").exists()
    with pytest.raises(E.ProtocolError, match="scored already"):
        E.evaluate_run(out / "protocol.yaml", sha, runs["embers"]["rules"])
    (out / "protocol.yaml").write_text(text + "\n", encoding="utf-8")
    with pytest.raises(E.ProtocolError, match="SHA-256"):
        E.evaluate_run(out / "protocol.yaml", sha, runs["embers"]["rules"])


def _empty_truth(clip, d, n=2):
    """A window set of a clip and its truth (two labellers who saw no ember)."""
    from wfglink.verify.truth import merge_truth, write_truth
    from wfglink.verify.windows import make_windows, read_manifest

    wdir = d / "windows"
    make_windows(clip, wdir, n=n, k=8, seed=20261017)
    man = read_manifest(wdir)
    rows = pd.DataFrame({"window_id": man["window_id"], "k": np.nan, "x": np.nan, "y": np.nan, "confidence": np.nan,
                         "ember_id": np.nan, "size_class": "", "note": "none"})
    for n_ in ("a", "b"):
        rows.to_csv(d / f"{n_}.csv", index=False)
    return wdir, write_truth(merge_truth(wdir, d / "a.csv", d / "b.csv"), d / "truth.json")


def test_freeze_refuses_a_recording_in_two_populations(runs, frozen_inputs, tmp_path):
    from wfglink.verify.freeze import FreezeError, freeze

    w, t = frozen_inputs["windows"], frozen_inputs["truth"]
    with pytest.raises(FreezeError, match="two populations"):
        freeze(frozen_inputs["draft"], tmp_path / "p", {"windows": {"sealed_test": [w], "calibration_selection": [w]},
                                                        "truth": [t]})
    dev = tmp_path / "dev.yaml"
    dev.write_text(DRAFT.replace("populations:\n", "populations:\n  development:\n    recordings: [embers]\n"),
                   encoding="utf-8")
    with pytest.raises(FreezeError, match="development recording"):
        freeze(dev, tmp_path / "p", {"windows": {"sealed_test": [w]}, "truth": [t]})
    both = tmp_path / "both.yaml"
    both.write_text(DRAFT.replace("calibration_selection:\n    recordings: []",
                                  "calibration_selection:\n    recordings: [embers]"), encoding="utf-8")
    assert both.read_text() != DRAFT
    with pytest.raises(FreezeError, match="listed in two populations"):
        freeze(both, tmp_path / "p", {"windows": {"sealed_test": [w]}, "truth": [t]})
    assert not (tmp_path / "p" / "protocol.yaml").exists()
    rec = freeze(frozen_inputs["draft"], tmp_path / "ok", {"windows": {"sealed_test": [w]}, "truth": [t]})
    assert any("filled from the window sets only" in n for n in rec["notes"])


def test_sealed_recordings_are_scored_with_one_scorer(runs, frozen_inputs, tmp_path, monkeypatch):
    """Each sealed recording is scored once, and all with the scorer (and selection) of the first."""
    from wfglink.outputs.process import process_clip
    from wfglink.verify import evaluate as E
    from wfglink.verify.freeze import freeze

    monkeypatch.setattr(E, "git_clean", lambda p: True)
    monkeypatch.setattr(E, "SEALED_DIR", tmp_path / "sealed")
    (tmp_path / "pan_in").mkdir()
    pw, pt = _empty_truth(runs["pan"]["clip"], tmp_path / "pan_in")
    out = tmp_path / "proto"
    rec = freeze(frozen_inputs["draft"], out, {"windows": {"sealed_test": [frozen_inputs["windows"], pw]},
                                               "truth": [frozen_inputs["truth"], pt], "scoring_commit": "abc"})
    sha = rec["sha256"]
    pan_same = tmp_path / "pan_rules_a"                    # the embers run's scorer and settings on the pan clip
    process_clip(runs["pan"]["clip"], pan_same, _rules_cfg(RULES_A, dump=True), t_exp=T_EXP, overlay=False)
    hs = json.loads((runs["embers"]["rules"] / "high_precision" / "hp_summary.json").read_text())
    sel = tmp_path / "selection.json"
    sel.write_text(json.dumps({"status": "SELECTED", "family": "rules", "profile": "file_native",
                               "overlay_sha256": hs["scorer"]["overlay_sha256"],
                               "pinned_identity": {"rules": RuleScorer(RULES_A, 4).identity()}}), encoding="utf-8")
    wrong = tmp_path / "wrong_selection.json"
    wrong.write_text(json.dumps({"status": "SELECTED", "family": "temporal", "model_sha256": "0" * 64,
                                 "threshold": 0.9}), encoding="utf-8")
    with pytest.raises(E.ProtocolError, match="selection chose 'temporal'"):
        E.evaluate_run(out / "protocol.yaml", sha, runs["embers"]["rules"], selection=wrong)
    res = E.evaluate_run(out / "protocol.yaml", sha, runs["embers"]["rules"], selection=sel)
    assert res["selection"]["sha256"] and res["scorer_identity"]["method"] == "rules"
    ident = json.loads((out / E.IDENTITY_NAME).read_text())
    assert ident["identity"] == res["scorer_identity"] and (tmp_path / "sealed" / f"{sha}_identity.json").exists()
    # Another method, other thresholds, or the same scorer without the selection: refused, and the pan
    # recording's seal is not used up by a refusal.
    for run, kw, what in ((runs["pan"]["dump"], {"selection": None}, "method"),
                          (runs["pan"]["rules"], {"selection": None}, "thresholds_sha256"),
                          (pan_same, {"selection": None}, "selection_sha256")):
        with pytest.raises(E.ProtocolError, match=f"another scorer \\(.*{what}"):
            E.evaluate_run(out / "protocol.yaml", sha, run, **kw)
        assert not (out / "sealed_test_scored_pan.json").exists()
    res2 = E.evaluate_run(out / "protocol.yaml", sha, pan_same, selection=sel)
    assert res2["protocol"]["recording"] == "pan" and (out / "sealed_test_scored_pan.json").exists()
    with pytest.raises(E.ProtocolError, match="scored already"):
        E.evaluate_run(out / "protocol.yaml", sha, pan_same, selection=sel)


# Bench --------------------------------------------------------------------------------------------

def test_bench_smoke_on_a_short_synthetic_playlist(tmp_path):
    from wfglink.verify.bench import bench

    dots_clip(tmp_path / "c.mp4", frames=150)                       # 5 s at 30 fps
    (tmp_path / "pl.yaml").write_text(f"clips:\n  - clip: {tmp_path / 'c.mp4'}\n", encoding="utf-8")
    rep = bench(3.0, "accept_all", {"kind": "playlist", "path": str(tmp_path / "pl.yaml")}, out=tmp_path / "b.json")
    assert "Linux" in rep["note"] and (tmp_path / "b.json").exists()
    leg, hp = rep["modes"]["legacy"], rep["modes"]["high_precision"]
    for m in (leg, hp):
        assert "error" not in m, m.get("stderr")
        assert m["frames"]["analysed"] > 20 and m["frames"]["analysed_fps"] > 0
        assert m["publish_to_state_ms"]["median"] is not None and m["publish_to_state_ms"]["p95"] >= 0
        assert m["paints"] > 0 and m["rss_mb"]["peak"] and m["processing_ms"]["median"] is not None
    assert leg["observer_ms"]["n"] == 0 and hp["observer_ms"]["n"] > 0
    assert hp["confirmation_delay_s"]["accepted"] > 0 and hp["scorer"]["profile"] == "live_downscaled"
    assert math.isclose(hp["confirmation_delay_s"]["confirm_to_accept"]["median"], 0.0, abs_tol=1e-9)
    assert hp["publish_to_state_ms"]["decision_frames"]["status"] == "MEASURED"
    assert leg["publish_to_state_ms"]["decision_frames"]["status"] == "NOT_MEASURED"
    for m in (leg, hp):
        assert m["source_problem"] is None and m["synthetic_frames"] == 0 and m["run_live"]["states"]


def test_bench_flags_synthetic_fallback_and_unmeasured_decision_frames():
    from wfglink.verify.bench import decision_latency, source_problem

    pl = {"kind": "playlist", "path": "booth/missing.yaml"}
    assert "synthetic video" in source_problem(pl, 40, 50, {"states": {"synthetic": 50}})
    assert source_problem(pl, 0, 50, {"states": {"playing": 50}}) is None
    assert source_problem({"kind": "synthetic"}, 50, 50, {"states": {"synthetic": 50}}) is None
    off = decision_latency("high_precision", {"available": False, "profile": "live_downscaled",
                                              "reason": "method_unavailable:no_thresholds"}, [])
    assert off["status"] == "NOT_MEASURED" and "unavailable" in off["reason"] and "median" not in off
    assert decision_latency("high_precision", {"available": True}, [])["status"] == "NOT_MEASURED"
    on = decision_latency("high_precision", {"available": True}, [0.01, 0.02, 0.03])
    assert on["status"] == "MEASURED" and on["n"] == 3 and math.isclose(on["median"], 20.0)
