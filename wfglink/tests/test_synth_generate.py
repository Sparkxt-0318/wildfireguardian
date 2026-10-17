"""Synthetic clip generation: files, schemas, video timestamps, determinism, gate and field truth."""
import json
import math
import os
import time

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import yaml

from wfglink import PROJECT_ROOT
from wfglink.synth import truth as T
from wfglink.synth.degrade import read_video
from wfglink.synth.generate import (generate_clip, load_synth_config, merge_synth, prepare_clip, run, run_suite,
                                    suite_cases)

SMALL = {
    "frame_size": [320, 240], "duration_s": 2.0, "fps": 30.0,
    "embers": {"density": {"on_screen": 25, "pilot_particles": 300}, "snr": {"median": 20.0}},
    "sparks": {"enabled": True, "density": {"rate_hz": 3.0}},
    "scene": {"lights": {"count": 3},
              "flame": {"enabled": True, "center_frac": [0.7, 0.75], "size_frac": [0.2, 0.2]}},
    "particles": {"warmup_max_s": 3.0},
    "compression": {"preset": "veryfast"},
}
FILES = ("video.mp4", "truth_particles.parquet", "truth_frames.parquet", "truth_gate.parquet",
         "truth_field.parquet", "meta.json")


@pytest.fixture(scope="module")
def clips(tmp_path_factory):
    root = tmp_path_factory.mktemp("synth")
    cfg = load_synth_config([], SMALL)
    a = generate_clip(cfg, root / "a", seed=5)
    b = generate_clip(cfg, root / "b", seed=5)
    return a, b


def test_files_exist(clips):
    a, _ = clips
    for name in FILES:
        assert (a / name).is_file() and (a / name).stat().st_size > 0


def test_parquet_columns_match_schema_exactly(clips):
    a, _ = clips
    for stem, schema in T.SCHEMAS.items():
        got = pq.read_schema(a / f"{stem}.parquet")
        assert got.names == schema.names, stem
        assert [f.type for f in got] == [f.type for f in schema], stem
    # The shared schema names, in order.
    assert T.PARTICLES_SCHEMA.names == [
        "frame", "t_mid", "particle_id", "kind", "x_mid", "y_mid", "x_start", "y_start", "x_end", "y_end",
        "u", "v", "ua", "va", "flux", "sigma_px", "visible", "in_large_region", "streak_length_px"]
    assert T.FRAMES_SCHEMA.names == ["frame", "t_start", "t_mid", "t_end", "exposure_s", "duplicate",
                                     "n_visible_embers"]
    assert T.GATE_SCHEMA.names == ["gate", "particle_id", "t", "frame_before", "frame_after", "direction",
                                   "visible_both"]


def test_video_frames_and_pts(clips):
    a, _ = clips
    frames, pts = read_video(a / "video.mp4")
    tf = pd.read_parquet(a / "truth_frames.parquet")
    assert len(frames) == len(tf) == 60
    assert frames[0].shape == (240, 320, 3)
    assert np.max(np.abs(pts - tf["t_start"].to_numpy())) < 1e-3
    assert np.allclose(tf["t_end"] - tf["t_start"], tf["exposure_s"])
    assert np.allclose(tf["t_mid"], tf["t_start"] + 0.5 * tf["exposure_s"])


def test_same_seed_gives_identical_truth(clips):
    a, b = clips
    for stem in T.SCHEMAS:
        ta = pd.read_parquet(a / f"{stem}.parquet")
        tb = pd.read_parquet(b / f"{stem}.parquet")
        pd.testing.assert_frame_equal(ta, tb)
    # The rendered 8-bit frames before compression are identical.
    ma = json.loads((a / "meta.json").read_text())
    mb = json.loads((b / "meta.json").read_text())
    assert ma["frames_sha256"] == mb["frames_sha256"] and ma["config_sha256"] == mb["config_sha256"]
    # The encoded videos agree up to coding noise. The libx264 bitstream is usually bit
    # identical, but in a process that has already done other work the first encode can
    # differ slightly (observed with identical input frames, below this package), so the
    # pixel check here is a tolerance and frames_sha256 above is the exact one.
    fa, pa = read_video(a / "video.mp4")
    fb, pb = read_video(b / "video.mp4")
    assert len(fa) == len(fb) and np.array_equal(pa, pb)
    assert max(np.mean(np.abs(x.astype(int) - y)) for x, y in zip(fa, fb)) < 2.5


