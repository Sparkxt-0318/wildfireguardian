"""Synthetic generator: truth against the rendered frames, simulated time span, suite
expansion and early config validation."""
import math

import numpy as np
import pandas as pd
import pytest
import yaml

from wfglink import PROJECT_ROOT
from wfglink.synth import degrade as D
from wfglink.synth.degrade import LUMA_BGR, make_timing
from wfglink.synth.generate import generate_clip, load_synth_config, prepare_clip, resolve_gates, suite_cases
from wfglink.synth.render import render_exposure


def test_frames_match_truth_flux_and_position(tmp_path, monkeypatch):
    """Each isolated ember's light in the scene of frame i has the truth flux of frame i
    (after haze, exposure step, gain and global flicker) and its centroid at x_mid, y_mid."""
    scenes = {}
    orig = D.Camera.process

    def capture(self, scene, timing, i):
        scenes[i] = (scene.copy(), self.scale(timing, i))
        return orig(self, scene, timing, i)

    monkeypatch.setattr(D.Camera, "process", capture)
    cfg = load_synth_config([], {
        "frame_size": [320, 240], "duration_s": 1.0,
        "embers": {"density": {"on_screen": 12, "pilot_particles": 300}, "flicker": {"amp": 0.0},
                   "fade_in_s": 0.0, "fade_out_s": 0.0},
        "camera": {"gain": 1.5, "flicker": {"amp": 0.2, "freq_hz": 3.0}},
        "haze": {"beta_per_m": 0.01, "depth": {"mode": "constant", "depth_m": 60.0}, "particle_depth_m": 30.0},
        "timing": {"exposure_step": {"t_s": 0.5, "factor": 0.5}},
        "mismatch": {"rolling_shutter_s": 0.02},
        "compression": {"preset": "ultrafast"}})
    out = generate_clip(cfg, tmp_path / "c", seed=2)
    setup = prepare_clip(cfg, 2)
    tp = pd.read_parquet(out / "truth_particles.parquet")
    assert sorted(scenes) == list(range(setup.timing.n))
    assert len({round(s, 9) for _, s in scenes.values()}) > 2          # gain, flicker and the step vary
    checked = 0
    for i, (scene, scale) in scenes.items():
        res = ((scene - setup.background) @ LUMA_BGR) * scale
        rows = tp[tp["frame"] == i]
        for r in rows[rows["visible"] & (rows["kind"] == "ember")].itertuples():
            others = rows[rows["particle_id"] != r.particle_id]
            if (np.hypot(others["x_mid"] - r.x_mid, others["y_mid"] - r.y_mid) < 30).any():
                continue
            if not (15 < r.x_mid < 304 and 15 < r.y_mid < 224):
                continue
            # Embers born or dying during the exposure light up only part of it, so their
            # centroid is not at the exposure midpoint; they are checked in test_synth_render.
            j = int(r.particle_id)          # ember ids are indices into the system
            t0, t1 = setup.timing.t_start[i], setup.timing.t_end[i] + setup.readout_s
            if not (setup.system.t_birth[j] < t0 and setup.system.t_death[j] > t1):
                continue
            x0, y0 = int(round(r.x_mid)), int(round(r.y_mid))
            win = res[y0 - 15:y0 + 16, x0 - 15:x0 + 16]
            yy, xx = np.mgrid[y0 - 15:y0 + 16, x0 - 15:x0 + 16]
            f = win.sum()
            assert f == pytest.approx(r.flux, rel=2e-3)
            assert (win * xx).sum() / f == pytest.approx(r.x_mid, abs=0.05)
            assert (win * yy).sum() / f == pytest.approx(r.y_mid, abs=0.05)
            checked += 1
    assert checked > 50


def _jittered_seed(duration, fps, jitter):
    """First seed whose last exposure ends more than one frame interval after duration_s."""
    for seed in range(1000):
        tm = make_timing({"fps": fps, "duration_s": duration, "duty": 0.5, "timing": {"jitter_frac": jitter}}, seed)
        if tm.t_end[-1] > duration + float(np.max(np.diff(tm.t_start))) + 0.01:
            return seed
    raise AssertionError("no such seed")


