"""Synthetic rendering (motion blur, flux, color, rolling shutter) and the camera model."""
import math

import numpy as np
import pytest

from wfglink.synth import degrade as D
from wfglink.synth.particles import LUMA_BGR, LinearSources, glow_color
from wfglink.synth.render import RenderSettings, draw_spots, image_moments, n_substeps, render_exposure


def _mover(x0, y0, vx, vy, flux=1000.0, sigma=1.2, temp=1100.0, t_birth=-1.0, t_death=1.0, **kw):
    return LinearSources(pid=[0], kind=["ember"], t_birth=[t_birth], t_death=[t_death], flux=[flux],
                         sigma=[sigma], color=glow_color(temp), x0=[x0], y0=[y0], vx=[vx], vy=[vy], **kw)


def _luma(img):
    return img.astype(np.float64) @ LUMA_BGR


@pytest.mark.parametrize("angle", [0.0, 17.0, 45.0, 90.0, 133.0, 200.0])
@pytest.mark.parametrize("length", [10.0, 25.0])
def test_streak_length_matches_motion(angle, length):
    exp = 1 / 60
    speed = length / exp
    a = math.radians(angle)
    src = _mover(160.3, 120.6, speed * math.cos(a), speed * math.sin(a), sigma=1.0)
    img, truth, n = render_exposure([src], 0.0, exp, (320, 240), RenderSettings(n_sub_max=512), n_sub=256)
    m = image_moments(_luma(img))
    assert abs(m["length"] - speed * exp) < 0.1
    assert truth["streak_length_px"][0] == pytest.approx(length)
    assert m["flux"] == pytest.approx(1000.0, rel=0.01)
    # Centroid at the exposure midpoint, orientation along the motion (mod pi).
    assert m["x"] == pytest.approx(truth["x_mid"][0], abs=0.02)
    assert m["y"] == pytest.approx(truth["y_mid"][0], abs=0.02)
    d = (m["theta"] - a) % math.pi
    assert min(d, math.pi - d) < math.radians(0.5)


@pytest.mark.parametrize("length", [10.0, 20.0, 30.0])
def test_default_sample_rule_keeps_length_within_tenth_px(length):
    exp = 1 / 60
    src = _mover(150.2, 100.7, length / exp * 0.8, length / exp * 0.6, sigma=0.9)
    img, truth, n = render_exposure([src], 0.0, exp, (320, 240), RenderSettings(n_sub_max=256))
    assert n == max(8, math.ceil(2 * length - 1e-9))
    assert abs(image_moments(_luma(img))["length"] - length) < 0.1


def test_flux_conservation_and_color_ratio():
    col = glow_color(1000.0)[0]
    src = _mover(100.0, 80.0, 300.0, -120.0, flux=777.0, sigma=1.7, temp=1000.0)
    img, truth, _ = render_exposure([src], 0.0, 1 / 30, (240, 180))
    assert _luma(img).sum() == pytest.approx(777.0, rel=1e-4)
    assert truth["flux"][0] == pytest.approx(777.0)
    sums = img.astype(np.float64).sum(axis=(0, 1))
    assert np.allclose(sums / sums.sum(), col / col.sum(), atol=1e-5)
    # Red dominates an ember; blue is weakest.
    assert sums[2] > sums[1] > sums[0]


def test_partly_outside_frame():
    src = _mover(-1.0, 50.0, 0.0, 0.0, flux=500.0, sigma=1.5)
    img, truth, _ = render_exposure([src], 0.0, 1 / 60, (100, 100))
    inside = _luma(img).sum()
    assert 150.0 < inside < 350.0                      # about the half inside the frame
    assert truth["flux"][0] == pytest.approx(500.0)    # truth keeps the whole flux
    # Light from a source just outside the frame still reaches the edge column.
    src = _mover(-2.0, 50.0, 0.0, 0.0, flux=500.0, sigma=1.5)
    img, _, _ = render_exposure([src], 0.0, 1 / 60, (100, 100))
    assert img[50, 0].sum() > 1.0


