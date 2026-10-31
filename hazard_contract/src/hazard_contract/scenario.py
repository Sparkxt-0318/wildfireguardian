"""Scenario sets: arrays + meta, validation, folder I/O and the raster reference query engine.

Reference flux model ``sheet_solid_angle_v1`` (the ``wfg_latest`` law, see ``HeatSource``)
---------------------------------------------------------------------------------------
A burning cell is a uniformly emitting horizontal sheet with radiant emission ``q_rad``; a
receiver gets ``q_rad * Omega / (4 pi)`` where ``Omega`` is the cell's solid angle. For a
vehicle moving along a geometry at an unknown speed profile the engine returns bounds:

* upper bounds use, per cell, a provable bound on ``Omega`` from the nearest distance between
  the geometry and the cell, and treat unknown (unsupported) cells as burning;
* the peak lower bound uses exact ``Omega`` at probe points (vertices and segment midpoints,
  which the vehicle certainly visits) and only cells certainly burning;
* cells farther than ``near_radius_m`` are bounded by ``count * q_max * Omega_upper(R) / 4 pi``.

Sources outside the grid are not modelled: a geometry touching the grid's outside is
unsupported with infinite upper bounds; producers should pad the grid (see ``edge_burning``).
Upper kernels are inflated and lower kernels deflated by ``KERNEL_MARGIN`` (relative) so that
floating-point summation order can never invert the bounds.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from .geometry import (
    Grid, as_polyline, is_stationary, points_rect_dmax, polyline_cells, polyline_rect_dmin, probe_points_xy,
    solid_angle_cap, solid_angle_lower, solid_angle_rects, solid_angle_upper,
)
from .meta import ContractError, ScenarioMeta
from .query import SegmentHazard

MEMBERS_FILE = "members.npz"
META_FILE = "meta.json"
DEFAULT_NEAR_RADIUS_M = 5000.0
FOUR_PI = 4.0 * math.pi
KERNEL_MARGIN = 1e-9
OMEGA_ABS_ERR = 1e-13   # sr; absolute error allowance of the 4-term arctan solid angle


def _readonly(a: np.ndarray) -> np.ndarray:
    a.setflags(write=False)
    return a


class ScenarioSet:
    """K raster members on one grid. Arrays are copied and made read-only."""

    def __init__(self, ignite_s, extinguish_s, supported, meta: ScenarioMeta, *, validate: bool = True):
        self.ignite_s = _readonly(np.array(ignite_s, dtype=np.float64, copy=True))
        self.extinguish_s = _readonly(np.array(extinguish_s, dtype=np.float64, copy=True))
        self.supported = _readonly(np.array(supported, dtype=bool, copy=True))
        self.meta = meta
        self.grid = Grid(tuple(meta.transform), meta.height, meta.width)
        self._index: _Index | None = None
        if validate:
            self.validate()

    # ------------------------------------------------------------------ basics
    @property
    def K(self) -> int:
        return self.meta.K

    @property
    def shape(self) -> tuple[int, int, int]:
        return self.ignite_s.shape  # type: ignore[return-value]

    def validate(self) -> None:
        """Raise ContractError unless the arrays honour the v1 exchange format."""
        m = self.meta
        want = (m.K, m.height, m.width)
        for name in ("ignite_s", "extinguish_s", "supported"):
            if getattr(self, name).shape != want:
                raise ContractError(f"{name} has shape {getattr(self, name).shape}, meta says {want}")
        ig, ex, sup = self.ignite_s, self.extinguish_s, self.supported
        if np.any(sup & (np.isnan(ig) | np.isnan(ex))):
            raise ContractError("nan means unknown: cells with nan ignite_s/extinguish_s must be supported=False")
        s_ig, s_ex = ig[sup], ex[sup]
        if np.any(s_ex < s_ig):
            raise ContractError("extinguish_s < ignite_s in a supported cell")
        if np.any(s_ex == -np.inf):
            raise ContractError("extinguish_s = -inf in a supported cell")
        never = s_ig == np.inf
        if np.any(s_ex[never] != np.inf):
            raise ContractError("cells that never burn (ignite_s = inf) must have extinguish_s = inf")

    def member(self, k: int) -> "RasterMember":
        if not 0 <= k < self.K:
            raise IndexError(k)
        return RasterMember(self, k)

    def members(self) -> list["RasterMember"]:
        return [RasterMember(self, k) for k in range(self.K)]

    def edge_burning(self) -> np.ndarray:
        """Per member: does any grid-edge cell burn within the horizon or is it unknown? If so,
        fire may continue outside the grid, where this set says nothing (bool [K])."""
        edge = np.zeros((self.meta.height, self.meta.width), dtype=bool)
        edge[0, :] = edge[-1, :] = edge[:, 0] = edge[:, -1] = True
        ig, sup = self.ignite_s[:, edge], self.supported[:, edge]
        return np.any(~sup | (ig <= self.meta.horizon_s), axis=1)

    # --------------------------------------------------------------------- I/O
    def write(self, folder, *, dtype: str = "float64", overwrite: bool = False) -> Path:
        folder = Path(folder)
        if folder.exists() and any(folder.iterdir()) and not overwrite:
            raise FileExistsError(f"{folder} is not empty")
        folder.mkdir(parents=True, exist_ok=True)
        ig, ex = self.ignite_s, self.extinguish_s
        if dtype == "float32":
            ig32, ex32 = _round_outward_float32(ig, ex)
            exact = (np.array_equal(ig32.astype(np.float64), ig, equal_nan=True)
                     and np.array_equal(ex32.astype(np.float64), ex, equal_nan=True))
            if self.meta.heat_source.burn_duration_policy == "interval" and not exact:
                # widening an interval lowers C / duration: not conservative under this policy
                raise ValueError("float32 would change burning intervals of an interval-policy set; use float64")
            ig, ex = ig32, ex32
        elif dtype != "float64":
            raise ValueError("dtype must be 'float64' or 'float32'")
        np.savez_compressed(folder / MEMBERS_FILE, ignite_s=ig, extinguish_s=ex, supported=self.supported)
        (folder / META_FILE).write_text(self.meta.model_dump_json(indent=2) + "\n")
        return folder

    @classmethod
    def read(cls, folder) -> "ScenarioSet":
        folder = Path(folder)
        text = (folder / META_FILE).read_text()
        try:
            declared = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ContractError(f"invalid {META_FILE}: {exc}") from exc
        if not isinstance(declared, dict) or "contract_version" not in declared:
            raise ContractError(f"{META_FILE} does not declare contract_version")
        try:
            meta = ScenarioMeta.model_validate_json(text)
        except ValidationError as exc:
            raise ContractError(f"invalid {META_FILE}: {exc}") from exc
        with np.load(folder / MEMBERS_FILE, allow_pickle=False) as z:
            missing = {"ignite_s", "extinguish_s", "supported"} - set(z.files)
            if missing:
                raise ContractError(f"{MEMBERS_FILE} lacks {sorted(missing)}")
            return cls(z["ignite_s"], z["extinguish_s"], z["supported"], meta)

    # ------------------------------------------------------------------- query
    def query(self, geom_xy, t_in: float, t_out: float, members=None, *,
              near_radius_m: float = DEFAULT_NEAR_RADIUS_M) -> list[SegmentHazard]:
        """Hazard of occupying ``geom_xy`` during ``[t_in, t_out]`` (s after issue) per member."""
        g = as_polyline(geom_xy)
        a, b = float(t_in), float(t_out)
        if not (math.isfinite(a) and math.isfinite(b)) or b < a:
            raise ValueError(f"need finite t_in <= t_out, got {t_in}, {t_out}")
        R = float(near_radius_m)
        if not R > 0:
            raise ValueError("near_radius_m must be > 0")
        ks = list(range(self.K)) if members is None else [int(k) for k in members]
        if any(not 0 <= k < self.K for k in ks):
            raise IndexError(ks)
        idx = self._get_index()
        grid, horizon = self.grid, self.meta.horizon_s

        rows, cols, outside = polyline_cells(grid, g)
        beyond = b > horizon
        stationary = is_stationary(g)

        xmin, ymin = g.min(axis=0)
        xmax, ymax = g.max(axis=0)
        r0, r1, c0, c1 = grid.index_box(xmin - R, xmax + R, ymin - R, ymax + R)
        nb_c = c1 - c0
        crossed = (rows - r0) * nb_c + (cols - c0)
        if crossed.size and (crossed.min() < 0 or rows.min() < r0 or rows.max() >= r1
                             or cols.min() < c0 or cols.max() >= c1):  # pragma: no cover - invariant
            raise AssertionError("touched cells must lie inside the near box")

        sl = (ks, slice(r0, r1), slice(c0, c1))
        ig = self.ignite_s[sl].reshape(len(ks), -1)
        ex = self.extinguish_s[sl].reshape(len(ks), -1)
        sup = self.supported[sl].reshape(len(ks), -1)
        burns = sup & (ex > ig)
        active = burns & (ig <= b) & (ex > a)
        unknown = ~sup

        need = np.flatnonzero((active | unknown).any(axis=0))
        br = r0 + need // max(nb_c, 1)
        bc = c0 + need % max(nb_c, 1)
        x0, x1, y0, y1 = grid.cell_rects(br, bc)
        h = self.meta.heat_source.height_gap_m
        area = grid.cell_area_m2
        cap = solid_angle_cap(*grid.cell_size, h)
        dmin = polyline_rect_dmin(g, x0, x1, y0, y1)
        probes = probe_points_xy(g)
        up = (1.0 + KERNEL_MARGIN) / FOUR_PI
        lo = (1.0 - KERNEL_MARGIN) / FOUR_PI
        k_up = solid_angle_upper(dmin, area, h, cap) * up                                   # [n_need]
        # exact solid angles lose up to ~1e-15 sr to cancellation for far cells: deflate absolutely too
        k_lo_probe = np.maximum(solid_angle_rects(probes, x0, x1, y0, y1, h) * (1.0 - KERNEL_MARGIN)
                                - OMEGA_ABS_ERR, 0.0) / FOUR_PI                             # [n_probe, n_need]
        dmax_geom = points_rect_dmax(g, x0, x1, y0, y1).max(axis=0)                         # farthest over vertices
        k_lo_geom = solid_angle_lower(dmax_geom, area, h) * lo                               # [n_need]
        k_far = float(solid_angle_upper(np.array([R]), area, h, cap)[0]) * up
        pos = np.full(ig.shape[1], -1, dtype=np.int64)
        pos[need] = np.arange(need.size)

        out = []
        for j, k in enumerate(ks):
            out.append(self._member_result(
                k, a, b, horizon, stationary, outside, beyond, crossed,
                ig[j], ex[j], active[j], unknown[j], pos,
                k_up, k_lo_probe, k_lo_geom, idx, k_far,
            ))
        return out

    def query_uniform(self, geom_xy, t_in: float, t_out: float, members=None, *, max_len_m: float | None = None,
                      near_radius_m: float = DEFAULT_NEAR_RADIUS_M) -> list[SegmentHazard]:
        """Like :meth:`query`, but ASSUMING uniform motion along the polyline (the router's
        assumption for edge chords). The geometry is cut at every grid line and vertex (and into
        pieces no longer than ``max_len_m``); each piece is queried over its own sub-interval and
        the results are combined: contact any, supported all, peak bounds max, dose bounds sum."""
        g = as_polyline(geom_xy)
        a, b = float(t_in), float(t_out)
        if is_stationary(g) or b == a:
            return self.query(g, a, b, members, near_radius_m=near_radius_m)
        ks = list(range(self.K)) if members is None else [int(k) for k in members]
        pieces = uniform_pieces(self.grid, g, a, b, max_len_m)
        # Piece times carry floating-point error. Contact, upper bounds and support use intervals
        # widened by eps_t (clamped to [t_in, t_out]); lower bounds use intervals narrowed by eps_t,
        # so neither direction can be lost to rounding.
        eps_t = 8.0 * (len(g) + 8) * np.finfo(float).eps * (abs(a) + abs(b) + 1.0)

        def wide(ta: float, tb: float) -> tuple[float, float]:
            return max(a, ta - eps_t), min(b, tb + eps_t)

        up = [self.query(pg, *wide(ta, tb), ks, near_radius_m=near_radius_m) for pg, ta, tb in pieces]
        lo = [self.query(pg, ta + eps_t, tb - eps_t, ks, near_radius_m=near_radius_m)
              for pg, ta, tb in pieces if tb - ta > 2.0 * eps_t]
        # Exact contact under uniform motion (the router's occupancy rule): the cells holding each
        # open piece during its sub-interval, and the cells touching each cut point at its instant
        # (the final instant is t_out itself).
        checks = [(0.5 * (pg[0] + pg[1]), *wide(ta, tb)) for pg, ta, tb in pieces]
        checks += [(pg[0], *wide(ta, ta)) for pg, ta, _ in pieces] + [(g[-1], *wide(b, b))]
        hit = np.zeros(len(ks), dtype=bool)
        for xy, t0, t1 in checks:
            hit |= self._point_burning(xy, t0, t1, ks)
        beyond = b > self.meta.horizon_s
        out = []
        for j in range(len(ks)):
            rs = [pp[j] for pp in up]
            ls = [pp[j] for pp in lo]
            supported = all(r.supported for r in rs) and not beyond
            contact = True if hit[j] else (False if supported else None)
            out.append(SegmentHazard(
                contact=contact,
                flux_lower=max((r.flux_lower for r in ls), default=0.0),
                flux_upper=max(r.flux_upper for r in rs),
                supported=supported,
                dose_lower=float(sum(r.dose_lower for r in ls)),
                dose_upper=float(sum(r.dose_upper for r in rs)),
            ))
        return out

    # ---------------------------------------------------------------- internals
    def _point_burning(self, xy, t0: float, t1: float, ks: list[int]) -> np.ndarray:
        """Per member: is a supported cell touching the point burning at some instant of [t0, t1]?"""
        rows, cols, _ = polyline_cells(self.grid, np.asarray(xy, dtype=float).reshape(1, 2))
        if rows.size == 0:
            return np.zeros(len(ks), dtype=bool)
        kk = np.asarray(ks)[:, None]
        ig = self.ignite_s[kk, rows[None, :], cols[None, :]]
        ex = self.extinguish_s[kk, rows[None, :], cols[None, :]]
        sup = self.supported[kk, rows[None, :], cols[None, :]]
        return np.any(sup & (ex > ig) & (ig <= t1) & (ex > t0), axis=1)

    def _cell_emission(self, ig: np.ndarray, ex: np.ndarray) -> np.ndarray:
        """Radiant emission q_rad (kW/m^2) of each burning cell under the declared policy."""
        h = self.meta.heat_source
        if h.burn_duration_policy == "scalar":
            return np.full(ig.shape, h.emission_kw_m2(h.burn_duration_s))
        dur = ex - ig
        ok = np.isfinite(dur) & (dur > 0)
        return np.where(ok, h.emission_kw_m2(np.where(ok, dur, 1.0)), h.emission_kw_m2(h.burn_duration_s))

    def _get_index(self) -> "_Index":
        if self._index is None:
            self._index = _Index(self)
        return self._index

    def _member_result(self, k, a, b, horizon, stationary, outside, beyond, crossed,
                       ig, ex, active, unknown, pos, k_up, k_lo_probe, k_lo_geom, idx, k_far) -> SegmentHazard:
        cross_active = bool(active[crossed].any()) if crossed.size else False
        cross_unknown = bool(unknown[crossed].any()) if crossed.size else False
        supported = not (cross_unknown or outside or beyond)
        contact = True if cross_active else (False if supported else None)

        act = np.flatnonzero(active)
        unk = np.flatnonzero(unknown)
        a_ig, a_ex = ig[act], ex[act]
        P = self._cell_emission(a_ig, a_ex)
        c_up = P * k_up[pos[act]]
        c_lo_probe = P[None, :] * k_lo_probe[:, pos[act]]            # [n_probe, n_act]
        c_lo_geom = P * k_lo_geom[pos[act]]

        far_active = idx.count_active(k, a, b) - act.size
        far_unknown = idx.n_unknown[k] - unk.size
        q_unk = idx.q_unknown[k]
        static_up = 0.0
        if unk.size:
            static_up += float(np.sum(q_unk * k_up[pos[unk]]))
        if far_active > 0:
            static_up += far_active * idx.q_max[k] * k_far
        if far_unknown > 0:
            static_up += far_unknown * q_unk * k_far

        # The burning set B(t) = {ignite <= t < extinguish} only changes at ignition/extinction
        # times. Evaluate it exactly on every open piece between consecutive event times and at
        # every event instant (including a, b and the horizon). Peaks are max/min over both; doses
        # integrate the open pieces. Every bound is then a function of B(t) alone, hence
        # monotone in "more burning" (scalar policy).
        ev = np.concatenate([a_ig, a_ex])
        ev = ev[(ev > a) & (ev < b)]
        extra = [horizon] if a < horizon < b else []
        times = np.unique(np.concatenate([[a, b], ev, extra]))          # instants, sorted
        tp, tq = times[:-1], times[1:]                                  # open pieces (empty if a == b)
        Bp = (a_ig[None, :] <= tp[:, None]) & (a_ex[None, :] >= tq[:, None])      # [n_piece, n_act]
        Bi = (a_ig[None, :] <= times[:, None]) & (a_ex[None, :] > times[:, None])  # [n_inst, n_act]
        late_p = tp >= horizon
        late_i = times > horizon
        dt = tq - tp

        # Sum of all solid angles <= 2 pi: flux <= half the largest emission among cells that
        # may burn (an unknown cell's emission is unbounded under the interval policy).
        q_cap = max(idx.q_max[k], q_unk if idx.n_unknown[k] > 0 else 0.0)
        cap = 0.5 * q_cap * (1.0 + KERNEL_MARGIN)

        def upper(B, late):
            F = np.where(B, c_up[None, :], 0.0).sum(axis=1) + static_up
            F = np.minimum(F, cap)
            return np.where(late | outside, np.inf, F)

        Fp_up, Fi_up = upper(Bp, late_p), upper(Bi, late_i)
        Fp_lo = Bp.astype(float) @ c_lo_probe.T                          # [n_piece, n_probe]
        Fi_lo = Bi.astype(float) @ c_lo_probe.T                          # [n_inst, n_probe]
        Fp_lo[late_p, :] = 0.0
        Fi_lo[late_i, :] = 0.0
        Fp_lo_geom = Bp.astype(float) @ c_lo_geom
        Fp_lo_geom[late_p] = 0.0

        flux_upper = float(max(Fi_up.max(), Fp_up.max() if Fp_up.size else -np.inf))
        all_lo = np.concatenate([Fp_lo, Fi_lo], axis=0)                 # every distinct B(t)
        if stationary:
            flux_lower = float(all_lo[:, 0].max())       # occupant is at the point at every instant
        else:
            flux_lower = float(all_lo.min(axis=0).max())  # each probe is visited at some instant
        if b > a:
            dose_upper = float(np.sum(Fp_up * dt))
            dose_lower = float(np.sum((Fp_lo[:, 0] if stationary else Fp_lo_geom) * dt))
        else:
            dose_upper = dose_lower = 0.0
        return SegmentHazard(contact=contact, flux_lower=flux_lower, flux_upper=flux_upper,
                             supported=supported, dose_lower=dose_lower, dose_upper=dose_upper)


class RasterMember:
    """``HazardMember`` implementation for one member of a raster ScenarioSet."""

    def __init__(self, scenario: ScenarioSet, k: int):
        self.scenario = scenario
        self.k = k

    def segment(self, geom_xy, t_in: float, t_out: float, *,
                near_radius_m: float = DEFAULT_NEAR_RADIUS_M) -> SegmentHazard:
        return self.scenario.query(geom_xy, t_in, t_out, members=[self.k], near_radius_m=near_radius_m)[0]

    def segment_uniform(self, geom_xy, t_in: float, t_out: float, *, max_len_m: float | None = None,
                        near_radius_m: float = DEFAULT_NEAR_RADIUS_M) -> SegmentHazard:
        return self.scenario.query_uniform(geom_xy, t_in, t_out, members=[self.k], max_len_m=max_len_m,
                                           near_radius_m=near_radius_m)[0]

    def __repr__(self) -> str:
        return f"RasterMember(k={self.k}, source={self.scenario.meta.source})"


class _Index:
    """Per-member sorted ignition/extinction times for O(log n) active-cell counts."""

    def __init__(self, s: ScenarioSet):
        K = s.K
        self.ig_sorted, self.ex_sorted = [], []
        self.n_unknown = np.zeros(K, dtype=np.int64)
        self.q_max = np.zeros(K)
        self.q_unknown = np.zeros(K)
        hs = s.meta.heat_source
        q_scalar = float(hs.emission_kw_m2(hs.burn_duration_s))
        for k in range(K):
            sup = s.supported[k]
            ig, ex = s.ignite_s[k], s.extinguish_s[k]
            burns = sup & (ex > ig)
            self.ig_sorted.append(np.sort(ig[burns]))
            self.ex_sorted.append(np.sort(ex[burns]))
            self.n_unknown[k] = int((~sup).sum())
            qk = s._cell_emission(ig[burns], ex[burns])
            self.q_max[k] = float(qk.max()) if qk.size else q_scalar
            # Unknown cells may hold any times; under the interval policy their emission
            # C / (extinguish - ignite) has no upper bound.
            self.q_unknown[k] = np.inf if hs.burn_duration_policy == "interval" else max(q_scalar, self.q_max[k])

    def count_active(self, k: int, a: float, b: float) -> int:
        """Cells burning at some instant of [a, b]: #(ignite <= b) - #(extinguish <= a)."""
        return int(np.searchsorted(self.ig_sorted[k], b, side="right")
                   - np.searchsorted(self.ex_sorted[k], a, side="right"))