def test_meta_contents(clips):
    a, _ = clips
    m = json.loads((a / "meta.json").read_text())
    for key in ("config", "seed", "fps", "exposure_s", "duty", "px_per_m", "gates", "field_grid", "frame_size",
                "video", "provenance", "snr_model"):
        assert key in m
    assert m["seed"] == 5 and m["config"]["seed"] == 5
    assert m["frame_size"] == [320, 240] and m["video"] == "video.mp4"
    assert m["exposure_s"] == pytest.approx(0.5 / 30)
    assert m["field_grid"] == [16, 9]
    g = {d["name"]: d for d in m["gates"]}
    assert g["center_vertical"]["p1"] == [160.0, 240.0] and g["center_vertical"]["p2"] == [160.0, 0.0]
    assert m["provenance"]["script"] == "wfglink.synth.generate"
    sm = m["snr_model"]
    assert sm["flux_per_snr_per_sigma_px"] == pytest.approx(sm["noise_luma_dn_ref"] * 2 * math.sqrt(math.pi))


def test_truth_rows_kinds_and_flags(clips):
    a, _ = clips
    tp = pd.read_parquet(a / "truth_particles.parquet")
    tf = pd.read_parquet(a / "truth_frames.parquet")
    assert set(tp["kind"]) == {"ember", "spark", "light"}
    lights = tp[tp["kind"] == "light"]
    assert lights.groupby("frame").size().eq(3).all()
    assert np.allclose(lights[["u", "v", "streak_length_px"]].to_numpy(), 0.0)
    emb = tp[tp["kind"] == "ember"]
    assert np.allclose(emb["streak_length_px"], np.hypot(emb["x_end"] - emb["x_start"], emb["y_end"] - emb["y_start"]))
    # Air velocity of the base uniform flow.
    assert np.allclose(tp["ua"], 150.0) and np.allclose(tp["va"], 0.0)
    # Visible rows are inside the frame; n_visible_embers counts them per frame.
    vis = tp[tp["visible"]]
    assert vis["x_mid"].between(0, 319).all() and vis["y_mid"].between(0, 239).all()
    counts = tp[tp["visible"] & (tp["kind"] == "ember")].groupby("frame").size().reindex(tf["frame"], fill_value=0)
    assert np.array_equal(counts.to_numpy(), tf["n_visible_embers"].to_numpy())
    # Flame region: flagged embers lie inside its bounding box (center 224, 180; semi-axes 64, 48).
    inside = emb[emb["in_large_region"]]
    assert len(inside) > 0
    assert inside["x_mid"].between(224 - 64, 224 + 64).all() and inside["y_mid"].between(180 - 48, 180 + 48).all()
    assert not tp.duplicated(["frame", "particle_id"]).any()


def test_gate_truth_uses_embers_only(clips):
    a, _ = clips
    tg = pd.read_parquet(a / "truth_gate.parquet")
    tp = pd.read_parquet(a / "truth_particles.parquet")
    kinds = tp.drop_duplicates("particle_id").set_index("particle_id")["kind"]
    assert len(tg) > 0
    assert set(kinds.loc[tg["particle_id"]].unique()) == {"ember"}
    assert set(tg["direction"].unique()) <= {-1, 1}
    assert (tg["frame_after"] > tg["frame_before"]).all()