def test_jittered_frames_stay_inside_the_simulated_span():
    seed = _jittered_seed(1.0, 30.0, 0.5)
    cfg = load_synth_config([], {
        "frame_size": [160, 120], "duration_s": 1.0, "timing": {"jitter_frac": 0.5},
        "embers": {"density": {"on_screen": 20, "pilot_particles": 200}, "gust": {"strength": 0.0}},
        "scene": {"lights": {"count": 2}}, "particles": {"warmup_max_s": 2.0},
        "mismatch": {"rolling_shutter_s": 0.01}})
    s = prepare_clip(cfg, seed)
    t_last = float(s.timing.t_end[-1]) + s.readout_s
    assert t_last > 1.0 + float(np.max(np.diff(s.timing.t_start)))
    # Particles are simulated (and lights live) past the end of the last exposure.
    assert np.max(s.system.t_death) >= t_last
    assert np.all(s.scene.lights.t_death >= t_last)
    counts = []
    for i in range(s.timing.n):
        _, tr, _ = render_exposure(s.sources, float(s.timing.t_start[i]), float(s.timing.exposure_s[i]),
                                   s.frame_size, s.settings, readout_s=s.readout_s)
        inside = (tr["kind"] == "ember") & (tr["x_mid"] >= 0) & (tr["x_mid"] <= 159) & (tr["y_mid"] >= 0) \
            & (tr["y_mid"] <= 119)
        counts.append(int(inside.sum()))
        if i == s.timing.n - 1:
            assert np.sum(tr["kind"] == "light") == 2
            assert np.all(tr["alive_frac"][tr["kind"] == "light"] == 1.0)
    assert counts[-1] > 0.4 * np.mean(counts) > 0


def test_unjittered_span_is_unchanged():
    # Without jitter the last exposure ends before duration_s, so the simulated span is
    # duration_s plus one frame interval, as before (births reach the last grid steps).
    cfg = load_synth_config([], {"frame_size": [96, 64], "duration_s": 0.5,
                                 "embers": {"density": {"rate_hz": 40.0}}, "particles": {"warmup_s": 0.2}})
    s = prepare_clip(cfg, 0)
    h, t0 = s.system.h, s.system.t0
    n_steps = math.ceil((0.5 + 1 / 30 - t0) / h) + 1
    assert np.max(s.system.t_death) == pytest.approx(t0 + n_steps * h, abs=1e-9)


def test_suite_config_factor_keeps_base_case_files(tmp_path):
    base = tmp_path / "base_case.yaml"
    base.write_text(yaml.safe_dump({"duty": 0.25, "compression": {"crf": 30}}))
    suite = {"configs": [str(base)], "seeds": [0], "overrides": {"frame_size": [320, 240]},
             "factors": {"flow": {"configs": {"same": [str(base)],
                                              "shear": [str(PROJECT_ROOT / "configs" / "synth" / "shear.yaml")]}}}}
    cases, aliases = suite_cases(suite)
    by = {c["case"]: c["config"] for c in cases}
    assert aliases == {"flow-same": "base"}
    shear = by["flow-shear"]
    assert shear["flow"]["type"] == "shear"
    # Only the flow differs from the base case.
    assert shear["duty"] == 0.25 and shear["compression"]["crf"] == 30 and shear["frame_size"] == [320, 240]
    assert {k for k in shear if shear[k] != by["base"][k]} == {"flow"}


def test_core_suite_flow_variants_differ_only_in_flow():
    suite = yaml.safe_load((PROJECT_ROOT / "configs" / "suites" / "core.yaml").read_text())
    cases, _ = suite_cases(suite)
    by = {c["case"]: c["config"] for c in cases}
    for name in ("flow-shear", "flow-rankine"):
        assert {k for k in by[name] if by[name][k] != by["base"][k]} == {"flow"}
    for c in cases[1:]:
        if c["factor"] != "flow":
            diff = {k for k in c["config"] if c["config"][k] != by["base"][k]}
            assert len(diff) == 1, (c["case"], diff)


