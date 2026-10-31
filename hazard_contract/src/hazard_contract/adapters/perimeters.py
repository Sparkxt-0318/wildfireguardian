"""Scenario sets from an observed perimeter progression (time-of-arrival by bracketing)."""
from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from ..geometry import rasterize_polygons
from ..meta import ContractError, HeatSource, ScenarioMeta
from ..scenario import ScenarioSet
from ._common import grid_from, nominal_heat, parse_time, seconds_after

MODES = ("stratified", "rotated", "envelope")


def from_perimeters(perimeter_series: Iterable, burn_duration: float, *, transform, height: int, width: int,
                    crs_epsg: int, issue_time_utc, K: int = 4, mode: str = "stratified",
                    mapped_mask: np.ndarray | None = None, horizon_s: float | None = None,
                    heat: HeatSource | None = None, synthetic: bool = False,
                    model_version: str | None = None) -> ScenarioSet:
    """Build members from perimeters ``[(time, shape), ...]``.

    ``time`` is seconds after issue or a tz-aware datetime/ISO string. ``shape`` is a bool mask
    ``[height, width]`` on this grid or polygon ring(s) in grid CRS (rasterized all-touched, so
    a partly burned cell counts as burned). Perimeters are made cumulative.

    A cell first inside perimeter ``i >= 1`` ignited in ``(t[i-1], t[i]]``:

    * ``stratified``: member k ignites at fraction ``(k + 0.5) / K`` of that gap;
    * ``rotated``: fraction index ``(k + row + col) mod K`` (spatially mixed, like the sealed
      Caldor/Rim construction);
    * ``envelope`` (K = 1): burning from ``t[i-1]`` until ``t[i] + burn_duration`` — the union of
      every possible burning interval, the conservative choice.

    Cells inside the first perimeter burn on ``[-inf, t[0] + burn_duration)``. Cells outside the
    last perimeter never burn within the horizon, which is ``t[-1]`` (nothing is known after it).
    Cells outside ``mapped_mask`` are unsupported (never-mapped is not certified unburned).
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    if mode == "envelope" and K != 1:
        raise ValueError("mode='envelope' produces exactly one member (K=1)")
    if not burn_duration > 0:
        raise ValueError("burn_duration must be > 0")
    issue = parse_time(issue_time_utc)
    grid = grid_from(transform, height, width)
    series = []
    for t, shape in perimeter_series:
        ts = seconds_after(t, issue)
        arr = np.asarray(shape) if isinstance(shape, np.ndarray) else None
        if arr is not None and arr.dtype == bool:
            if arr.shape != (height, width):
                raise ValueError("perimeter mask shape must equal (height, width)")
            mask = arr.copy()
        else:
            mask = rasterize_polygons(grid, shape)
        series.append((ts, mask))
    if not series:
        raise ValueError("need at least one perimeter")
    series.sort(key=lambda p: p[0])
    times = np.array([p[0] for p in series])
    if np.any(np.diff(times) <= 0):
        raise ValueError("perimeter times must be distinct")
    cum = np.logical_or.accumulate(np.stack([p[1] for p in series]), axis=0)
    t_last = float(times[-1])
    if horizon_s is None:
        horizon_s = t_last
    if horizon_s > t_last:
        raise ContractError("horizon_s cannot exceed the last perimeter time: nothing is known after it")
    if not horizon_s > 0:
        raise ContractError("the last perimeter must be after issue time (horizon_s > 0)")

    burned_any = cum[-1]
    first = np.where(burned_any, np.argmax(cum, axis=0), -1)
    ig = np.full((K, height, width), np.inf)
    ex = np.full((K, height, width), np.inf)
    rows, cols = np.mgrid[0:height, 0:width]
    in_first = first == 0
    later = first >= 1
    lo = np.where(later, times[np.maximum(first - 1, 0)], np.nan)
    hi = np.where(later, times[np.maximum(first, 0)], np.nan)
    for k in range(K):
        if mode == "envelope":
            ig_k = lo
            ex_k = hi + burn_duration
        else:
            frac = ((k + 0.5) / K) if mode == "stratified" else (((k + rows + cols) % K) + 0.5) / K
            ig_k = lo + frac * (hi - lo)
            ex_k = ig_k + burn_duration
        ig[k] = np.where(later, ig_k, ig[k])
        ex[k] = np.where(later, ex_k, ex[k])
        ig[k][in_first] = -np.inf
        ex[k][in_first] = times[0] + burn_duration
    # cells igniting after the horizon do not burn within it
    late = ig > horizon_s
    ig[late] = np.inf
    ex[late] = np.inf
    sup = np.ones((K, height, width), dtype=bool)
    if mapped_mask is not None:
        mm = np.asarray(mapped_mask, dtype=bool)
        if mm.shape != (height, width):
            raise ValueError("mapped_mask shape must equal (height, width)")
        sup[:, ~mm] = False
        ig[:, ~mm] = np.nan
        ex[:, ~mm] = np.nan
    meta = ScenarioMeta(
        crs_epsg=crs_epsg, transform=tuple(float(t) for t in transform), height=height, width=width, K=K,
        issue_time_utc=issue, horizon_s=float(horizon_s), source="perimeter", synthetic=bool(synthetic),
        model_version=model_version or f"perimeter-{mode}-v1", weather_source="none (observed perimeters)",
        heat_source=heat or nominal_heat(burn_duration, "nominal heat-source parameters for perimeter timing"),
        provenance={"perimeter_times_s": times.tolist(), "mode": mode},
    )
    return ScenarioSet(ig, ex, sup, meta)
