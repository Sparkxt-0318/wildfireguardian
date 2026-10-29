"""Dose forms, thresholds and provenance."""
import json
import math

import numpy as np
import pytest

import wfg_flamefront as W


def test_tdu_of_constant_flux():
    t = np.linspace(0.0, 60.0, 61)
    q = np.full(t.size, 10.0)
    assert abs(W.dose(q, t, "tdu") - 60.0 * 10.0 ** (4.0 / 3.0)) < 1e-9
    assert abs(W.dose(q, t, "linear") - 600.0) < 1e-12


def test_linear_dose_matches_frozen_integrate_heat_flux():
    heat = pytest.importorskip("wfg_latest.radiation.heat")
    rng = np.random.default_rng(3)
    t = np.cumsum(rng.uniform(0.1, 3.0, 200))
    q = rng.uniform(0, 40, 200)
    ours = W.dose(q, t, "linear")                                  # kJ/m2
    frozen = float(heat.integrate_heat_flux(q * 1000.0, t)) / 1000.0   # J/m2 -> kJ/m2
    assert abs(ours - frozen) <= 1e-12 * max(1.0, abs(frozen))


def test_bands_and_probit():
    assert W.as3959_band(5.0) == "BAL-12.5"
    assert W.as3959_band(12.5) == "BAL-12.5"
    assert W.as3959_band(12.6) == "BAL-19"
    assert W.as3959_band(39.0) == "BAL-40"
    assert W.as3959_band(41.0) == "BAL-FZ"
    p = W.probit_lethality(2000.0)
    assert abs(p["probit"] - (-14.9 + 2.56 * math.log(2000.0))) < 1e-12
    assert 0.3 < p["probability"] < 0.7          # about 50 % lethality near 2000 TDU
    a_w = W.constants.EISENBERG_PROBIT["a_w"]
    assert abs((-14.9 - a_w) - 23.58) < 0.01     # the W/m2 shift


def test_provenance_complete_and_json():
    p = W.provenance()
    assert p["law_version"] == "wfg.radiation.law/2-flamefront"
    json.dumps(p, allow_nan=False)
    for k in ("HEAT_CONTENT_KJ_KG", "BYRAM_FLAME_LENGTH_COEFF", "EMISSIVE_POWER_SURFACE_KW_M2", "MAX_SPREAD_RATE_M_S",
              "POINT_RESIDENCE_S", "CUTOFF_RADIUS_M", "TDU_THRESHOLDS", "EISENBERG_PROBIT"):
        assert k in p["constants"]
    for k in ("byram_flame_length", "view_factor", "tdu", "probit", "as3959", "emissive_power", "flame_tilt"):
        assert "verification" in p["sources"][k]


def test_byram_examples_and_tilt():
    L = W.byram_flame_length_m([1000.0, 5000.0, 20000.0])
    assert np.allclose(L, [1.86, 3.90, 7.37], atol=0.01)
    assert W.tilt_angle_rad(2.0, 0.0) == 0.0
    th = W.tilt_angle_rad(2.0, 5.0)
    assert abs(math.tan(th) - 1.4 * 5.0 / math.sqrt(9.80665 * 2.0)) < 1e-12


def test_deterministic():
    from conftest import synthetic_member
    m, tr = synthetic_member()
    g = W.Grid(tr, *m["ignition_time_s"].shape)
    pts = np.array([[g.centre_x(5) + 13.0, g.centre_y(6) - 7.0], [g.centre_x(9), g.centre_y(3)]])
    q1 = W.flux_at_points(pts, [100.0, 900.0, 2000.0], m, g, None)
    q2 = W.flux_at_points(pts, [100.0, 900.0, 2000.0], m, g, None)
    assert np.array_equal(q1, q2)


def test_importable_with_numpy_only():
    import subprocess, sys
    from pathlib import Path
    src = Path(W.__file__).resolve().parents[1]
    code = ("import sys; sys.modules['scipy'] = None; sys.modules['matplotlib'] = None; sys.modules['torch'] = None; "
            "sys.path.insert(0, %r); import wfg_flamefront as W; print(W.LAW_VERSION)" % str(src))
    out = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
    assert out.returncode == 0 and "2-flamefront" in out.stdout, out.stderr
