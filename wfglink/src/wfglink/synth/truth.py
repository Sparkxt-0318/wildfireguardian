"""Ground-truth tables of synthetic clips: schemas, gate crossings and the true field.

Files (Parquet, column order and types exactly as below):

truth_particles: one row per frame per particle that exists during that frame's exposure
  (alive for a positive time within it), for every kind: "ember", "spark", "light",
  "headlight". Positions are in px (x right, y down), times in s, velocities in px/s.
  - t_mid is the particle's own exposure midpoint: the frame midpoint, shifted by the
    rolling-shutter row delay when that is on, and clamped to the particle's lifetime.
  - x/y_start and x/y_end are at the exposure start and end, clamped to the lifetime.
  - u, v: mean ember velocity over the exposure (displacement / alive duration).
  - ua, va: air velocity at (x_mid, y_mid, t_mid).
  - flux: integrated rendered intensity (BT.601 luma, DN px^2, linear before gamma) of the
    particle in this frame before noise: emission, flicker, haze transmission, gain and
    exposure included, whether or not all of it lands inside the frame.
  - visible: alive for at least half the exposure, center inside the frame
    (0 <= x <= W - 1, 0 <= y <= H - 1, pixel centers at integers) and flux at or above the
    detectability floor visible_min_snr x local luma noise sigma x sqrt(A), the flux whose
    matched-filter SNR is visible_min_snr. A = matched_filter_area(sigma_px,
    streak_length_px): 4 pi sigma_px^2 for a static point (so the floor is that of the
    point-source SNR used to set ember brightness) and larger for a streak, which spreads
    the same flux over more pixels. The local noise is that of the noise-free background
    at the particle in this frame (flames and lamps excluded), in linear DN before gamma
    and compression; compression can still erase faint embers that are flagged visible.
  - in_large_region: center inside a flame region or near a headlight lamp.
  For a duplicated frame (a repeat of the previous image) the rows of the previous frame
  are repeated with the new frame index (positions, times and flux of the exposure shown).

truth_frames: one row per frame slot. t_start equals the video PTS. For a duplicate the
  times are the slot's own (the image is the previous exposure).

truth_gate: crossings of ember paths through gate segments. A crossing happens between
  consecutive non-duplicate frames k and k+1 (both with the particle alive at its exposure
  midpoint) when the segment from the particle's midpoint position in frame k to the one in
  frame k+1 crosses the gate line and the crossing point lies inside the gate segment.
  This is hysteresis free. With n = (-(y2 - y1), x2 - x1) / |p2 - p1| and
  s(P) = n . (P - p1), a point with s <= 0 is on the negative side; direction is +1 for a
  move from the negative to the positive side (toward the normal) and -1 otherwise. t is
  linearly interpolated between the two midpoint times at the crossing.

truth_field: per cell of the field grid (cols x rows; cell (c, r) holds positions with
  floor(x cols / W) = c and floor(y rows / H) = r), from visible ember
  rows of non-duplicate frames: the mean (and median) over particles of each particle's
  mean ember velocity and mean air velocity in that cell, the number of distinct particles
  and of rows, and the air velocity at the cell center averaged over all frame midpoints
  (the Eulerian air field, independent of where embers happened to be).
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.special import ndtr

from wfglink.synth.flows import Flow

PARTICLES_SCHEMA = pa.schema([
    ("frame", pa.int64()), ("t_mid", pa.float64()), ("particle_id", pa.int64()), ("kind", pa.string()),
    ("x_mid", pa.float64()), ("y_mid", pa.float64()), ("x_start", pa.float64()), ("y_start", pa.float64()),
    ("x_end", pa.float64()), ("y_end", pa.float64()), ("u", pa.float64()), ("v", pa.float64()),
    ("ua", pa.float64()), ("va", pa.float64()), ("flux", pa.float64()), ("sigma_px", pa.float64()),
    ("visible", pa.bool_()), ("in_large_region", pa.bool_()), ("streak_length_px", pa.float64()),
])

FRAMES_SCHEMA = pa.schema([
    ("frame", pa.int64()), ("t_start", pa.float64()), ("t_mid", pa.float64()), ("t_end", pa.float64()),
    ("exposure_s", pa.float64()), ("duplicate", pa.bool_()), ("n_visible_embers", pa.int64()),
])

GATE_SCHEMA = pa.schema([
    ("gate", pa.string()), ("particle_id", pa.int64()), ("t", pa.float64()), ("frame_before", pa.int64()),
    ("frame_after", pa.int64()), ("direction", pa.int8()), ("visible_both", pa.bool_()),
])

FIELD_SCHEMA = pa.schema([
    ("col", pa.int64()), ("row", pa.int64()), ("x_center", pa.float64()), ("y_center", pa.float64()),
    ("n_particles", pa.int64()), ("n_samples", pa.int64()),
    ("u", pa.float64()), ("v", pa.float64()), ("ua", pa.float64()), ("va", pa.float64()),
    ("u_median", pa.float64()), ("v_median", pa.float64()), ("ua_median", pa.float64()), ("va_median", pa.float64()),
    ("ua_center", pa.float64()), ("va_center", pa.float64()),
])

SCHEMAS = {"truth_particles": PARTICLES_SCHEMA, "truth_frames": FRAMES_SCHEMA,
           "truth_gate": GATE_SCHEMA, "truth_field": FIELD_SCHEMA}


def to_table(columns: Mapping[str, np.ndarray | Sequence], schema: pa.Schema) -> pa.Table:
    """Build a table with exactly the schema's columns, in order, cast to its types."""
    arrays = []
    for f in schema:
        col = columns[f.name]
        arrays.append(pa.array(np.asarray(col) if not isinstance(col, pa.Array) else col, type=f.type))
    return pa.Table.from_arrays(arrays, schema=schema)


