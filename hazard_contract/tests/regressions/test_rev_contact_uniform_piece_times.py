# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""REPRO (contact lens, query_uniform / uniform_pieces time conventions).

uniform_pieces() interpolates every piece time as t_in + (t_out - t_in) * (cum[i] + f * len_i) / total in plain
floating point (cum = sequential cumsum, total = pairwise np.sum) and never pins the last time to t_out or widens
any piece interval outward. query_uniform() then (a) checks the closing instant at pieces[-1][2] instead of
t_out and (b) decides the horizon from the last piece's tb instead of t_out. For multi-vertex polylines the last
piece ends 1 ulp before or after t_out about 60% of the time; interior cell-entry instants drift by a few ulps.

Consequences (contract: closed occupancy [t_in, t_out] meets half-open burning [ig, ex); "instants count";
supported is False iff ... or t_out > horizon_s):
  * a touched cell igniting exactly at t_out under the end point is missed: contact=False, supported=True, and
    flux_upper is below the true peak at t_out;
  * t_out > horizon can be reported supported=True / contact=False;
  * t_out == horizon is reported unsupported (contact None) for a query that is fully within the horizon;
  * an interior cell entered at an exact instant (t = 160 s) is checked from 160.00000000000009 s, missing a cell
    that is burning at 160 s.
"""
from datetime import datetime, timezone
from fractions import Fraction

import numpy as np

from hazard_contract import HeatSource, ScenarioMeta, ScenarioSet

HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
            emission_height_m=5.0, receiver_height_m=0.0)
INF = np.inf


def _set(ig, ex=None, *, cell=100.0, horizon=3600.0, burn=1000.0):
    ig = np.asarray(ig, float)[None]
    ex = np.where(np.isfinite(ig), ig + burn, ig) if ex is None else np.asarray(ex, float)[None]
    _, H, W = ig.shape
    meta = ScenarioMeta(crs_epsg=3310, transform=(cell, 0.0, 0.0, 0.0, -cell, H * cell), height=H, width=W, K=1,
                        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=horizon,
                        source="synthetic", synthetic=True, model_version="repro", weather_source="SYNTHETIC",
                        heat_source=HeatSource(burn_duration_s=burn, **HEAT))
    return ScenarioSet(ig, ex, np.ones(ig.shape, bool), meta)


# Irregular 12- and 17-vertex roads inside row 0 of a 1 x 3 strip of 100 m cells, from cell (0,0) to (0,2).
ROAD_A = np.array([[50.0, 50.0], [53.7, 39.0], [90.7, 28.9], [95.5, 61.9], [115.0, 46.9], [137.3, 67.9],
                   [150.7, 34.1], [185.8, 39.2], [191.5, 68.0], [224.0, 50.4], [224.4, 50.4], [250.0, 50.0]])
ROAD_B = np.array([[50.0, 50.0], [59.8, 78.5], [60.8, 73.9], [96.9, 70.7], [107.2, 43.5], [126.7, 49.6],
                   [131.7, 60.6], [153.1, 23.6], [180.5, 53.3], [211.0, 36.3], [211.6, 72.8], [250.0, 50.0]])
ROAD_C = np.array([[50.0, 50.0], [72.5, 63.8], [86.8, 26.8], [92.6, 74.8], [111.3, 68.1], [132.3, 72.7],
                   [143.2, 51.4], [145.8, 74.9], [168.9, 22.8], [170.8, 21.8], [175.6, 21.2], [177.0, 35.2],
                   [181.9, 34.9], [202.8, 31.3], [218.0, 54.0], [233.1, 22.3], [250.0, 50.0]])


def _sheet_flux(q, px, py, x0, x1, y0, y1, h=5.0):
    """Independent sheet-law flux q * Omega / (4 pi) of one rectangle at height h above (px, py)."""
    def G(u, v):
        return np.arctan(u * v / (h * np.sqrt(u * u + v * v + h * h)))
    u0, u1, v0, v1 = x0 - px, x1 - px, y0 - py, y1 - py
    return q * (G(u1, v1) - G(u0, v1) - G(u1, v0) + G(u0, v0)) / (4 * np.pi)


def test_cell_igniting_at_t_out_under_the_end_point_is_contact():
    s = _set([[INF, INF, 3600.0]], horizon=5000.0)        # end cell ignites exactly when the vehicle arrives
    hz = s.member(0).segment_uniform(ROAD_A, 0.0, 3600.0)
    # the package's own instant query at the end point agrees that this is contact
    assert s.member(0).segment(ROAD_A[-1], 3600.0, 3600.0).contact is True
    assert hz.contact is True, hz                        # actual: contact=False, supported=True


def test_flux_upper_covers_the_peak_at_t_out():
    s = _set([[INF, INF, 3600.0]], horizon=5000.0)
    q = s.meta.heat_source.emission_kw_m2(s.meta.heat_source.burn_duration_s)
    true_peak_at_t_out = _sheet_flux(q, 250.0, 50.0, 200.0, 300.0, 0.0, 100.0)   # ~2.54 kW/m^2
    hz = s.member(0).segment_uniform(ROAD_A, 0.0, 3600.0)
    assert hz.flux_upper >= true_peak_at_t_out, (hz, true_peak_at_t_out)        # actual flux_upper = 0.0


def test_t_out_past_the_horizon_is_never_supported():
    s = _set([[INF, INF, INF]], horizon=3600.0)
    t_out = float(np.nextafter(3600.0, INF))
    assert t_out > s.meta.horizon_s
    hz = s.member(0).segment_uniform(ROAD_C, 0.0, t_out)
    assert hz.supported is False and hz.contact is None, hz    # actual: supported=True, contact=False


def test_t_out_at_the_horizon_is_supported():
    s = _set([[INF, INF, INF]], horizon=3600.0)
    hz = s.member(0).segment_uniform(ROAD_B, 0.0, 3600.0)       # t_out == horizon: fully known, no fire
    assert s.member(0).segment(ROAD_B, 0.0, 3600.0).supported is True
    assert hz.supported is True and hz.contact is False, hz    # actual: supported=False, contact=None


def test_interior_cell_entry_instant_is_exact():
    # 5 x 5 grid of 100 m cells; segments of length 25, 25, 12.5, 12.5 over [0, 300] -> vertex times 0,100,200,250,300.
    g = np.array([[400.0, 462.5], [385.0, 482.5], [410.0, 482.5], [397.5, 482.5], [397.5, 495.0]])
    # Exact uniform motion: on the second segment x = 385 + 25 (t - 100) / 100 reaches x = 400 (cell (0,4)) at t = 160.
    t_enter = Fraction(100) + Fraction(100) * Fraction(15, 25)
    assert t_enter == 160
    ig = np.full((5, 5), INF)
    ex = np.full((5, 5), INF)
    ig[0, 4] = 110.00000000000003
    ex[0, 4] = 160.00000000000003                              # still burning at the exact entry instant 160
    assert Fraction(ig[0, 4]) <= t_enter < Fraction(ex[0, 4])
    s = _set(ig, ex, horizon=5000.0)
    hz = s.member(0).segment_uniform(g, 0.0, 300.0)
    assert hz.contact is True, hz                              # actual: contact=False, supported=True
