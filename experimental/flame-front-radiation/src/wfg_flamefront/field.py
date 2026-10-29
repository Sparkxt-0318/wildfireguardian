"""Grid geometry and the arrival-time field built from one v1/v2 scenario member.

Geometry. ``Grid`` is a north-up or south-up axis-aligned affine grid in metres, ``x = a*(col) + c`` and
``y = e*(row) + f`` at pixel corners (the rasterio/GDAL convention also used by ``wfg_latest``). Rotated or sheared
grids are refused. Cell centres sit at ``col + 0.5, row + 0.5``. The dual grid has its nodes at the cell centres; dual
square ``(r, c)`` has corners at the centres of cells ``(r, c), (r, c+1), (r+1, c), (r+1, c+1)``. Inside a dual square
the four quadrants split at the midlines belong to the four corner cells (their "host" cells).

Arrival field. A member supplies ``ignition_time_s[H, W]`` (seconds since the cutoff; ``inf`` never within the horizon,
``nan`` unknown) plus present-fire activity. ``FrontField`` turns it into a finite arrival-time value at every cell centre
with the conventions recorded in ``provenance.ASSUMPTIONS``:

* new ignition ``b``: arrival ``b``;
* present fire (active at the cutoff): ``R_max - T`` under the bridge's scalar maximum-remaining enclosure, ``0`` for a
  present cell of unknown age (the bridge activates it on ``[0, T)``), or ``r - T`` per cell when per-cell remaining times
  are supplied and ``present_fire="per_cell"``;
* known burned and no longer active: ``-T``;
* never ignited within the horizon: ``never_arrival_s`` (default ``horizon + T``);
* unknown cumulative state without a drawn ignition, or ``nan``: unknown, excluded and counted.

Activity. v1 activity per breakpoint interval is either read from the member's ``flame`` frames and ``breakpoints``
(exact v1 member arrays) or rebuilt from ignition, ``T``, present-fire mask and ``R_max`` exactly as the bridge does.
"""
from __future__ import annotations

import bisect
import math
from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np

from . import provenance as PV


class LawError(ValueError):
    pass


@dataclass(frozen=True)
class Grid:
    transform: tuple
    height: int
    width: int

    def __post_init__(self):
        a, b, c, d, e, f = (float(v) for v in self.transform)
        if b != 0.0 or d != 0.0:
            raise LawError("only axis-aligned grids are supported (b = d = 0)")
        if a == 0.0 or e == 0.0 or not all(math.isfinite(v) for v in (a, c, e, f)):
            raise LawError("degenerate grid transform")
        object.__setattr__(self, "transform", (a, b, c, d, e, f))
        object.__setattr__(self, "height", int(self.height))
        object.__setattr__(self, "width", int(self.width))

    @classmethod
    def coerce(cls, grid, shape=None):
        if isinstance(grid, Grid):
            return grid
        if isinstance(grid, Mapping) and "resolution" in grid:
            # routing graph grid: south-up rows starting at y0; native arrays are north-up
            res = float(grid["resolution"]); H = int(grid["height"]); W = int(grid["width"])
            return cls((res, 0.0, float(grid["x0"]), 0.0, -res, float(grid["y0"]) + H * res), H, W)
        t = getattr(grid, "transform", grid)
        if shape is None:
            raise LawError("array shape required with a bare affine transform")
        return cls(tuple(float(v) for v in t), int(shape[0]), int(shape[1]))

    @property
    def a(self):
        return self.transform[0]

    @property
    def e(self):
        return self.transform[4]

    @property
    def dx(self):
        return abs(self.transform[0])

    @property
    def dy(self):
        return abs(self.transform[4])

    def centre_x(self, col):
        return self.transform[2] + self.transform[0] * (np.asarray(col, dtype=float) + 0.5)

    def centre_y(self, row):
        return self.transform[5] + self.transform[4] * (np.asarray(row, dtype=float) + 0.5)

    def to_index(self, x, y):
        """Continuous index coordinates (u, v): centre of cell (r, c) at (u, v) = (c, r)."""
        u = (np.asarray(x, dtype=float) - self.transform[2]) / self.transform[0] - 0.5
        v = (np.asarray(y, dtype=float) - self.transform[5]) / self.transform[4] - 0.5
        return u, v

    def to_xy(self, u, v):
        return self.centre_x(u), self.centre_y(v)

    def cell_of(self, x, y):
        """Host cell (row, col) of a point (floor rule); may be outside the grid."""
        u, v = self.to_index(x, y)
        return np.floor(v + 0.5).astype(np.int64), np.floor(u + 0.5).astype(np.int64)


