"""Tests for crossing.radar_flame. Every radar frame and thermal frame here is SYNTHETIC (generated below with a
stated, illustrative physics model), not a measurement:

- static point reflectors at fixed ranges/bearings, complex amplitude A*exp(j*phi0) times the steering vector of a
  4-element lambda/2 azimuth array, +-1 bin range leakage at -10 dB, plus circular complex Gaussian noise
  (variance 1 per element and bin);
- flame effect on echoes beyond the near edge only: amplitude loss (dB) + Gaussian amplitude flicker (dB) + phase
  random walk (rad per frame), applied in frames where the flame is "on";
- smoke-only: no radar effect at all; thermal maximum below 120 C;
- water mist / hot exhaust: radar loss + flicker, but cool thermal.
"""
import math

import numpy as np
import pytest

from crossing.radar_flame import (DEFAULT_ARRAY, RadarBaseline, RadarFlameConfig, RadarFlameDetector, RadarFrame,
                                  beam, first_solid_echo, fuse_flame)
from crossing.thermal import C_TO_K, CameraModel, flame_at_bearing, flame_mask

N_BINS = 100
RES = 0.25          # m per bin
FS = 10.0           # frames per second
NEAR_EDGE = 8.0     # m
CAM = CameraModel()


class Scene:
    """Synthetic static radar scene (see module docstring)."""

    def __init__(self, targets, seed=0):
        rng = np.random.default_rng(seed)
        self.targets = [(r, b, a, float(rng.uniform(-math.pi, math.pi))) for r, b, a in targets]

    def frames(self, n, t0=0.0, seed=1, flame=None, on=None):
        """n frames from t0 at FS. flame: dict(loss_db, amp_flicker_db, phase_step_rad); on: bool[n] (flame on)."""
        rng = np.random.default_rng(seed)
        n_ant = 4
        static = np.zeros((N_BINS, n_ant), complex)
        behind = np.zeros((N_BINS, n_ant), complex)
        for r, b, a, ph in self.targets:
            sv = DEFAULT_ARRAY.steering(b, n_ant)
            b0 = int(round(r / RES))
            for db, g in ((-1, 0.316), (0, 1.0), (1, 0.316)):
                tgt = behind if r > NEAR_EDGE else static
                tgt[b0 + db] += a * g * np.exp(1j * ph) * sv
        if on is None:
            on = np.ones(n, bool)
        noise = (rng.normal(size=(n, N_BINS, n_ant)) + 1j * rng.normal(size=(n, N_BINS, n_ant))) / math.sqrt(2)
        out = []
        psi = 0.0
        for i in range(n):
            g = 1.0
            if flame is not None and on[i]:
                psi += rng.normal(0.0, flame.get("phase_step_rad", 0.0))
                ldb = flame.get("loss_db", 0.0) + rng.normal(0.0, flame.get("amp_flicker_db", 0.0))
                if "loss_range_db" in flame:
                    ldb = rng.uniform(*flame["loss_range_db"])
                g = 10 ** (-ldb / 20.0) * np.exp(1j * psi)
            iq = (static + g * behind + noise[i]).astype(np.complex64)
            out.append(RadarFrame(t=t0 + i / FS, range_res_m=RES, iq=iq, sim=True))
        return out


TARGETS = [(4.0, 0.0, 30.0), (14.0, 0.0, 40.0), (20.0, 2.0, 15.0)]


def thermal_frame(kind, seed=0):
    """SYNTHETIC thermal frame (K). 'flame': 450 C block at boresight; 'smoke': warm plume, max < 120 C;
    'cool': mist / exhaust region at ~45 C."""
    rng = np.random.default_rng(seed)
    f = (20.0 + C_TO_K + rng.normal(0, 0.3, (192, 256))).astype(np.float32)
    if kind == "flame":
        f[90:140, 118:138] = 450.0 + C_TO_K
    elif kind == "smoke":
        yy, xx = np.mgrid[0:192, 0:256]
        f += (90.0 * np.exp(-((xx - 128) ** 2 / 3000.0 + (yy - 80) ** 2 / 1500.0))).astype(np.float32)
        assert f.max() - C_TO_K < 120.0
    elif kind == "cool":
        f[90:140, 110:146] = 45.0 + C_TO_K
    return f


def thermal_flag(kind, bearing=0.0):
    return flame_at_bearing(flame_mask(thermal_frame(kind)), bearing, tol_deg=3.0)[0]


@pytest.fixture(scope="module")
def scene():
    return Scene(TARGETS, seed=0)


