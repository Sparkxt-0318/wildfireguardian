"""Tests for apps/crossing/virtual_fds (step 8 virtual unit in FDS).

The fast tests use a SYNTHETIC uniform flaming slab (virtual_fds.fields.synthetic_slab), not FDS data, and check
shapes, finite values and the basic geometry of every stage. The real-data test runs only when the out-of-repo
C064 npz files are present (C064_FIRE_DATA or the default path) and is skipped otherwise.
"""
import math
import os
from pathlib import Path

import numpy as np
import pytest

from crossing import depth as dp
from crossing import thermal as th
from crossing.flux import PlateSpec
from virtual_fds import fields as F
from virtual_fds import lwir, pipeline as pl, plate as pt, radar_path as rp


@pytest.fixture(scope="module")
def slab():
    # flame zone x in [10, 20] m, 4 m tall; vehicle at x = 30 m -> leading edge 10 m ahead, depth 10 m
    return F.synthetic_slab(nx=48, ny=24, nz=10, x_lead=20.0, depth=10.0, height=4.0)


def test_synthetic_truth_metrics(slab):
    m = slab.metrics(20.0)
    assert m["le"] == pytest.approx(20.0)
    assert m["te"] == pytest.approx(10.0)
    assert m["depth"] == pytest.approx(10.0)
    assert m["flame_height"] == pytest.approx(4.0)


def test_sampler_trilinear_and_outside(slab):
    s = F.Sampler(slab, slab.temp_k, outside=[slab.t_ambient_k])
    v = s.sample([15.0, 25.0, 500.0], [0.0, 0.0, 0.0], [1.0, 1.0, 1.0])[0]
    assert v[0] == pytest.approx(1250.0)
    assert v[1] == pytest.approx(F.T_AMBIENT_K)
    assert v[2] == pytest.approx(F.T_AMBIENT_K)          # outside the grid -> ambient
    # halfway between a flame cell centre (19.5) and an ambient one (20.5)
    assert s.sample([20.0], [0.0], [1.0])[0][0] == pytest.approx(0.5 * (1250.0 + F.T_AMBIENT_K))


def test_band_planck_inversion_round_trip():
    T = np.array([250.0, 305.15, 600.0, 1100.0])
    L = lwir.band_radiance(T).sum(axis=0)
    back = lwir.apparent_temperature_k(L, eps=1.0)
    assert np.allclose(back, T, atol=0.6)
    # with eps < 1 a blackbody reads warmer than it is; at ambient it reads ambient
    assert lwir.apparent_temperature_k(lwir.band_radiance(305.15).sum(), eps=0.95, t_refl_k=305.15) == pytest.approx(305.15, abs=0.6)


def test_render_shapes_finite_and_cap(slab):
    r = lwir.render(slab, (30.0, 0.0, 2.5))
    assert r.temps_k.shape == (192, 256)
    assert np.all(np.isfinite(r.temps_k)) and np.all(np.isfinite(r.unclipped_k))
    assert r.temps_k.max() <= lwir.TC001_MAX_C + 273.15 + 1e-3
    assert r.temps_k.min() >= lwir.TC001_MIN_C + 273.15 - 1e-3
    ok, why = th.validate_frame(r.temps_k)
    assert ok, why
    assert r.max_optical_depth > 0


def test_optically_thin_soot_reads_cooler_than_gas():
    # no gas term, little soot: a 1250 K slab must read far below its gas temperature (optically thin)
    f = F.synthetic_slab(soot_kg_m3=1e-6)
    r = lwir.render(f, (30.0, 0.0, 2.5), params=lwir.OpticsParams(kappa_gas0=0.0))
    centre = r.unclipped_k[80, 128]
    assert F.T_AMBIENT_K < centre < 900.0


def test_observe_near_edge_and_height(slab):
    ob = pl.observe(slab, 30.0)
    s = ob.summary()
    assert s["valid_frame"] and s["flame_pixels"] > 100 and s["flame_at_boresight"]
    # base of the slab is 10 m from the camera; pixel quantisation at 10 m from 2.5 m height is ~0.2 m
    assert s["near_edge_m"] == pytest.approx(10.0, abs=0.6)
    assert s["flame_height_m"] is not None and 0.0 < s["flame_height_m"] <= 4.5
    assert set(s["alt_threshold"]) == {"200", "400"}