def test_field_truth(clips):
    a, _ = clips
    tfi = pd.read_parquet(a / "truth_field.parquet")
    assert len(tfi) == 16 * 9
    assert np.allclose(tfi["ua_center"], 150.0) and np.allclose(tfi["va_center"], 0.0)
    filled = tfi[tfi["n_particles"] > 0]
    assert len(filled) > 30
    assert (filled["n_samples"] >= filled["n_particles"]).all()
    assert np.allclose(filled["ua"], 150.0)
    assert (filled["v"] > 0).all()            # embers settle (+y) relative to the horizontal wind
    assert tfi.loc[tfi["n_particles"] == 0, "u"].isna().all()


def test_snr_maps_to_flux():
    cfg = load_synth_config([], {
        "frame_size": [320, 240], "duration_s": 1.0,
        "embers": {"density": {"rate_hz": 60.0}, "snr": {"median": 12.0, "log_sigma": 0.2},
                   "flicker": {"amp": 0.0}, "fade_in_s": 0.0, "fade_out_s": 0.0, "gust": {"strength": 0.0}},
        "particles": {"warmup_s": 2.0}})
    setup = prepare_clip(cfg, 2)
    sysm = setup.system
    snr = sysm.flux * setup.camera.gain / (setup.flux_per_snr * sysm.sigma)
    assert np.median(snr) == pytest.approx(12.0, rel=0.08)
    assert np.std(np.log(snr)) == pytest.approx(0.2, rel=0.2)


def test_gate_truth_matches_analytic_count_in_uniform_flow(tmp_path):
    u = 120.0
    cfg = load_synth_config([], {
        "frame_size": [320, 240], "duration_s": 3.0,
        "flow": {"type": "uniform", "u": u, "v": 0.0},
        "embers": {"vt_m_s": None, "density": {"rate_hz": 40.0}, "gust": {"strength": 0.0},
                   "lifetime_s": 1000.0, "spawn": {"mode": "upwind"}},
        "particles": {"warmup_s": 3.0},
        "gates": [{"name": "g", "p1": [160.0, 240.0], "p2": [160.0, 0.0]}],
        "compression": {"preset": "ultrafast"}})
    out = generate_clip(cfg, tmp_path / "gate", seed=11)
    tg = pd.read_parquet(out / "truth_gate.parquet")
    tf = pd.read_parquet(out / "truth_frames.parquet")
    sysm = prepare_clip(cfg, 11).system
    tm = tf["t_mid"].to_numpy()
    # Tracers: x(t) = x_birth + u (t - t_birth), so the crossing time of x = 160 is exact.
    xb, _ = sysm.position(np.arange(len(sysm)), sysm.t_birth)
    tc = sysm.t_birth + (160.0 - xb) / u
    k = np.searchsorted(tm, tc, side="right") - 1          # t_mid[k] <= tc < t_mid[k + 1]
    ok = (k >= 0) & (k < tm.size - 1)
    kk = np.clip(k, 0, tm.size - 2)
    ok &= (sysm.t_birth <= tm[kk]) & (sysm.t_death >= tm[kk + 1])
    expected = np.sort(sysm.pid[ok])
    assert len(tg) == expected.size > 50
    assert np.array_equal(np.sort(tg["particle_id"].to_numpy()), expected)
    want_t = dict(zip(sysm.pid[ok], tc[ok]))
    assert np.allclose(tg["t"].to_numpy(), [want_t[p] for p in tg["particle_id"]], atol=1e-9)
    assert (tg["direction"] == 1).all()
    assert np.array_equal(tg["frame_after"] - tg["frame_before"], np.ones(len(tg), np.int64))
    # Steady inflow: every tracer born upstream crosses, so the count is rate x time (Poisson).
    lam = 40.0 * (tm[-1] - tm[0])
    assert abs(len(tg) - lam) < 4 * math.sqrt(lam)


def test_segment_crossings_geometry():
    p1, p2 = [0.0, 10.0], [10.0, 10.0]                     # normal (0, 1): moving down is +1
    crossed, lam, direction = T.segment_crossings(np.array([5.0, 5.0, 15.0, 5.0]), np.array([5.0, 15.0, 5.0, 10.0]),
                                                  np.array([5.0, 5.0, 15.0, 5.0]), np.array([15.0, 5.0, 15.0, 12.0]),
                                                  p1, p2)
    assert crossed.tolist() == [True, True, False, True]
    assert direction[:2].tolist() == [1, -1]
    assert lam[0] == pytest.approx(0.5)
    # A point exactly on the line is on the negative side.
    assert lam[3] == pytest.approx(0.0) and direction[3] == 1
    assert np.allclose(T.gate_normal([640, 720], [640, 0]), [1.0, 0.0])


