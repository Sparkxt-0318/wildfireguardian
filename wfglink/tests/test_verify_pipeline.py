"""High-precision verifier in the pipeline and file mode: the control equals legacy, legacy outputs stay
the same, decisions are causal and bounded, unavailable methods count nothing, and label-score works."""
import copy
import json
import math
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import pytest
from dots_clip import dots_clip, write_clip_settings

from wfglink.config import load_config
from wfglink.io.frames import Frame
from wfglink.io.synthetic_live import SyntheticLiveSource
from wfglink.pipeline import Pipeline
from wfglink.verify.config import hp_config
from wfglink.verify.ledger import ACCEPTED, PUBLIC_FIELDS

TESTS = Path(__file__).resolve().parent
RULES = {"lower": {"snr_med": 4.0, "speed_med": 40.0, "straightness": 0.6},
         "upper": {"hotspot_max": 30.0},
         "iqr": {"snr_med": 2.0, "speed_med": 20.0, "straightness": 0.1, "hotspot_max": 5.0}}


def _frames(n=100, size=(400, 225), seed=3):
    """A fixed list of synthetic frames (the source draws its noise from OpenCV's global generator,
    so two sources with one seed differ; both pipelines of a test get the same frames)."""
    cv2.setRNGSeed(seed)
    src = SyntheticLiveSource(width=size[0], height=size[1], realtime=False, seed=seed)
    src.open()
    return [src.read() for _ in range(n)]


@pytest.fixture(scope="module")
def frames():
    return _frames()


def _rules_cfg(profile="file_native", **verify):
    return hp_config("rules", overrides={"verify": {"rules": {"thresholds": {profile: RULES}}, **verify}})


def _run(cfg, frames, record=True, downscale=False, finish=True, each=None):
    pipe = Pipeline(cfg, fps=30, record=record, downscale=downscale)
    st = None
    for i, f in enumerate(frames):
        st = pipe.process(f)
        if each is not None:
            each(i, pipe, st)
    if finish:
        pipe.finish()
    return pipe, st


def _ev(counter, mod=True):
    return sorted((int(e.track_id) % 10 ** 9 if mod else int(e.track_id), e.t, e.direction, e.s) for e in counter.events)


# The control and the legacy outputs ----------------------------------------------------------------

@pytest.mark.parametrize("profile", ["file_native", "live_downscaled"])
def test_accept_all_reproduces_the_legacy_counter_events(frames, profile):
    rec, down = profile == "file_native", profile == "live_downscaled"
    leg, st0 = _run(load_config(), frames, record=rec, downscale=down)
    hp, st1 = _run(hp_config("accept_all"), frames, record=rec, downscale=down)
    obs = hp.observer
    assert obs.profile == profile and len(leg.counter.events) > 10
    assert _ev(obs.counter) == _ev(leg.counter) == _ev(hp.counter)
    assert (st1.cpc_gross, st1.cpc_net, st1.pnf, st1.speed) == (st0.cpc_gross, st0.cpc_net, st0.pnf, st0.speed)
    assert st1.precision_mode == "accept_all" and st1.precision_status == "" and st0.precision_mode == ""
    dec = obs.ledger.decisions()
    assert dec and all(d.state == ACCEPTED or d.reason == "static" for d in dec)
    assert all(d.t_decision == d.t_confirm for d in dec if d.state == ACCEPTED)


def test_a_high_precision_run_leaves_the_legacy_pipeline_unchanged(frames):
    legacy_rows, hp_rows = [], []

    def row(store):
        def f(i, pipe, st):
            s = pipe.observer.legacy_state if pipe.observer is not None else st
            store.append((s.cpc_gross, s.cpc_net, s.count_rate, s.speed, s.direction_deg, len(s.detections),
                          len(s.trails), s.warm))
        return f

    leg, _ = _run(load_config(), frames, each=row(legacy_rows))
    hp, st = _run(_rules_cfg(), frames, each=row(hp_rows))
    assert legacy_rows == hp_rows
    a, b = leg.tables(), hp.tables()
    for k in a:
        assert a[k].equals(b[k]), k
    assert _ev(leg.counter) == _ev(hp.counter)
    assert st.precision_mode == "rules"
    dec = hp.observer.ledger.decisions()
    assert {d.state for d in dec} >= {"method_accepted", "rejected"}       # the rules decide both ways