def test_radar_excess_phase_sign_and_detector(slab):
    sc = rp.Scene(x_r=30.0, x_ref=5.0, max_range_m=30.0)
    ph = rp.excess_phase(slab, sc)
    assert ph["bins"].shape == (sc.n_bins,) and np.all(np.isfinite(ph["bins"]))
    assert ph["reflector"] < 0                         # hot gas: lower refractivity, shorter optical path
    # path through 10 m of 1250 K gas: (n-1) drop 77.6e-6*1013.25*(1/305.15 - 1/1250) = 1.95e-4 -> ~5 mm one way
    expect = 4 * math.pi / rp.LAMBDA_M * rp.N_DRY * rp.P_HPA * (1 / 1250.0 - 1 / F.T_AMBIENT_K) * 10.0
    assert ph["reflector"] == pytest.approx(expect, rel=0.12)
    # flickering phase: scale the static slab phase per frame (seeded) -> detector sees an effect at the reflector
    rng = np.random.default_rng(3)
    t = np.arange(9, dtype=float)
    phases = [{"bins": ph["bins"] * g, "reflector": ph["reflector"] * g} for g in rng.uniform(0.6, 1.4, t.size)]
    run = rp.run_detector(t, phases, sc, near_edge_slant_m=math.hypot(10.0, 2.5), seed=1)
    assert run.state.status in ("FLAME_EFFECT", "NO_EFFECT", "UNKNOWN")
    assert run.state.status == "FLAME_EFFECT"
    assert run.oracle_z.shape == (sc.n_bins,)
    # a static field (no flicker) must not produce an effect
    calm = rp.run_detector(t, [ph] * t.size, sc, near_edge_slant_m=math.hypot(10.0, 2.5), seed=1)
    assert calm.state.status != "FLAME_EFFECT"


def test_attenuation_estimates_orders():
    assert rp.soot_loss_db_per_m(3e-7) < 0.01
    lo = rp.plasma_loss_db_per_m(1e15, 1e11)
    hi = rp.plasma_loss_db_per_m(1e17, 1e11)
    assert 0 < lo < hi and hi / lo == pytest.approx(100.0, rel=1e-6)


def test_plate_round_trip_recovers_step():
    t = np.arange(0.0, 60.0, 0.5)
    q = np.where(t >= 10.0, 8.0, 0.0)
    res = pt.simulate_plate(t, q, air_c=32.0, spec=PlateSpec(), seed=5)
    at = pt.recovered_at(res, 40.0, half_s=5.0)
    assert at["n"] > 50
    assert at["q_recovered_kw_m2"] == pytest.approx(8.0, abs=0.4)
    assert np.isfinite(res.plate_true_c).all() and res.plate_true_c.max() > 40.0


def test_depth_estimates_on_synthetic_track(slab):
    ob = pl.observe(slab, 30.0)
    # a front advancing at 1.3 m/s seen from a parked vehicle (synthetic track, not FDS)
    track = [(ti, 20.0 + 1.3 * ti) for ti in np.arange(0.0, 9.0)]
    ests = pl.estimates(track, ob, near_edge_slant_m=math.hypot(10.0, 2.5), far_echo_slant_m=math.hypot(25.0, 1.5),
                        flicker_z=np.zeros(600))
    assert ests["a_spread_burn"].valid
    assert ests["a_spread_burn"].value_m == pytest.approx(1.3 * pl.C064_GRASS.residence_s, rel=1e-6)
    assert ests["c_radar_ceiling"].valid and not ests["e_radar_loss_depth"].valid
    combs = pl.combine_variants(ests)
    row = pl.depth_row(combs["default(a+b)"], 10.0)
    assert row["valid"] and math.isfinite(row["depth_m"]) and row["lo_m"] < row["depth_m"] < row["hi_m"]