def test_invalid_frame_size_and_gates_fail_early(tmp_path):
    with pytest.raises(ValueError, match="even"):
        prepare_clip(load_synth_config([], {"frame_size": [97, 64], "duration_s": 0.2}), 0)
    with pytest.raises(ValueError, match="zero length"):
        resolve_gates({"gates": [{"name": "g", "p1": [5.0, 5.0], "p2": [5.0, 5.0]}]}, (64, 48))
    with pytest.raises(ValueError, match="unique"):
        resolve_gates({"gates": [{"name": "g", "p1": [0, 0], "p2": [1, 1]}, {"name": "g", "p1": [0, 1], "p2": [1, 0]}]},
                      (64, 48))
    cfg = load_synth_config([], {"frame_size": [96, 64], "duration_s": 0.2,
                                 "embers": {"density": {"rate_hz": 5.0}}, "particles": {"warmup_s": 0.1},
                                 "gates": [{"name": "bad", "p1_frac": [0.5, 0.5], "p2_frac": [0.5, 0.5]}]})
    with pytest.raises(ValueError, match="zero length"):
        generate_clip(cfg, tmp_path / "bad", seed=0)
    assert not (tmp_path / "bad" / "video.mp4").exists()          # nothing was rendered


def test_snr_brightness_needs_camera_noise():
    quiet = {"frame_size": [96, 64], "duration_s": 0.2, "particles": {"warmup_s": 0.1},
             "camera": {"read_noise_dn": 0.0, "electrons_per_dn": 1e15}, "embers": {"density": {"rate_hz": 5.0}}}
    with pytest.raises(ValueError, match="SNR"):
        prepare_clip(load_synth_config([], quiet), 0)
    quiet["embers"]["flux"] = {"median": 300.0, "log_sigma": 0.0}
    s = prepare_clip(load_synth_config([], quiet), 0)
    assert np.allclose(s.system.flux, 300.0)


def test_gate_truth_brackets_with_duplicates_and_rolling_shutter(tmp_path):
    cfg = load_synth_config([], {
        "frame_size": [160, 120], "duration_s": 1.5,
        "embers": {"density": {"on_screen": 25, "pilot_particles": 200}},
        "particles": {"warmup_max_s": 2.0},
        "timing": {"jitter_frac": 0.3, "duplicate_prob": 0.3},
        "mismatch": {"rolling_shutter_s": 0.02},
        "compression": {"preset": "ultrafast"}})
    out = generate_clip(cfg, tmp_path / "g", seed=6)
    tg = pd.read_parquet(out / "truth_gate.parquet")
    tf = pd.read_parquet(out / "truth_frames.parquet").set_index("frame")
    tp = pd.read_parquet(out / "truth_particles.parquet").set_index(["frame", "particle_id"])
    assert len(tg) > 10
    dup = tf["duplicate"]
    assert not dup.loc[tg["frame_before"]].any() and not dup.loc[tg["frame_after"]].any()
    # Consecutive real frames: every frame strictly between them is a duplicate.
    for a, b in zip(tg["frame_before"], tg["frame_after"]):
        assert b > a and dup.loc[a + 1:b - 1].all()
    assert (tg["frame_after"] - tg["frame_before"] > 1).any()
    # The crossing time lies between the particle's own (row-delayed) midpoint times, and
    # the positions there are on opposite sides of the gate in the recorded direction.
    gates = {g["name"]: g for g in resolve_gates(cfg, (160, 120))}
    for g in tg.itertuples():
        r0 = tp.loc[(g.frame_before, g.particle_id)]
        r1 = tp.loc[(g.frame_after, g.particle_id)]
        assert r0.t_mid <= g.t <= r1.t_mid
        p1, p2 = np.array(gates[g.gate]["p1"]), np.array(gates[g.gate]["p2"])
        d = p2 - p1
        n = np.array([-d[1], d[0]]) / np.hypot(*d)
        s0 = n @ (np.array([r0.x_mid, r0.y_mid]) - p1)
        s1 = n @ (np.array([r1.x_mid, r1.y_mid]) - p1)
        assert (s0 <= 0 < s1) if g.direction == 1 else (s1 <= 0 < s0)
        assert g.visible_both == (r0.visible and r1.visible)