@pytest.fixture(scope="module")
def baseline(scene):
    return RadarBaseline.capture(scene.frames(100, t0=0.0, seed=11))


def run(detector, frames, near=NEAR_EDGE, bearing=0.0):
    return [detector.update(f, near_edge_m=near, bearing_deg=bearing) for f in frames]


def test_beam_peaks_at_target_bearing():
    sv = DEFAULT_ARRAY.steering(12.0, 4)
    iq = np.zeros((10, 4), complex); iq[5] = sv
    p = [abs(beam(iq, b)[5]) for b in (-20, 0, 12, 25)]
    assert p[2] == pytest.approx(1.0) and max(p[0], p[1], p[3]) < 0.9


def test_baseline_roundtrip_and_minimum(scene, baseline, tmp_path):
    with pytest.raises(ValueError):
        RadarBaseline.capture(scene.frames(10))
    p = tmp_path / "radar_baseline.json"
    baseline.save(p)
    back = RadarBaseline.load(p)
    assert back.n_bins == N_BINS and set(back.heatmap) == set(baseline.heatmap)
    assert np.allclose(back.heatmap[0.0].mean_db, baseline.heatmap[0.0].mean_db)


def test_1_smoke_only_gives_no_flame_every_window(scene, baseline):
    det = RadarFlameDetector(baseline, window_s=3.0)
    states = run(det, scene.frames(600, t0=20.0, seed=21))            # 60 s of smoke-only: no radar effect
    th = thermal_flag("smoke")
    assert th is False
    evaluated = [s for s in states[31:]]
    assert len(evaluated) > 500
    assert all(s.status == "NO_EFFECT" for s in evaluated), {s.reason for s in evaluated if s.status != "NO_EFFECT"}
    assert all(fuse_flame(s, th).status == "NO_FLAME" for s in evaluated)


def test_2_flame_phase_flicker_and_loss_with_hot_thermal_is_flame(scene, baseline):
    det = RadarFlameDetector(baseline, window_s=3.0)
    flame = dict(loss_db=2.0, amp_flicker_db=0.5, phase_step_rad=0.3)
    s = run(det, scene.frames(40, t0=20.0, seed=22, flame=flame))[-1]
    assert s.status == "FLAME_EFFECT", s.reason
    assert s.flicker_phase_z >= 4.0
    assert s.far_echo_m is not None and s.far_echo_m > NEAR_EDGE
    assert min(s.effect_ranges_m) > NEAR_EDGE                         # nothing in front of the near edge
    th = thermal_flag("flame")
    assert th is True
    assert fuse_flame(s, th).status == "FLAME"


def test_3_flame_like_radar_but_cold_thermal_is_no_flame(scene, baseline):
    # water mist / hot exhaust plume: 1-3 dB loss and flicker on the radar, thermal stays cool
    det = RadarFlameDetector(baseline, window_s=3.0)
    mist = dict(loss_db=2.0, amp_flicker_db=0.8, phase_step_rad=0.15)
    s = run(det, scene.frames(40, t0=20.0, seed=23, flame=mist))[-1]
    assert s.status == "FLAME_EFFECT"
    th = thermal_flag("cool")
    assert th is False
    f = fuse_flame(s, th)
    assert f.status == "NO_FLAME"


def test_4_hot_thermal_but_radar_unknown_is_unknown(scene, baseline):
    th = thermal_flag("flame")
    frames = scene.frames(40, t0=20.0, seed=24)
    # (a) no baseline
    s = run(RadarFlameDetector(None), frames)[-1]
    assert s.status == "UNKNOWN" and "baseline" in s.reason
    assert fuse_flame(s, th).status == "UNKNOWN"
    # (b) no echo behind the near edge (near edge beyond every reflector)
    s = run(RadarFlameDetector(baseline), frames, near=22.0)[-1]
    assert s.status == "UNKNOWN"
    assert fuse_flame(s, th).status == "UNKNOWN"
    # (b2) echo behind fully blanked by the flame (cannot look behind it)
    blank = scene.frames(40, t0=20.0, seed=25, flame=dict(loss_db=60.0))
    s = run(RadarFlameDetector(baseline), blank)[-1]
    assert s.status == "UNKNOWN" and "cannot look behind" in s.reason
    assert fuse_flame(s, th).status == "UNKNOWN"
    # (c) stale: newest frame 2 s old
    det = RadarFlameDetector(baseline)
    run(det, frames)
    s = det.evaluate(now=frames[-1].t + 2.0, near_edge_m=NEAR_EDGE)
    assert s.status == "UNKNOWN" and "stale" in s.reason
    assert fuse_flame(s, th).status == "UNKNOWN"
    # (d) less than 1 s of frames
    s = run(RadarFlameDetector(baseline), frames[:8])[-1]
    assert s.status == "UNKNOWN"
    # (e) newest frame has neither heatmap nor range profile
    det = RadarFlameDetector(baseline)
    run(det, frames)
    s = det.update(RadarFrame(t=frames[-1].t + 0.1, range_res_m=RES), near_edge_m=NEAR_EDGE)
    assert s.status == "UNKNOWN"
    # (f) vehicle moving
    s = RadarFlameDetector(baseline).update(frames[0], moving=True)
    assert s.status == "UNKNOWN"
    # (g) noise floor raised (interference): +15 dB of noise
    loud = [RadarFrame(t=f.t, range_res_m=RES, iq=f.iq * 6.0) for f in frames]
    s = run(RadarFlameDetector(baseline), loud)[-1]
    assert s.status == "UNKNOWN" and "noise" in s.reason
    # (h) thermal flag unavailable
    assert fuse_flame(run(RadarFlameDetector(baseline), frames)[-1], None).status == "UNKNOWN"


