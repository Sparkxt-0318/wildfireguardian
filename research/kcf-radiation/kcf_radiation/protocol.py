"""Frozen parameters of PROTOCOL.md (section numbers in comments). Changing anything here is an amendment."""
from __future__ import annotations

from dataclasses import replace

from . import fuels
from .model import Setting

# 3. spread rate limits (m/s)
R_MIN_M_S = 0.001          # 0.06 m/min
R_MAX_M_S = 2.5            # 150 m/min = 9 km/h (above the press-reported 8.2 km/h Gyeongbuk maximum)

# 4.2 fuel groups: (low, middle, high); high = hazardous end. Sources in METHOD.md table 3.
fuels.GROUPS.update({
    "conifer": {"surface_kg_m2": (0.50, 0.76, 1.10), "cbh_m": (5.2, 4.4, 3.6), "cbd_kg_m3": (0.13, 0.20, 0.27),
                "cfl_kg_m2": (1.27, 2.12, 3.08), "fmc_pct": 100.0},
    "mixed": {"surface_kg_m2": (0.50, 0.76, 1.10), "cbh_m": (5.2, 4.4, 3.6), "cbd_kg_m3": (0.065, 0.10, 0.135),
              "cfl_kg_m2": (0.64, 1.06, 1.54), "fmc_pct": 100.0},
    "broadleaf": {"surface_kg_m2": (0.10, 0.54, 0.81), "cbh_m": None, "cbd_kg_m3": None, "cfl_kg_m2": None, "fmc_pct": None},
    "shrub": {"surface_kg_m2": (0.35, 1.17, 1.46), "cbh_m": None, "cbd_kg_m3": None, "cfl_kg_m2": None, "fmc_pct": None},
    "grass": {"surface_kg_m2": (0.09, 0.25, 0.48), "cbh_m": None, "cbd_kg_m3": None, "cfl_kg_m2": None, "fmc_pct": None},
})

# 4.7 thresholds (kW/m2) and baseline setting
THRESHOLDS = (7.0, 4.7, 2.5)
BASELINE = Setting(level="middle", T_flame_K=1200.0, emissivity=1.0, vf_kind="tilted", transmissivity=True,
                   heat_kj_kg=18000.0, front_width_m=375.0, receiver_height_m=1.5, thresholds=THRESHOLDS,
                   tilt_law="baseline")

# 7.3 settings carried through the panels (each changes one thing from the baseline)
SENSITIVITY_SETTINGS = {
    "fuel_low": replace(BASELINE, level="low"),
    "fuel_high": replace(BASELINE, level="high"),
    "T1090": replace(BASELINE, T_flame_K=1090.0),
    "T1400": replace(BASELINE, T_flame_K=1400.0),
    "vf_planar": replace(BASELINE, vf_kind="planar"),
    "vf_max": replace(BASELINE, vf_kind="tilted_max"),
    "vf_cylinder": replace(BASELINE, vf_kind="cylinder"),
    "no_tau": replace(BASELINE, transmissivity=False),
}