def test_failed_rerun_is_not_left_marked_finished(tmp_path, monkeypatch):
    from wfglink.synth.generate import _is_done

    cfg = load_synth_config([], {"frame_size": [64, 48], "duration_s": 0.3, "embers": {"density": {"rate_hz": 5.0}},
                                 "particles": {"warmup_s": 0.1}, "compression": {"preset": "ultrafast"}})
    out = generate_clip(cfg, tmp_path / "clip", seed=1)
    assert _is_done(out, cfg, 1)
    orig = D.Camera.process

    def fail_late(self, scene, timing, i):
        if i == 3:
            raise RuntimeError("simulated crash")
        return orig(self, scene, timing, i)

    monkeypatch.setattr(D.Camera, "process", fail_late)
    with pytest.raises(RuntimeError, match="simulated crash"):
        generate_clip(cfg, out, seed=1)
    # The video was partly rewritten, so the folder must not pass as a finished clip.
    assert not (out / "meta.json").exists() and not _is_done(out, cfg, 1)


def test_gate_truth_matches_dense_trajectory_crossings_in_a_vortex(tmp_path):
    """Settling embers on curved paths: every crossing of the continuous trajectory that
    two frame midpoints bracket (particle alive at both) is in truth_gate, with the right
    direction and time, for a horizontal and a vertical gate."""
    cfg = load_synth_config([], {
        "frame_size": [320, 240], "duration_s": 2.0,
        "flow": {"type": "rankine", "center_frac": [0.5, 0.5], "core_radius": 50.0, "core_speed": 120.0,
                 "background": [80.0, 0.0]},
        "embers": {"density": {"on_screen": 40, "pilot_particles": 400}},
        "gates": [{"name": "h", "p1_frac": [0.0, 0.5], "p2_frac": [1.0, 0.5]},
                  {"name": "v", "p1_frac": [0.5, 1.0], "p2_frac": [0.5, 0.0]}],
        "compression": {"preset": "ultrafast"}})
    out = generate_clip(cfg, tmp_path / "g", seed=3)
    tg = pd.read_parquet(out / "truth_gate.parquet")
    tm = pd.read_parquet(out / "truth_frames.parquet")["t_mid"].to_numpy()
    sysm = prepare_clip(cfg, 3).system
    want = []
    for g in resolve_gates(cfg, (320, 240)):
        p1, p2 = np.array(g["p1"]), np.array(g["p2"])
        d = p2 - p1
        n = np.array([-d[1], d[0]]) / np.hypot(*d)
        for j in range(len(sysm)):
            ta, tb = max(sysm.t_birth[j], tm[0]), min(sysm.t_death[j], tm[-1])
            if tb <= ta:
                continue
            t = np.arange(ta, tb, 5e-4)
            x, y = sysm.position(np.full(t.size, j), t)
            side = n[0] * (x - p1[0]) + n[1] * (y - p1[1]) > 0
            for k in np.nonzero(side[1:] != side[:-1])[0]:
                mu = ((x[k] - p1[0]) * d[0] + (y[k] - p1[1]) * d[1]) / (d @ d)
                f = np.searchsorted(tm, t[k], side="right") - 1
                if 0 <= mu <= 1 and 0 <= f < tm.size - 1 and sysm.t_birth[j] <= tm[f] and sysm.t_death[j] >= tm[f + 1]:
                    want.append((g["name"], int(sysm.pid[j]), 1 if side[k + 1] else -1, float(t[k]), f))
    want = pd.DataFrame(want, columns=["gate", "particle_id", "direction", "t_dense", "frame"])
    assert len(want) > 40 and set(want["direction"]) == {-1, 1}
    m = tg.merge(want, on=["gate", "particle_id", "direction"], how="outer", indicator=True)
    assert (m["_merge"] == "both").all() and len(m) == len(tg) == len(want)
    assert np.abs(m["t"] - m["t_dense"]).max() < 2e-3
    assert np.array_equal(m["frame_before"], m["frame"])