def _gusts(seed=52, n=40):
    rng = np.random.default_rng(seed)
    on = np.zeros(n, bool)
    i = 0
    while i < n:                                     # alternating gust / gap segments of 2-6 frames
        n_on = int(rng.integers(3, 7)); n_off = int(rng.integers(1, 4))
        on[i:i + n_on] = True; i += n_on + n_off
    return on


def test_5_intermittent_flame_far_echo_found_by_window_max():
    # one reflector behind the flame at 14 m, ~20 dB above the noise floor in clear looks;
    # flame frames (gusts, ~65 % of the time) attenuate it by 12-16 dB; gaps give clear looks.
    # A 4 m reflector in front of the flame is the CONTROL echo (without one an effect is UNKNOWN: test_5b).
    sc = Scene([(4.0, 0.0, 30.0), (14.0, 0.0, 4.2)], seed=5)
    bl = RadarBaseline.capture(sc.frames(100, seed=51))
    on = _gusts()
    frames = sc.frames(40, t0=20.0, seed=53, flame=dict(loss_range_db=(12.0, 16.0), phase_step_rad=0.3), on=on)
    det = RadarFlameDetector(bl, window_s=3.0)
    s = run(det, frames)[-1]
    pb = s.per_bin
    b14 = int(round(14.0 / RES))
    snr_max = pb["window_max_db"][b14] - s.noise_db
    snr_mean = pb["window_mean_db"][b14] - s.noise_db
    print(f"\nintermittent flame: duty {on[-31:].mean():.2f}, window-max SNR {snr_max:.1f} dB, "
          f"window-mean SNR {snr_mean:.1f} dB, present {pb['present_frac'][b14]:.2f}, far echo {s.far_echo_m} m")
    assert snr_mean < 12.0                           # a mean-amplitude rule would not find the far echo
    assert snr_max >= 12.0
    assert s.far_echo_m == pytest.approx(14.0, abs=2 * RES)
    assert s.status == "FLAME_EFFECT"
    # and the pure function agrees
    assert first_solid_echo(pb["window_max_db"], s.noise_db, NEAR_EDGE, RES, present_frac=pb["present_frac"]) \
        == pytest.approx(s.far_echo_m)
    assert first_solid_echo(pb["window_mean_db"], s.noise_db, NEAR_EDGE, RES, present_frac=pb["present_frac"]) \
        != pytest.approx(14.0, abs=2 * RES)


def test_5b_effect_without_a_control_echo_in_front_is_unknown():
    # same intermittent flame, but nothing in front of the flame to tell a flame from vibration or interference
    sc = Scene([(14.0, 0.0, 4.2)], seed=5)
    bl = RadarBaseline.capture(sc.frames(100, seed=51))
    frames = sc.frames(40, t0=20.0, seed=53, flame=dict(loss_range_db=(12.0, 16.0), phase_step_rad=0.3), on=_gusts())
    s = run(RadarFlameDetector(bl, window_s=3.0), frames)[-1]
    assert s.status == "UNKNOWN" and "no control echo" in s.reason, s.reason
    assert fuse_flame(s, True).status == "UNKNOWN"
    # the same config with require_control off reports the effect (documents what the gate removes)
    s2 = run(RadarFlameDetector(bl, cfg=RadarFlameConfig(require_control=False)), frames)[-1]
    assert s2.status == "FLAME_EFFECT", s2.reason


