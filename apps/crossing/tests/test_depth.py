"""depth.py: estimators a-e, combine (DESIGN 6.6), intensity."""
import math
from types import SimpleNamespace

import numpy as np
import pytest

from crossing import depth as dp
from crossing.fuels import get_fuel

GR2 = get_fuel("GR2")


def _track(rate=0.1, n=50, dt=0.2, noise=0.02, seed=1):
    rng = np.random.default_rng(seed)
    t = np.arange(n) * dt
    return np.column_stack([t, 3.0 + rate * t + rng.normal(0, noise, n)])


def test_spread_burn_recovers_rate_and_depth():
    e = dp.spread_burn(_track(), GR2)
    assert e.valid
    assert e.details["spread_m_s"] == pytest.approx(0.1, abs=0.01)
    assert e.value_m == pytest.approx(e.details["spread_m_s"] * GR2.residence_s)
    assert e.lo_m < e.value_m < e.hi_m
    assert e.sigma_log >= GR2.residence_rel_sigma


def test_spread_burn_enu_projection_matches_1d():
    tr = _track()
    u = np.array([0.6, -0.8])                        # unit vector towards the vehicle
    en = np.column_stack([tr[:, 0], 100 + tr[:, 1] * u[0], 50 + tr[:, 1] * u[1]])
    a = dp.spread_burn(tr, GR2)
    b = dp.spread_burn(en, GR2, toward_en=2 * u)     # length does not matter
    assert b.valid and b.value_m == pytest.approx(a.value_m, rel=1e-9)
    assert not dp.spread_burn(en, GR2).valid       # direction required


@pytest.mark.parametrize("kw,why", [
    (dict(n=20), "span"),                            # 3.8 s < 5 s
    (dict(rate=0.01), "rate"),                       # too slow
    (dict(rate=-0.1), "rate"),                       # receding
    (dict(rate=0.05, noise=2.0), "poor fit"),
])
def test_spread_burn_invalid(kw, why):
    e = dp.spread_burn(_track(**kw), GR2)
    assert not e.valid and e.value_m is None, why


def test_spread_burn_rejects_nan_and_garbage():
    tr = _track()
    tr[5, 1] = np.nan
    assert not dp.spread_burn(tr, GR2).valid
    assert not dp.spread_burn("nonsense", GR2).valid
    assert not dp.spread_burn([], GR2).valid


def test_byram():
    e = dp.byram(1.5, GR2)
    i = (1.5 / 0.0775) ** (1 / 0.46)
    assert e.valid and e.details["intensity_kw_m"] == pytest.approx(i)
    assert e.value_m == pytest.approx(i * GR2.residence_s / (GR2.heat_kj_kg * GR2.consumed_load_kg_m2))
    # PHYS-5: sigma = sqrt(model 0.6^2 + residence-time^2 + H*w 0.3^2), the t_r part reported as shared
    assert e.sigma_log == pytest.approx(math.sqrt(0.6 ** 2 + GR2.residence_rel_sigma ** 2 + 0.3 ** 2))
    assert e.details["shared_log_sigma"] == pytest.approx(GR2.residence_rel_sigma)
    for bad in (None, 0.0, -1.0, float("nan"), float("inf"), 500.0, True):
        assert not dp.byram(bad, GR2).valid


def test_radar_ceiling_and_loss_depth():
    c = dp.radar_ceiling(20.0, 26.0)
    assert c.valid and c.kind == "ceiling" and c.value_m == pytest.approx(6.0)
    assert not dp.radar_ceiling(20.0, 19.0).valid
    assert not dp.radar_ceiling(None, 19.0).valid
    assert not dp.radar_loss_depth(6.0, None).valid
    assert not dp.radar_loss_depth(0.0, 2.0).valid
    e = dp.radar_loss_depth(6.0, 2.0)
    assert e.valid and e.value_m == pytest.approx(3.0)


def test_flicker_extent():
    z = np.zeros(300)
    z[200:230] = 6.0                 # 20.0 - 22.9 m
    z[231:235] = 6.0                 # after a 1-bin gap: same run
    z[260:270] = 6.0                 # far away: separate, ignored
    e = dp.flicker_extent(z, near_edge_m=19.5, range_res_m=0.1)
    assert e.valid and e.kind == "experimental"
    assert e.value_m == pytest.approx(23.4 - 19.5 + 0.1)
    assert not dp.flicker_extent(np.zeros(300), 19.5).valid


def _est(name, v, s):
    return dp._lognormal(name, v, s)


