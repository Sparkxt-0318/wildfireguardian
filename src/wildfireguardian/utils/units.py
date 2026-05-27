"""Unit-conversion constants used across the project.

Rothermel's 1972 paper, Albini 1976, and Andrews 2018 all work in US
customary units (feet, pounds, Btu, minutes, miles per hour). The Korean
operational context speaks SI exclusively. We compute internally in
Rothermel's original units (to match published reference values exactly)
and convert at the public boundary.

Keep this table small and accurate. Anything ambiguous belongs in the
calling site's docstring, not here.
"""

from __future__ import annotations

# ---------- Length ----------
FT_PER_M: float = 3.280839895013123          # 1 m = 3.2808... ft
M_PER_FT: float = 0.3048                      # 1 ft = 0.3048 m (exact)

# ---------- Speed ----------
# Rothermel's wind is given in feet per minute at midflame height. We accept
# m/s at the public API boundary.
FTMIN_PER_MS: float = 196.8503937007874       # 1 m/s = 196.85 ft/min
MS_PER_FTMIN: float = 1.0 / FTMIN_PER_MS      # 1 ft/min = 0.00508 m/s
MPH_PER_MS: float = 2.2369362920544025        # 1 m/s = 2.2369 mph

# ---------- Mass / area / load ----------
# Fuel load is given in lb/ft² in Rothermel and kg/m² in Korean fuel maps.
KGM2_PER_LBFT2: float = 4.882427636383       # 1 lb/ft² ≈ 4.882 kg/m²
LBFT2_PER_KGM2: float = 1.0 / KGM2_PER_LBFT2

# ---------- SAV ----------
# Surface area to volume ratio: Rothermel uses 1/ft, modern lab work uses
# 1/cm. 1 1/ft = (1/0.3048) 1/m = 3.281 1/m = 0.03281 1/cm.
PER_FT_TO_PER_CM: float = 0.03280839895013123

# ---------- Heat ----------
# Heat content: Rothermel uses Btu/lb (typical wildland fuel ≈ 8000 Btu/lb).
KJKG_PER_BTULB: float = 2.326                # 1 Btu/lb = 2.326 kJ/kg

__all__ = [
    "FT_PER_M",
    "M_PER_FT",
    "FTMIN_PER_MS",
    "MS_PER_FTMIN",
    "MPH_PER_MS",
    "KGM2_PER_LBFT2",
    "LBFT2_PER_KGM2",
    "PER_FT_TO_PER_CM",
    "KJKG_PER_BTULB",
]