def test_6_noise_only_false_positive_rate(scene, baseline):
    """500 (almost) independent 3 s windows of no-flame data at k = 4: measured false FLAME_EFFECT rate."""
    cfg = RadarFlameConfig()
    assert cfg.k_flicker == 4.0 and cfg.k_loss == 4.0
    det = RadarFlameDetector(baseline, cfg=cfg)
    n_win, per = 500, 30
    fp = 0
    worst = {"loss_z": -np.inf, "flicker_amp_z": -np.inf, "flicker_phase_z": -np.inf}
    t0 = 100.0
    for w in range(n_win):
        frames = scene.frames(per, t0=t0 + w * per / FS, seed=1000 + w)
        for f in frames:
            det.push(f)
        s = det.evaluate(frames[-1].t, near_edge_m=NEAR_EDGE)
        assert s.status in ("NO_EFFECT", "FLAME_EFFECT"), s.reason
        fp += s.status == "FLAME_EFFECT"
        for k in worst:
            worst[k] = max(worst[k], getattr(s, k))
    print(f"\nnoise-only: {fp} false FLAME_EFFECT in {n_win} windows (rate {fp / n_win:.4f}) at k = 4; "
          f"largest z over all windows: " + ", ".join(f"{k} {v:.2f}" for k, v in worst.items()))
    assert fp == 0


def test_6b_noise_only_rate_over_several_baselines():
    """Same measurement over 4 more baseline captures and 3 scene phase draws (2000 windows). The false-alarm rate
    depends on how representative the baseline capture is; this reports it across captures."""
    fp = n = 0
    for b in range(4):
        sc = Scene(TARGETS, seed=b % 3)
        bl = RadarBaseline.capture(sc.frames(100, seed=200 + 7 * b))
        det = RadarFlameDetector(bl)
        for w in range(500):
            frames = sc.frames(30, t0=100.0 + 3.0 * w, seed=20000 + 1000 * b + w)
            for f in frames:
                det.push(f)
            fp += det.evaluate(frames[-1].t, near_edge_m=NEAR_EDGE).status == "FLAME_EFFECT"
            n += 1
    print(f"\nnoise-only over 4 baselines: {fp} false FLAME_EFFECT in {n} windows (rate {fp / n:.5f})")
    assert fp == 0


def test_range_profile_only_source(scene):
    """Frames with only the TLV 2 range profile (no heatmap, no phase): loss is still detected, smoke is not."""
    def prof(frames):
        return [RadarFrame(t=f.t, range_res_m=RES, range_profile_db=20 * np.log10(np.abs(f.iq).sum(axis=1)))
                for f in frames]
    bl = RadarBaseline.capture(prof(scene.frames(100, seed=61)))
    assert bl.profile is not None and not bl.heatmap
    on = RadarFlameConfig(allow_profile_only=True)
    s = run(RadarFlameDetector(bl, cfg=on), prof(scene.frames(40, t0=20.0, seed=62)))[-1]
    assert s.status == "NO_EFFECT" and s.source == "profile"
    s = run(RadarFlameDetector(bl, cfg=RadarFlameConfig(allow_profile_only=True)),
            prof(scene.frames(40, t0=20.0, seed=63, flame=dict(loss_db=3.0))))[-1]
    assert s.status == "FLAME_EFFECT" and s.loss_db >= 1.0
    assert np.isnan(s.flicker_phase_rad)
    # PHYS-6: by default (TLV 2 scaling unverified on the EVM) the profile-only path gives UNKNOWN, flame or not
    for seed, flame in ((62, None), (63, dict(loss_db=3.0))):
        s = run(RadarFlameDetector(bl), prof(scene.frames(40, t0=20.0, seed=seed, flame=flame)))[-1]
        assert s.status == "UNKNOWN" and "UNVERIFIED" in s.reason


# ------------------------------------------------------------------------------------------------------------------
# Ground clutter in EVERY range bin (the step 8 virtual-unit geometry, SYNTHETIC): radar 2.5 m up, ground clutter in
# every bin beyond 2.5 m with per-antenna SNR 25 - 30 log10(r / 10 m) dB and a static random phase per bin, a corner
# reflector at 25 m with 45 - 40 log10(r / 10 m) dB, 4 antennas in phase (boresight), unit complex noise per
# antenna, 0.1 m bins to 40 m, 10 frames/s. Effects (illustrative, not measured):
#   flame: echoes beyond the near edge get a common phase random walk (rad/frame) and a loss (dB);
#   mist: 2 dB loss + 0.35 dB amplitude flicker beyond the near edge, no phase walk (as wfgvu.synth);
#   vibration: a common phase jitter N(0, sigma) per frame on EVERY echo (platform; absent from the baseline);
#   noise_gain: receiver noise amplitude multiplied (interference).
C_RES = 0.1
C_BINS = 400
C_NEAR = 12.0
C_REFL = 25.0
C_NOISE_TRUE_DB = 10 * math.log10(1.0 / 4) + 20 * math.log10(math.sqrt(math.log(2.0)))   # beam noise, Rayleigh median