def test_n_substeps_rule():
    s = RenderSettings(n_sub_min=8, n_sub_max=48, samples_per_px=2.0, samples_per_tumble_cycle=8.0)
    assert n_substeps(0.0, 0.016, 0.0, s) == 8
    assert n_substeps(6.2, 0.016, 0.0, s) == 13
    assert n_substeps(100.0, 0.016, 0.0, s) == 48
    assert n_substeps(1.0, 1 / 60, 60.0, s) == 8
    assert n_substeps(1.0, 1 / 30, 60.0, s) == 16


def _pixel_gauss(c, sigma, n):
    """Gaussian of centre c integrated over pixels 0 .. n - 1 (pixel centres at integers)."""
    from scipy.special import ndtr

    i = np.arange(n)
    return ndtr((i + 0.5 - c) / sigma) - ndtr((i - 0.5 - c) / sigma)


@pytest.mark.parametrize("one_color", [True, False])
def test_spots_equal_exact_pixel_integrated_gaussians(one_color):
    rng = np.random.default_rng(3)
    n = 400
    x, y = rng.uniform(-8, 330, n), rng.uniform(-8, 250, n)
    w = rng.uniform(0.1, 2.0, n)
    owner = rng.integers(0, 60, n)
    col = rng.uniform(0, 1, (60, 3))[owner] if one_color else rng.uniform(0, 1, (n, 3))
    sig = rng.choice([0.6, 1.1, 2.0, 5.0], 60)[owner]     # one sigma per source, as rendered
    a = draw_spots(x, y, w, col, sig, (320, 240), owner=owner)
    # Reference: every sample drawn on the full frame with the exact, uncut profiles.
    ref = np.zeros((240, 320, 3))
    for xi, yi, wi, ci, si in zip(x, y, w, col, sig):
        ref += wi * np.outer(_pixel_gauss(yi, si, 240), _pixel_gauss(xi, si, 320))[..., None] * ci
    assert np.max(np.abs(a - ref)) < 1e-5 * max(1.0, float(ref.max()))
    inside = (x > 40) & (x < 280) & (y > 40) & (y < 200)    # far from the edges, all light lands
    b = draw_spots(x[inside], y[inside], w[inside], col[inside], sig[inside], (320, 240), owner=owner[inside])
    assert b.astype(np.float64).sum(axis=(0, 1)) == pytest.approx((w[inside, None] * col[inside]).sum(axis=0), rel=1e-6)


@pytest.mark.parametrize("sigma", [0.6, 1.0, 2.0])
def test_spot_shape_does_not_depend_on_subpixel_phase(sigma):
    """A static spot has no apparent streak length and a 2.5 px horizontal streak measures
    2.5 px at every sub-pixel phase (bilinear splatting gave 0 to 1.73 px and 2.25 to 2.87 px)."""
    exp = 1 / 60
    lengths, widths = [], []
    for fx in (0.0, 0.25, 0.5, 0.75):
        for fy in (0.0, 0.25, 0.5, 0.75):
            static = _mover(100.0 + fx, 80.0 + fy, 0.0, 0.0, sigma=sigma)
            m = image_moments(_luma(render_exposure([static], 0.0, exp, (220, 160))[0]))
            assert m["length"] < 0.2
            assert m["lam1"] == pytest.approx(sigma ** 2 + 1 / 12, abs=0.01)
            moving = _mover(100.0 + fx - 1.25, 80.0 + fy, 2.5 / exp, 0.0, sigma=sigma)
            m = image_moments(_luma(render_exposure([moving], 0.0, exp, (220, 160), n_sub=64)[0]))
            lengths.append(m["length"])
            widths.append(m["lam2"])
    assert np.allclose(lengths, 2.5, atol=0.01)
    assert np.allclose(widths, sigma ** 2 + 1 / 12, atol=0.01)