def test_combine_inverse_variance_log_mean_and_uncalibrated_scale():
    r = dp.combine([_est("spread_burn", 2.0, 0.3), _est("byram", 8.0, 0.3)])
    assert r.valid and r.depth_m == pytest.approx(4.0)
    sig = 0.3 / math.sqrt(2)
    assert r.sigma_log == pytest.approx(sig)
    assert r.hi_m == pytest.approx(4.0 * math.exp(dp.Z90 * sig * 1.5))
    assert r.lo_m == pytest.approx(4.0 * math.exp(-dp.Z90 * sig * 1.5))
    assert not r.calibrated and r.scale == 1.5 and any("uncalibrated" in f for f in r.flags)
    assert r.level == 0.90
    # unequal weights pull towards the tighter estimate
    r2 = dp.combine([_est("spread_burn", 2.0, 0.2), _est("byram", 8.0, 0.6)])
    assert r2.depth_m < 4.0


def test_combine_calibrated_scale():
    cal = SimpleNamespace(calibrated=True, scale=1.2, n_pairs=20, trust_radar_ceiling=False)
    r = dp.combine([_est("byram", 3.0, 0.4)], cal)
    assert r.calibrated and r.n_pairs == 20 and r.hi_m == pytest.approx(3.0 * math.exp(dp.Z90 * 0.4 * 1.2))


def test_radar_ceiling_never_lowers_upper_end_unless_trusted():
    ests = [_est("byram", 3.0, 0.6), dp.radar_ceiling(20.0, 23.5)]
    untrusted = dp.combine(ests, SimpleNamespace(calibrated=False, scale=1.5, n_pairs=3, trust_radar_ceiling=False))
    alone = dp.combine([ests[0]])
    assert untrusted.hi_m == pytest.approx(alone.hi_m) and untrusted.depth_m == pytest.approx(alone.depth_m)
    assert "radar_ceiling" not in untrusted.used and untrusted.ceiling_m == pytest.approx(3.5)
    trusted = dp.combine(ests, SimpleNamespace(calibrated=True, scale=1.0, n_pairs=12, trust_radar_ceiling=True))
    alone1 = dp.combine([ests[0]], SimpleNamespace(calibrated=True, scale=1.0, n_pairs=12, trust_radar_ceiling=True))
    assert "radar_ceiling" not in trusted.used                       # PHYS-1: never in the mean
    assert trusted.depth_m == pytest.approx(alone1.depth_m) and trusted.lo_m == pytest.approx(alone1.lo_m)
    assert trusted.hi_m == pytest.approx(3.5)                         # only caps the upper end


def test_combine_excludes_experimental_and_invalid():
    r = dp.combine([_est("flicker_extent", 9.0, 0.8), dp.byram(None, GR2)])
    assert not r.valid and r.reason
    # DEPTH-HI rule: an experimental estimator alone, even when enabled, never decides: invalid -> CLOSED
    r2 = dp.combine([_est("flicker_extent", 9.0, 0.8)], enabled=["flicker_extent"])
    assert not r2.valid and "experimental" in r2.reason and r2.hi_decision_m is None
    assert not dp.combine([]).valid


def test_intensity_sources():
    i_h = dp.intensity((1.0, 0.8, 1.3), None, GR2)
    assert i_h.valid and i_h.sources == ["byram_flame_height"]
    assert i_h.lo < i_h.i_kw_m < i_h.hi
    assert i_h.hi == pytest.approx((1.3 / 0.0775) ** (1 / 0.46))
    sp = dp.spread_burn(_track(), GR2)
    i_s = dp.intensity(None, sp, GR2)
    assert i_s.valid and i_s.i_kw_m == pytest.approx(sp.details["spread_m_s"] * GR2.energy_kj_m2)
    both = dp.intensity((1.0, 0.8, 1.3), sp, GR2)
    assert both.hi == pytest.approx(max(i_h.hi, i_s.hi)) and len(both.sources) == 2
    assert not dp.intensity(None, None, GR2).valid
    assert not dp.intensity(float("nan"), dp.byram(None, GR2), GR2).valid


