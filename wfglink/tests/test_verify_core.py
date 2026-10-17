"""High-precision verifier, core parts: config, ring, motion, hotspots, features, models, scorers, ledger."""
import math

import cv2
import numpy as np
import pytest

from wfglink.detect.candidates import Detections, DetectorState
from wfglink.verify import ledger as L
from wfglink.verify.config import OVERLAY, VerifyConfig, hp_config, profile_of
from wfglink.verify.features import (FEATURE_NAMES, FI, WI, WINDOW_NAMES, HitRecord, Kin, hit_features,
                                     window_features)
from wfglink.verify.models import MLP, PCA, LogReg, Model, ModelUnavailable, load, make_envelope, save
from wfglink.verify.motion import GlobalMotion, HotspotMap
from wfglink.verify.ring import FrameRing, RingFrame
from wfglink.verify.scorers import AcceptAll, RuleScorer, Unavailable, build_scorer, ood

VCFG = VerifyConfig.from_cfg(hp_config("rules"))


# Config ------------------------------------------------------------------------------------

def test_config_section_is_opt_in_and_complete():
    from wfglink.config import load_config

    assert VerifyConfig.from_cfg(load_config()) is None
    assert OVERLAY.name == "high_precision.yaml"
    v = VerifyConfig.from_cfg(hp_config("patch"))
    assert v.method == "patch" and v.mode == "high_precision" and v.window_hits == 6 and v.min_hits == 4
    assert v.patch.factor == 3 and v.budget("file_native") == 4096 and v.budget("live_downscaled") == 1024
    assert v.models["patch"]["file_native"].sha256 is None
    cfg = hp_config("rules")
    del cfg["verify"]["motion"]["hold_s"]
    with pytest.raises(KeyError, match="verify.motion.hold_s"):
        VerifyConfig.from_cfg(cfg)
    with pytest.raises(ValueError):
        hp_config("magic")
    assert profile_of(True, False) == "file_native" and profile_of(False, True) == "live_downscaled"
    assert profile_of(False, False) == "unprofiled"
    for target, context in ((17, 34), (16, 48)):            # an even factor or an even target cannot centre
        bad = hp_config("rules", overrides={"verify": {"patch": {"target_px": target, "context_px": context}}})
        with pytest.raises(ValueError, match="odd multiple"):
            VerifyConfig.from_cfg(bad)
    assert "\u2014" not in OVERLAY.read_text(encoding="utf-8") and "\u2013" not in OVERLAY.read_text(encoding="utf-8")


# Ring ----------------------------------------------------------------------------------------

def test_ring_keeps_the_last_frames_and_refuses_a_frame_out_of_order():
    ring = FrameRing(3)
    z = np.zeros((4, 4), np.uint8)
    for i in range(5):
        ring.push(RingFrame(i, i * 0.1, z, z, z.astype(np.float32)))
    assert len(ring) == 3 and [f.index for f in ring.frames()] == [2, 3, 4]
    assert ring.back(1).index == 4 and ring.back(3).index == 2 and ring.back(4) is None
    with pytest.raises(ValueError):
        ring.push(RingFrame(9, 0.4, z, z, z.astype(np.float32)))
    ring.clear()
    assert len(ring) == 0 and ring.latest_t is None


# Motion and hotspots ---------------------------------------------------------------------------

def _texture(seed=0, shape=(500, 1300)):
    rng = np.random.default_rng(seed)
    return np.clip(cv2.GaussianBlur(rng.normal(60, 30, shape).astype(np.float32), (0, 0), 3), 0, 255).astype(np.uint8)


def test_a_pan_is_camera_motion_and_static_noise_is_not():
    rng = np.random.default_rng(1)
    big = _texture()
    mc = VCFG.motion

    def run(frames):
        m = GlobalMotion(mc)
        return [m.update(f, i / 30.0) for i, f in enumerate(frames)]

    noisy = lambda img: np.clip(img + rng.normal(0, 2, img.shape), 0, 255).astype(np.uint8)  # noqa: E731
    static = run([noisy(big[50:410, 50:690]) for _ in range(40)])
    assert not any(s.unsupported for s in static) and max(s.shift_px for s in static) < mc.max_shift_px
    pan = run([noisy(big[50:410, 50 + 3 * max(0, i - 10):690 + 3 * max(0, i - 10)]) for i in range(40)])
    flags = [s.unsupported for s in pan]
    assert not any(flags[:11]) and all(flags[12:])          # two moving frames in a row, then held
    assert all(2.0 < s.shift_px < 4.5 for s in pan[11:])
    # Many bright embers moving together (a shower in the wind) on a static scene are not a pan.
    yy, xx = np.mgrid[0:360, 0:640]
    emb = rng.uniform([0, 0], [640, 360], (60, 2))
    frames = []
    for i in range(30):
        img = big[50:410, 50:690].astype(np.float64)
        for x, y in emb + [5.0 * i, -4.0 * i]:
            img += 150 * np.exp(-((xx - x % 640) ** 2 + (yy - y % 360) ** 2) / 2.0)
        frames.append(noisy(np.clip(img, 0, 255)))
    assert not any(s.unsupported for s in run(frames))
    # A dark textureless scene: noise is not a shift.
    dark = run([noisy(np.full((360, 640), 10, np.uint8)) for _ in range(40)])
    assert not any(s.unsupported for s in dark)
    # The hold: once moving, decisions stay withheld for hold_s.
    m = GlobalMotion(mc)
    for i in range(14):
        x0 = 50 + 3 * i
        st = m.update(noisy(big[50:410, x0:x0 + 640]), i / 30.0)
    assert st.unsupported and math.isclose(m.unsupported_until, 13 / 30.0 + mc.hold_s)


