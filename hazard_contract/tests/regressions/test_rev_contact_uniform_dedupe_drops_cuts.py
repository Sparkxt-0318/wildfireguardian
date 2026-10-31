# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""REPRO (contact lens, uniform_pieces near corners / near grid lines).

uniform_pieces() passes every segment's cut fractions through _dedupe_sorted(f, tol=1e-12), which DROPS any
grid-line crossing within 1e-12 (as a fraction of the segment) of the previous cut. The dropped crossing is
real: the vehicle is inside the cell between the two crossings for a short but non-zero time, and
query_uniform() checks that cell only at a single instant (the kept cut), never over the interval it is
occupied. A cell that ignites inside that interval is missed: contact=False with supported=True, although the
exact closed-cell rule under uniform motion (which segment_uniform claims to implement) says contact=True.
A zero-length piece is harmless to every other part of query_uniform, so nothing needs the tolerance.
"""
from datetime import datetime, timezone
from fractions import Fraction

import numpy as np

from hazard_contract import HeatSource, ScenarioMeta, ScenarioSet

HEAT = dict(fuel_load_kg_m2=10.0, consumed_fraction=0.1, heat_content_kj_kg=18608.0, radiative_fraction=0.3,
            emission_height_m=5.0, receiver_height_m=0.0)
INF = np.inf


def _set(ig, *, cell=100.0, burn=1000.0):
    ig = np.asarray(ig, float)[None]
    ex = np.where(np.isfinite(ig), ig + burn, ig)
    _, H, W = ig.shape
    meta = ScenarioMeta(crs_epsg=3310, transform=(cell, 0.0, 0.0, 0.0, -cell, H * cell), height=H, width=W, K=1,
                        issue_time_utc=datetime(2021, 8, 17, tzinfo=timezone.utc), horizon_s=5000.0,
                        source="synthetic", synthetic=True, model_version="repro", weather_source="SYNTHETIC",
                        heat_source=HeatSource(burn_duration_s=burn, **HEAT))
    return ScenarioSet(ig, ex, np.ones(ig.shape, bool), meta)


def test_diagonal_passing_next_to_a_corner():
    # 3 x 3 grid of 100 m cells. The road passes 3e-11 m from the grid corner (200, 200): it crosses x = 200 at
    # exact fraction 1/2 and y = 200 at 1/2 + 3e-13, so it is inside cell (1, 2) (x in [200, 300], y in [100, 200])
    # during [500, 500 + 3e-10] s of uniform motion over [0, 1000].
    p0, p1 = (150.0, 150.0), (250.0, 250.0 - 6e-11)
    P0 = [Fraction(v) for v in p0]
    P1 = [Fraction(v) for v in p1]
    fx = (200 - P0[0]) / (P1[0] - P0[0])
    fy = (200 - P0[1]) / (P1[1] - P0[1])
    t_enter, t_leave = 1000 * fx, 1000 * fy
    assert t_enter < t_leave                               # the cell really is occupied for a non-zero time
    ig = np.full((3, 3), INF)
    ig[1, 2] = 500.00000000015                             # ignites while the vehicle is inside it
    assert t_enter < Fraction(ig[1, 2]) <= t_leave
    s = _set(ig)
    hz = s.member(0).segment_uniform(np.array([p0, p1]), 0.0, 1000.0)
    assert hz.contact is True, hz                          # actual: contact=False, supported=True


def test_segment_starting_just_before_a_grid_line():
    # 1 x 3 strip of 100 m cells. A 99 m chord starts 5e-11 m left of the line x = 100: it stays in cell (0,0)
    # (closed square x <= 100) during [0, 1000 * 5e-11 / 99] ~ [0, 5.05e-10] s.
    x0 = 100.0 - 5e-11
    g = np.array([[x0, 50.0], [x0 + 99.0, 50.0]])
    t_leave = Fraction(1000) * (Fraction(100) - Fraction(x0)) / (Fraction(g[1, 0]) - Fraction(x0))
    ig = [[2e-10, INF, INF]]                               # cell (0,0) ignites while the vehicle is still in it
    assert 0 < Fraction(2e-10) <= t_leave
    s = _set(ig)
    hz = s.member(0).segment_uniform(g, 0.0, 1000.0)
    assert hz.contact is True, hz                          # actual: contact=False, supported=True