def write_table(columns: Mapping[str, np.ndarray | Sequence], schema: pa.Schema, path: str | Path) -> Path:
    path = Path(path)
    pq.write_table(to_table(columns, schema), path)
    return path


def empty_columns(schema: pa.Schema) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for f in schema:
        if pa.types.is_string(f.type):
            out[f.name] = np.zeros(0, dtype=object)
        elif pa.types.is_boolean(f.type):
            out[f.name] = np.zeros(0, dtype=bool)
        elif pa.types.is_integer(f.type):
            out[f.name] = np.zeros(0, dtype=f.type.to_pandas_dtype())
        else:
            out[f.name] = np.zeros(0)
    return out


def matched_filter_area(sigma_px: np.ndarray | float, length_px: np.ndarray | float) -> np.ndarray:
    """Noise-equivalent area A (px^2) of the matched filter for a Gaussian streak.

    The streak is a Gaussian spot of sigma s swept at constant speed along a straight
    segment of length L. A filter matched to its unit-flux profile p measures its flux F
    with noise sigma_n sqrt(A), A = 1 / sum(p^2), so its matched-filter SNR is
    F / (sigma_n sqrt(A)). The profile is a Gaussian across the streak times a box of
    length L convolved with the Gaussian along it, so sum(p^2) is the product of
    1 / (2 sqrt(pi) s) across and, with q = sqrt(2) s, of
    (2 / L^2) (L (Phi(L / q) - 1/2) - q / sqrt(2 pi) (1 - exp(-L^2 / (2 q^2)))) along.
    A is 4 pi s^2 for a point (L = 0), the area behind the point-source SNR definition, and
    tends to 2 sqrt(pi) s L for long streaks: motion blur spreads the same flux over more
    noise, so a streak is harder to detect than a point of the same flux.
    """
    s = np.asarray(sigma_px, dtype=np.float64)
    length = np.abs(np.asarray(length_px, dtype=np.float64))
    q = math.sqrt(2.0) * s
    point = length < 1e-6 * q
    ll = np.where(point, 1.0, length)
    along = (2.0 / ll ** 2) * (ll * (ndtr(ll / q) - 0.5)
                               - q / math.sqrt(2.0 * math.pi) * -np.expm1(-ll ** 2 / (2.0 * q ** 2)))
    along = np.where(point, 1.0 / (2.0 * math.sqrt(math.pi) * s), along)
    return 2.0 * math.sqrt(math.pi) * s / along