def _scene_texture(seed=0, shape=(360, 640)):
    """A textured scene with the contrast of real footage at thumbnail size (35 DN, 6 px grain)."""
    g = cv2.GaussianBlur(np.random.default_rng(seed).normal(0, 1, shape).astype(np.float32), (0, 0), 6)
    return np.clip(100 + g / g.std() * 35, 0, 255).astype(np.uint8)


def test_large_local_changes_on_a_fixed_camera_are_not_camera_motion():
    rng = np.random.default_rng(4)
    base = _scene_texture()
    mc = VCFG.motion
    yy, xx = np.mgrid[0:360, 0:640]

    def run(frames):
        m = GlobalMotion(mc)
        return [m.update(np.clip(f + rng.normal(0, 2, f.shape), 0, 255).astype(np.uint8), i / 30.0)
                for i, f in enumerate(frames)]

    still = [base.astype(np.float64)] * 10
    # A flickering bright region over 35 % of the picture (flames, a lit wall).
    left = xx < 0.35 * 640
    flicker = []
    for i in range(40):
        img = base.astype(np.float64)
        img[left] += 60 + 50 * math.sin(1.7 * i) + rng.normal(0, 15, img.shape)[left]
        flicker.append(img)
    st = run(still + flicker)
    assert not any(s.unsupported for s in st) and 2 <= max(s.tiles_changed for s in st) <= 4   # local, not global
    # Textured flames over 40 % of the picture, changing every frame.
    box = (xx > 200) & (xx < 480) & (yy > 60)
    flames = []
    for i in range(40):
        blob = cv2.GaussianBlur(rng.normal(0, 1, (360, 640)), (0, 0), 25)
        img = base.astype(np.float64)
        img[box] += np.abs(blob / blob.std() * 40)[box]
        flames.append(img)
    assert not any(s.unsupported for s in run(still + flames))
    # Smooth changes over the whole picture: an exposure step, a gain flicker, drifting haze.
    expo = [base + (20.0 if i >= 5 else 0.0) for i in range(30)]
    gain = [base * (1.3 if i % 2 else 1.0) for i in range(30)]
    haze = [base + 25 * np.exp(-((xx - 20 * i) ** 2 + (yy - 180) ** 2) / (2 * 150.0 ** 2)) for i in range(30)]
    for frames in (expo, gain, haze):
        assert not any(s.unsupported for s in run(still + frames))
    # A zoom and a rotation (no single shift explains them) are camera motion; one cut is not.
    for kind in ("zoom", "rotate"):
        moved = []
        for i in range(20):
            a, z = (0.0, 1.0 + 0.02 * i) if kind == "zoom" else (1.0 * i, 1.0)
            m = cv2.getRotationMatrix2D((320, 180), a, z)
            moved.append(cv2.warpAffine(base, m, (640, 360), borderMode=cv2.BORDER_REFLECT).astype(np.float64))
        st = run(still + moved)
        assert not any(s.unsupported for s in st[:11]) and all(s.unsupported for s in st[12:]), kind
        assert all(s.tiles_changed >= 7 for s in st[11:]) and max(s.shift_px for s in st) < mc.max_shift_px
    cut = run(still + [_scene_texture(7).astype(np.float64)] * 10)
    assert cut[10].tiles_changed == 9 and not any(s.unsupported for s in cut)


