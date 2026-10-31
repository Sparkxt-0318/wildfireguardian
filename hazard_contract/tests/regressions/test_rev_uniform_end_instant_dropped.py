# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""segment_uniform / query_uniform never evaluate the instant t_out for many-vertex polylines.

uniform_pieces() normalises arc length by ``total = seg_len.sum()`` (numpy pairwise summation for
>= 8 segments) but builds vertex times from ``cum = np.cumsum(seg_len)`` (sequential summation).
When the two disagree, the last piece ends at ``t_out - 1 ulp``: the closed occupancy interval's
final instant (the vehicle at the end point at t_out) is never checked, neither for contact nor
for the peak-flux bound. A cell at the end point igniting at t_out (e.g. a perimeter time or a
lattice time) is then reported as contact=False, supported=True with flux_upper far below the
true peak.

Truth is computed independently: the sheet law q_rad * Omega / (4 pi) with Omega integrated by
composite Gauss-Legendre quadrature over the burning cell.
"""
from datetime import datetime, timezone

import numpy as np

import hazard_contract as hc
from hazard_contract.scenario import uniform_pieces

INF = np.inf
HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
            emission_height_m=5.0, receiver_height_m=0.0, burn_duration_s=3970.4642815249267)
# 10 vertices (9 segments), integer metres, inside a 10 x 10 grid of 100 m cells
G = np.array([[507, 112], [755, 816], [483, 390], [939, 377], [872, 420], [376, 364], [69, 282],
              [235, 71], [541, 443], [35, 163]], dtype=float)
T_IN, T_OUT = 0.0, 60.0


def scenario(ig_end_cell: float) -> hc.ScenarioSet:
    ig = np.full((1, 10, 10), INF)
    ig[0, 8, 0] = ig_end_cell                      # the cell holding the end point (35, 163)
    ex = np.where(np.isfinite(ig), ig + HEAT["burn_duration_s"], ig)
    meta = hc.ScenarioMeta(
        crs_epsg=3310, transform=(100.0, 0.0, 0.0, 0.0, -100.0, 1000.0), height=10, width=10, K=1,
        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=3600.0, source="synthetic",
        synthetic=True, model_version="review", weather_source="SYNTHETIC", heat_source=hc.HeatSource(**HEAT))
    return hc.ScenarioSet(ig, ex, np.ones(ig.shape, bool), meta)


def omega_gl(px, py, x0, x1, y0, y1, h, n=24, split=8):
    xg, wg = np.polynomial.legendre.leggauss(n)
    tot = 0.0
    xs, ys = np.linspace(x0, x1, split + 1), np.linspace(y0, y1, split + 1)
    for i in range(split):
        for j in range(split):
            X = 0.5 * (xs[i + 1] - xs[i]) * xg + 0.5 * (xs[i] + xs[i + 1])
            Y = 0.5 * (ys[j + 1] - ys[j]) * xg + 0.5 * (ys[j] + ys[j + 1])
            XX, YY = np.meshgrid(X, Y, indexing="ij")
            k = h / ((XX - px) ** 2 + (YY - py) ** 2 + h * h) ** 1.5
            tot += np.sum(np.outer(wg, wg) * k) * 0.25 * (xs[i + 1] - xs[i]) * (ys[j + 1] - ys[j])
    return tot


def test_last_uniform_piece_stops_short_of_t_out():
    s = scenario(INF)
    assert uniform_pieces(s.grid, G, T_IN, T_OUT)[-1][2] == T_OUT, "the occupancy interval ends at t_out"


def test_end_point_ignition_at_t_out_is_missed():
    s = scenario(T_OUT)                             # end cell ignites exactly when the vehicle arrives
    q = s.meta.heat_source.emission_kw_m2(s.meta.heat_source.burn_duration_s)
    end = G[-1]
    # independent truth: at t = t_out the vehicle (uniform motion) is at the end point, inside the burning cell
    true_peak = q * omega_gl(end[0], end[1], 0.0, 100.0, 100.0, 200.0, 5.0) / (4 * np.pi)
    assert true_peak > 0.6
    any_speed = s.member(0).segment(G, T_IN, T_OUT)
    assert any_speed.contact is True                 # the any-speed query sees it
    hz = s.member(0).segment_uniform(G, T_IN, T_OUT)
    assert hz.supported is True
    assert hz.flux_upper >= true_peak and hz.contact is True, \
        f"uniform motion ends inside a cell burning at t_out (true peak {true_peak:.4f} kW/m^2), got {hz}"


# Same root cause, other direction: the last piece ends at t_out + 1 ulp. With t_out == horizon (a
# request whose dwell ends exactly at the hazard's valid_until), the query is reported unsupported
# with infinite flux/dose bounds although nothing after the horizon is occupied.
G2 = np.array([[272, 873], [510, 840], [637, 737], [100, 540], [508, 864], [364, 596], [68, 390],
               [327, 157], [810, 382], [969, 588]], dtype=float)


def test_query_ending_exactly_at_horizon_becomes_unsupported():
    s = scenario(INF)                                # nothing burns; horizon_s = 3600
    assert s.member(0).segment(G2, 0.0, 3600.0).supported is True
    hz = s.member(0).segment_uniform(G2, 0.0, 3600.0)
    assert hz.supported is True and hz.flux_upper < np.inf, f"t_out == horizon, got {hz}"