def gate_normal(p1: Sequence[float], p2: Sequence[float]) -> np.ndarray:
    """Unit normal n = (-(y2 - y1), x2 - x1) / |p2 - p1| of the gate segment p1 -> p2."""
    d = np.asarray(p2, dtype=np.float64) - np.asarray(p1, dtype=np.float64)
    n = np.array([-d[1], d[0]])
    return n / np.hypot(*d)


def segment_crossings(x0: np.ndarray, y0: np.ndarray, x1: np.ndarray, y1: np.ndarray,
                      p1: Sequence[float], p2: Sequence[float]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """For moves P0 -> P1: (crossed, lambda along the move, direction +1/-1)."""
    p1 = np.asarray(p1, dtype=np.float64)
    p2 = np.asarray(p2, dtype=np.float64)
    n = gate_normal(p1, p2)
    s0 = n[0] * (x0 - p1[0]) + n[1] * (y0 - p1[1])
    s1 = n[0] * (x1 - p1[0]) + n[1] * (y1 - p1[1])
    side0, side1 = s0 > 0, s1 > 0
    change = side0 != side1
    denom = np.where(change, s0 - s1, 1.0)
    lam = np.where(change, s0 / denom, 0.0)
    cx, cy = x0 + lam * (x1 - x0), y0 + lam * (y1 - y0)
    d = p2 - p1
    mu = ((cx - p1[0]) * d[0] + (cy - p1[1]) * d[1]) / float(d @ d)
    crossed = change & (mu >= 0.0) & (mu <= 1.0)
    direction = np.where(side1 & ~side0, 1, -1).astype(np.int8)
    return crossed, lam, direction


def gate_truth(rows: pd.DataFrame, frames: pd.DataFrame, gates: Sequence[Mapping]) -> dict[str, np.ndarray]:
    """Gate crossings (truth_gate columns) from truth_particles rows and truth_frames.

    rows needs: frame, particle_id, kind, t_mid, x_mid, y_mid, visible, alive_mid.
    """
    real = frames.loc[~frames["duplicate"].to_numpy(), "frame"].to_numpy()
    rank = np.full(int(frames["frame"].max()) + 1 if len(frames) else 0, -1, np.int64)
    rank[real] = np.arange(real.size)
    r = rows[(rows["kind"] == "ember") & rows["alive_mid"]]
    r = r[rank[r["frame"].to_numpy()] >= 0] if len(r) else r
    out = {k: [] for k in ("gate", "particle_id", "t", "frame_before", "frame_after", "direction", "visible_both")}
    if len(r):
        r = r.assign(rank=rank[r["frame"].to_numpy()]).sort_values(["particle_id", "rank"], kind="stable")
        pid = r["particle_id"].to_numpy()
        rk = r["rank"].to_numpy()
        pair = (pid[1:] == pid[:-1]) & (rk[1:] == rk[:-1] + 1)
        i0 = np.nonzero(pair)[0]
        i1 = i0 + 1
        x, y = r["x_mid"].to_numpy(), r["y_mid"].to_numpy()
        t = r["t_mid"].to_numpy()
        fr = r["frame"].to_numpy()
        vis = r["visible"].to_numpy()
        for g in gates:
            crossed, lam, direction = segment_crossings(x[i0], y[i0], x[i1], y[i1], g["p1"], g["p2"])
            k0, k1 = i0[crossed], i1[crossed]
            lam = lam[crossed]
            out["gate"].append(np.full(k0.size, str(g["name"]), dtype=object))
            out["particle_id"].append(pid[k0])
            out["t"].append(t[k0] + lam * (t[k1] - t[k0]))
            out["frame_before"].append(fr[k0])
            out["frame_after"].append(fr[k1])
            out["direction"].append(direction[crossed])
            out["visible_both"].append(vis[k0] & vis[k1])
    cols = empty_columns(GATE_SCHEMA)
    for k, parts in out.items():
        if parts:
            cols[k] = np.concatenate(parts)
    if cols["t"].size:
        order = np.lexsort((cols["particle_id"], cols["t"], cols["gate"].astype(str)))
        cols = {k: v[order] for k, v in cols.items()}
    return cols


def field_truth(rows: pd.DataFrame, frames: pd.DataFrame, flow: Flow, frame_size: Sequence[int],
                grid: Sequence[int]) -> dict[str, np.ndarray]:
    """Per-cell true ember and air velocities (truth_field columns)."""
    w, h = int(frame_size[0]), int(frame_size[1])
    cols, nrows = int(grid[0]), int(grid[1])
    cw, ch = w / cols, h / nrows
    cc, rr = np.meshgrid(np.arange(cols), np.arange(nrows))
    cc, rr = cc.ravel(), rr.ravel()
    xc, yc = (cc + 0.5) * cw, (rr + 0.5) * ch
    real = frames.loc[~frames["duplicate"].to_numpy()]
    tm = real["t_mid"].to_numpy()
    if tm.size:
        ua_c, va_c = flow.velocity(xc[:, None], yc[:, None], tm[None, :])
        ua_c, va_c = ua_c.mean(axis=1), va_c.mean(axis=1)
    else:
        ua_c = va_c = np.full(cc.size, np.nan)
    real_set = real["frame"].to_numpy()
    e = rows[(rows["kind"] == "ember") & rows["visible"] & rows["frame"].isin(real_set)]
    ncell = cols * nrows
    stats = {k: np.full(ncell, np.nan) for k in ("u", "v", "ua", "va", "u_median", "v_median", "ua_median", "va_median")}
    n_part = np.zeros(ncell, np.int64)
    n_samp = np.zeros(ncell, np.int64)
    if len(e):
        ci = np.clip(np.floor(e["x_mid"].to_numpy() / cw).astype(np.int64), 0, cols - 1)
        ri = np.clip(np.floor(e["y_mid"].to_numpy() / ch).astype(np.int64), 0, nrows - 1)
        cell = ri * cols + ci
        d = pd.DataFrame({"cell": cell, "pid": e["particle_id"].to_numpy(), "u": e["u"].to_numpy(),
                          "v": e["v"].to_numpy(), "ua": e["ua"].to_numpy(), "va": e["va"].to_numpy()})
        n_samp = np.bincount(cell, minlength=ncell).astype(np.int64)
        per = d.groupby(["cell", "pid"], sort=True)[["u", "v", "ua", "va"]].mean().reset_index()
        agg_mean = per.groupby("cell")[["u", "v", "ua", "va"]].mean()
        agg_med = per.groupby("cell")[["u", "v", "ua", "va"]].median()
        cnt = per.groupby("cell")["pid"].count()
        idx = agg_mean.index.to_numpy()
        for k in ("u", "v", "ua", "va"):
            stats[k][idx] = agg_mean[k].to_numpy()
            stats[f"{k}_median"][idx] = agg_med[k].to_numpy()
        n_part[cnt.index.to_numpy()] = cnt.to_numpy()
    return {"col": cc.astype(np.int64), "row": rr.astype(np.int64), "x_center": xc, "y_center": yc,
            "n_particles": n_part, "n_samples": n_samp, **stats, "ua_center": ua_c, "va_center": va_c}
