"""Truth sources of the synthetic-truth harness (Contract E, extended by orchestrator decision with device_offline).

A truth is a single member in the same construction law as the forecast members (scalar coarse-cell duration T,
present fire on [0, R) shared with the forecast cutoff state, first-new ignitions at exact seconds), so the same checker
scores it. Sources:

  holdout_trajectory     one Monte Carlo trajectory of the export v3 rollout that is withheld from the forecast members;
                         ignition seconds by the same sub-hour rule ("uniform"). A model world, not a real fire.
  reconstructed_arrival  the kriged time-of-arrival raster of the historical fire (Zenodo 10.5281/zenodo.21788344, the
                         raster the forecast was built from; hash checked against the export record): a cell with
                         cutoff < TOA <= cutoff + 1 h ignites at second 3600 (TOA - cutoff_h). Present fire is the export
                         cutoff state, which equals TOA <= cutoff (checked). A reconstruction, not observed flames.
  device_offline         sparse interval-valued observations (schema wfg.truth.device-offline/1, see the README): per
                         graph cell, observed burning and observed not-burning half-open intervals; every other
                         (cell, time) is unknown and is excluded from scoring (it can neither cause nor clear a flag).
  observed_perimeters    NIROPS unions exist only for U.S. fires outside this panel: not available here.
  external_simulator     FARSITE/ELMFIRE runs: see the README for the installation attempt and its outcome.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fractions import Fraction as F
from pathlib import Path

import numpy as np

from . import toa as TOA

SOURCES = ("holdout_trajectory", "reconstructed_arrival", "observed_perimeters", "external_simulator", "device_offline")
DEVICE_SCHEMA = "wfg.truth.device-offline/1"


@dataclass
class Truth:
    source: str
    label: str
    births: dict                       # graph cell -> Fraction ignition second (first-new burns within the horizon)
    current: list                      # graph cells of present fire
    R: F
    T: F
    meta: dict = field(default_factory=dict)
    burning: dict = None               # device_offline: graph cell -> [(lo, hi)] observed burning [lo, hi)
    not_burning: dict = None           # device_offline: graph cell -> [(lo, hi)] observed not burning [lo, hi)
    horizon: float = 3600.0

    @property
    def observed(self):
        return self.burning is not None

    def cell_intervals(self, unknown_as_burning=False):
        """Exact activity intervals for a planner. For device_offline: observed burning intervals, plus the unknown
        (cell, time) set when unknown_as_burning (the pessimistic clairvoyant that certifies routes from observations)."""
        out = {}
        if not self.observed:
            for c, b in self.births.items():
                out.setdefault(c, []).append((F(b), F(b) + self.T))
            if self.R > 0:
                for c in self.current:
                    out.setdefault(c, []).append((F(0), self.R))
            return {k: sorted(set(v)) for k, v in out.items()}
        for c, ivs in self.burning.items():
            out.setdefault(c, []).extend((F(a), F(b)) for a, b in ivs)
        if unknown_as_burning:
            for c, ivs in self.unknown_intervals().items():
                out.setdefault(c, []).extend(ivs)
        return {k: sorted(set(v)) for k, v in out.items()}

    def unknown_intervals(self, cells=None):
        """Per cell, the unknown half-open intervals within [0, horizon + 1) (cells never mentioned are wholly unknown
        only when `cells` lists them; the harness asks for the cells a journey or the graph touches)."""
        H = F(self.horizon) + 1
        known = {}
        for d in (self.burning or {}), (self.not_burning or {}):
            for c, ivs in d.items():
                known.setdefault(c, []).extend((F(a), F(b)) for a, b in ivs)
        cells = set(known) | set(cells or ())
        out = {}
        for c in cells:
            cur, gaps = F(0), []
            for a, b in sorted(known.get(c, [])):
                if a > cur:
                    gaps.append((cur, min(a, H)))
                cur = max(cur, b)
            if cur < H:
                gaps.append((cur, H))
            if gaps:
                out[c] = gaps
        return out


class _Intervals:
    """Duck-typed contact model for planners: only `cell_intervals` is read."""

    def __init__(self, cell_intervals):
        self.cell_intervals = cell_intervals


def planning_model(truth, unknown_as_burning=True, cells=None):
    if truth.observed and unknown_as_burning:
        iv = truth.cell_intervals(unknown_as_burning=False)
        for c, gaps in truth.unknown_intervals(cells).items():
            iv.setdefault(c, []).extend(gaps)
        return _Intervals({k: sorted(set(v)) for k, v in iv.items()})
    return _Intervals(truth.cell_intervals())


# ------------------------------------------------------------------------------------------------ builders
def native_to_graph(index, shape):
    H, W = shape
    r, c = divmod(int(index), W)
    return (H - 1 - r) * W + c


def from_native_events(events_native, current_graph, R, T, shape, source, label, meta=None):
    flat = np.asarray(events_native, dtype=float).ravel()
    idx = np.flatnonzero(np.isfinite(flat))
    births = {native_to_graph(i, shape): F(float(flat[i])) for i in idx}
    return Truth(source=source, label=label, births=births, current=list(current_graph), R=F(R), T=F(T), meta=meta or {})


def holdout_trajectory(fbh_window_events, index, current_graph, R, T, shape, *, meta=None):
    """fbh_window_events: [N,h,w] ignition seconds (inf: none) of all trajectories on the window."""
    return from_native_events(fbh_window_events[index], current_graph, R, T, shape, "holdout_trajectory",
                              "trajectory_%d" % index, dict(meta or {}, trajectory_index=int(index)))


def reconstructed_arrival(toa_path, *, t0_utc, cutoff_utc, window, export, expected_sha256, current_graph, R, T, shape,
                          horizon_s=3600.0):
    """Truth from the reconstructed arrival raster; checks its hash and the identity of the cutoff state."""
    digest = hashlib.sha256(Path(toa_path).read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise ValueError("TOA_RASTER_HASH_MISMATCH")
    arr, transform, meta = TOA.read(toa_path)
    if [float(v) for v in transform] != [float(v) for v in export["affine_transform"]]:
        raise ValueError("TOA_GRID_DIFFERS_FROM_EXPORT")
    t0 = datetime.fromisoformat(t0_utc.replace("Z", "+00:00"))
    cut = datetime.fromisoformat(cutoff_utc.replace("Z", "+00:00"))
    c_h = (cut - t0).total_seconds() / 3600.0
    known = np.isfinite(arr)
    burned = known & (arr <= c_h)
    exp_burned = export["source_burned_area_valid"] & (np.nan_to_num(export["source_burned_area"]) == 1)
    if not (np.array_equal(burned, exp_burned) and np.array_equal(known, export["source_burned_area_valid"])):
        raise ValueError("CUTOFF_STATE_DIFFERS_FROM_RECONSTRUCTION")
    sec = (arr - c_h) * 3600.0
    new = known & (sec > 0) & (sec < horizon_s)
    events = np.where(new, sec, np.inf)
    if window is not None:
        events = events[window["r0"]:window["r1"] + 1, window["c0"]:window["c1"] + 1]
    return from_native_events(events, current_graph, R, T, shape, "reconstructed_arrival", "toa_%s" % cutoff_utc,
                              {"toa_sha256": digest, "t0_utc": t0_utc, "cutoff_hours_since_t0": c_h,
                               "raster_t0_tag": meta.get("t0_utc"), "new_ignitions": int(np.isfinite(events).sum())})


def device_offline(packet, *, T=None, R=0, current_graph=()):
    """Load a device_offline truth packet (dict or path)."""
    if not isinstance(packet, dict):
        packet = json.loads(Path(packet).read_text())
    if packet.get("schema") != DEVICE_SCHEMA:
        raise ValueError("device_offline schema %s required" % DEVICE_SCHEMA)
    burning, not_burning = {}, {}
    for row in packet["observations"]:
        c = int(row["cell"])
        for a, b in row.get("burning", []):
            if not F(a) < F(b):
                raise ValueError("empty or reversed interval")
            burning.setdefault(c, []).append((F(a), F(b)))
        for a, b in row.get("not_burning", []):
            if not F(a) < F(b):
                raise ValueError("empty or reversed interval")
            not_burning.setdefault(c, []).append((F(a), F(b)))
    for c in set(burning) & set(not_burning):
        for a, b in burning[c]:
            if any(a < d and c_ < b for c_, d in not_burning[c]):
                raise ValueError("cell %d observed burning and not burning at once" % c)
    return Truth(source="device_offline", label=packet.get("label", "device_offline"), births={}, current=list(current_graph),
                 R=F(R), T=F(T if T is not None else 1), meta={"provenance": packet.get("provenance")}, burning=burning,
                 not_burning=not_burning, horizon=float(packet.get("horizon_s", 3600.0)))


def read_esri_ascii(path):
    """ESRI ASCII grid (FARSITE *_ArrivalTime.asc): returns (array north-up, xll, yll, cellsize, nodata)."""
    header, rows = {}, []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if not parts:
                continue
            if parts[0].isalpha() or parts[0].upper() in ("NCOLS", "NROWS", "XLLCORNER", "YLLCORNER", "CELLSIZE", "NODATA_VALUE"):
                header[parts[0].upper()] = float(parts[1])
            else:
                rows.append([float(v) for v in parts])
    arr = np.array(rows, dtype=float)
    if arr.shape != (int(header["NROWS"]), int(header["NCOLS"])):
        raise ValueError("ESRI ASCII grid shape differs from its header")
    nd = header.get("NODATA_VALUE", -9999.0)
    return np.where(arr == nd, np.nan, arr), header["XLLCORNER"], header["YLLCORNER"], header["CELLSIZE"], nd


def external_simulator(arrival_path, *, grid, start_offset_s, current_graph, R, T, label="farsite", units_s=60.0,
                       horizon_s=3600.0, meta=None):
    """Truth from an external simulator arrival-time grid (FARSITE minutes since its start). A routing cell ignites at
    the earliest arrival of any simulator pixel whose centre lies in the cell, shifted by `start_offset_s` (simulator start
    minus forecast cutoff); cells first reached in (0, horizon) seconds become first-new ignitions. Negative or missing
    arrivals never ignite. `grid` is the routing graph grid (south-up graph cells)."""
    arr, xll, yll, cs, _ = read_esri_ascii(arrival_path)
    nr, nc = arr.shape
    W, H = int(grid["width"]), int(grid["height"])
    x0, y0, res = float(grid["x0"]), float(grid["y0"]), float(grid["resolution"])
    first = {}                       # earliest arrival of the cell over every simulator pixel it contains
    for i in range(nr):
        y = yll + (nr - 1 - i + 0.5) * cs
        for j in range(nc):
            v = arr[i, j]
            if not np.isfinite(v) or v < 0:
                continue
            x = xll + (j + 0.5) * cs
            col, row = int(np.floor((x - x0) / res)), int(np.floor((y - y0) / res))
            if not (0 <= col < W and 0 <= row < H):
                continue
            t = F(float(v) * units_s + float(start_offset_s))
            c = row * W + col
            first[c] = min(first.get(c, t), t)
    births = {c: t for c, t in first.items() if 0 < t < horizon_s and c not in set(current_graph)}
    return Truth(source="external_simulator", label=label, births=births, current=list(current_graph), R=F(R), T=F(T),
                 meta=dict(meta or {}, arrival_path=str(arrival_path)))
