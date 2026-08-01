"""WildfireGuardian — wildfire spread forecasting and household-level evacuation
and rescue routing.

Top-level package. Importing this module is intentionally cheap: subpackages
that depend on optional heavy dependencies (geopandas, rasterio, osmnx) are
loaded lazily on first attribute access.

See the project README for status, motivation, and references.
"""

from __future__ import annotations

__version__ = "0.1.0a1"

__all__ = [
    "__version__",
]
