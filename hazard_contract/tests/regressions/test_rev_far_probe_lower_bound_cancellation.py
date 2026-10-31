# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""Peak/dose LOWER bounds exceed the truth for far cells: KERNEL_MARGIN (1e-9) does not cover the
catastrophic cancellation of the inclusion-exclusion arctan formula in solid_angle_rects.

For a cell tens of km from a probe, the four arctan terms are ~pi/2 each and their combination
loses ~8 digits, so the "exact" Omega used for flux_lower is off by up to ~1e-7 relative, far more
than the 1e-9 deflation the module docstring says makes inversion impossible.

Configuration (default near_radius_m): a straight ~134 km path P0 -> P0 + (L, L) and one burning
cell centred at P0 + (L, 0). The cell centre lies on the path's perpendicular bisector and the
square is symmetric about it, so the true flux along the path peaks exactly at the midpoint,
which is one of the lower-bound probes.
Truth: Omega by composite Gauss-Legendre quadrature (sum of positive terms, no cancellation;
accurate to ~1e-15 relative for a smooth kernel 67 km away).
"""
from datetime import datetime, timezone

import numpy as np

import hazard_contract as hc

INF = np.inf
T = 3970.4642815249267
HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
            emission_height_m=5.0, receiver_height_m=0.0, burn_duration_s=T)
XG, WG = np.polynomial.legendre.leggauss(24)
N, M = 270, 252


def omega_gl(px, py, x0, x1, y0, y1, h, split=4):
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


def scenario():
    ig = np.full((1, N, N), INF)
    ig[0, N - 1, M] = -100.0                          # burning throughout the query
    ex = np.where(np.isfinite(ig), ig + T, ig)
    meta = hc.ScenarioMeta(
        crs_epsg=3310, transform=(375.0, 0.0, 0.0, 0.0, -375.0, N * 375.0), height=N, width=N, K=1,
        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=3600.0, source="synthetic",
        synthetic=True, model_version="review", weather_source="SYNTHETIC", heat_source=hc.HeatSource(**HEAT))
    return hc.ScenarioSet(ig, ex, np.ones(ig.shape, bool), meta)


def test_moving_flux_lower_exceeds_true_peak():
    s = scenario()
    q = s.meta.heat_source.emission_kw_m2(T)
    x0, x1, y0, y1 = 375.0 * M, 375.0 * (M + 1), 0.0, 375.0
    P0, L = np.array([187.5, 187.5]), 375.0 * M
    g = np.array([P0, P0 + [L, L]])
    hz = s.member(0).segment(g, 0.0, 60.0)          # default near_radius_m = 5 km
    mid = g.mean(axis=0)
    true_peak = q * omega_gl(mid[0], mid[1], x0, x1, y0, y1, 5.0) / (4 * np.pi)
    for d in (-1.0, 1.0, -100.0, 100.0):             # the midpoint is the true peak along the path
        p = mid + d * np.array([1.0, 1.0])
        assert q * omega_gl(p[0], p[1], x0, x1, y0, y1, 5.0) / (4 * np.pi) <= true_peak
    assert hz.flux_lower <= true_peak, f"flux_lower {hz.flux_lower!r} > true peak {true_peak!r}"


def test_stationary_flux_and_dose_lower_exceed_truth():
    s = scenario()
    q = s.meta.heat_source.emission_kw_m2(T)
    x0, x1, y0, y1 = 375.0 * M, 375.0 * (M + 1), 0.0, 375.0
    p = np.array([187.5 + 375.0 * M / 2, 187.5 + 375.0 * M / 2])
    hz = s.member(0).segment(p, 0.0, 60.0, near_radius_m=100_000.0)
    truth = q * omega_gl(p[0], p[1], x0, x1, y0, y1, 5.0) / (4 * np.pi)
    assert hz.flux_lower <= truth, f"flux_lower {hz.flux_lower!r} > true flux {truth!r}"
    assert hz.dose_lower <= 60.0 * truth, f"dose_lower {hz.dose_lower!r} > true dose {60.0 * truth!r}"