def test_a_fixed_camera_real_clip_is_not_camera_motion():
    """C6 (NIST Dragon, a dense shower on a fixed camera; regression of the residual test, which
    had flagged 78 % of it). Skipped when the clip is not fetched (data/raw is not in git)."""
    from wfglink import PROJECT_ROOT
    from wfglink.io.sources import FileSource

    clip = PROJECT_ROOT / "data" / "raw" / "C6_nist_dragon.mp4"
    if not clip.is_file():
        pytest.skip("data/raw/C6_nist_dragon.mp4 not fetched")
    m = GlobalMotion(VCFG.motion)
    src = FileSource(clip, start_s=17.05)
    src.open()
    st, prev = [], None
    try:
        while (f := src.read()) is not None and f.t <= 22.55 - 17.05:
            y = cv2.cvtColor(f.image, cv2.COLOR_BGR2GRAY)
            if prev is not None and np.array_equal(y, prev):
                continue
            prev = y
            st.append(m.update(y, f.t))
    finally:
        src.close()
    assert len(st) > 100
    assert np.mean([s.unsupported for s in st]) < 0.02 and max(s.shift_px for s in st) < VCFG.motion.max_shift_px


def test_hotspots_are_read_before_the_frame_is_added_and_decay_in_real_time():
    h = HotspotMap(VCFG.hotspot)
    h.ensure((64, 64))
    assert h.read([5.0], [5.0], 0.0)[0] == 0.0
    h.add([5.0, 6.0, 40.0], [5.0, 6.0, 40.0], 0.0)
    assert h.read([5.0, 40.0, 60.0], [5.0, 40.0, 60.0], 0.0).tolist() == [2.0, 1.0, 0.0]
    hl = VCFG.hotspot.half_life_s
    assert math.isclose(h.read([5.0], [5.0], hl)[0], 1.0)
    h.add([], [], 2 * hl)
    assert math.isclose(h.read([5.0], [5.0], 2 * hl)[0], 0.5)


# Features ------------------------------------------------------------------------------------

def _scene(points, shape=(120, 160), seed=0, bg_level=20.0, sigma=2.0, amp=40.0):
    rng = np.random.default_rng(seed)
    bg = np.full(shape, bg_level, np.float32) + np.linspace(0, 30, shape[1], dtype=np.float32)[None, :]
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    lum = bg + rng.normal(0, 1.0, shape).astype(np.float32)
    for x, y in points:
        lum += amp * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / 2.0)
    st = DetectorState(luma=np.clip(lum, 0, 255).astype(np.uint8), background=np.clip(bg, 0, 255).astype(np.uint8),
                       sigma=np.full(shape, sigma, np.float32))
    pts = np.array(points, np.float64)
    det = Detections(x=pts[:, 0], y=pts[:, 1], area=np.full(len(pts), 9.0), peak=np.full(len(pts), 100.0),
                     flux=np.full(len(pts), 500.0), lam1=np.ones(len(pts)), lam2=np.ones(len(pts)),
                     theta=np.zeros(len(pts)), length=np.full(len(pts), 2.0), width=np.full(len(pts), 3.0),
                     sat_frac=np.zeros(len(pts)), color=np.array([np.nan] + [1.5] * (len(pts) - 1)),
                     flags=np.zeros(len(pts), np.uint8))
    return det, st


def test_hit_features_snr_background_and_centred_patches():
    det, st = _scene([(40.0, 50.0), (100.0, 30.0), (3.0, 3.0)])
    hot = HotspotMap(VCFG.hotspot)
    hot.ensure(st.luma.shape)
    b = hit_features(det, st, FrameRing(4), hot, None, None, patch_cfg=VCFG.patch, t=0.0, frame=0)
    assert b.values.shape == (3, len(FEATURE_NAMES)) and b.patches.shape == (3, 2, 17, 17)
    assert b.patches.dtype == np.float16 and not b.over_budget.any()
    assert np.allclose(b.col("snr"), 50.0)                     # peak 100 / sigma 2
    assert b.col("bg_luma")[0] == st.background[50, 40]
    assert b.col("color_nan").tolist() == [1.0, 0.0, 0.0] and b.col("color")[0] == 0.0
    assert b.col("density").tolist() == [0.0, 0.0, 0.0] and (b.col("hotspot") == 0).all()
    assert np.isnan(b.col("pre_presence")).all() and np.isnan(b.col("ctx_change")).all()   # no earlier frames
    assert b.col("bg_grad")[0] > 0 and b.col("codec")[0] == 0.0 and b.col("large_near")[0] == 0.0
    for i in range(2):
        tgt = b.patches[i, 0].astype(np.float32)
        assert np.unravel_index(np.argmax(tgt), tgt.shape) == (8, 8)          # centred on the detection
        ctx = b.patches[i, 1].astype(np.float32)
        assert np.unravel_index(np.argmax(ctx), ctx.shape) == (8, 8)
    edge = b.patches[2, 0].astype(np.float32)                                  # outside the picture: 0
    assert (edge[:5, :5] == 0).all() and np.unravel_index(np.argmax(edge), edge.shape) == (8, 8)


