# Regression test from the independent hazard_contract v1 review (2026-10-31): it failed before the fix.
"""The flux law (sheet_solid_angle_v1) works in metres: emission_height_m is in metres and cell
sizes / distances come from the transform in CRS units. ScenarioMeta (and so every adapter and
ScenarioSet.read) accepts ANY crs_epsg and any non-zero pixel size, including a geographic CRS in
degrees. The router's validator refuses exactly this ("arbitrary/custom geographic CRS cannot pass
as metres", wfg_latest/router_validation/validation.py:132-140); the contract does not.

Here from_drawn_zones builds a set on an EPSG:4326 grid of 0.0034 deg cells (~300 m x 375 m at
37 N). A vehicle parked at the centre of a burning cell gets flux_upper ~5e-6 kW/m^2 and
dose_upper ~0.003 kJ/m^2 over 10 min, with supported=True, while the sheet law on the physical
cell gives ~0.66 kW/m^2 (~400 kJ/m^2). Refusing the CRS would be honest; silently computing
metre physics on degrees is not.
"""
import math

import numpy as np
import pytest

import hazard_contract as hc

DEG = 0.0034
X0, Y0 = 129.0, 37.0


def test_geographic_grid_is_refused_or_bounds_stay_physical():
    zone = np.array([[X0 + 4 * DEG, Y0 - 6 * DEG], [X0 + 6 * DEG, Y0 - 6 * DEG],
                     [X0 + 6 * DEG, Y0 - 4 * DEG], [X0 + 4 * DEG, Y0 - 4 * DEG]])
    try:
        s = hc.from_drawn_zones(zone, 0.1, transform=(DEG, 0.0, X0, 0.0, -DEG, Y0), height=10, width=10,
                                crs_epsg=4326, issue_time_utc="2025-03-25T00:00:00Z", horizon_s=3600.0,
                                burn_duration_s=3970.0)
    except (ValueError, hc.ContractError):
        return                                     # refusing a non-metre CRS is the honest outcome
    c = s.grid.cell_centers(np.array([5]), np.array([5]))[0]
    assert s.ignite_s[0, 5, 5] == -np.inf          # the cell burns on [-inf, 3970)
    hz = s.member(0).segment(c, 0.0, 600.0)
    assert hz.supported and hz.contact is True
    h = s.meta.heat_source
    a = DEG * 111320.0 * math.cos(math.radians(Y0)) / 2.0   # half-widths of the physical cell (m)
    b = DEG * 110574.0 / 2.0
    g = h.height_gap_m
    omega = 4.0 * math.atan(a * b / (g * math.sqrt(a * a + b * b + g * g)))
    physical = h.emission_kw_m2(h.burn_duration_s) * omega / (4.0 * math.pi)
    assert hz.flux_upper >= physical, f"flux_upper {hz.flux_upper:.3g} kW/m^2 vs physical {physical:.3g} kW/m^2"
    assert hz.dose_upper >= physical * 600.0, f"dose_upper {hz.dose_upper:.3g} vs physical {physical * 600:.3g} kJ/m^2"
