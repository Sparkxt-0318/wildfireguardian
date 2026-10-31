# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""Polygon holes (interior rings) are filled by rasterize_polygons ("holes are not subtracted -
conservative"). That is conservative for ONE burned-area mask, but both time-dependent adapters
turn "burned earlier" into "extinguished earlier" (extinguish = ignite + burn_duration), so a filled
hole makes the cell read as SAFE later, while the hole's real fire arrives:

* from_perimeters(mode="envelope"), documented as "the union of every possible burning interval":
  a cell inside a hole of the t=0 perimeter (unburned at t=0) and inside the t=1800 perimeter
  ignites in (0, 1800] and may burn until 1800 + 900 = 2700. The envelope gives it [-inf, 900), so a
  stationary query at t=1000 reports contact=False, supported=True.
* from_drawn_zones: a zone with an unburned island. The island cell (4,4) lies 200 m from the hole
  edge; at 1 m/s it ignites at t=200 and burns [200, 800). The adapter gives it [-inf, 600), so at
  t=700 the query reports contact=False, supported=True and flux_upper=0 while the cell is burning.
"""
import math

import numpy as np

import hazard_contract as hc

GRID = dict(transform=(100.0, 0.0, 0.0, 0.0, -100.0, 1000.0), height=10, width=10, crs_epsg=3310,
            issue_time_utc="2021-08-18T00:00:00Z")


def _center(s, r, c):
    return s.grid.cell_centers(np.array([r]), np.array([c]))[0]


def test_perimeter_envelope_hole_cell_reads_safe_while_it_may_burn():
    ext = np.array([[100.0, 100.0], [900.0, 100.0], [900.0, 900.0], [100.0, 900.0]])
    hole = np.array([[300.0, 300.0], [700.0, 300.0], [700.0, 700.0], [300.0, 700.0]])
    # t=0: burned annulus with an unburned island; t=1800: the island has burned too
    series = [(0.0, [ext, hole]), (1800.0, ext)]
    env = hc.from_perimeters(series, 900.0, K=1, mode="envelope", **GRID)
    # cell (4,4) spans x 400..500, y 500..600: strictly inside the hole, untouched by any ring
    # => first burned in (0, 1800] => the union of its possible burning intervals is (0, 2700)
    hz = env.member(0).segment(_center(env, 4, 4), 1000.0, 1000.0)
    assert not (hz.contact is False and hz.supported), (
        f"hole cell reads as safe at t=1000: {hz}; arrays ig={env.ignite_s[0, 4, 4]}, "
        f"ex={env.extinguish_s[0, 4, 4]}; envelope must cover [0, 2700)")
    assert env.extinguish_s[0, 4, 4] >= 1800.0 + 900.0


def test_drawn_zone_island_cell_reads_safe_while_burning():
    v, D = 1.0, 600.0
    ext = np.array([[0.0, 0.0], [1000.0, 0.0], [1000.0, 1000.0], [0.0, 1000.0]])
    island = np.array([[200.0, 200.0], [800.0, 200.0], [800.0, 800.0], [200.0, 800.0]])
    z = hc.from_drawn_zones([[ext, island]], v, horizon_s=3600.0, burn_duration_s=D, **GRID)
    # cell (4,4): x 400..500, y 500..600 -> 200 m from the island edge (x=200 and y=800)
    d_true = 200.0
    t = 700.0                                   # true burning interval [200, 800) contains t
    assert d_true / v <= t < d_true / v + D
    hz = z.member(0).segment(_center(z, 4, 4), t, t)
    # independent sheet-law flux at the centre of a burning 100 m cell, h = 5 m (closed form)
    h = z.meta.heat_source
    a = 50.0
    omega = 4.0 * math.atan(a * a / (h.height_gap_m * math.sqrt(2 * a * a + h.height_gap_m ** 2)))
    true_flux_min = h.emission_kw_m2(h.burn_duration_s) * omega / (4 * math.pi)
    assert not (hz.contact is False and hz.supported), (
        f"island cell burning on [200, 800) reads as safe at t=700: {hz}; "
        f"arrays ig={z.ignite_s[0, 4, 4]}, ex={z.extinguish_s[0, 4, 4]}")
    assert hz.flux_upper >= true_flux_min, (hz.flux_upper, true_flux_min)