def test_hit_features_batched_equal_one_at_a_time_and_respect_the_budget():
    pts = [(20.0 + 9 * k, 30.0 + 5 * (k % 4)) for k in range(12)]
    det, st = _scene(pts, seed=1)
    _, prev = _scene(pts, seed=2)
    ring = FrameRing(4)
    for i in range(3):
        ring.push(RingFrame(i, i * 0.1, prev.luma, prev.background, prev.sigma))
    hot = HotspotMap(VCFG.hotspot)
    hot.ensure(st.luma.shape)
    hot.add([20.0, 21.0], [30.0, 31.0], 0.2)
    kw = dict(patch_cfg=VCFG.patch, t=0.3, frame=3)
    full = hit_features(det, st, ring, hot, None, None, **kw)
    assert np.isfinite(full.values).all()
    for i in range(len(pts)):
        prio = np.ones(len(pts), np.int64)
        prio[i] = 0
        one = hit_features(det, st, ring, hot, None, None, priority=prio, cap=1, **kw)
        assert one.over_budget.sum() == len(pts) - 1 and not one.over_budget[i]
        assert np.array_equal(one.values[i], full.values[i])
        assert np.array_equal(one.patches[i], full.patches[i])
        assert np.isnan(one.values[np.arange(len(pts)) != i]).all()
    prio = np.array([2] * 6 + [0] * 3 + [1] * 3)
    capped = hit_features(det, st, ring, hot, None, None, priority=prio, cap=5, **kw)
    assert np.flatnonzero(~capped.over_budget).tolist() == [6, 7, 8, 9, 10]   # confirmed, then tentative