# ------------------------------------------------------------------------------- PHYS-1: ceiling only caps hi
def test_trusted_ceiling_only_caps_hi_never_raises_lo_or_depth():
    """PHYS-1 regression (probe p1): byram 1.31 m (sigma 0.6) + a trusted 12 m ceiling used to give depth 11.8 m,
    lo 10.45 m (in-flame flux 48x lower). Now: depth and lo as without the ceiling, hi = min(hi, ceiling)."""
    b = dp._lognormal("byram", 1.31, 0.6)
    trust = SimpleNamespace(calibrated=False, scale=1.5, n_pairs=9, trust_radar_ceiling=True)
    alone = dp.combine([b], trust)
    assert alone.lo_m == pytest.approx(1.31 * math.exp(-dp.Z90 * 0.6 * 1.5)) and alone.lo_m == pytest.approx(0.30,
                                                                                                         abs=0.01)
    r = dp.combine([b, dp.radar_ceiling(10.0, 22.0)], trust)
    assert r.depth_m == pytest.approx(1.31) and r.lo_m == pytest.approx(alone.lo_m)
    assert r.hi_m == pytest.approx(min(alone.hi_m, 12.0)) and r.hi_m == pytest.approx(5.76, abs=0.02)
    assert "radar_ceiling" not in r.used
    r3 = dp.combine([b, dp.radar_ceiling(10.0, 13.0)], trust)            # 3 m ceiling: caps hi only
    assert r3.hi_m == pytest.approx(3.0) and r3.lo_m == pytest.approx(alone.lo_m)
    assert r3.depth_m == pytest.approx(1.31) and any("capped" in f for f in r3.flags)
    r_low = dp.combine([b, dp.radar_ceiling(10.0, 11.0)], trust)         # ceiling 1.0 < depth: conflict
    assert r_low.hi_m == pytest.approx(alone.hi_m) and any("conflict" in f for f in r_low.flags)
    # even if a caller lists it as enabled
    r_en = dp.combine([b, dp.radar_ceiling(10.0, 22.0)], trust, enabled=["byram", "radar_ceiling"])
    assert r_en.used == ["byram"] and r_en.lo_m == pytest.approx(alone.lo_m)


# ------------------------------------------------------------------------ PHYS-5: shared residence-time error
def test_shared_residence_time_error_is_not_averaged_away():
    """PHYS-5: spread_burn (SE/R 0.05) and byram share the fuel's t_r error (0.30): the combined sigma_log must not
    fall below it (the old independent combination gave 0.271)."""
    tr = GR2.residence_rel_sigma
    a = dp._lognormal("spread_burn", 2.0, math.sqrt(0.05 ** 2 + tr ** 2), shared_log_sigma=tr)
    b = dp.byram(1.5, GR2)
    r = dp.combine([a, b])
    assert r.valid and r.sigma_log >= tr - 1e-12
    assert "GLS" in r.method
    old = 1.0 / math.sqrt(1.0 / a.sigma_log ** 2 + 1.0 / b.sigma_log ** 2)
    assert r.sigma_log > old
    # with real estimators
    sp = dp.spread_burn(_track(noise=0.001), GR2)
    assert sp.valid and sp.details["shared_log_sigma"] == pytest.approx(tr)
    r2 = dp.combine([sp, b])
    assert r2.sigma_log >= tr - 1e-12
    # an estimator without the t_r term (radar_loss_depth) can still narrow below it
    e = dp.radar_loss_depth(6.0, 2.0, sigma_log=0.1)
    r3 = dp.combine([sp, b, e])
    assert r3.valid and r3.sigma_log < tr


# ----------------------------------------------------------------- FS-2 / PHYS-2: unbounded height upper end
@pytest.mark.parametrize("fh,spread", [((5.0, 4.0, float("inf")), None), ((5.0, 4.0, 150.0), None),
                                       ((5.0, 4.0, float("inf")), 0.5), ((5.0, 4.0, float("nan")), None),
                                       ((5.0, 4.0, 4.5), None), ((150.0, 100.0, 160.0), 0.5),
                                       ((float("inf"), 1.0, float("inf")), 0.5), ((2.0, 1.5, float("inf")), None)])
def test_intensity_invalid_when_flame_height_upper_end_unbounded(fh, spread):
    """Probe p1: intensity((5, 4, inf)) gave hi = the central value (8591 kW/m, vs 30832 with h_hi = 9 m). An
    unbounded / out-of-range / inverted upper end, or a bad central height, must make intensity INVALID (CLOSED),
    also when a finite spread-rate source is present."""
    r = dp.intensity(fh, spread, GR2)
    assert not r.valid and r.hi is None


def test_intensity_bad_lower_end_never_raised_to_central():
    r = dp.intensity((5.0, float("nan"), 9.0), None, GR2)
    assert r.valid and r.lo == 0.0 and r.hi == pytest.approx(dp.byram_intensity_from_length(9.0))


def test_combine_reports_decision_upper_end_in_to_dict():
    # DEPTH-HI rule (full tests in test_depth_hi_rule.py): a low narrow estimator does not pull the decision end down
    r = dp.combine([_est("spread_burn", 0.6, 0.2), _est("byram", 1.2, 0.8)])
    d = r.to_dict()
    assert d["hi_decision_m"] == pytest.approx(_est("byram", 1.2, 0.8).hi_m) and d["hi_decision_m"] > d["hi_m"]
    assert d["hi_decision_from"] == "byram" and d["hi_decision_rule"] and d["disagree_ratio"] == pytest.approx(2.0)
    assert dp.combine([]).to_dict()["hi_decision_m"] is None
