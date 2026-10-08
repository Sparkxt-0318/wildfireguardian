"""Detection preprocessing: spatial and temporal selection, analysis coordinates, and the 375 m cell summary.

Inputs are tables with columns lon, lat (degrees), time (UTC datetime) and sensor. Perimeters are shapely
geometries in a projected CRS (EPSG:5070 for the United States, EPSG:5179 for Korea).
"""
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer

CELL_KM = 0.375
GEOSTATIONARY_BUFFER_M = 2000.0


def select(table, perimeter, crs, start, end, buffer_m=0.0):
    """Rows acquired within [start, end] (both ends included) whose location lies strictly inside the perimeter
    (VIIRS: buffer_m = 0) or inside the perimeter expanded by buffer_m (geostationary pixels: 2,000 m).
    Fully identical rows are removed first."""
    table = table.drop_duplicates()
    t = table[(table["time"] >= start) & (table["time"] <= end)]
    x, y = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform(t["lon"].values, t["lat"].values)
    area = perimeter.buffer(buffer_m) if buffer_m else perimeter
    shapely.prepare(area)
    return t[shapely.contains_properly(area, shapely.points(x, y))].reset_index(drop=True)


def us_km(lon, lat):
    """Analysis coordinates of the U.S. events: EPSG:5070 in km."""
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True).transform(np.asarray(lon), np.asarray(lat))
    return np.asarray(x) / 1000.0, np.asarray(y) / 1000.0


def kr_km(lon, lat, lat_centre):
    """Analysis coordinates of the Korean events: x = lon * 111 * cos(lat_centre) km, y = lat * 111 km."""
    return np.asarray(lon) * 111.0 * np.cos(np.radians(lat_centre)), np.asarray(lat) * 111.0


def cell_summary(x_km, y_km, hours, lon, lat):
    """One observation per 375 m cell (cells centred on multiples of 375 m): the time is the median of the detection
    times in the cell; the location is that of the earliest detection (ties: smaller latitude, then longitude)."""
    d = pd.DataFrame({"x": x_km, "y": y_km, "t": hours, "lon": lon, "lat": lat})
    d["cx"], d["cy"] = np.round(d["x"] / CELL_KM), np.round(d["y"] / CELL_KM)
    d = d.sort_values(["t", "lat", "lon"], kind="stable")
    return d.groupby(["cx", "cy"], as_index=False).agg(x=("x", "first"), y=("y", "first"), t=("t", "median"))[["x", "y", "t"]]


def hours_since(time, origin):
    """Elapsed hours from the event time origin (00:00 UTC of the first day of the collection window in the
    United States; the ignition time of the Korea Forest Service situation-map record in Korea)."""
    return (pd.to_datetime(time) - pd.Timestamp(origin)).dt.total_seconds() / 3600.0
