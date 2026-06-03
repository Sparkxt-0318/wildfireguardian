"""WildfireGuardian v2 — data-driven per-cell fire-spread classifier.

A per-cell P(ignites by next overpass) model on a 375 m EPSG:5179 grid,
trained on NASA FIRMS VIIRS overpass sequences with ESA WorldCover fuel,
SRTM/Copernicus terrain, and ECMWF ERA5 weather. Evaluated with
leave-one-fire-out cross-validation. See ``docs/SPREAD_MODEL_REPORT_V2_FINAL.md``.

This is the v2 *re-train* on corrected data (uljin fuel-orientation + ERA5
fix; gangneung_donghae fuel re-fetch). Methodology is unchanged from v2; the
orientation-safe :class:`~wildfireguardian.spread_v2_xgb.grid.RasterSampler` is the
structural guarantee that the prior orientation bug cannot recur.
"""

SEED = 42

__all__ = ["SEED"]
