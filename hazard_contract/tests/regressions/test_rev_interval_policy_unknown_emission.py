# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""Interval burn-duration policy: unknown cells are bounded with an emission they need not respect.

Under burn_duration_policy="interval", a cell's emission is C / (extinguish_s - ignite_s), so a
short burn emits more. An unknown (nan, unsupported) cell may hold ANY times, yet _Index sets
q_unknown = max(q_scalar, q_max over known cells) and the global cap uses the same number. A
completion in which the unknown neighbour burns for 100 s instead of the 3970 s fallback is
consistent with the data. It gives ~19x the reported flux_upper on a query that reports
supported=True, contact=False ("treat unknown as burning" is not honoured).
Truth: sheet law with Omega from composite Gauss-Legendre quadrature over the cell.
"""
from datetime import datetime, timezone

import numpy as np

import hazard_contract as hc

INF, NAN = np.inf, np.nan
T = 3970.4642815249267
HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
            emission_height_m=5.0, receiver_height_m=0.0, burn_duration_s=T, burn_duration_policy="interval")
XG, WG = np.polynomial.legendre.leggauss(24)


def omega_gl(px, py, x0, x1, y0, y1, h, split=8):
    tot = 0.0
    xs, ys = np.linspace(x0, x1, split + 1), np.linspace(y0, y1, split + 1)
    for i in range(split):
        X = 0.5 * (xs[i + 1] - xs[i]) * XG + 0.5 * (xs[i] + xs[i + 1])
        for j in range(split):
            Y = 0.5 * (ys[j + 1] - ys[j]) * XG + 0.5 * (ys[j] + ys[j + 1])
            XX, YY = np.meshgrid(X, Y, indexing="ij")
            k = h / ((XX - px) ** 2 + (YY - py) ** 2 + h * h) ** 1.5
            tot += np.sum(np.outer(WG, WG) * k) * 0.25 * (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return tot


def make(ig, ex, sup):
    meta = hc.ScenarioMeta(
        crs_epsg=3310, transform=(375.0, 0.0, 0.0, 0.0, -375.0, 1125.0), height=3, width=3, K=1,
        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=3600.0, source="synthetic",
        synthetic=True, model_version="review", weather_source="SYNTHETIC", heat_source=hc.HeatSource(**HEAT))
    return hc.ScenarioSet(np.asarray(ig, float)[None], np.asarray(ex, float)[None], np.asarray(sup, bool)[None], meta)


def test_unknown_neighbour_with_short_burn_exceeds_flux_upper():
    ig = np.full((3, 3), INF)
    ig[1, 2] = NAN                                    # unknown east neighbour
    ex = ig.copy()
    ig[0, 0], ex[0, 0] = 0.0, T                       # one known burning cell (normal duration) far corner
    s = make(ig, ex, ~np.isnan(ig))
    rx, ry = 562.5, 562.5                             # centre of cell (1, 1)
    hz = s.member(0).segment(np.array([rx, ry]), 0.0, 60.0)
    assert hz.supported is True and hz.contact is False
    # consistent completion: the unknown cell burns on [0, 100) (a 100 s burn)
    C = s.meta.heat_source.emission_kw_m2(1.0)       # emission for a 1 s burn = C
    true_flux = (C / 100.0) * omega_gl(rx, ry, 750.0, 1125.0, 375.0, 750.0, 5.0) / (4 * np.pi) \
        + (C / T) * omega_gl(rx, ry, 0.0, 375.0, 750.0, 1125.0, 5.0) / (4 * np.pi)
    assert hz.flux_upper >= true_flux, f"flux_upper {hz.flux_upper} < {true_flux} for a consistent completion"
    assert hz.dose_upper >= 60.0 * true_flux


def test_cap_uses_fallback_emission_for_touched_unknown_cell():
    ig = np.full((3, 3), INF)
    ig[1, 1] = NAN                                    # receiver stands in an unknown cell
    s = make(ig, ig.copy(), ~np.isnan(ig))
    hz = s.member(0).segment(np.array([562.5, 562.5]), 0.0, 10.0)
    assert hz.supported is False                      # touched unknown cell: unresolved, fine...
    C = s.meta.heat_source.emission_kw_m2(1.0)
    true_flux = (C / 30.0) * omega_gl(562.5, 562.5, 375.0, 750.0, 375.0, 750.0, 5.0) / (4 * np.pi)  # 30 s burn
    # ...but the reported upper bound is still finite and is not an upper bound
    assert hz.flux_upper >= true_flux, f"flux_upper {hz.flux_upper} < {true_flux}"