def test_duplicates_jitter_and_rolling_shutter(tmp_path):
    cfg = load_synth_config([], {
        "frame_size": [160, 120], "duration_s": 1.5,
        "embers": {"density": {"on_screen": 15, "pilot_particles": 200}},
        "particles": {"warmup_max_s": 2.0},
        "timing": {"jitter_frac": 0.3, "duplicate_prob": 0.25},
        "mismatch": {"rolling_shutter_s": 0.02},
        "compression": {"preset": "ultrafast"}})
    out = generate_clip(cfg, tmp_path / "dup", seed=4)
    tf = pd.read_parquet(out / "truth_frames.parquet")
    tp = pd.read_parquet(out / "truth_particles.parquet")
    frames, pts = read_video(out / "video.mp4")
    assert len(frames) == len(tf) and np.max(np.abs(pts - tf["t_start"])) < 1e-3
    assert np.std(np.diff(tf["t_start"])) > 0.002          # variable frame intervals
    dups = tf.index[tf["duplicate"]].to_numpy()
    assert dups.size > 0 and 0 not in dups
    cols = [c for c in tp.columns if c != "frame"]
    diff = [np.mean(np.abs(frames[i].astype(int) - frames[i - 1])) for i in range(1, len(frames))]
    normal = np.median([d for i, d in enumerate(diff, 1) if i not in dups])
    for i in dups:
        a = tp[tp["frame"] == i - 1][cols].reset_index(drop=True)
        b = tp[tp["frame"] == i][cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)
        # The encoded duplicate is nearly the previous image (only coding noise differs).
        assert diff[i - 1] < 0.5 * normal
    # Rolling shutter: each particle's midpoint is delayed by its row.
    real = tp[~tp["frame"].isin(dups)].merge(tf[["frame", "t_mid"]], on="frame", suffixes=("", "_frame"))
    # Visible rows are alive at their midpoint (rows of particles born or dying near the
    # midpoint have it clamped to the lifetime instead).
    alive = real[real["visible"]]
    assert len(alive) > 100
    delay = alive["t_mid"] - alive["t_mid_frame"]
    assert np.allclose(delay, alive["y_mid"] / 120 * 0.02, atol=1e-6)


def test_config_merge_replaces_flow():
    cfg = load_synth_config(["configs/synth/shear.yaml"])
    assert cfg["flow"] == {"type": "shear", "u0": 150.0, "dudy": -0.25, "y_ref_frac": 0.5, "v": 0.0}
    assert cfg["fps"] == 30.0 and cfg["compression"]["crf"] == 23
    merged = merge_synth({"a": {"b": 1, "c": 2}, "flow": {"type": "uniform", "u": 1}},
                         {"a": {"c": 3}, "flow": {"type": "shear", "u0": 2}})
    assert merged == {"a": {"b": 1, "c": 3}, "flow": {"type": "shear", "u0": 2}}
    for name in ("uniform", "shear", "rankine", "lamb_oseen", "turbulence"):
        c = load_synth_config([f"configs/synth/{name}.yaml"])
        from wfglink.synth.flows import from_config
        f = from_config(c["flow"], c["frame_size"], 0)
        u, v = f.velocity(np.array([10.0, 640.0]), np.array([10.0, 360.0]), 0.5)
        assert np.all(np.isfinite(u)) and np.all(np.isfinite(v))