class ClutterScene:
    def __init__(self, seed=0, reflector=True):
        rng = np.random.default_rng(seed)
        r = np.arange(C_BINS) * C_RES
        snr = np.where(r > 2.5, 25.0 - 30.0 * np.log10(np.maximum(r, 1e-3) / 10.0), -np.inf)
        self.echo = np.where(np.isfinite(snr), 10 ** (snr / 20.0), 0.0) * np.exp(1j * rng.uniform(-np.pi, np.pi, C_BINS))
        if reflector:
            b = int(round(C_REFL / C_RES))
            self.echo[b] += 10 ** ((45.0 - 40.0 * math.log10(C_REFL / 10.0)) / 20.0) * np.exp(1j * rng.uniform(-3, 3))
        self.r = r

    def frames(self, n, t0=0.0, seed=1, flame=None, mist=False, vib=0.0, noise_gain=1.0, onset=None, near=C_NEAR):
        rng = np.random.default_rng(seed)
        behind = self.r > near
        psi = 0.0
        out = []
        for i in range(n):
            t = t0 + i / FS
            g = np.ones(C_BINS, complex)
            active = onset is None or t >= onset - 1e-9
            if flame is not None and active:
                psi += rng.normal(0.0, flame.get("phase_step_rad", 0.0))
                g = np.where(behind, 10 ** (-flame.get("loss_db", 0.0) / 20.0) * np.exp(1j * psi), g)
            if mist and active:
                g = np.where(behind, 10 ** (-(2.0 + rng.normal(0.0, 0.35)) / 20.0), g)
            jit = np.exp(1j * rng.normal(0.0, vib)) if vib > 0 else 1.0
            noise = (rng.normal(size=(C_BINS, 4)) + 1j * rng.normal(size=(C_BINS, 4))) / math.sqrt(2) * noise_gain
            iq = (self.echo * g * jit)[:, None] + noise
            out.append(RadarFrame(t=t, range_res_m=C_RES, iq=iq.astype(np.complex64), sim=True))
        return out


@pytest.fixture(scope="module")
def clutter():
    return ClutterScene(seed=3)


@pytest.fixture(scope="module")
def clutter_baseline(clutter):
    return RadarBaseline.capture(clutter.frames(100, seed=31), bearings_deg=(0.0,))


def test_clutter_noise_floor_not_biased_by_clutter(clutter, clutter_baseline):
    st = clutter_baseline.heatmap[0.0]
    print(f"\nclutter everywhere: true beam noise {C_NOISE_TRUE_DB:.2f} dB; temporal estimate {st.noise_db:.2f} dB "
          f"({st.noise_method}); level estimate (25th pct of medians) {st.level_db:.2f} dB")
    assert st.noise_method == "temporal"
    assert C_NOISE_TRUE_DB - 0.3 <= st.noise_db <= C_NOISE_TRUE_DB + 1.0      # never far below the truth
    assert st.level_db >= C_NOISE_TRUE_DB + 8.0                              # the old estimator's clutter bias


def test_clutter_flame_scored_beyond_15m_and_far_echo_is_the_reflector(clutter, clutter_baseline):
    frames = clutter.frames(40, t0=20.0, seed=32, flame=dict(phase_step_rad=0.3, loss_db=1.0))
    s = run(RadarFlameDetector(clutter_baseline, window_s=3.0), frames, near=C_NEAR)[-1]
    z = np.asarray(s.per_bin["flicker_phase_z"], dtype=float)
    r = np.asarray(s.per_bin["range_m"])
    scored = np.isfinite(z) & (r > 15.0) & (np.abs(r - C_REFL) > 0.5)
    print(f"\nclutter flame: {s.status}, clutter bins scored beyond 15 m: {int(scored.sum())}, max range scored "
          f"{r[np.isfinite(z)].max():.1f} m, effect bins {len(s.effect_ranges_m)}, far echo {s.far_echo_m} m, "
          f"control bins {s.n_control_bins}")
    assert s.status == "FLAME_EFFECT", s.reason
    assert scored.sum() > 50 and r[np.isfinite(z)].max() > 25.0
    assert max(s.effect_ranges_m) > 20.0 and min(s.effect_ranges_m) > C_NEAR
    assert s.far_echo_m == pytest.approx(C_REFL, abs=2 * C_RES)              # not the first clutter bin past 12 m
    assert fuse_flame(s, True).status == "FLAME"


