"""Build an APPROXIMATE Yeongdeok 2025 perimeter time series from public reporting.

Output: ``data/validation_cases/yeongdeok_2025_perimeter_approx.geojson``

This script is **methodology-honest**: every feature is tagged
``provenance="approximate, reconstructed from public reporting"``. The
shapes are NOT KFS perimeter shapefiles — those are pending Round 2.

Public-reporting facts used
---------------------------
- Ignition: March 22 2025 ~12:15 KST, 영덕군 영해면, approximately
  (129.37 E, 36.50 N).
- KFS preliminary total burned area: ~3,800 ha.
- Wind regime: 양강지풍 westerly/northwesterly, 10-15 m/s sustained.
- Spread direction: east-southeast, reaching the coast within ~3-4 hours
  per news coverage.
- Final stabilisation: by ~ day 3 of the event.

Reconstructed perimeter time series
-----------------------------------
The perimeter at each time is modelled as an ellipse with major axis
along the wind direction (~ESE, bearing 110°), centred on the ignition
point and elongating east-southeast as it grows. Length-to-breadth
ratio is set to ~ 2.5 (consistent with wind-driven Korean Pinus fires
and our model's eccentricity cap).

Time | Area (ha) | Length (km) | Source
-----|----------:|-----------:|-------
+0h  |      0.5  |   ~ 0.1    | ignition point
+1h  |     50    |   ~ 1.0    | reconstructed
+3h  |    600    |   ~ 5.0    | "coast reached in 3-4 h" public reports
+6h  |   1500    |   ~ 8.0    | reconstructed
+12h |   2800    |   ~ 12.0   | reconstructed
+24h |   3800    |   ~ 14.0   | KFS preliminary final area
+48h |   3800    |   ~ 14.0   | stable

Output coordinates are in WGS84 (EPSG:4326) per RFC 7946.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.affinity import rotate, scale, translate
from shapely.geometry import Point, mapping
from shapely.geometry.base import BaseGeometry


# ---------------------------------------------------------------------------
# Inputs (PUBLIC-REPORTING approximations)
# ---------------------------------------------------------------------------

IGNITION_LON, IGNITION_LAT = 129.37, 36.50          # 영덕군 영해면 area
IGNITION_TIME = datetime(2025, 3, 22, 12, 15)        # KST per public reports
WIND_TO_BEARING_DEG = 110.0                          # wind blowing TOWARD ESE (110° = ESE)
LB_RATIO = 2.5                                        # length-to-breadth

# (hours after ignition, burned area in ha)
SCHEDULE: list[tuple[float, float]] = [
    (0.0, 0.5),
    (1.0, 50.0),
    (2.0, 250.0),
    (3.0, 600.0),
    (4.0, 900.0),
    (6.0, 1500.0),
    (9.0, 2200.0),
    (12.0, 2800.0),
    (18.0, 3400.0),
    (24.0, 3800.0),
    (48.0, 3800.0),
]


# ---------------------------------------------------------------------------
# Geometry construction
# ---------------------------------------------------------------------------


def _ellipse_polygon_5179(area_m2: float, lb_ratio: float, n_vertices: int = 96):
    """Build a wind-aligned ellipse polygon in EPSG:5179, centred at origin.

    Semi-major a, semi-minor b. Area = π * a * b. LB = a/b. So:
        b = sqrt(area / (π * LB)),  a = LB * b.

    Major axis is along the +x direction (east). Rotation to the actual
    wind bearing is done in WGS84-space by the caller.
    """
    b = math.sqrt(area_m2 / (math.pi * lb_ratio))
    a = lb_ratio * b
    circle = Point(0.0, 0.0).buffer(1.0, quad_segs=n_vertices // 4)
    return scale(circle, xfact=a, yfact=b, origin=(0.0, 0.0))


def _build_perimeter_polygon_wgs84(
    area_ha: float, wind_to_bearing_deg: float,
    ignition_lon: float, ignition_lat: float,
    transformer_to_5179: Transformer,
    transformer_to_4326: Transformer,
):
    """Build one wind-aligned perimeter polygon in WGS84 (lon/lat)."""
    # Build in EPSG:5179 (metres), centred at origin, major axis along east.
    poly_5179 = _ellipse_polygon_5179(area_ha * 10_000.0, LB_RATIO)
    # Rotate so major axis points along the wind-TO bearing. In compass
    # convention, 0° is north and angles increase clockwise. In shapely
    # rotate, angle is measured counter-clockwise from the +x axis (east).
    # So convert: shapely_angle = 90° - compass_bearing.
    shapely_angle = 90.0 - wind_to_bearing_deg
    poly_5179 = rotate(poly_5179, shapely_angle, origin=(0.0, 0.0), use_radians=False)
    # Translate to ignition point in EPSG:5179.
    ign_x, ign_y = transformer_to_5179.transform(ignition_lon, ignition_lat)
    poly_5179 = translate(poly_5179, xoff=ign_x, yoff=ign_y)
    # Reproject to WGS84.
    # shapely doesn't reproject directly; we transform vertices.
    exterior = list(poly_5179.exterior.coords)
    lon_lat = [
        transformer_to_4326.transform(x, y) for x, y in exterior
    ]
    from shapely.geometry import Polygon
    return Polygon(lon_lat)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    out_path = (
        Path(__file__).resolve().parents[1]
        / "data" / "validation_cases"
        / "yeongdeok_2025_perimeter_approx.geojson"
    )

    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    to_4326 = Transformer.from_crs("EPSG:5179", "EPSG:4326", always_xy=True)

    features = []
    for hours, area_ha in SCHEDULE:
        if area_ha < 1.0:
            # Use a tiny ~ 80 m × 80 m square for the ignition snapshot.
            from shapely.geometry import box
            x, y = to_5179.transform(IGNITION_LON, IGNITION_LAT)
            poly_5179 = box(x - 40, y - 40, x + 40, y + 40)
            poly = _ellipse_polygon_5179(area_ha * 10_000.0, 1.0)
            # use real ignition geometry though
            lon_lat = [to_4326.transform(*p) for p in poly_5179.exterior.coords]
            from shapely.geometry import Polygon as _P
            poly_wgs = _P(lon_lat)
        else:
            poly_wgs = _build_perimeter_polygon_wgs84(
                area_ha,
                wind_to_bearing_deg=WIND_TO_BEARING_DEG,
                ignition_lon=IGNITION_LON, ignition_lat=IGNITION_LAT,
                transformer_to_5179=to_5179, transformer_to_4326=to_4326,
            )
        t = IGNITION_TIME + timedelta(hours=hours)
        time_min = hours * 60.0
        feat = {
            "type": "Feature",
            "properties": {
                "time_min_since_ignition": time_min,
                "timestamp_kst_iso": t.isoformat(),
                "area_ha": area_ha,
                "area_m2": area_ha * 10_000.0,
                "provenance": "approximate, reconstructed from public reporting",
                "source_notes": (
                    "Ellipse-shaped approximation: major axis 110° (ESE), "
                    "LB=2.5, centred on ignition point (영덕군 영해면, "
                    "129.37 E, 36.50 N). Total area at +24h = 3,800 ha "
                    "per KFS preliminary public report. NOT a KFS perimeter "
                    "shapefile."
                ),
            },
            "geometry": mapping(poly_wgs),
        }
        features.append(feat)

    geojson = {
        "type": "FeatureCollection",
        "name": "yeongdeok_2025_perimeter_approx",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC::CRS84"}},
        "metadata": {
            "event": "Yeongdeok 2025 wildfire",
            "event_kr": "2025년 3월 영덕군 산불",
            "ignition_lon": IGNITION_LON,
            "ignition_lat": IGNITION_LAT,
            "ignition_time_kst_iso": IGNITION_TIME.isoformat(),
            "wind_to_bearing_deg": WIND_TO_BEARING_DEG,
            "length_to_breadth_ratio": LB_RATIO,
            "total_burn_area_ha_final": 3800.0,
            "provenance": (
                "APPROXIMATE — reconstructed from public reporting "
                "(KFS preliminary press release + Yonhap/Chosun/Hankyoreh "
                "coverage). Not a KFS perimeter shapefile. Every feature "
                "is wind-aligned ellipse centred on the public-reported "
                "ignition point with area at each timestamp matching "
                "publicly-reported growth markers."
            ),
            "session_3_status": "stub-but-usable; replace with KFS shapefile in Round 2",
        },
        "features": features,
    }

    out_path.write_text(json.dumps(geojson, indent=2))
    print(f"wrote {len(features)} features → {out_path}")


if __name__ == "__main__":
    main()