@dataclass
class FrontField:
    tau: np.ndarray                    # [H, W] arrival seconds at cell centres, nan = unknown/excluded
    unknown: np.ndarray                # [H, W] bool
    breakpoints: np.ndarray            # [K+1]
    frames: np.ndarray                 # [K, H, W] bool activity per interval [bp_k, bp_k+1)
    grid: Grid
    horizon_s: float
    duration_s: float
    conventions: dict = field(default_factory=dict)
    _sq: Any = None

    @property
    def shape(self):
        return self.tau.shape

    def frame_index(self, t):
        bp = self.breakpoints
        k = bisect.bisect_right(bp, float(t)) - 1
        return min(max(k, 0), len(bp) - 2)

    def active_at(self, t):
        return self.frames[self.frame_index(t)]

    def active_anywhere(self, a, b):
        """Cells active at some time in the closed interval [a, b] (frames are half-open)."""
        bp = self.breakpoints
        k0 = self.frame_index(a)
        k1 = self.frame_index(b)
        if b > bp[-1]:
            k1 = len(bp) - 2
        return self.frames[k0:k1 + 1].any(axis=0)

    def active_throughout(self, a, b):
        k0 = self.frame_index(a)
        k1 = self.frame_index(b)
        return self.frames[k0:k1 + 1].all(axis=0)

    def unsupported_cells(self):
        return int(self.unknown.sum())

    def squares(self):
        """Corner arrays of every dual square: c00, c01, c10, c11 [H-1, W-1] and validity."""
        if self._sq is None:
            t = self.tau
            c00, c01, c10, c11 = t[:-1, :-1], t[:-1, 1:], t[1:, :-1], t[1:, 1:]
            ok = np.isfinite(c00) & np.isfinite(c01) & np.isfinite(c10) & np.isfinite(c11)
            self._sq = (c00, c01, c10, c11, ok)
        return self._sq


def _get(member, key, default=None):
    if isinstance(member, Mapping):
        return member.get(key, default)
    return getattr(member, key, default)


