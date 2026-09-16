"""Coordinate reference system helpers and the geographic-CRS guard (T1.5e).

CONVENTION FOR THIS PROGRAM
------------------------------
- **EPSG:5186** (Korea 2000 / Central Belt 2010, a projected, metre-unit CRS)
  is the ANALYSIS CRS. Any distance, area, buffer, slope-run or routing-cost
  computation happens in this CRS.
- **EPSG:4326** (WGS84, geographic, degree-unit) is the EXCHANGE CRS ONLY:
  what addresses, APIs (FIRMS, VWorld, KMA) and most public datasets hand
  back. It is never used for a distance or area computation in this program,
  because a degree of longitude is not a constant physical distance (it
  shrinks with latitude), so "distance" in degrees is not a distance at all.

Every function that computes a length or an area in this module first checks
its CRS with :func:`assert_projected_crs` and refuses (raises
``ValueError``) if the CRS is geographic. This guard exists so a
geometry accidentally left in EPSG:4326 fails loudly at the computation site
instead of silently producing a number that LOOKS like metres or hectares
but is not.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pyproj

if TYPE_CHECKING:  # pragma: no cover - typing only
    import geopandas as gpd
    from shapely.geometry.base import BaseGeometry

#: The program's analysis CRS: Korea 2000 / Central Belt 2010, projected,
#: units of metres. Never geographic.
ANALYSIS_CRS = "EPSG:5186"

#: The program's exchange CRS: WGS84, geographic, units of decimal degrees.
#: Used only for input/output with addresses, APIs and most public data;
#: never for a distance or an area computation (see module docstring).
EXCHANGE_CRS = "EPSG:4326"


def assert_projected_crs(crs) -> pyproj.CRS:
    """Refuse a geographic CRS. Raises ``ValueError`` if ``crs`` is geographic.

    Parameters
    ----------
    crs:
        Anything ``pyproj.CRS(...)`` accepts: an EPSG string
        (``"EPSG:5186"``), an int (``5186``), a WKT string, or an existing
        ``pyproj.CRS``/``geopandas`` ``.crs`` object.

    Returns
    -------
    pyproj.CRS
        The parsed CRS, on success, so a caller can chain
        ``crs = assert_projected_crs(gdf.crs)`` and reuse it.

    Raises
    ------
    ValueError
        If ``crs`` is ``None`` (no CRS set at all, which is equally unsafe to
        compute a distance or area against) or is a geographic CRS (degree
        units, e.g. EPSG:4326).
    """
    if crs is None:
        raise ValueError(
            "refusing to compute a distance or area: no CRS is set at all "
            f"(expected a projected CRS, e.g. {ANALYSIS_CRS})"
        )
    parsed = pyproj.CRS(crs)
    if parsed.is_geographic:
        raise ValueError(
            f"refusing to compute a distance or area on geographic CRS "
            f"{parsed.to_string()!r}: reproject to the analysis CRS "
            f"({ANALYSIS_CRS}) first (see research/shared/geo/crs.py "
            f"module docstring for the exchange-vs-analysis convention)"
        )
    return parsed


def transform_point(
    lon: float, lat: float, src: str = EXCHANGE_CRS, dst: str = ANALYSIS_CRS
) -> tuple[float, float]:
    """Transform one ``(lon, lat)`` point between two CRSs.

    Coordinate order is ``(lon, lat)`` in and ``(x, y)`` out, matching the
    ``always_xy=True`` convention (longitude/easting first), which is the
    convention every other function in this module and this program uses;
    the opposite of the ``(lat, lon)`` order used elsewhere in this program's
    plain-tuple APIs (e.g. ``research/shared/geo/geocode.py``); callers
    crossing between the two must not swap them by accident.

    Parameters
    ----------
    lon, lat:
        Source coordinate, in ``src``'s units (degrees for EPSG:4326).
    src, dst:
        CRS strings ``pyproj.CRS`` accepts. Defaults transform
        exchange -> analysis (EPSG:4326 -> EPSG:5186).

    Returns
    -------
    (x, y):
        The transformed coordinate, in ``dst``'s units (metres for
        EPSG:5186).
    """
    transformer = pyproj.Transformer.from_crs(src, dst, always_xy=True)
    x, y = transformer.transform(lon, lat)
    return float(x), float(y)


def to_analysis_crs(gdf: "gpd.GeoDataFrame") -> "gpd.GeoDataFrame":
    """Reproject a GeoDataFrame to the analysis CRS (:data:`ANALYSIS_CRS`).

    Raises ``ValueError`` (via ``geopandas``) if ``gdf.crs`` is unset; a
    GeoDataFrame with no known source CRS cannot be reprojected safely.
    """
    if gdf.crs is None:
        raise ValueError(
            "cannot reproject to the analysis CRS: gdf.crs is unset. Set "
            "the correct source CRS explicitly first (do not guess)."
        )
    return gdf.to_crs(ANALYSIS_CRS)


def to_exchange_crs(gdf: "gpd.GeoDataFrame") -> "gpd.GeoDataFrame":
    """Reproject a GeoDataFrame to the exchange CRS (:data:`EXCHANGE_CRS`).

    For output/exchange only (addresses, APIs, human-facing maps); never
    used to prepare geometry for a distance or area computation.
    """
    if gdf.crs is None:
        raise ValueError(
            "cannot reproject to the exchange CRS: gdf.crs is unset. Set "
            "the correct source CRS explicitly first (do not guess)."
        )
    return gdf.to_crs(EXCHANGE_CRS)


def safe_length_m(geom: "BaseGeometry", crs) -> float:
    """``geom.length`` in metres, after :func:`assert_projected_crs` passes.

    ``geom`` must already be expressed in ``crs`` (this function does not
    reproject; it only guards the units the caller claims to be in).
    """
    assert_projected_crs(crs)
    return float(geom.length)


def safe_area_m2(geom: "BaseGeometry", crs) -> float:
    """``geom.area`` in square metres, after :func:`assert_projected_crs` passes.

    ``geom`` must already be expressed in ``crs`` (this function does not
    reproject; it only guards the units the caller claims to be in).
    """
    assert_projected_crs(crs)
    return float(geom.area)
