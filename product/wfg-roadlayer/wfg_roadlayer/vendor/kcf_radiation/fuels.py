"""Fuel parameters by land-cover class, low / middle / high (PROTOCOL.md section 4.2; METHOD.md section 3).

The only per-cell vegetation information is the Copernicus Global Land Cover 2019 class (100 m, mode-resampled to
375 m) and canopy height. Each class is mapped to one fuel group; each group carries a low, middle and high value
for every parameter, from the published sources cited in METHOD.md table 3. "High" is the hazardous end
(more fuel, lower canopy base, denser canopy).

Parameter names:
  surface_kg_m2  fuel consumed in the flaming front (Byram's w), kg/m2
  cfl_kg_m2      canopy fuel load available to a crown fire, kg/m2 (None: no canopy)
  cbh_m          canopy base height, m
  cbd_kg_m3      canopy bulk density, kg/m3
  fmc_pct        foliar moisture content, %
"""
from __future__ import annotations

import numpy as np

LEVELS = ("low", "middle", "high")

# Filled from METHOD.md table 3 (values and sources frozen in PROTOCOL.md section 4.2).
GROUPS: dict = {}

# Copernicus LC100 discrete classes -> fuel group
LC_TO_GROUP = {
    111: "conifer", 113: "conifer", 121: "conifer", 123: "conifer",      # evergreen / deciduous needle-leaf
    112: "broadleaf", 114: "broadleaf", 122: "broadleaf", 124: "broadleaf",
    115: "mixed", 116: "mixed", 125: "mixed", 126: "mixed",              # mixed and unknown forest
    20: "shrub",
    30: "grass", 40: "grass", 60: "grass", 90: "grass", 100: "grass",   # herbaceous, cropland, sparse, wetland, moss
    50: "grass", 70: "grass", 80: "grass", 200: "grass", 0: "grass",    # built-up, snow, water, sea, unknown
}
# A cell the arrival raster marks as burned burns; a non-vegetated class in it is read as grass (the lightest
# fuel), not as unburnable (PROTOCOL.md 4.2).


def group_of(lc_code) -> str:
    try:
        return LC_TO_GROUP.get(int(lc_code), "grass")
    except (TypeError, ValueError):
        return "grass"


def params(group: str, level: str) -> dict:
    g = GROUPS[group]
    return {k: (v[LEVELS.index(level)] if isinstance(v, tuple) else v) for k, v in g.items()}