def test_rolling_shutter_sample_times():
    readout, exp, H = 0.02, 0.01, 200
    # Horizontal motion: the row is fixed, so the delay is exactly y / H readout.
    src = _mover(50.0, 150.0, 400.0, 0.0, t_death=10.0)
    _, tr, _ = render_exposure([src], 1.0, exp, (300, H), readout_s=readout)
    assert tr["t_mid"][0] == pytest.approx(1.0 + 0.5 * exp + 150.0 / H * readout, abs=1e-12)
    assert tr["x_start"][0] == pytest.approx(50.0 + 400.0 * (1.0 + 150.0 / H * readout), abs=1e-9)
    # Vertical motion: the sample time solves t = t0 + f exp + y(t) / H readout.
    src = _mover(50.0, 20.0, 0.0, 500.0)
    _, tr, _ = render_exposure([src], 0.1, exp, (300, H), readout_s=readout)
    t = tr["t_mid"][0]
    y = 20.0 + 500.0 * t
    assert t == pytest.approx(0.1 + 0.5 * exp + y / H * readout, abs=1e-9)
    assert tr["y_mid"][0] == pytest.approx(y)
    # Without a rolling shutter the midpoint is the frame's.
    _, tr, _ = render_exposure([src], 0.1, exp, (300, H))
    assert tr["t_mid"][0] == pytest.approx(0.1 + 0.5 * exp)


def test_birth_inside_exposure_is_clamped():
    exp = 0.02
    src = _mover(50.0, 50.0, 500.0, 0.0, flux=100.0, t_birth=0.015, t_death=5.0)
    img, tr, _ = render_exposure([src], 0.0, exp, (200, 100), n_sub=200)
    assert tr["alive_frac"][0] == pytest.approx(0.25)
    assert not tr["alive_mid"][0]
    assert tr["x_start"][0] == pytest.approx(50.0 + 500.0 * 0.015)
    assert tr["x_end"][0] == pytest.approx(50.0 + 500.0 * 0.02)
    assert tr["u"][0] == pytest.approx(500.0)
    assert tr["flux"][0] == pytest.approx(25.0, rel=0.01)
    assert _luma(img).sum() == pytest.approx(tr["flux"][0], rel=1e-4)
    # A source dead before the exposure is not rendered and has no truth row.
    dead = _mover(50.0, 50.0, 0.0, 0.0, t_birth=-1.0, t_death=-0.5)
    img, tr, _ = render_exposure([dead], 0.0, exp, (200, 100))
    assert tr["pid"].size == 0 and img.sum() == 0


def test_tumbling_makes_dashed_streaks():
    exp = 1 / 30
    common = dict(flux=2000.0, sigma=0.8)
    plain = _mover(40.0, 50.0, 3000.0, 0.0, **common)
    dashed = _mover(40.0, 50.0, 3000.0, 0.0, tumble_amp=[1.0], tumble_hz=[90.0], **common)
    profiles = []
    for src in (plain, dashed):
        img, _, n = render_exposure([src], 0.0, exp, (200, 100), RenderSettings(n_sub_max=512))
        profiles.append(_luma(img)[48:53].sum(axis=0)[45:135])
    p0, p1 = profiles
    assert p0.min() > 0.5 * p0.max()
    assert p1.min() < 0.1 * p1.max()


# Camera model ----------------------------------------------------------------------------
def test_noise_statistics_and_luma_sigma():
    img = np.empty((400, 400, 3), np.float32)
    img[...] = [20.0, 40.0, 60.0]
    out = D.add_noise(img, gain=2.0, electrons_per_dn=4.0, read_noise_dn=0.5, seed=(1, 2, 3), channel_corr=0.5)
    d = (out - img).reshape(-1, 3).astype(np.float64)
    want_var = np.array([20.0, 40.0, 60.0]) * 2.0 / 4.0 + 0.25
    assert np.allclose(d.mean(axis=0), 0.0, atol=0.03)
    assert np.allclose(d.var(axis=0), want_var, rtol=0.03)
    corr = np.corrcoef(d.T)
    assert corr[0, 1] == pytest.approx(0.5, abs=0.02)
    cam = D.Camera({"camera": {"gain": 2.0, "electrons_per_dn": 4.0, "read_noise_dn": 0.5, "channel_noise_corr": 0.5}}, 0)
    sig = cam.luma_noise_sigma(np.array([10.0, 20.0, 30.0]), scale=2.0, gain_eff=2.0)
    assert float(sig) == pytest.approx(float((d @ LUMA_BGR).std()), rel=0.02)
    # Same seed, same noise; different frame, different noise.
    again = D.add_noise(img, gain=2.0, electrons_per_dn=4.0, read_noise_dn=0.5, seed=(1, 2, 3), channel_corr=0.5)
    other = D.add_noise(img, gain=2.0, electrons_per_dn=4.0, read_noise_dn=0.5, seed=(1, 2, 4), channel_corr=0.5)
    assert np.array_equal(out, again) and not np.array_equal(out, other)