def test_clutter_first_solid_echo_is_not_clutter(clutter, clutter_baseline):
    st = clutter_baseline.heatmap[0.0]
    # baseline mean of the scene WITH the reflector: the reflector, not the first clutter bin beyond the near edge
    assert first_solid_echo(st.mean_db, st.noise_db, C_NEAR, C_RES, reference_std_db=st.std_db) \
        == pytest.approx(C_REFL, abs=2 * C_RES)
    # clutter only: no solid echo anywhere beyond the near edge, though every bin is >= 12 dB above the noise
    bare = ClutterScene(seed=3, reflector=False)
    bb = RadarBaseline.capture(bare.frames(100, seed=33), bearings_deg=(0.0,)).heatmap[0.0]
    r = np.arange(C_BINS) * C_RES
    assert np.all(bb.mean_db[(r > C_NEAR) & (r < 30.0)] >= bb.noise_db + 12.0)
    assert first_solid_echo(bb.mean_db, bb.noise_db, C_NEAR, C_RES) is None
    s = run(RadarFlameDetector(RadarBaseline.capture(bare.frames(100, seed=33), bearings_deg=(0.0,))),
            bare.frames(40, t0=20.0, seed=34, flame=dict(phase_step_rad=0.3)))[-1]
    assert s.status == "UNKNOWN" and "no solid echo" in s.reason and s.far_echo_m is None
    assert fuse_flame(s, True).status == "UNKNOWN"


def test_clutter_no_fire_and_smoke_only_never_flame_effect(clutter, clutter_baseline):
    """200 windows of no-flame clutter data (smoke has no radar effect, so smoke-only radar data is the same): no
    FLAME_EFFECT, and with the smoke thermal frame never FLAME."""
    det = RadarFlameDetector(clutter_baseline)
    th = thermal_flag("smoke")
    assert th is False
    counts = {"FLAME_EFFECT": 0, "NO_EFFECT": 0, "UNKNOWN": 0}
    worst = -np.inf
    for w in range(200):
        frames = clutter.frames(30, t0=100.0 + 3.0 * w, seed=3000 + w)
        for f in frames:
            det.push(f)
        s = det.evaluate(frames[-1].t, near_edge_m=C_NEAR)
        counts[s.status] += 1
        worst = max(worst, s.flicker_phase_z if math.isfinite(s.flicker_phase_z) else -np.inf)
        assert fuse_flame(s, th).status != "FLAME"
    print(f"\nclutter no-fire / smoke-only: {counts} in 200 windows; largest phase z {worst:.2f}")
    assert counts["FLAME_EFFECT"] == 0


@pytest.mark.parametrize("vib", [0.005, 0.01, 0.02, 0.05, 0.1, 0.3])
def test_vibration_like_common_phase_jitter_never_flame_effect(clutter, clutter_baseline, scene, baseline, vib):
    """Platform vibration (common phase jitter on every echo, absent from the baseline) on the clutter scene and on
    the sparse scene (4 m reflector in front of the flame): never FLAME_EFFECT."""
    out = []
    for k in range(5):
        s1 = run(RadarFlameDetector(clutter_baseline), clutter.frames(40, t0=20.0, seed=400 + k, vib=vib))[-1]
        s2 = run(RadarFlameDetector(baseline), scene_vib(scene, 40, seed=500 + k, vib=vib))[-1]
        out += [s1.status, s2.status]
        assert s1.status != "FLAME_EFFECT", s1.reason
        assert s2.status != "FLAME_EFFECT", s2.reason
    print(f"\nvibration {vib} rad: statuses {sorted(set(out))}")


def scene_vib(scene, n, seed, vib):
    """The sparse scene's frames with a common phase jitter on every echo (noise unchanged)."""
    rng = np.random.default_rng(seed + 7)
    calm = scene.frames(n, t0=20.0, seed=seed)
    # echo part = frame - noise (Scene.frames draws its noise first from default_rng(seed)); jitter only the echoes
    rng_n = np.random.default_rng(seed)
    noise = (rng_n.normal(size=(n, N_BINS, 4)) + 1j * rng_n.normal(size=(n, N_BINS, 4))) / math.sqrt(2)
    res = []
    for i, f in enumerate(calm):
        echo = f.iq - noise[i]
        res.append(RadarFrame(t=f.t, range_res_m=RES, iq=(echo * np.exp(1j * rng.normal(0.0, vib)) + noise[i])
                              .astype(np.complex64), sim=True))
    return res