def uniform_pieces(grid: Grid, g: np.ndarray, t_in: float, t_out: float,
                   max_len_m: float | None = None) -> list[tuple[np.ndarray, float, float]]:
    """Cut a polyline at vertices and grid lines (and to ``max_len_m``) with uniform-motion times.

    Vertex times come from one cumulative sum (so adjacent segments agree), the first and last
    times are exactly ``t_in`` and ``t_out``, and every vertex point is exact. Only exact
    duplicate cut fractions are merged: a real crossing is never dropped.
    """
    seg_len = np.hypot(*(g[1:] - g[:-1]).T)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    total = cum[-1]
    span = t_out - t_in
    nz = np.flatnonzero(seg_len > 0.0)
    px = grid.to_pixel(g)
    pieces = []
    for i in nz:
        ts = [np.array([0.0, 1.0])]
        d = px[i + 1] - px[i]
        for axis in (0, 1):
            if d[axis] != 0.0:
                lo, hi = sorted((px[i][axis], px[i + 1][axis]))
                ks = np.arange(np.ceil(lo), np.floor(hi) + 1.0)
                if ks.size:
                    ts.append((ks - px[i][axis]) / d[axis])
        f = np.unique(np.clip(np.concatenate(ts), 0.0, 1.0))
        if max_len_m:
            n_sub = np.maximum(np.ceil((np.diff(f) * seg_len[i]) / max_len_m).astype(int), 1)
            f = np.unique(np.concatenate([np.linspace(f[j], f[j + 1], n_sub[j] + 1) for j in range(len(f) - 1)]))
        pts = g[i][None, :] + f[:, None] * (g[i + 1] - g[i])[None, :]
        pts[0], pts[-1] = g[i], g[i + 1]
        times = t_in + ((cum[i] + f * seg_len[i]) / total) * span
        times[0] = t_in + (cum[i] / total) * span
        times[-1] = t_in + (cum[i + 1] / total) * span
        if i == nz[0]:
            times[0] = t_in
        if i == nz[-1]:
            times[-1] = t_out
        times = np.maximum.accumulate(np.clip(times, t_in, t_out))
        for j in range(len(f) - 1):
            pieces.append((pts[j:j + 2].copy(), float(times[j]), float(times[j + 1])))
    return pieces


def _round_outward_float32(ig: np.ndarray, ex: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Cast to float32 rounding ignitions down and extinctions up: burning intervals only grow."""
    ig32 = ig.astype(np.float32)
    up = ig32.astype(np.float64) > ig
    ig32[up] = np.nextafter(ig32[up], np.float32(-np.inf))
    ex32 = ex.astype(np.float32)
    down = ex32.astype(np.float64) < ex
    ex32[down] = np.nextafter(ex32[down], np.float32(np.inf))
    return ig32, ex32