def test_poisson_shot_noise():
    img = np.full((300, 300, 3), 3.0, np.float32)
    out = D.add_noise(img, gain=1.0, electrons_per_dn=2.0, read_noise_dn=0.0, seed=(4,), mode="poisson")
    e = out.astype(np.float64) * 2.0
    assert np.allclose(e, np.rint(e))                     # whole electrons
    assert e.mean() == pytest.approx(6.0, rel=0.01)
    assert e.var() == pytest.approx(6.0, rel=0.03)


def test_gamma_quantize_and_unsharp():
    x = np.linspace(0, 255, 1000, dtype=np.float32).reshape(10, 100)
    enc = D.gamma_encode(np.dstack([x, x, x]), 2.2)
    assert np.allclose(D.gamma_decode(enc, 2.2)[..., 0], x, atol=1e-3)
    assert enc[0, 0, 0] == 0 and enc[-1, -1, 0] == pytest.approx(255.0)
    q = D.quantize(np.array([[[-3.0, 0.4, 0.6], [254.6, 300.0, 127.5]]], np.float32))
    assert q.dtype == np.uint8 and q.tolist() == [[[0, 0, 1], [255, 255, 128]]]
    edge = np.zeros((20, 20, 3), np.float32)
    edge[:, 10:] = 100.0
    sh = D.unsharp(edge, 1.0, 1.0)
    assert sh.max() > 100.0 and sh.min() < 0.0


def test_haze_and_depth():
    j = np.full((50, 60, 3), 10.0, np.float32)
    d = D.depth_map({"mode": "constant", "depth_m": 40.0}, (60, 50))
    t = D.transmission(d, 0.02)
    out = D.apply_haze(j, t, [30.0, 30.0, 30.0])
    tt = math.exp(-0.8)
    assert np.allclose(out, 10.0 * tt + 30.0 * (1 - tt), atol=1e-4)
    g = D.depth_map({"mode": "ground_plane", "camera_height_m": 10.0, "focal_px": 500.0,
                     "horizon_frac": 0.5, "z_max_m": 300.0}, (60, 100))
    col = g[:, 0]
    assert np.all(col[:51] == 300.0)                      # sky and horizon at z_max
    assert np.all(np.diff(col) <= 0)                      # nearer toward the bottom
    below_cap = col < 300.0
    assert below_cap[67:].all() and np.all(np.diff(col[67:]) < 0)
    assert col[99] == pytest.approx(10.0 * 500.0 / 49.0)


def test_defocus_and_bloom_conserve_energy():
    img = np.zeros((60, 60, 3), np.float32)
    img[30, 30] = 1000.0
    k = D.pillbox_kernel(3.0)
    assert k.sum() == pytest.approx(1.0) and k.shape == (7, 7)
    df = D.defocus(img, 3.0)
    assert df.sum() == pytest.approx(img.sum(), rel=1e-5)
    assert df[30, 30, 0] < 1000.0 and df[30, 33, 0] > 0 and df[30, 34, 0] == 0
    big = np.zeros((80, 80, 3), np.float32)
    big[38:42, 38:42] = 900.0
    b = D.bloom(big, 255.0, sigma_px=2.0, vertical_frac=0.5, vertical_len_px=15)
    assert b.sum() == pytest.approx(big.sum(), rel=1e-4)
    assert b[30, 40, 0] > 0                               # vertical smear
    assert b[40, 40, 0] < 900.0
    small = np.full((10, 10, 3), 100.0, np.float32)
    assert D.bloom(small, 255.0) is small                 # nothing above full well