def test_run_with_yaml_files(tmp_path):
    small = tmp_path / "small.yaml"
    small.write_text(yaml.safe_dump({"frame_size": [128, 96], "duration_s": 0.5,
                                     "embers": {"density": {"on_screen": 8, "pilot_particles": 100}},
                                     "particles": {"warmup_max_s": 1.0},
                                     "compression": {"preset": "ultrafast"}}))
    out = run([str(PROJECT_ROOT / "configs" / "synth" / "rankine.yaml"), str(small)], tmp_path / "clip", seed=3)
    m = json.loads((out / "meta.json").read_text())
    assert m["config"]["flow"]["type"] == "rankine" and m["frame_size"] == [128, 96] and m["n_frames"] == 15


def test_core_suite_expansion():
    suite = yaml.safe_load((PROJECT_ROOT / "configs" / "suites" / "core.yaml").read_text())
    cases, aliases = suite_cases(suite)
    names = [c["case"] for c in cases]
    assert len(cases) == 13 and len(cases) * len(suite["seeds"]) == 39
    assert set(aliases) == {"crf-23", "snr-10", "duty-0.5", "density-medium", "flow-uniform"}
    base = cases[0]["config"]
    assert base["frame_size"] == [1280, 720] and base["fps"] == 30.0 and base["duration_s"] == 5.0
    assert base["compression"]["crf"] == 23 and base["embers"]["snr"]["median"] == 10.0
    assert base["duty"] == 0.5 and base["embers"]["density"]["on_screen"] == 100
    assert base["flow"]["type"] == "uniform"
    by = {c["case"]: c["config"] for c in cases}
    assert by["crf-35"]["compression"]["crf"] == 35 and by["crf-35"]["duty"] == 0.5
    assert by["density-high"]["embers"]["density"]["on_screen"] == 300
    assert by["flow-rankine"]["flow"]["type"] == "rankine" and by["flow-rankine"]["compression"]["crf"] == 23
    assert "snr-3" in names and "duty-0.25" in names


def test_run_suite_small(tmp_path):
    base = tmp_path / "tiny.yaml"
    base.write_text(yaml.safe_dump({"frame_size": [96, 64], "duration_s": 0.4,
                                    "embers": {"density": {"on_screen": 5, "pilot_particles": 60}},
                                    "particles": {"warmup_max_s": 0.5}, "compression": {"preset": "ultrafast"}}))
    suite = tmp_path / "suite.yaml"
    suite.write_text(yaml.safe_dump({"name": "tiny", "configs": [str(base)], "seeds": [0, 1],
                                     "factors": {"crf": {"key": "compression.crf", "values": [23, 30]}}}))
    paths = run_suite(suite, tmp_path / "out", workers=1)
    assert [p.relative_to(tmp_path / "out").as_posix() for p in paths] == [
        "base/seed_0", "base/seed_1", "crf-30/seed_0", "crf-30/seed_1"]
    man = json.loads((tmp_path / "out" / "manifest.json").read_text())
    assert man["aliases"] == {"crf-23": "base"} and len(man["clips"]) == 4
    assert json.loads((paths[2] / "meta.json").read_text())["crf"] == 30
    stamp = (paths[0] / "meta.json").stat().st_mtime_ns
    time.sleep(0.01)
    run_suite(suite, tmp_path / "out", workers=1)           # finished clips are kept
    assert (paths[0] / "meta.json").stat().st_mtime_ns == stamp
    again = run_suite(suite, tmp_path / "out2", workers=2)  # process pool path
    for p, q in zip(paths, again):
        pd.testing.assert_frame_equal(pd.read_parquet(p / "truth_particles.parquet"),
                                      pd.read_parquet(q / "truth_particles.parquet"))


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("WFGLINK_SLOW"), reason="set WFGLINK_SLOW=1 to run the 720p timing check")
def test_720p_clip_generates_within_a_minute(tmp_path):
    t0 = time.perf_counter()
    out = run([], tmp_path / "hd", seed=0)
    elapsed = time.perf_counter() - t0
    m = json.loads((out / "meta.json").read_text())
    assert m["frame_size"] == [1280, 720] and m["n_frames"] == 150
    assert 60 < m["stats"]["mean_embers_in_frame"] < 160
    assert elapsed < 60.0
