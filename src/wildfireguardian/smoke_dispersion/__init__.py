"""Atmospheric smoke dispersion.

Session 3 adds a Gaussian-plume (Pasquill-Gifford) ground-level PM2.5
concentration model — an ARCHITECTURE DEMONSTRATION, not validated
science. A production smoke product would couple to HYSPLIT or a CMAQ
Eulerian solver.

See :mod:`.gaussian_plume`.
"""

from __future__ import annotations

from .gaussian_plume import (
    PlumeConfig,
    StabilityClass,
    estimate_pm25_emission_rate_ug_s,
    gaussian_plume_concentration,
    plume_grid,
    sigma_y_briggs,
    sigma_z_briggs,
)

__all__ = [
    "StabilityClass",
    "PlumeConfig",
    "sigma_y_briggs",
    "sigma_z_briggs",
    "estimate_pm25_emission_rate_ug_s",
    "gaussian_plume_concentration",
    "plume_grid",
]