def test_water_mist_on_clutter_never_flame(clutter, clutter_baseline):
    th = thermal_flag("cool")
    assert th is False
    seen = set()
    for k in range(5):
        states = run(RadarFlameDetector(clutter_baseline), clutter.frames(40, t0=20.0, seed=600 + k, mist=True))
        for s in states:
            seen.add(s.status)
            assert fuse_flame(s, th).status != "FLAME"
    print(f"\nwater mist on clutter: radar statuses {sorted(seen)} (a mist effect is expected; the thermal AND rejects)")


def test_window_mostly_pre_flame_is_not_accepted(scene, baseline):
    """Flame begins at t = 23.0 s inside a 3 s window: FLAME_EFFECT only once the effect has held >= 2 s."""
    det = RadarFlameDetector(baseline, window_s=3.0)
    flame = dict(loss_db=2.0, amp_flicker_db=0.5, phase_step_rad=0.3)
    calm = scene.frames(30, t0=20.0, seed=70)
    hot = scene.frames(40, t0=23.0, seed=71, flame=flame)
    first = None
    for f in calm + hot:
        s = det.update(f, near_edge_m=NEAR_EDGE)
        since = f.t - 23.0
        if s.status == "FLAME_EFFECT" and first is None:
            first = since
        if since < 1.85:
            assert s.status != "FLAME_EFFECT", (since, s.reason, s.effect_s)
        if 0.0 <= since < 1.0:
            assert s.status == "UNKNOWN" and ("held for only" in s.reason), s.reason
    print(f"\nflame onset: first FLAME_EFFECT {first:.1f} s after onset (min_effect_s = 2.0)")
    assert first is not None and first <= 2.5


def test_moving_gives_unknown_and_invalidates_baseline(scene, baseline):
    frames = scene.frames(40, t0=20.0, seed=80, flame=dict(phase_step_rad=0.3))
    det = RadarFlameDetector(baseline)
    run(det, frames[:30])
    s = det.update(frames[30], near_edge_m=NEAR_EDGE, moving=True)
    assert s.status == "UNKNOWN" and "moving" in s.reason and s.baseline_invalidated
    assert det.baseline is None and "moving" in det.invalidated_reason
    assert fuse_flame(s, True).status == "UNKNOWN"
    # stopped again: still UNKNOWN until a new baseline is captured; old frames are gone
    for f in frames[31:]:
        s = det.update(f, near_edge_m=NEAR_EDGE)
        assert s.status == "UNKNOWN" and "invalidated" in s.reason
    det.baseline = baseline
    assert det.invalidated_reason == ""
    s = det.evaluate(frames[-1].t, near_edge_m=NEAR_EDGE)
    assert s.status == "UNKNOWN" and "frames in window" in s.reason          # window was cleared at the move
    # moving with no baseline is UNKNOWN too, and says nothing was invalidated
    s = RadarFlameDetector(None).update(frames[0], moving=True)
    assert s.status == "UNKNOWN" and not s.baseline_invalidated


def test_noise_rise_without_flame_never_flame_effect(clutter, clutter_baseline):
    # +6 dB of receiver noise (below the 10 dB ceiling): the floor follows the measured rise, no FLAME_EFFECT
    for k in range(5):
        s = run(RadarFlameDetector(clutter_baseline), clutter.frames(40, t0=20.0, seed=700 + k, noise_gain=2.0))[-1]
        assert s.status != "FLAME_EFFECT", s.reason
        assert 4.5 < s.noise_rise_db < 7.5
    # +15.6 dB: above the ceiling
    s = run(RadarFlameDetector(clutter_baseline), clutter.frames(40, t0=20.0, seed=710, noise_gain=6.0))[-1]
    assert s.status == "UNKNOWN" and "noise" in s.reason


def test_old_baseline_file_without_temporal_fields_still_loads(scene, baseline, tmp_path):
    d = baseline.to_dict()
    for v in d["heatmap"].values():
        for k in ("level_db", "resid_db", "noise_method"):
            v.pop(k)
        v["noise_db"] = v["noise_db"] + 0.0
    old = RadarBaseline.from_dict(d)
    assert old.heatmap[0.0].noise_method == "level" and old.heatmap[0.0].resid_db is None
    s = run(RadarFlameDetector(old), scene.frames(40, t0=20.0, seed=90))[-1]
    assert s.status == "NO_EFFECT", s.reason
    p = tmp_path / "bl.json"
    baseline.save(p)
    back = RadarBaseline.load(p).heatmap[0.0]
    assert back.noise_method == "temporal" and np.allclose(back.resid_db, baseline.heatmap[0.0].resid_db)