def test_frame_timing_effects():
    cfg = {"fps": 30.0, "duration_s": 4.0, "duty": 1.0,
           "timing": {"jitter_frac": 0.3, "duplicate_prob": 0.2, "exposure_step": {"t_s": 2.0, "factor": 0.5}},
           "camera": {"flicker": {"amp": 0.2, "freq_hz": 3.0}}}
    tm = D.make_timing(cfg, 3)
    assert tm.n == 120
    iv = np.diff(tm.t_start)
    assert np.all(iv > 0) and iv.min() >= 0.7 / 30 - 1e-12 and iv.max() <= 1.3 / 30 + 1e-12
    assert np.all(tm.exposure_s[:-1] <= iv + 1e-12)       # never longer than the interval
    after = tm.t_start >= 2.0
    assert np.all(tm.gain_ratio[after] == 2.0) and np.all(tm.gain_ratio[~after] == 1.0)
    assert np.all(tm.exposure_s[after] <= 0.5 / 30 + 1e-12)
    assert not tm.duplicate[0] and 0.1 < tm.duplicate.mean() < 0.3
    assert tm.illumination.min() >= 0.8 - 1e-9 and tm.illumination.max() <= 1.2 + 1e-9
    plain = D.make_timing({"fps": 25.0, "duration_s": 2.0, "duty": 0.5}, 0)
    assert np.allclose(plain.t_start, np.arange(50) / 25.0) and np.allclose(plain.exposure_s, 0.02)
    assert not plain.duplicate.any()


def test_camera_denoise_blends_with_previous_frame():
    cfg = {"fps": 30.0, "duration_s": 0.1, "duty": 0.5,
           "camera": {"read_noise_dn": 0.0, "electrons_per_dn": 1e9}, "mismatch": {"denoise_alpha": 0.25}}
    tm = D.make_timing(cfg, 0)
    cam = D.Camera(cfg, 0)
    a = cam.process(np.full((8, 8, 3), 100.0, np.float32), tm, 0)
    b = cam.process(np.full((8, 8, 3), 0.0, np.float32), tm, 1)
    assert int(b[0, 0, 0]) == int(round(0.75 * float(D.gamma_encode(np.full((1, 1, 3), 100.0, np.float32))[0, 0, 0])))
    assert a[0, 0, 0] > b[0, 0, 0] > 0


def test_h264_roundtrip_with_variable_pts():
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[0:120, 0:160]
    frames = [np.dstack([(xx + 3 * i) % 256, (yy * 2) % 256, np.full_like(xx, 80)]).astype(np.uint8) for i in range(12)]
    pts = np.cumsum(np.r_[0.0, (1 / 30) * (1 + 0.4 * rng.uniform(-1, 1, 11))])
    dec, got = D.compress_roundtrip(frames, 30.0, crf=18, pts_s=pts)
    assert len(dec) == 12
    assert np.max(np.abs(got - pts)) < 1e-4
    mse = np.mean([(a.astype(float) - b) ** 2 for a, b in zip(frames, dec)])
    assert 10 * math.log10(255 ** 2 / mse) > 30


def test_h265_roundtrip_if_available():
    if not D.has_encoder("h265"):
        pytest.skip("this PyAV build has no libx265 encoder, so H.265 output is unavailable")
    frames = [np.full((64, 96, 3), 40 + 10 * i, np.uint8) for i in range(5)]
    dec, pts = D.compress_roundtrip(frames, 30.0, crf=23, codec="h265")
    assert len(dec) == 5 and np.allclose(pts, np.arange(5) / 30.0, atol=1e-4)


def test_missing_encoder_message():
    with pytest.raises(RuntimeError, match="no definitely_not_a_codec encoder"):
        D.encoder_name("definitely_not_a_codec")


def test_writer_rejects_non_increasing_pts(tmp_path):
    w = D.VideoWriter(tmp_path / "x.mp4", (32, 32), 30.0)
    w.write(np.zeros((32, 32, 3), np.uint8), 0.0)
    with pytest.raises(ValueError):
        w.write(np.zeros((32, 32, 3), np.uint8), 0.0)
    w.close()