def test_ceiling_uses_the_apps_horizontal_conversion():
    """PHYS-7: the virtual ceiling is formed as crossing/pipeline.py forms it (horizontal distances, far echo assumed
    at ground level), not as a difference of slant ranges."""
    h = pl.CAMERA_HEIGHT_M
    near_slant, far_slant = math.hypot(10.0, h), math.hypot(25.0, h - 1.0)    # reflector at z = 1.0 m
    c = pl.ceiling_like_app(near_slant, far_slant, 0.0488)
    far_h_app = math.sqrt(far_slant ** 2 - h ** 2)                             # crossing/pipeline.py far_h
    assert c.valid and c.value_m == pytest.approx(far_h_app - 10.0, rel=1e-9)
    assert abs(c.value_m - (far_slant - near_slant)) > 0.1                     # the slant difference differs
    assert c.value_m < 15.0                                                    # elevated echo: app ceiling a bit low
    assert pl.slant_to_horizontal(h * 0.9) is None and pl.slant_to_horizontal(None) is None
    ob_ests = pl.estimates([(0.0, 0.0)], _ob_stub(),
                           near_edge_slant_m=near_slant, far_echo_slant_m=far_slant)
    assert ob_ests["c_radar_ceiling"].value_m == pytest.approx(c.value_m, rel=1e-12)


def _ob_stub():
    class _O:
        flame_height = None
    return _O()


def test_soot_band_numbers_in_the_lwir_docstring():
    """PHYS-9: C_SOOT * f_v / lambda at the band centres."""
    assert 7.0 / 11e-6 == pytest.approx(6.4e5, rel=0.01) and 7.0 / 9e-6 == pytest.approx(7.8e5, rel=0.01)
    assert "6.4e5 f_v in" in lwir.__doc__ and "7.8e5 f_v in the 8-10 um band" in lwir.__doc__


def test_real_c064_one_frame_if_present():
    fd = F.FireData(os.environ.get("C064_FIRE_DATA", str(F.DEFAULT_FIRE_DATA)))
    if not fd.available:
        pytest.skip("C064 npz files not present (out-of-repo data)")
    k = int(np.argmin(np.abs(fd.dt5_times() - 60.0)))
    f = fd.dt5_field(k)
    m = f.metrics(20.0)
    assert m is not None and 5.0 < m["depth"] < 20.0
    ob = pl.observe(f, m["le"] + 10.0)
    s = ob.summary()
    assert s["valid_frame"] and s["flame_pixels"] > 0
    assert s["near_edge_m"] is not None and 5.0 < s["near_edge_m"] < 30.0


def test_scene_from_default_cfg_reads_bins_spacing_and_range():
    """The main radar case reads the bins from config/iwr6843aop_vu.cfg (128 x 0.468 m, echoes to 54 m), not the old
    512 x 0.0488 m / 22.5 m defaults; echoes beyond the IF-limited range are absent; clutter scales with bin length."""
    g = rp.cfg_geometry(rp.DEFAULT_CFG)
    assert g["n_bins"] == 128
    assert g["range_res_m"] == pytest.approx(0.4684, abs=1e-3)
    assert g["max_range_m"] == pytest.approx(53.96, abs=0.05)
    assert g["lambda_m"] == pytest.approx(rp.C_LIGHT / 60.275e9, rel=1e-9)
    sc = rp.Scene.from_cfg(g, x_r=30.0, x_ref=5.0)
    assert sc.n_bins == 128 and sc.ranges[-1] == pytest.approx(127 * g["range_res_m"])
    assert sc.clutter_g0_db == pytest.approx(25.0 + 10 * math.log10(g["range_res_m"] / rp.CLUTTER_REF_RES_M))
    assert rp.Scene.from_cfg(g, x_r=30.0, scale_clutter=False).clutter_g0_db == pytest.approx(25.0)
    snr = sc.snr_db()
    assert np.all(np.isneginf(snr[sc.ranges > g["max_range_m"]])) and np.isfinite(snr[sc.ranges < 50.0][-1])
    assert sc.reflector_bin == int(round(sc.reflector_range / g["range_res_m"]))
    far = rp.Scene.from_cfg(g, x_r=60.0, x_ref=0.0)            # reflector at ~60 m: beyond the 54 m IF limit
    assert far.reflector_bin is None
    short = rp.cfg_geometry(rp.SHORT_CFG)
    assert short["n_bins"] == 512 and short["max_range_m"] == pytest.approx(22.48, abs=0.05)
    old = rp.Scene(x_r=30.0)                                   # no config: earlier defaults kept for the synthetic tests
    assert old.range_res_m == pytest.approx(0.0488) and old.lambda_m == pytest.approx(rp.LAMBDA_M)