def test_matched_filter_area_of_points_and_streaks():
    from wfglink.synth.particles import LinearSources, glow_color
    from wfglink.synth.truth import matched_filter_area

    s = np.array([0.6, 1.0, 2.0])
    assert np.allclose(matched_filter_area(s, 0.0), 4 * math.pi * s ** 2)
    assert np.allclose(matched_filter_area(s, 1e-4), 4 * math.pi * s ** 2, rtol=1e-6)
    # Long streaks: A -> 2 sqrt(pi) s L (plus an end term that does not grow with L).
    a1, a2 = matched_filter_area(1.0, 400.0), matched_filter_area(1.0, 800.0)
    assert (a2 - a1) / 400.0 == pytest.approx(2 * math.sqrt(math.pi), rel=1e-3)
    assert np.all(np.diff(matched_filter_area(1.0, np.linspace(0, 30, 31))) > 0)
    # Against a rendered unit-flux streak: the rendered spot is the pixel-integrated
    # Gaussian, of variance s^2 + 1/12, so compare with that sigma.
    exp = 1 / 60
    for sig, length, ang in ((0.6, 0.0, 0.0), (1.0, 6.0, 30.0), (1.3, 15.0, 100.0), (2.0, 30.0, 0.0)):
        a = math.radians(ang)
        src = LinearSources(pid=[0], kind=["ember"], t_birth=[-1.0], t_death=[1.0], flux=[1.0], sigma=[sig],
                            color=glow_color(1100.0), x0=[110.3 - 0.5 * length * math.cos(a)],
                            y0=[80.6 - 0.5 * length * math.sin(a)],
                            vx=[length / exp * math.cos(a)], vy=[length / exp * math.sin(a)])
        img, _, _ = render_exposure([src], 0.0, exp, (220, 160), n_sub=1024)
        p = img.astype(np.float64) @ LUMA_BGR
        want = matched_filter_area(math.sqrt(sig ** 2 + 1 / 12), length)
        assert 1.0 / np.sum(p ** 2) == pytest.approx(float(want), rel=0.05)   # pixel shape is not Gaussian


def test_fast_faint_streaks_are_not_visible(tmp_path):
    """Equal point-source SNR 5: static embers pass the SNR 3 floor, 20 px streaks
    (matched-filter SNR about 2) do not."""
    base = {"frame_size": [320, 240], "duration_s": 0.5, "duty": 1.0,
            "scene": {"background": {"kind": "flat"}},
            "embers": {"vt_m_s": None, "density": {"rate_hz": 150.0}, "gust": {"strength": 0.0},
                       "snr": {"median": 5.0, "log_sigma": 0.0}, "sigma_px": 1.0, "flicker": {"amp": 0.0},
                       "fade_in_s": 0.0, "fade_out_s": 0.0, "spawn": {"mode": "frame"}, "lifetime_s": 100.0},
            "particles": {"warmup_s": 0.2}, "compression": {"preset": "ultrafast"}}
    vis = {}
    for name, u in (("slow", 3.0), ("fast", 600.0)):
        cfg = load_synth_config([], {**base, "flow": {"type": "uniform", "u": u, "v": 0.0}})
        tp = pd.read_parquet(generate_clip(cfg, tmp_path / name, seed=1) / "truth_particles.parquet")
        later = tp["particle_id"].duplicated()                      # not the frame of birth
        inner = tp[(tp["kind"] == "ember") & tp["x_mid"].between(30, 290) & tp["y_mid"].between(30, 210) & later]
        if name == "fast":
            inner = inner[inner["streak_length_px"] > 19.99]       # alive for the whole exposure
            assert np.allclose(inner["streak_length_px"], 20.0)
        assert len(inner) > 50
        vis[name] = inner["visible"].mean()
    assert vis["slow"] == 1.0 and vis["fast"] == 0.0