def test_default_mode_never_imports_the_verifier(tmp_path):
    code = f"""
import sys
sys.path.insert(0, {str(TESTS)!r})
from dots_clip import dots_clip
from wfglink.cli import build_parser, main
from wfglink.outputs.process import process_clip
from wfglink.ui.booth_app import LiveAnalyser
build_parser()
clip = {str(tmp_path / 'c.mp4')!r}
dots_clip(clip, frames=20)
assert main(["process", clip, "--out", {str(tmp_path / 'out')!r}, "--no-overlay", "--exposure", "0.01"]) == 0
print(sorted(m for m in sys.modules if m.startswith("wfglink.verify")))
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, res.stderr[-3000:]
    assert res.stdout.strip().splitlines()[-1] == "[]"


# Causality, timestamps, retro acceptance -------------------------------------------------------------

def _snapshot(obs):
    return ({d.key: tuple(getattr(d, f) for f in PUBLIC_FIELDS) for d in obs.ledger.decisions()},
            _ev(obs.counter, mod=False))


def test_decisions_use_past_and_current_frames_only(frames):
    m = 70
    snap = {}
    ring_ok = []

    def each(i, pipe, st):
        obs = pipe.observer
        t = frames[i].t
        ring_ok.append(all(rf.t <= t for rf in obs.ring.frames()))
        assert all(not (d.t_decision > t) for d in obs.ledger.decisions())
        if i == m - 1:
            snap["long"] = copy.deepcopy(_snapshot(obs))
            snap["state"] = (st.cpc_gross, st.precision_pending, len(st.detections))

    _run(_rules_cfg(), frames, each=each)
    short, st = _run(_rules_cfg(), frames[:m], finish=False)
    assert all(ring_ok) and len(short.observer.ring) == short.observer.vcfg.ring_frames
    assert _snapshot(short.observer) == snap["long"] and snap["long"][0]
    assert (st.cpc_gross, st.precision_pending, len(st.detections)) == snap["state"]


def test_accepted_tracks_keep_their_crossing_times_and_delays_stay_within_the_deadline(frames):
    hp, _ = _run(_rules_cfg(), frames)
    obs = hp.observer
    ev = obs.tables()["hp_events"]
    assert len(ev) and (ev["delay_s"] >= -1e-9).all() and (ev["delay_s"] <= obs.vcfg.deadline_s + 1e-9).all()
    assert (ev["t"] <= ev["t_counted"] + 1e-9).all() and (ev["t_decision"] <= ev["t_counted"] + 1e-9).all()
    assert (ev["delay_s"] > 0).any()
    legacy = {}
    for e in hp.counter.events:
        legacy.setdefault(e.track_id, []).append((e.t, e.direction, e.s))
    accepted = {d.track_id for d in obs.ledger.decisions() if d.state == ACCEPTED or d.revoked}
    for tid, g in ev.groupby("track_id"):
        assert tid in accepted
        assert sorted(zip(g["t"], g["direction"], g["s"])) == sorted(legacy.get(tid, []))
    for tid in accepted:                  # an accepted track counts exactly its legacy crossings
        assert sorted(legacy.get(tid, [])) == sorted(zip(*(ev.loc[ev["track_id"] == tid, c] for c in ("t", "direction", "s"))))


class _Late:
    """A gated scorer that is never valid until told otherwise (to force acceptances at track ends)."""

    method, threshold, min_hits, gated, available = "late", 0.5, 0, True, True

    def __init__(self):
        self.ok = False

    def score(self, w, p):
        return (1.0, True, "") if self.ok else (math.nan, False, "too_few_hits")

    def identity(self):
        return {"method": self.method}


def test_a_retro_acceptance_counts_each_crossing_at_its_own_time(frames):
    cfg = hp_config("accept_all", overrides={"verify": {"deadline_s": 1000.0}})
    pipe = Pipeline(cfg, fps=30, record=True)
    late = pipe.observer.scorer = _Late()
    for f in frames:
        st = pipe.process(f)
    assert st.cpc_gross == 0 and st.precision_pending > 0
    late.ok = True
    pipe.finish()
    obs = pipe.observer
    retro = [d for d in obs.ledger.decisions() if d.state == ACCEPTED]
    assert retro and all(d.retro for d in retro)
    ev = obs.tables()["hp_events"]
    assert len(ev) and ev["retro"].all() and (ev["t"] < ev["t_decision"]).all()
    legacy = [(e.track_id, e.t, e.direction, e.s) for e in pipe.counter.events if e.track_id in {d.track_id for d in retro}]
    assert sorted(zip(ev["track_id"], ev["t"], ev["direction"], ev["s"])) == sorted(legacy)


# Unavailable methods ----------------------------------------------------------------------------

def _patch_model(path):
    from wfglink.provenance import sha256_file
    from wfglink.verify.models import PCA, LogReg, Model, save

    rng = np.random.default_rng(0)
    X = rng.normal(0, 1, (200, 2 * 17 * 17))
    y = (X[:, 0] > 0).astype(float)
    pca = PCA().fit(X, 4)
    save(path, Model("patch", LogReg().fit(pca.transform(X), y), (), pca=pca), {"profile": "file_native"})
    return sha256_file(path)


@pytest.mark.parametrize("case", ["missing_file", "sha_mismatch", "profile_mismatch", "no_thresholds"])
def test_an_unavailable_method_accepts_nothing_and_counts_nothing(frames, tmp_path, case):
    path = tmp_path / "patch.npz"
    sha = _patch_model(path) if case != "missing_file" else "ab" * 32
    spec = {"file_native": {"path": str(path), "sha256": "00" * 32 if case == "sha_mismatch" else sha, "threshold": 0.5}}
    cfg = hp_config("rules") if case == "no_thresholds" else hp_config("patch", overrides={"verify": {"models": {"patch": spec}}})
    hp, st = _run(cfg, frames[:60], record=case != "profile_mismatch", downscale=case == "profile_mismatch")
    obs = hp.observer
    assert obs.scorer.reason == f"method_unavailable:{case}"
    dec = obs.ledger.decisions()
    assert dec and not any(d.state == ACCEPTED for d in dec)
    assert all(d.reason in (f"method_unavailable:{case}", "static") for d in dec)
    assert (st.cpc_gross, st.cpc_net, st.count_rate, st.pnf, st.speed) == (None, None, None, None, None)
    assert st.precision_status == "unavailable" and len(st.detections) == 0 and st.trails == []
    assert obs.accepted_points(st.t).shape == (0, 2) and len(obs.tables()["hp_events"]) == 0


def test_a_pinned_model_for_the_profile_is_used(frames, tmp_path):
    from wfglink.verify.scorers import PatchScorer

    path = tmp_path / "patch.npz"
    spec = {"file_native": {"path": str(path), "sha256": _patch_model(path), "threshold": 0.5}}
    hp, st = _run(hp_config("patch", overrides={"verify": {"models": {"patch": spec}}}), frames[:60])
    assert isinstance(hp.observer.scorer, PatchScorer) and st.precision_status in ("", "incomplete")
    assert {d.state for d in hp.observer.ledger.decisions()} - {"candidate"}
    ident = hp.observer.scorer.identity()
    assert ident["model_sha256"] == spec["file_native"]["sha256"] and ident["sidecar_sha256"]


# Epochs, bounded state, camera motion ------------------------------------------------------------------

def test_a_cut_starts_a_new_epoch_without_key_collisions(frames):
    leg = Pipeline(load_config(), fps=30, downscale=True)
    hp = Pipeline(hp_config("accept_all"), fps=30, downscale=True)
    other = _frames(60, seed=9)
    for p in (leg, hp):
        for f in frames[:80]:
            p.process(f)
        p.cut()
        for g in other:
            p.process(Frame(g.image, frames[79].t + 1.0 + g.t, g.index, 0.0))
        p.finish()
    obs = hp.observer
    dec = obs.ledger.decisions()
    keys = [d.key for d in dec]
    assert len(keys) == len(set(keys)) and {d.epoch for d in dec} == {0, 1} and obs.epoch == 1
    tids0 = {d.track_id for d in dec if d.epoch == 0}
    tids1 = {d.track_id for d in dec if d.epoch == 1}
    assert tids0 & tids1                                      # the new tracker reuses ids; the keys differ
    assert _ev(obs.counter) == _ev(leg.counter)


def test_state_stays_bounded_over_a_long_live_run(monkeypatch):
    import wfglink.verify.observer as O

    monkeypatch.setattr(O, "LIVE_ROWS", 50)
    pipe = Pipeline(_rules_cfg("live_downscaled"), fps=30, downscale=True)
    obs = pipe.observer
    obs.ledger.archive_cap = 20
    cv2.setRNGSeed(5)
    src = SyntheticLiveSource(width=320, height=180, realtime=False, seed=5, rate_hz=60.0)
    src.open()
    sizes = []
    for i in range(360):
        if i and i % 90 == 0:
            pipe.cut()
        f = src.read()
        pipe.process(f)
        sizes.append((len(obs._buffers), len(obs.ledger.active), len(obs._withheld)))
        assert set(obs._buffers) <= set(obs.ledger.active)
        assert len(obs.ring) <= obs.vcfg.ring_frames and len(obs._batches) <= obs._history
    assert obs.epoch == 3 and obs.ledger.dropped > 0 and len(obs.ledger.archive) <= 20
    assert len(obs._rows) <= 50 and len(obs._ms) <= 50 and len(obs._event_info) <= 50 + 200
    assert len(obs.counter._state) <= len(pipe.tracker.active_tracks()) + 1
    assert max(s[0] for s in sizes) < 200 and max(s[2] for s in sizes) <= 2
    assert not obs._shown                                      # the booth keeps no per-frame history


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
        out.append(Frame(np.stack([g // 2, (g * 3) // 4, g], axis=2), i / 30.0, i, 0.0))
    return out


def test_camera_motion_withholds_decisions_and_crossings():
    fr = _pan_frames()
    rules = {"lower": {"snr_med": 2.0}, "iqr": {"snr_med": 1.0}}
    hp, _ = _run(hp_config("rules", overrides={"verify": {"rules": {"thresholds": {"file_native": rules}}}}), fr)
    obs = hp.observer
    hf = obs.tables()["hp_frames"]
    held = hf.loc[hf["withheld"], "t"].to_numpy()
    assert held.size and held.min() <= fr[48].t and held.max() >= fr[75].t
    assert set(hf.loc[hf["withheld"], "status"]) == {"camera_motion"}
    ev = obs.tables()["hp_events"]
    for a, b in obs._withheld:
        assert not ((ev["t"] > a) & (ev["t"] < b)).any()
    assert obs.stats["withheld_s"] > 0.8 and obs.stats["motion_unsupported_s"] > 0.8
    dec = obs.ledger.decisions()
    assert all(not (a < d.t_decision < b) for d in dec if d.state == ACCEPTED for a, b in obs._withheld)
    ctrl, _ = _run(hp_config("accept_all"), fr)                 # the control is never gated
    assert ctrl.observer.stats["withheld_s"] == 0 and _ev(ctrl.observer.counter) == _ev(ctrl.counter)


# File mode -----------------------------------------------------------------------------------------

ROI = [20, 10, 300, 230]


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """A dots clip processed by `process` in default mode and with --high-precision accept_all."""
    from wfglink.cli import main

    d = tmp_path_factory.mktemp("hp")
    clip = d / "dots.mp4"
    grid = [(20 + 50 * i, 15 + 45 * j, 4, 3) for i in range(6) for j in range(5)]
    truth = dots_clip(clip, dots=grid, frames=75)
    cs = write_clip_settings(d / "dots.yaml", clip, roi=ROI, segments_s=[[0.0, 2.5]])
    assert main(["process", str(cs), "--out", str(d / "legacy"), "--no-overlay"]) == 0
    assert main(["process", str(cs), "--out", str(d / "hp"), "--no-overlay", "--high-precision", "accept_all"]) == 0
    return {"dir": d, "clip": clip, "settings": cs, "truth": truth}


def _clean(summary):
    return {k: v for k, v in summary.items() if k not in ("created", "seconds", "git_commit", "git_dirty", "high_precision")}


def test_process_keeps_the_legacy_outputs_and_writes_high_precision(runs):
    a, b = runs["dir"] / "legacy", runs["dir"] / "hp"
    for name in ("detections", "frames", "track_points", "tracks", "field"):
        x, y = pd.read_parquet(a / f"{name}.parquet"), pd.read_parquet(b / f"{name}.parquet")
        if name == "frames":
            x, y = x.drop(columns="ms"), y.drop(columns="ms")
        assert x.equals(y), name
    sa, sb = (json.loads((p / "summary.json").read_text()) for p in (a, b))
    assert "high_precision" not in sa and _clean(sa) == _clean(sb)
    hp = sb["high_precision"]
    assert hp["method"] == "accept_all" and hp["profile"] == "file_native" and hp["status"] == "ok"
    d = b / "high_precision"
    for name in ("hp_decisions", "hp_events", "hp_tracks", "hp_frames", "hp_points"):
        assert (d / f"{name}.parquet").exists(), name
    hs = json.loads((d / "hp_summary.json").read_text())
    assert hs["raw_reference"] == sa["totals"]
    for k in ("cpc_gross", "cpc_gross_ci", "cpc_net", "cpc_net_ci", "count_rate_per_s", "count_rate_ci", "pnf",
              "duration_s"):
        assert hs["totals"][k] == sa["totals"][k], k                # the control's totals are the legacy ones
    assert hs["scorer"]["overlay_sha256"] and hs["scorer"]["config_sha256"] != sa["config_sha256"]
    assert hs["decisions"]["by_state"]["method_accepted"] > 0 and hs["time"]["withheld_s"] == 0
    assert hs["delays"]["confirm_to_decision_s"]["median"] == 0.0 and hs["observer_ms"]["median"] > 0
    tr = pd.read_parquet(d / "hp_tracks.parquet")
    legacy_tracks = pd.read_parquet(a / "tracks.parquet")
    assert set(legacy_tracks.columns) <= set(tr.columns) and len(tr) == hs["decisions"]["ever_accepted"]
    assert sb["high_precision"]["accepted_tracks"] == len(tr)
    fl = json.loads((d / "frame_level" / "summary.json").read_text())
    assert fl["input"] == sa["input"]
    det = pd.read_parquet(d / "frame_level" / "detections.parquet")
    assert list(det.columns) == list(pd.read_parquet(a / "detections.parquet").columns) and 0 < len(det)


def test_label_score_scores_the_frame_level_pseudo_run(runs, tmp_path):
    from wfglink.cli import main
    from wfglink.validate import labels as L

    tiles = tmp_path / "tiles"
    L.make_tiles(runs["settings"], tiles, frames=6, reserve=1, tiles_per_frame=2, tile_px=64, seed=3)
    man = pd.read_csv(tiles / "manifest.csv", dtype={"tile_id": str})
    rows = []
    for _, t in man.iterrows():
        p = runs["truth"][int(round(t["pts_s"] * 30))] - [ROI[0] + t["x0"], ROI[1] + t["y0"]]
        p = p[(p[:, 0] >= -0.5) & (p[:, 0] < t["w"] - 0.5) & (p[:, 1] >= -0.5) & (p[:, 1] < t["h"] - 0.5)]
        rows += [{"tile_id": t["tile_id"], "x": x, "y": y, "confidence": 1.0, "note": ""} for x, y in p]
        if not len(p):
            rows.append({"tile_id": t["tile_id"], "x": np.nan, "y": np.nan, "confidence": np.nan, "note": "none"})
    labels = tmp_path / "labels.csv"
    pd.DataFrame(rows).to_csv(labels, index=False)
    fl = runs["dir"] / "hp" / "high_precision" / "frame_level"
    res = L.score_labels(tiles, labels, fl)
    raw = L.score_labels(tiles, labels, runs["dir"] / "legacy")
    assert res["frames"] > 0 and res["tp"] > 0 and res["fp"] == 0 and res["tp"] <= raw["tp"]
    assert main(["label-score", str(tiles), "--labels", str(labels), "--run", str(fl), "--out",
                 str(tmp_path / "s.json")]) == 0


def test_process_flags_dump_and_the_tracking_only_scope(runs, tmp_path, monkeypatch):
    from wfglink.cli import main
    from wfglink.outputs.process import process_clip

    with pytest.raises(SystemExit):
        main(["process", str(runs["clip"]), "--out", str(tmp_path / "x"), "--verify-dump"])
    out = tmp_path / "dump"
    assert main(["process", str(runs["clip"]), "--out", str(out), "--no-overlay", "--exposure", "0.012",
                 "--high-precision", "--verify-dump"]) == 0
    d = out / "high_precision"
    hs = json.loads((d / "hp_summary.json").read_text())
    assert hs["method"] == "rules" and hs["status"] == "unavailable" and hs["totals"] is None
    hits = pd.read_parquet(d / "hp_hits.parquet")
    z = np.load(d / "hp_patches.npz")
    assert len(hits) and z["patches"].shape[1:] == (2, 17, 17) and len(pd.read_parquet(d / "hp_windows.parquet"))

    captured = {}

    class Capture:
        def __init__(self, path, *args):
            self.key = Path(path).parent.name
            captured[self.key] = []

        def write(self, state):
            captured[self.key].append(state)

        def close(self):
            pass

    monkeypatch.setattr("wfglink.outputs.process.OverlayWriter", Capture)
    o1, o2 = tmp_path / "t_legacy", tmp_path / "t_hp"
    s1 = process_clip(runs["clip"], o1, load_config(), metrics_scope="tracking_only", overlay=True)
    s2 = process_clip(runs["clip"], o2, hp_config("accept_all"), metrics_scope="tracking_only", overlay=True)
    assert _clean(s1) == _clean(s2)
    for name in ("detections", "track_points", "tracks"):
        assert pd.read_parquet(o1 / f"{name}.parquet").equals(pd.read_parquet(o2 / f"{name}.parquet")), name
    hs = json.loads((o2 / "high_precision" / "hp_summary.json").read_text())
    assert hs["status"] == "not_real_time" and hs["totals"] is None
    assert set(hs["decisions"]["by_reason"]) <= {"insufficient_evidence:timebase_not_real_time", "rejected:static"}
    assert len(pd.read_parquet(o2 / "high_precision" / "hp_events.parquet")) == 0
    hp_states, legacy_states = captured["high_precision"], captured[o2.name]
    assert len(hp_states) == len(legacy_states) == len(captured[o1.name])
    assert all(s.precision_mode == "accept_all" and s.precision_status == "not_real_time" for s in hp_states)
    assert all(s.precision_mode == "" for s in legacy_states) and all(s.cpc_gross is None for s in hp_states)


def test_withheld_time_is_measured_inside_the_counted_span():
    from wfglink.outputs.process import _withheld_in

    fr = pd.DataFrame({"t": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5], "withheld": [True, True, False, True, True, False]})
    assert _withheld_in(fr, 0.0, 0.5) == pytest.approx(0.3)        # frames 0.1, 0.3 and 0.4 (0.0 stands for no time)
    assert _withheld_in(fr, 0.25, 0.5) == pytest.approx(0.15)      # warm-up motion before the span does not count
    assert _withheld_in(fr.iloc[0:0], 0.0, 1.0) == 0.0


# A track accepted, then revoked; the overlay; a failing verifier ------------------------------------

def _rest_clip(path, W=320, H=240, fps=30, frames=150, seed=0):
    """Two embers from frame 15: one flies across the default gate (x = 0.62 W) and comes to rest
    at x = 230 (a static light from then on), the other keeps moving."""
    import av

    rng = np.random.default_rng(seed)
    base = 18 + rng.normal(0, 2.0, (H, W))
    yy, xx = np.mgrid[0:H, 0:W]
    with av.open(str(path), "w") as c:
        st = c.add_stream("libx264", rate=fps)
        st.width, st.height, st.pix_fmt = W, H, "yuv420p"
        st.options = {"crf": "10", "preset": "veryfast"}
        for k in range(frames):
            lum = base + rng.normal(0, 1.0, (H, W))
            if k >= 15:
                for x, y in ((min(60 + 4 * (k - 15), 230), 120 + 0.5 * min(k - 15, 42)),
                             (40 + 4 * (k - 15) % 240, 60 + 1.0 * ((k - 15) % 120))):
                    lum += 170 * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.0)
            g = np.clip(lum, 0, 255).astype(np.uint8)
            for pkt in st.encode(av.VideoFrame.from_ndarray(np.stack([g // 2, (g * 3) // 4, g], axis=2),
                                                            format="bgr24")):
                c.mux(pkt)
        for pkt in st.encode():
            c.mux(pkt)


@pytest.fixture(scope="module")
def rest_runs(tmp_path_factory):
    from wfglink.outputs.process import process_clip

    d = tmp_path_factory.mktemp("rest")
    clip = d / "rest.mp4"
    _rest_clip(clip)
    kw = dict(t_exp=0.012, overlay=True, overlay_size=(320, 180), lang="en")
    process_clip(clip, d / "legacy", load_config(), **kw)
    process_clip(clip, d / "hp", hp_config("accept_all"), **kw)
    return d


def test_a_revoked_track_is_one_track_in_every_high_precision_output(rest_runs):
    hp = rest_runs / "hp" / "high_precision"
    dec = pd.read_parquet(hp / "hp_decisions.parquet")
    rev = dec[dec["revoked"]]
    assert len(rev) == 1 and (rev["state"] == "rejected").all() and (rev["reason"] == "static").all()
    r = rev.iloc[0]
    assert r["t_accept"] == r["t_confirm"] < r["t_decision"] and r["frame_accept"] < r["frame_decision"]
    hs = json.loads((hp / "hp_summary.json").read_text())
    tr = pd.read_parquet(hp / "hp_tracks.parquet")
    assert int(r["track_id"]) in set(tr["track_id"]) and tr.loc[tr["track_id"] == r["track_id"], "revoked"].all()
    assert len(tr) == hs["decisions"]["ever_accepted"] and hs["decisions"]["revoked"] == 1
    crossed = tr.loc[tr["track_id"] == r["track_id"], ["crossings_pos", "crossings_neg"]].to_numpy().sum()
    assert crossed >= 1                                         # crossed the gate before it came to rest
    assert int(tr["crossings_pos"].sum() + tr["crossings_neg"].sum()) == hs["totals"]["cpc_gross"]
    assert hs["totals"]["cpc_gross"] == json.loads((rest_runs / "legacy" / "summary.json").read_text())["totals"]["cpc_gross"]
    assert hs["delays"]["confirm_to_decision_s"]["n"] == len(tr)
    summary = json.loads((rest_runs / "hp" / "summary.json").read_text())["high_precision"]
    assert summary["accepted_tracks"] == len(tr) and summary["revoked_tracks"] == 1
    # Every point drawn as accepted is a point of an ever-accepted track, marked accepted_at.
    pts = pd.read_parquet(hp / "hp_points.parquet")
    det = pd.read_parquet(hp / "frame_level" / "detections.parquet")
    drawn = set(zip(det["frame"], det["x"].round(6), det["y"].round(6)))
    shown = pts[pts["accepted_at"]]
    assert drawn and drawn <= set(zip(shown["frame"], shown["x_meas"].round(6), shown["y_meas"].round(6)))
    own = pts[pts["track_id"] == r["track_id"]]
    assert own["accepted_at"].any() and not own.loc[own["t"] >= r["t_decision"] - 1e-9, "accepted_at"].any()


def test_the_legacy_overlay_of_a_high_precision_run_is_unchanged(rest_runs):
    from wfglink.provenance import sha256_file

    a, b = rest_runs / "legacy" / "overlay.mp4", rest_runs / "hp" / "overlay.mp4"
    assert sha256_file(a) == sha256_file(b)
    hp = rest_runs / "hp" / "high_precision" / "overlay.mp4"
    assert hp.is_file() and sha256_file(hp) != sha256_file(a)     # the high-precision screen carries its tag


@pytest.mark.parametrize("hook", ["frame", "retire"])
def test_a_failing_verifier_never_stops_the_legacy_analysis(frames, monkeypatch, hook):
    import wfglink.verify.observer as O
    from wfglink.verify.ledger import Ledger

    calls = {"n": 0}

    def boom(*a, **k):
        calls["n"] += 1
        raise RuntimeError("injected")

    if hook == "frame":
        real = O.hit_features
        monkeypatch.setattr(O, "hit_features", lambda *a, **k: boom() if a[-1] is not None and k["frame"] == 40
                            else real(*a, **k))
    else:
        monkeypatch.setattr(Ledger, "on_finished", boom)
    leg, st0 = _run(load_config(), frames)
    hp, st1 = _run(hp_config("accept_all"), frames)
    obs = hp.observer
    assert calls["n"] == 1 and obs.failed == "RuntimeError: injected"
    assert obs.scorer.reason == "method_unavailable:observer_error"
    a, b = leg.tables(), hp.tables()
    for k in a:
        assert a[k].equals(b[k]), k
    assert _ev(leg.counter) == _ev(hp.counter) and obs.legacy_state.cpc_gross == st0.cpc_gross
    assert st1.precision_status == "unavailable" and st1.cpc_gross is None and len(st1.detections) == 0
    assert set(obs.tables()) >= {"hp_decisions", "hp_events", "hp_tracks", "hp_frames"}


def test_tracking_only_reports_the_timebase_before_an_unavailable_method_and_a_cut_dump(runs, tmp_path, monkeypatch):
    import wfglink.verify.observer as O
    from wfglink.outputs.process import process_clip

    process_clip(runs["clip"], tmp_path / "t", hp_config("rules"), metrics_scope="tracking_only", overlay=False)
    hs = json.loads((tmp_path / "t" / "high_precision" / "hp_summary.json").read_text())
    assert hs["status"] == "not_real_time" and hs["scorer_status"] == "method_unavailable:no_thresholds"
    rows = pd.read_parquet(tmp_path / "t" / "high_precision" / "hp_frames.parquet")
    assert set(rows["status"]) == {"not_real_time"}
    monkeypatch.setattr(O, "DUMP_MAX_ROWS", 25)
    process_clip(runs["clip"], tmp_path / "d", hp_config("accept_all", overrides={"verify": {"dump": True}}),
                 t_exp=0.012, overlay=False)
    hs = json.loads((tmp_path / "d" / "high_precision" / "hp_summary.json").read_text())
    assert hs["dump"]["dump_truncated"] and hs["dump"]["dump_rows"] <= 25 and hs["status"] == "partial"
    assert "dump" in hs["status_reason"]