@pytest.mark.parametrize("scenario", ["no_fire", "smoke_only", "water_mist", "flame_front"])
def test_wfgvu_synth_scenarios(scenario):
    """wfgvu.synth radar (SYNTHETIC: ~400 Rayleigh ground scatterers, TX leakage, 0.03 rad engine-idle jitter, a solid
    object beyond the flame; see its docstring). Baseline from 2.0-7.9 s, evaluation every 0.2 s after the 8 s onset.
    no_fire / smoke_only: never FLAME_EFFECT; water_mist: radar effect allowed (by design of the synth) but never
    FLAME with its cool thermal; flame_front: FLAME_EFFECT, not before 1.8 s after onset."""
    synth = pytest.importorskip("wfgvu.synth")
    p = synth.make_params(scenario, seed=0, duration_s=24.0)
    sim = synth.RadarSim(p, synth.Scene(p), np.random.default_rng([0, 2]))
    frames = [rf_frame(sim.frame(float(t)), float(t)) for t in np.arange(0.0, 24.0, 0.1)]
    bl = RadarBaseline.capture([f for f in frames if 2.0 <= f.t < p.onset_s - 0.05], bearings_deg=(0.0,))
    near = math.hypot(p.range_m if p.range_m else 12.0, p.radar_height_m)
    det = RadarFlameDetector(bl)
    th = {"no_fire": False, "smoke_only": thermal_flag("smoke"), "water_mist": thermal_flag("cool"),
          "flame_front": True}[scenario]
    seen = {}
    first = None
    for f in frames:
        det.push(f)
        if f.t >= p.onset_s and int(round(f.t * 10)) % 2 == 0:
            s = det.evaluate(f.t, near_edge_m=near)
            seen[s.status] = seen.get(s.status, 0) + 1
            if s.status == "FLAME_EFFECT" and first is None:
                first = f.t - p.onset_s
            if scenario != "flame_front":
                assert fuse_flame(s, th).status != "FLAME"
    print(f"\nsynth {scenario}: {seen}, first FLAME_EFFECT {first} s after onset, far echo {s.far_echo_m} m")
    if scenario in ("no_fire", "smoke_only"):
        assert seen.get("FLAME_EFFECT", 0) == 0
    if scenario == "flame_front":
        assert first is not None and first >= 1.8 and seen["FLAME_EFFECT"] >= 0.8 * sum(seen.values())


def rf_frame(data, t):
    from crossing.radar_flame import frame_from_reading
    return frame_from_reading(data, t, sim=True)


def test_radar_ceiling_never_lowers_depth_unless_trusted():
    """A too-small radar ceiling (e.g. a post inside the flame zone) must not lower depth_m or the upper end."""
    from types import SimpleNamespace
    from crossing import depth as dp
    est = [dp.Estimate(name="byram", value_m=6.0, lo_m=3.0, hi_m=12.0, sigma_log=0.6, valid=True, reason="ok")]
    ref = dp.combine(est, None)
    tiny = dp.radar_ceiling(10.0, 10.3, 0.05)                 # 0.3 m ceiling
    for calib in (None, SimpleNamespace(trust_radar_ceiling=False, calibrated=False, n_pairs=0)):
        d = dp.combine(est + [tiny], calib)
        assert d.depth_m == pytest.approx(ref.depth_m) and d.hi_m == pytest.approx(ref.hi_m)
        assert d.ceiling_m == pytest.approx(0.3)
    # Trusted by calibration (n >= 9 pairs, measured <= ceiling every time): PHYS-1, the ceiling never enters the
    # mean; it may only cap hi_m when it is >= depth_m. A 0.3 m ceiling under a 6.0 m depth is a conflict: nothing
    # changes (flagged).
    trusted = SimpleNamespace(trust_radar_ceiling=True, calibrated=False, n_pairs=9)
    d = dp.combine(est + [tiny], trusted)
    assert "radar_ceiling" not in d.used
    assert d.depth_m == pytest.approx(ref.depth_m) and d.hi_m == pytest.approx(ref.hi_m)
    assert d.lo_m == pytest.approx(ref.lo_m) and any("conflict" in f for f in d.flags)