def test_hit_features_measure_snr_codec_and_large_regions_on_the_detecting_level():
    det, st = _scene([(41.0, 51.0), (100.0, 30.0)])
    det.scale = np.array([2.0, 1.0])
    lv_sigma = np.full((60, 80), 2.0, np.float32)
    lv_sigma[25, 20] = 5.0                     # (41, 51) at factor 2 is level pixel (20.25, 25.25)
    seed = np.zeros((60 // 4, 80 // 4), np.uint8)
    seed[25 // 4, 20 // 4] = 30                # the mirror test's seed level of that block (block 4 level px)
    large = np.zeros((60, 80), np.uint8)
    large[0:60, 0:10] = 1                      # 10 of the 51 level columns around x = 20 (from -5 to 45)
    lv = DetectorState(sigma=lv_sigma, mirror_seed=seed, large_mask=large)
    b = hit_features(det, st, FrameRing(4), None, None, {2: lv}, patch_cfg=VCFG.patch, t=0.0, frame=0, mirror_block=4)
    assert b.col("snr").tolist() == [100.0 / 5.0, 100.0 / 2.0]
    assert b.col("codec")[0] == pytest.approx(30 / 100.0) and b.col("codec")[1] == 0.0
    assert b.col("large_near")[0] == pytest.approx(10 * 51 / (46 * 51)) and b.col("large_near")[1] == 0.0
    assert b.col("scale").tolist() == [2.0, 1.0]
    # Native-level features and patches of a coarse detection come from the native maps.
    assert b.col("bg_luma")[0] == st.background[51, 41]
    tgt = b.patches[0, 0].astype(np.float32)
    assert np.unravel_index(np.argmax(tgt), tgt.shape) == (8, 8)


def _hits(n, vx=150.0, vy=0.0, dt=1 / 30, length=6.0, theta=0.0, values=True):
    out = []
    for k in range(n):
        v = np.zeros(len(FEATURE_NAMES), np.float32)
        v[FI["snr"]] = 10 + k
        v[FI["hotspot"]] = k
        v[FI["pre_presence"]] = np.nan
        out.append(HitRecord(k, k * dt, 10 + vx * k * dt, 20 + vy * k * dt, length, theta, 50.0 + k,
                             v if values else None, None))
    return out


def test_window_features_of_a_straight_track():
    w = window_features(_hits(6), Kin(t_first=-0.1, elapsed=6))
    assert w.shape == (len(WINDOW_NAMES),)
    assert w[WI["n_hits"]] == 6 and w[WI["hit_ratio"]] == 1.0 and math.isclose(w[WI["age_s"]], 5 / 30 + 0.1)
    assert math.isclose(w[WI["speed_med"]], 150.0, rel_tol=1e-9) and w[WI["speed_cv"]] < 1e-9
    assert math.isclose(w[WI["net_disp"]], 25.0) and math.isclose(w[WI["straightness"]], 1.0)
    assert w[WI["accel_rms"]] < 1e-6 and w[WI["turn_med_deg"]] < 1e-6
    assert w[WI["n_streak"]] == 6 and w[WI["align_frac"]] == 1.0
    assert w[WI["snr_med"]] == 12.5 and w[WI["snr_min"]] == 10 and w[WI["hotspot_max"]] == 5
    assert np.isnan(w[WI["pre_presence_med"]])
    cross = window_features(_hits(6, theta=math.pi / 2), Kin(0.0, 9))
    assert cross[WI["align_frac"]] == 0.0 and math.isclose(cross[WI["hit_ratio"]], 6 / 9)
    bare = window_features(_hits(3, values=False), Kin(0.0, 3))
    assert np.isnan(bare[WI["snr_med"]]) and bare[WI["n_hits"]] == 3


# Models ----------------------------------------------------------------------------------------

def _data(n=400, d=5, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(0, 1, (n, d))
    y = (X[:, 0] + 0.5 * X[:, 1] + 0.3 * rng.normal(0, 1, n) > 0).astype(float)
    X[rng.random((n, d)) < 0.02] = np.nan
    return X, y


def test_logreg_and_mlp_are_deterministic_and_learn():
    X, y = _data()
    a, b = LogReg(l2=1.0).fit(X, y), LogReg(l2=1.0).fit(X, y)
    assert np.array_equal(a.w, b.w) and np.mean((a.decision_function(X) > 0) == (y > 0.5)) > 0.85
    m1 = MLP(hidden=8, epochs=15, batch_size=64, lr=1e-2, seed=3).fit(X, y)
    m2 = MLP(hidden=8, epochs=15, batch_size=64, lr=1e-2, seed=3).fit(X, y)
    assert np.array_equal(m1.W1, m2.W1) and np.mean((m1.decision_function(X) > 0) == (y > 0.5)) > 0.85
    m3 = MLP(hidden=8, epochs=15, batch_size=64, lr=1e-2, seed=4).fit(X, y)
    assert not np.array_equal(m1.W1, m3.W1)
    hn = MLP(hidden=8, epochs=15, batch_size=64, lr=1e-2, seed=3, hard_neg_frac=0.3, hard_neg_epoch=5).fit(X, y)
    assert not np.array_equal(m1.W1, hn.W1) and np.isfinite(hn.decision_function(X)).all()
    p = PCA().fit(np.nan_to_num(X), 2)
    assert p.components.shape == (2, 5) and np.allclose(p.components @ p.components.T, np.eye(2), atol=1e-9)


def test_models_save_and_load_with_a_pinned_sha_and_sidecar(tmp_path):
    from wfglink.provenance import sha256_file

    X, y = _data()
    est = MLP(hidden=6, epochs=5, batch_size=64, seed=1).fit(X, y)
    names = ("snr_med", "speed_med", "net_disp", "straightness", "hotspot_max")
    model = Model("temporal", est, names, envelope=make_envelope(names, X), meta={"profile": "file_native"})
    path = tmp_path / "m" / "temporal.npz"
    side = save(path, model, {"training_data_sha256": {"windows": "ab" * 32}, "command_line": "test"})
    sha = sha256_file(path)
    assert side["npz_sha256"] == sha and side["profile"] == "file_native" and side["seed"] == 1 and side["epochs"] == 5
    assert set(side) >= {"feature_names", "standardization", "pca", "envelope", "training_data_sha256", "command_line"}
    back = load(path, sha)
    assert back.feature_names == names and np.allclose(back.logits(X), model.logits(X))
    save(tmp_path / "again.npz", model, {"training_data_sha256": {"windows": "ab" * 32}, "command_line": "test"})
    assert sha256_file(tmp_path / "again.npz") == sha                 # same model, same bytes
    for pin, reason in ((None, "sha_unpinned"), ("00" * 32, "sha_mismatch")):
        with pytest.raises(ModelUnavailable) as e:
            load(path, pin)
        assert e.value.reason == reason
    with pytest.raises(ModelUnavailable) as e:
        load(tmp_path / "missing.npz", sha)
    assert e.value.reason == "missing_file"
    path.with_suffix(".json").unlink()
    with pytest.raises(ModelUnavailable) as e:
        load(path, sha)
    assert e.value.reason == "missing_sidecar"
    pca = PCA().fit(np.nan_to_num(X), 3)
    pm = Model("patch", LogReg().fit(pca.transform(np.nan_to_num(X)), y), (), pca=pca, meta={"profile": "file_native"})
    save(tmp_path / "p.npz", pm)
    assert np.allclose(load(tmp_path / "p.npz", sha256_file(tmp_path / "p.npz")).logits(np.nan_to_num(X)),
                       pm.logits(np.nan_to_num(X)))


def test_a_pinned_model_refuses_an_edited_sidecar_a_bad_archive_and_wrong_sizes(tmp_path):
    import json

    from wfglink.provenance import sha256_file
    from wfglink.verify.models import validate

    X, y = _data()
    names = ("snr_med", "speed_med", "net_disp", "straightness", "hotspot_max")
    model = Model("temporal", MLP(hidden=4, epochs=2, seed=1).fit(X, y), names, envelope=make_envelope(names, X),
                  meta={"profile": "file_native"})
    path = tmp_path / "t.npz"
    save(path, model)
    sha, side = sha256_file(path), json.loads(path.with_suffix(".json").read_text())
    assert load(path, sha).meta["profile"] == "file_native"
    edits = {"profile": "live_downscaled", "feature_names": list(reversed(names)), "envelope": None, "kind": "patch",
             "hyper": {**side["hyper"], "hidden": 5}}
    for key, value in edits.items():               # the pinned SHA-256 covers every run-time field
        path.with_suffix(".json").write_text(json.dumps({**side, key: value}))
        with pytest.raises(ModelUnavailable) as e:
            load(path, sha)
        assert e.value.reason == "sidecar_mismatch", key
    path.with_suffix(".json").write_text(json.dumps({**side, "command_line": "edited"}))   # not a run-time field
    assert load(path, sha).feature_names == names
    junk = tmp_path / "junk.npz"
    junk.write_bytes(b"not a zip archive")
    junk.with_suffix(".json").write_text(json.dumps({**side, "npz_sha256": sha256_file(junk)}))
    with pytest.raises(ModelUnavailable) as e:
        load(junk, sha256_file(junk))
    assert e.value.reason == "bad_format"
    validate(load(path, sha), 17)
    with pytest.raises(ModelUnavailable):
        validate(Model("temporal", model.estimator, names[:4]), 17)          # 4 names for 5 inputs
    pca = PCA().fit(np.random.default_rng(0).normal(0, 1, (50, 2 * 9 * 9)), 3)
    pm = Model("patch", LogReg().fit(pca.transform(np.random.default_rng(1).normal(0, 1, (50, 162))), y[:50]), (),
               pca=pca)
    validate(pm, 9)
    with pytest.raises(ModelUnavailable) as e:
        validate(pm, 17)                                                       # patches of another size
    assert e.value.reason == "bad_format"


# Scorers ---------------------------------------------------------------------------------------

RULES = {"lower": {"snr_med": 5.0, "speed_med": 20.0}, "upper": {"hotspot_max": 3.0},
         "iqr": {"snr_med": 2.0, "speed_med": 10.0, "hotspot_max": 1.0}}


def test_rule_scorer_margins_fixed_rules_and_missing_features():
    r = RuleScorer(RULES, min_hits=4)
    w = window_features(_hits(6), Kin(0.0, 6))
    s, ok, _ = r.score(w, None)
    # margins: n_hits 2, align 0.5, snr (12.5 - 5) / 2, speed (150 - 20) / 10, hotspot (3 - 5) / 1
    assert ok and math.isclose(s, -2.0)
    w2 = w.copy()
    w2[WI["hotspot_max"]] = 1.0
    assert math.isclose(r.score(w2, None)[0], 0.5)                  # the streak alignment rule binds
    w2[WI["align_frac"]] = 0.2
    assert r.score(w2, None)[0] < 0
    w2[WI["n_streak"]] = 1
    assert r.score(w2, None)[0] >= 0                                # fewer than two streaks: no alignment rule
    w2[WI["snr_med"]] = np.nan
    assert r.score(w2, None)[1:] == (False, "missing_feature:snr_med")
    with pytest.raises(ValueError):
        RuleScorer({"lower": {"area": 1.0}, "iqr": {"area": 1.0}}, 4)
    with pytest.raises(ValueError):
        RuleScorer({"lower": {"snr_med": 1.0}}, 4)


def test_build_scorer_reasons_and_ood():
    import dataclasses

    assert isinstance(build_scorer(VerifyConfig.from_cfg(hp_config("accept_all")), "unprofiled"), AcceptAll)
    u = build_scorer(VCFG, "file_native")
    assert isinstance(u, Unavailable) and u.reason == "method_unavailable:no_thresholds"
    v = dataclasses.replace(VCFG, rules_thresholds={"file_native": RULES})
    assert isinstance(build_scorer(v, "file_native"), RuleScorer)
    assert build_scorer(v, "live_downscaled").reason == "method_unavailable:profile_mismatch"
    assert build_scorer(dataclasses.replace(VCFG, rules_thresholds={"file_native": {"lower": {"x": 1}}}),
                        "file_native").reason == "method_unavailable:bad_thresholds"
    assert build_scorer(dataclasses.replace(VCFG, rules_thresholds={"file_native": {}}),
                        "file_native").reason == "method_unavailable:no_thresholds"
    assert build_scorer(dataclasses.replace(VCFG, rules_thresholds={"file_native": {}, "live_downscaled": RULES}),
                        "file_native").reason == "method_unavailable:no_thresholds"
    p = VerifyConfig.from_cfg(hp_config("patch"))
    assert build_scorer(p, "file_native").reason == "method_unavailable:no_threshold"
    assert build_scorer(p, "live_downscaled").reason == "method_unavailable:profile_mismatch"
    env = {"names": ["snr_med", "speed_med", "net_disp"], "median": [10.0, 100.0, 20.0], "mad": [1.0, 10.0, 2.0]}
    w = np.full(len(WINDOW_NAMES), np.nan)
    w[[WI["snr_med"], WI["speed_med"], WI["net_disp"]]] = [11.0, 110.0, 21.0]
    assert not ood(w, env, 6.0, 2)
    w[WI["snr_med"]] = 100.0
    assert not ood(w, env, 6.0, 2)
    w[WI["speed_med"]] = 1000.0
    assert ood(w, env, 6.0, 2)


def test_a_model_trained_for_another_profile_or_size_is_unavailable(tmp_path):
    from wfglink.provenance import sha256_file
    from wfglink.verify.scorers import PatchScorer

    rng = np.random.default_rng(0)

    def patch_model(path, profile, px):
        X = rng.normal(0, 1, (120, 2 * px * px))
        pca = PCA().fit(X, 3)
        save(path, Model("patch", LogReg().fit(pca.transform(X), (X[:, 0] > 0).astype(float)), (), pca=pca),
             {"profile": profile})
        return {"path": str(path), "sha256": sha256_file(path), "threshold": 0.5}

    def scorer(spec):
        return build_scorer(VerifyConfig.from_cfg(hp_config("patch", overrides={"verify": {"models": {"patch": {
            "file_native": spec}}}})), "file_native")

    assert isinstance(scorer(patch_model(tmp_path / "ok.npz", "file_native", 17)), PatchScorer)
    # Pinned under file_native, but trained (and stored) for the booth's profile.
    assert scorer(patch_model(tmp_path / "live.npz", "live_downscaled", 17)).reason == "method_unavailable:profile_mismatch"
    # Pinned and of the right profile, but for 9 px patches: refused before it could fail in a frame.
    assert scorer(patch_model(tmp_path / "small.npz", "file_native", 9)).reason == "method_unavailable:bad_format"


# Ledger ----------------------------------------------------------------------------------------

class _Track:
    def __init__(self, tid, t0=0.0, n=3, dt=0.1):
        self.track_id = tid
        self.t_first = t0
        self.records = [(k, t0 + k * dt, 10.0 + 5 * k, 20.0, 10.0 + 5 * k, 20.0, 50.0, 0.0, 2.0, 0.0, 100.0, 500.0,
                         1.0, 0, False, 0) for k in range(n)]


class _Fixed:
    method = "fixed"
    gated = True
    threshold = 0.5
    min_hits = 4

    def __init__(self, score, valid=True, reason=""):
        self.s, self.valid, self.reason_ = score, valid, reason

    def score(self, w, p):
        return self.s, self.valid, self.reason_


def _win(n, **kw):
    return L.Window(np.zeros(len(WINDOW_NAMES)), None, n, **kw)


def test_ledger_transitions_and_reasons():
    led = L.Ledger(VCFG)
    k = L.make_key(0, 7)
    d = led.on_confirmed(k, _Track(7))
    assert d.state == L.CANDIDATE and d.t_confirm == pytest.approx(0.2) and d.confirm_idx == 2
    assert not led.checkpoint(k, 0.2, _win(2), _Fixed(1.0), frame=2) and "too_few_hits" in d.reasons
    assert not led.checkpoint(k, 0.3, _win(4), _Fixed(1.0), {"camera_motion"}, frame=3) and d.motion_tainted
    assert led.checkpoint(k, 0.4, _win(4), _Fixed(0.9), frame=4)
    assert led.accepted(k) and d.t_decision == 0.4 and d.frame_decision == 4 and d.reason == "passed"
    assert not led.checkpoint(k, 0.5, _win(4), _Fixed(0.9), frame=5)                    # decided once
    assert led.on_static(k, 0.5, t=0.6, frame=6) and d.revoked and d.state == L.REJECTED and not led.accepted(k)
    assert (d.t_accept, d.frame_accept, d.t_decision, d.frame_decision) == (0.4, 4, 0.6, 6) and led.ever_accepted(k)

    k2 = L.make_key(0, 8)
    led.on_confirmed(k2, _Track(8))
    led.checkpoint(k2, 0.3, _win(4), _Fixed(0.1), frame=3)
    assert led.deadline(0.3 + VCFG.deadline_s - 0.15, 9) == []
    assert led.deadline(0.2 + VCFG.deadline_s, 10) == [k2]
    assert led.get(k2).state == L.REJECTED and led.get(k2).reason == "score_below_threshold"

    k3 = L.make_key(0, 9)
    led.on_confirmed(k3, _Track(9))
    led.checkpoint(k3, 0.3, _win(4, over_budget=True), _Fixed(1.0, False, "out_of_distribution"), frame=3)
    led.checkpoint(k3, 0.4, _win(1, over_budget=True), _Fixed(1.0), frame=4)
    led.checkpoint(k3, 0.5, _win(4), Unavailable("no_model"), frame=5)
    led.deadline(5.0, 50)
    d3 = led.get(k3)
    assert d3.state == L.INSUFFICIENT and d3.reason == "method_unavailable:no_model" and d3.ood and d3.over_budget

    k4 = L.make_key(0, 10)
    led.on_confirmed(k4, _Track(10))
    led.checkpoint(k4, 0.3, _win(4, motion_tainted=True), _Fixed(1.0), frame=3)
    led.deadline(5.0, 50)
    assert led.get(k4).reason == "camera_motion"
    # The control is never gated and needs no hits.
    k5 = L.make_key(0, 11)
    led.on_confirmed(k5, _Track(11))
    assert led.checkpoint(k5, 0.2, _win(0, motion_tainted=True), AcceptAll(), {"camera_motion"}, frame=2)
    # ... but a timebase that is not real time stops every scorer.
    k6 = L.make_key(0, 12)
    led.on_confirmed(k6, _Track(12))
    assert not led.checkpoint(k6, 0.2, _win(0), AcceptAll(), {"timebase_not_real_time"}, frame=2)
    led.deadline(5.0, 50)
    assert led.get(k6).reason == "timebase_not_real_time"


def test_ledger_finish_is_retro_and_the_archive_is_bounded():
    led = L.Ledger(VCFG, keep_all=False, archive_cap=5)
    for tid in range(1, 21):
        k = L.make_key(0, tid)
        led.on_confirmed(k, _Track(tid, t0=tid))
        acc = led.on_finished(k, tid + 0.4, _win(4), _Fixed(0.9 if tid % 2 else 0.1), t=tid + 0.5, frame=tid)
        d = led.get(k)
        assert d.retro and acc == bool(tid % 2)
        assert d.state == (L.ACCEPTED if tid % 2 else L.REJECTED)
    assert len(led.archive) == 5 and led.dropped == 15 and not led.active
    assert led.accepted(L.make_key(0, 19)) and not led.accepted(L.make_key(0, 1))
    full = L.Ledger(VCFG)
    for tid in range(1, 30):
        full.on_confirmed(L.make_key(0, tid), _Track(tid))
        full.on_finished(L.make_key(0, tid), 1.0, None, _Fixed(1.0))
    assert len(full.archive) == 29 and {d.reason for d in full.decisions()} == {"too_few_hits"}


def test_keys_of_epochs_never_collide_and_fragments_are_flagged():
    assert L.make_key(0, 5) == 5 and L.make_key(1, 5) != L.make_key(0, 5) and L.split_key(L.make_key(3, 42)) == (3, 42)
    led = L.Ledger(VCFG)
    a = _Track(1, t0=0.0, n=5)                       # ends at t = 0.4, x = 30, moving +x at 50 px/s
    led.on_confirmed(1, a)
    led.checkpoint(1, 0.3, _win(4), _Fixed(1.0), frame=3)
    r = a.records[-1]
    led.on_finished(1, r[1], None, _Fixed(1.0), t=0.45, frame=5, end=(r[1], r[2], r[3], 50.0, 0.0))
    b = _Track(2, t0=0.6, n=3)
    b.records = [rr[:2] + (40.0 + 5 * i, 20.0) + rr[4:] for i, rr in enumerate(b.records)]
    assert led.on_confirmed(2, b).probable_fragment_of == 1
    c = _Track(3, t0=0.6, n=3)
    c.records = [rr[:2] + (40.0, 20.0 + 5 * i) + rr[4:] for i, rr in enumerate(c.records)]   # moving across
    assert led.on_confirmed(3, c).probable_fragment_of == -1
    # A new shot (epoch) has other coordinates: no fragment across a cut, by key or after new_epoch.
    assert led.on_confirmed(L.make_key(1, 2), b).probable_fragment_of == -1
    led.new_epoch()
    assert not led._ends
