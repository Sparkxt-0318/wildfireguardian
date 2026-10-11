"""Pixel-center locations in WGS84, without dependence on prediction values.

Affine coefficients use the pixel-corner convention ``(a,b,c,d,e,f)`` and
coordinates returned by this module always use ``(latitude, longitude)`` in
degrees. Unknown predictions still have locations; spatial/time padding does
not. Tensor-like inputs are copied to CPU without importing a tensor library.
"""

from __future__ import annotations

from numbers import Integral
from typing import Any

import numpy as np


def _numpy(value: Any, name: str) -> np.ndarray:
    if value is None:
        raise ValueError(f"{name} is required to locate predictions on Earth")
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    if np.ma.isMaskedArray(value) and np.any(np.ma.getmaskarray(value)):
        raise ValueError(f"{name} must not contain masked values")
    try:
        return np.asarray(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a numeric array") from error


def _epsg_codes(value: Any) -> np.ndarray:
    codes = _numpy(value, "epsg")
    if codes.dtype.kind not in "iu" or np.any(codes <= 0):
        raise ValueError("epsg must contain positive integer EPSG codes, excluding booleans")
    return codes


def _crs(code: int):
    from pyproj import CRS
    from pyproj.exceptions import CRSError

    try:
        return CRS.from_epsg(code)
    except CRSError as error:
        raise ValueError(f"Unsupported EPSG code: {code}") from error


def validate_metric_crs(epsg: Any) -> int:
    """Return one integer EPSG code for a projected CRS in metres.

    The physical heat model works in a metric plane. Geographic coordinates or
    projected coordinates whose horizontal units are feet cannot be used as its
    metric geometry. This validation does not apply to probability-only maps.
    """
    codes = _epsg_codes(epsg)
    if codes.ndim != 0:
        raise ValueError("epsg must be one integer scalar for a metric grid")
    code = int(codes)
    crs = _crs(code)
    if (not crs.is_projected or len(crs.axis_info) < 2
            or any(axis.unit_conversion_factor != 1.0 for axis in crs.axis_info[:2])):
        raise ValueError("heat geometry requires a projected CRS with horizontal units in metres")
    return code


def geographic_coordinates_for_points(receiver_xy_m: Any, *, epsg: Any) -> np.ndarray:
    """Convert ``[...,2]`` source-CRS x/y points to WGS84 latitude/longitude.

    The name reflects use by the metric heat model; conversion itself supports
    any valid source EPSG CRS. Point coordinates must be finite. The result has
    the same shape as the input and uses float64 degrees, with latitude first.
    """
    points = _numpy(receiver_xy_m, "coordinates")
    if points.ndim < 1 or points.shape[-1] != 2 or points.dtype.kind not in "iuf":
        raise ValueError("coordinates must be a real numeric array with final axis (x,y)")
    points = np.asarray(points, dtype=np.float64)
    if not np.isfinite(points).all():
        raise ValueError("coordinates must be finite")
    codes = _epsg_codes(epsg)
    if codes.ndim != 0:
        raise ValueError("epsg must be one integer scalar for point coordinates")
    from pyproj import Transformer
    from pyproj.exceptions import ProjError

    source = _crs(int(codes))
    flat = points.reshape(-1, 2)
    try:
        transformer = Transformer.from_crs(source, _crs(4326), always_xy=True)
        if len(flat) == 1:
            # pyproj's size-one array fast path otherwise relies on NumPy's
            # deprecated implicit conversion from a one-dimensional array.
            longitude, latitude = transformer.transform(float(flat[0, 0]), float(flat[0, 1]),
                                                         errcheck=True)
        else:
            longitude, latitude = transformer.transform(flat[:, 0], flat[:, 1], errcheck=True)
    except ProjError as error:
        raise ValueError("coordinates cannot be transformed to finite WGS84 locations") from error
    result = np.stack((latitude, longitude), axis=-1).astype(np.float64, copy=False).reshape(points.shape)
    if (not np.isfinite(result).all() or np.any(np.abs(result[..., 0]) > 90)
            or np.any(np.abs(result[..., 1]) > 180)):
        raise ValueError("coordinates do not describe valid WGS84 latitude/longitude locations")
    return result


def _prefix_broadcast(array: np.ndarray, leading: tuple[int, ...], name: str,
                      trailing: tuple[int, ...] = ()) -> np.ndarray:
    """Align metadata dimensions from the left, before time/channel dimensions."""
    prefix = array.shape[:-len(trailing)] if trailing else array.shape
    # A sample's [1,H,W] pixel mask also works for a squeezed [H,W] heat map.
    while len(prefix) > len(leading) and prefix[-1] == 1:
        prefix = prefix[:-1]
    if len(prefix) > len(leading) or any(
        size not in (1, leading[index]) for index, size in enumerate(prefix)
    ):
        raise ValueError(f"{name} dimensions must match the prediction's leading dimensions")
    aligned = prefix + (1,) * (len(leading) - len(prefix)) + trailing
    try:
        return np.broadcast_to(array.reshape(aligned), leading + trailing)
    except ValueError as error:
        raise ValueError(f"{name} shape does not match the prediction matrix") from error


def geographic_coordinates(shape, *, affine_transform, epsg, pixel_valid=None,
                           time_valid=None) -> np.ndarray:
    """Return WGS84 pixel centers with shape ``tuple(shape) + (2,)``.

    ``shape`` is a prediction shape, either ``[H,W]`` or ``[...,1,H,W]``.
    The last result axis is ``(latitude,longitude)`` in float64 degrees. Affine
    metadata has shape ``[6]`` or ``[...,6]``; EPSG codes are a scalar or have
    matching metadata prefixes. Prefixes align from the left: metadata ``[B]``
    broadcasts over the time/channel dimensions of prediction ``[B,T,1,H,W]``.
    Thus different batch items can retain different transforms and CRS codes.

    Optional boolean ``pixel_valid`` has trailing ``[H,W]`` (typically
    ``[1,H,W]`` or ``[B,1,H,W]``). Boolean ``time_valid`` has only prefix/time
    dimensions (typically ``[T]`` or ``[B,T]``). False entries give coordinate
    pairs ``(NaN,NaN)``. These masks describe padding, rather than prediction
    availability; no probability/outcome tensor is read by this function.
    """
    try:
        shape = tuple(shape)
    except TypeError as error:
        raise ValueError("shape must contain positive integer dimensions ending in (H,W)") from error
    if (len(shape) < 2 or any(isinstance(size, (bool, np.bool_))
            or not isinstance(size, Integral) or size <= 0 for size in shape)):
        raise ValueError("shape must contain positive integer dimensions ending in (H,W)")
    shape = tuple(int(size) for size in shape)
    leading, spatial = shape[:-2], shape[-2:]
    transform = _numpy(affine_transform, "affine_transform")
    if transform.ndim < 1 or transform.shape[-1] != 6 or transform.dtype.kind not in "iuf":
        raise ValueError("affine_transform must contain six real coefficients (a,b,c,d,e,f)")
    transform = np.asarray(transform, dtype=np.float64)
    if not np.isfinite(transform).all():
        raise ValueError("affine_transform must be finite")
    with np.errstate(over="ignore", invalid="ignore"):
        determinant = transform[..., 0] * transform[..., 4] - transform[..., 1] * transform[..., 3]
    if not np.isfinite(determinant).all() or np.any(determinant == 0):
        raise ValueError("affine_transform must have a finite nonzero cell area")
    transforms = _prefix_broadcast(transform, leading, "affine_transform", (6,))
    codes = _prefix_broadcast(_epsg_codes(epsg), leading, "epsg")
    for code in np.unique(codes):
        _crs(int(code))

    known = np.ones(shape, dtype=np.bool_)
    if pixel_valid is not None:
        pixels = _numpy(pixel_valid, "pixel_valid")
        if pixels.dtype.kind != "b":
            raise ValueError("pixel_valid must contain booleans")
        if pixels.ndim < 2 or pixels.shape[-2:] != spatial:
            raise ValueError("pixel_valid must have the same trailing (H,W) shape as predictions")
        known &= _prefix_broadcast(pixels, leading, "pixel_valid", spatial)
    if time_valid is not None:
        times = _numpy(time_valid, "time_valid")
        if times.dtype.kind != "b":
            raise ValueError("time_valid must contain booleans")
        known &= _prefix_broadcast(times, leading, "time_valid")[..., None, None]

    result = np.full(shape + (2,), np.nan, dtype=np.float64)
    rows, columns = np.indices(spatial, dtype=np.float64)
    rows += 0.5
    columns += 0.5
    # Convert each unique spatial grid once, then align it over times/channels.
    # A union mask avoids transforming extrapolated padding outside the Earth.
    groups: dict[tuple, list[tuple[int, ...]]] = {}
    for index in np.ndindex(leading):
        key = (int(codes[index]), *transforms[index].tolist())
        groups.setdefault(key, []).append(index)
    for key, indices in groups.items():
        union = np.logical_or.reduce([known[index] for index in indices])
        if not union.any():
            continue
        code, a, b, c, d, e, f = key
        x = a * columns[union] + b * rows[union] + c
        y = d * columns[union] + e * rows[union] + f
        converted = geographic_coordinates_for_points(np.stack((x, y), axis=-1), epsg=code)
        centers = np.full(spatial + (2,), np.nan, dtype=np.float64)
        centers[union] = converted
        for index in indices:
            result[index] = np.where(known[index][..., None], centers, np.nan)
    return result