def prepare(member, grid=None, *, horizon_s=None, duration_s=None, never_arrival_s=None, present_fire="enclosure"):
    """Build a ``FrontField`` from a member mapping (or return it unchanged if it already is one).

    Recognised member keys: ``ignition_time_s`` (required, [H, W]); ``current_active`` ([H, W] bool, present fire);
    ``remaining_s`` (scalar R_max); ``present_remaining_s`` ([H, W], per-cell remaining, nan = unknown age);
    ``unknown_age`` ([H, W] bool); ``known_burned`` ([H, W] bool); ``unknown_state`` ([H, W] bool);
    ``burning_duration_s`` (T); ``horizon_s``; ``breakpoints`` and ``flame`` (v1 activity frames).
    """
    if isinstance(member, FrontField):
        return member
    ign = np.array(_get(member, "ignition_time_s"), dtype=float)
    if ign.ndim != 2:
        raise LawError("ignition_time_s must be [H, W]")
    H, W = ign.shape
    g = Grid.coerce(grid if grid is not None else _get(member, "grid"), (H, W))
    if (g.height, g.width) != (H, W):
        raise LawError("grid shape %s differs from member shape %s" % ((g.height, g.width), (H, W)))
    T = float(duration_s if duration_s is not None else _get(member, "burning_duration_s", PV.COARSE_CELL_DURATION_S))
    hz = float(horizon_s if horizon_s is not None else _get(member, "horizon_s", PV.HORIZON_S))
    never = float(never_arrival_s) if never_arrival_s is not None else hz + T
    cur = _get(member, "current_active")
    cur = np.zeros((H, W), bool) if cur is None else np.array(cur, dtype=bool)
    R = _get(member, "remaining_s")
    R = 0.0 if R is None else float(R)
    unknown_age = _get(member, "unknown_age")
    unknown_age = np.zeros((H, W), bool) if unknown_age is None else np.array(unknown_age, dtype=bool) & cur
    known_burned = _get(member, "known_burned")
    known_burned = cur.copy() if known_burned is None else (np.array(known_burned, dtype=bool) | cur)
    unknown_state = _get(member, "unknown_state")
    unknown_state = np.zeros((H, W), bool) if unknown_state is None else np.array(unknown_state, dtype=bool)
    finite = np.isfinite(ign)
    tau = np.full((H, W), never)
    tau[finite] = ign[finite]
    if present_fire == "per_cell" and _get(member, "present_remaining_s") is not None:
        r = np.array(_get(member, "present_remaining_s"), dtype=float)
        exact = cur & np.isfinite(r) & ~unknown_age
        tau[exact] = r[exact] - T
        tau[cur & ~exact] = 0.0
    elif present_fire in ("enclosure", "per_cell"):
        tau[cur] = R - T
        tau[unknown_age] = 0.0
    else:
        raise LawError("present_fire must be 'enclosure' or 'per_cell'")
    burned_out = known_burned & ~cur & ~finite
    tau[burned_out] = -T
    unknown = (np.isnan(ign) | (unknown_state & ~finite & ~cur))
    tau[unknown] = np.nan
    # activity frames
    bp = _get(member, "breakpoints")
    fl = _get(member, "flame")
    if bp is not None and fl is not None:
        bp = np.array(bp, dtype=float)
        frames = np.array(fl, dtype=bool)
        if frames.ndim == 2:
            frames = frames.reshape(len(bp) - 1, H, W)
    else:
        ext = np.where(finite, ign + T, np.inf)
        knots = {0.0, hz}
        knots.update(float(v) for v in ign[finite] if 0.0 < v < hz)
        knots.update(float(v) for v in ext[finite] if 0.0 < v < hz)
        if cur.any() and 0.0 < R < hz:
            knots.add(R)
        bp = np.array(sorted(knots))
        frames = []
        for left in bp[:-1]:
            act = finite & (ign <= left) & (left < ext)
            if cur.any() and left < R:
                act = act | cur
            frames.append(act)
        frames = np.array(frames, dtype=bool)
    return FrontField(tau=tau, unknown=unknown, breakpoints=bp, frames=frames, grid=g, horizon_s=hz, duration_s=T,
                      conventions={"never_arrival_s": never, "present_fire": present_fire,
                                   "present_fire_arrival_s": (R - T) if cur.any() else None,
                                   "burned_out_arrival_s": -T, "unsupported_cells": int(unknown.sum())})


def load_packet_members(packet_dir, *, present_fire="enclosure", never_arrival_s=None):
    """Read the v1 member arrays of a frozen packet (constructed_arrays.npz + REPORT.json).

    Returns (members, grid, info): one mapping per scenario member, ready for ``prepare``.
    """
    import json
    from pathlib import Path
    packet_dir = Path(packet_dir)
    report = json.loads((packet_dir / "REPORT.json").read_text())
    meta = report["native_metadata"]
    asm = meta["construction"]["assumptions"]
    with np.load(packet_dir / "constructed_arrays.npz", allow_pickle=False) as a:
        arrays = {k: a[k].copy() for k in a.files}
    H, W = arrays["current_active"].shape
    grid = Grid(tuple(float(v) for v in meta["affine_transform"]), H, W)
    ids = list(report["rows"][0]["request"]["incurred"])
    members = []
    for k in range(arrays["ignition_time_s"].shape[0]):
        members.append({
            "id": ids[k] if k < len(ids) else str(k),
            "ignition_time_s": arrays["ignition_time_s"][k],
            "current_active": arrays["current_active"],
            "remaining_s": float(asm["initial_remaining_s"]),
            "present_remaining_s": arrays["mask__initial_remaining_s_native"],
            "unknown_age": arrays["mask__present_fire_unknown_age_enclosed"],
            "known_burned": arrays["mask__known_burned"],
            "unknown_state": arrays["mask__unknown_cumulative_state"],
            "burning_duration_s": float(asm["burning_duration_s"]),
            "horizon_s": float(asm["horizon_s"]),
        })
    info = {"assumptions": asm, "shape": (H, W), "member_ids": ids}
    return members, grid, info
